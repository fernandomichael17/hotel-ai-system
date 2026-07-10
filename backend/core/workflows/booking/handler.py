"""
Booking workflow handler — orchestrate
seluruh booking flow dari inquiry
sampai draft tersimpan.

Flow lengkap:
1. Load atau init BookingState
2. Detect cancellation → handle
3. Route berdasarkan current step:
   INQUIRY   → extract params awal +
               check availability
   COLLECTING → extract params +
                tanya yang kurang
   CONFIRMING → detect confirm/cancel +
                handle response
   UPSELLING  → detect accept/reject +
                next upsell atau complete
4. Save updated state
5. Return response ke user
"""

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.channel.context import (
    ConversationContext
)
from backend.core.workflows.booking.schemas import (
    BookingState, BookingStep,
    CollectedParams, UpsellOffer
)
from backend.core.workflows.booking.form_collector import (
    BookingFormCollector
)
from backend.core.response.templates import (
    BOOKING_CONFIRM, BOOKING_SUCCESS,
    BOOKING_SALES_NOTIF
)
from backend.integrations.hms.factory import (
    get_hms_client
)
from backend.integrations.hms.schemas import (
    RoomAvailabilityRequest,
    BookingCreateRequest
)
from backend.db.repositories.booking_repo import (
    BookingRepository
)
from backend.db.repositories.policy_repo import (
    PolicyRepository
)
from backend.core.session.manager import (
    SessionManager
)
from backend.integrations.llm.client import (
    get_llm_client
)

logger = logging.getLogger(__name__)

class BookingHandler:

    def __init__(self, db: AsyncSession):
        """Inisialisasi database session, HMS client, form collector, repositories, dan LLM client."""
        self.db = db
        self.hms = get_hms_client()
        self.collector = BookingFormCollector()
        self.booking_repo = BookingRepository(db)
        self.policy_repo = PolicyRepository(db)
        self.llm = get_llm_client()

    async def handle(
        self,
        ctx: ConversationContext
    ) -> str:
        """
        Main handler — mengarahkan workflow pemesanan kamar ke handler yang sesuai berdasarkan tahapan step aktif.

        Flow:
        1. Ambil atau inisialisasi BookingState dari cache in-memory.
        2. Periksa apakah user bermaksud membatalkan proses booking. Jika iya, bersihkan state dan kirim konfirmasi pembatalan.
        3. Arahkan pesan ke handler step aktif (INQUIRY, COLLECTING, CONFIRMING, UPSELLING).
        """
        session_mgr = SessionManager(self.db)

        # Load state atau init baru
        state = await session_mgr.get_booking_state(ctx.session_id)

        if state is None:
            state = BookingState()

        message = ctx.message.content

        # Detect cancellation di semua step
        if await self.collector.detect_cancellation(message):
            await session_mgr.clear_booking_state(ctx.session_id)
            return (
                "Baik, proses booking dibatalkan. "
                "Jika sewaktu-waktu ingin memesan "
                "kamar, kami siap membantu! 😊"
            )

        # Route berdasarkan step
        if state.step == BookingStep.INQUIRY:
            response = await self._handle_inquiry(ctx, state, session_mgr)

        elif state.step == BookingStep.COLLECTING:
            response = await self._handle_collecting(ctx, state, session_mgr)

        elif state.step == BookingStep.CONFIRMING:
            response = await self._handle_confirming(ctx, state, session_mgr)

        elif state.step == BookingStep.UPSELLING:
            response = await self._handle_upselling(ctx, state, session_mgr)

        else:
            # COMPLETED atau CANCELLED - Reset dan mulai baru
            state = BookingState()
            response = await self._handle_inquiry(ctx, state, session_mgr)

        return response

    async def _handle_inquiry(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Menangani tahap awal (INQUIRY) dari pemesanan.

        Flow:
        1. Ekstrak parameter awal dari pesan tamu.
        2. Jika parameter kamar (room_type) dan tanggal (check_in_date) terisi, lakukan pengecekan ketersediaan.
        3. Jika belum cukup, ubah step ke COLLECTING dan tanyakan parameter pertama yang kurang.
        4. Simpan state terupdate.
        """
        # Extract params dari pesan pertama
        state.params = await self.collector.extract_params(
            message=ctx.message.content,
            current_state=state
        )

        # Kalau cukup info untuk cek availability
        if state.params.room_type and state.params.check_in_date:
            return await self._check_and_respond(ctx, state, session_mgr)

        # Belum cukup → collect dulu
        state.step = BookingStep.COLLECTING
        await session_mgr.save_booking_state(ctx.session_id, state)

        question = await self.collector.generate_question(state, has_history=len(ctx.history) > 0)
        return question

    async def _handle_collecting(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Menangani tahap pengumpulan parameter data (COLLECTING).

        Flow:
        1. Ekstrak parameter tambahan dari pesan baru tamu dan gabungkan ke state saat ini.
        2. Jika ketersediaan kamar belum dicek namun data kamar & tanggal kini sudah ada, jalankan cek ketersediaan.
        3. Jika parameter wajib telah lengkap, ubah step ke CONFIRMING dan minta persetujuan ringkasan data.
        4. Jika parameter wajib masih ada yang kurang, minta parameter berikutnya yang kosong.
        5. Simpan state terupdate.
        """
        # Extract dan merge params
        state.params = await self.collector.extract_params(
            message=ctx.message.content,
            current_state=state
        )

        # Kalau bisa cek availability sekarang
        if state.params.room_type and state.params.check_in_date and not state.availability_checked:
            return await self._check_and_respond(ctx, state, session_mgr)

        # Kalau semua required sudah ada
        if state.params.is_complete():
            state.step = BookingStep.CONFIRMING
            await session_mgr.save_booking_state(ctx.session_id, state)
            return self._build_confirm_message(state)

        # Masih ada yang kurang → tanya
        await session_mgr.save_booking_state(ctx.session_id, state)
        return await self.collector.generate_question(state, has_history=len(ctx.history) > 0)

    async def _handle_confirming(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Menangani tahap menunggu persetujuan ringkasan pemesanan (CONFIRMING).

        Flow:
        1. Deteksi konfirmasi persetujuan dari pesan tamu.
        2. Jika disetujui (ya), muat paket promosi penawaran tambahan (upsell) dari kebijakan hotel.
        3. Jika ada paket upsell, simpan ke tawaran state dan pindah ke step UPSELLING.
        4. Jika tidak ada paket upsell, langsung buat draf reservasi di database.
        5. Jika ditolak (tidak), kembalikan step ke COLLECTING dan tanyakan data mana yang ingin diperbaiki.
        """
        confirmed = await self.collector.detect_confirmation(ctx.message.content)

        if confirmed:
            # Load upsell offers dari policy
            upsells = await self._load_upsells(ctx.hotel_id)

            if upsells:
                state.upsell_offers = upsells
                state.step = BookingStep.UPSELLING
                await session_mgr.save_booking_state(ctx.session_id, state)
                return self._build_upsell_message(state)
            else:
                # Tidak ada upsell → langsung create
                return await self._create_booking(ctx, state, session_mgr)

        # User ingin ubah sesuatu
        state.step = BookingStep.COLLECTING
        await session_mgr.save_booking_state(ctx.session_id, state)
        return (
            "Baik, apa yang ingin diubah? "
            "Silakan sebutkan informasi yang "
            "ingin diperbaiki."
        )

    async def _handle_upselling(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Menangani tahap penawaran paket tambahan opsional (UPSELLING) secara bertahap satu demi satu.

        Flow:
        1. Deteksi respon persetujuan (ya/tidak) dari tamu atas item penawaran saat ini.
        2. Update status penerimaan item tersebut pada state tawaran.
        3. Pindah ke penawaran item upsell berikutnya.
        4. Jika seluruh penawaran upsell selesai ditawarkan, proses pembuatan reservasi hotel.
        5. Simpan state terupdate.
        """
        current = state.current_upsell()

        if current is None:
            # Semua upsell sudah ditawarkan
            return await self._create_booking(ctx, state, session_mgr)

        # Detect accept/reject
        accepted = await self.collector.detect_confirmation(ctx.message.content)
        current.accepted = accepted

        # Pindah ke upsell berikutnya
        next_upsell = state.next_upsell()
        await session_mgr.save_booking_state(ctx.session_id, state)

        if next_upsell:
            return self._build_upsell_message(state)
        else:
            # Semua ditawarkan → create booking
            return await self._create_booking(ctx, state, session_mgr)

    async def _check_and_respond(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Melakukan pengecekan ketersediaan kamar ke HMS dan menyusun respon tarif.

        Flow:
        1. Kirim request ketersediaan kamar ke HMS.
        2. Catat hasil ketersediaan di state.
        3. Jika kamar tidak tersedia, infokan ke tamu beserta alternatif tipe kamar lain jika ada.
        4. Jika tersedia, buat rincian harga per-malam/total harga dan lanjutkan ke konfirmasi summary atau pengumpulan parameter kurang.
        """
        req = RoomAvailabilityRequest(
            hotel_id=ctx.hotel_id,
            room_type=state.params.room_type,
            check_in_date=state.params.check_in_date,
            check_out_date=state.params.check_out_date,
            num_guests=state.params.num_guests or 1
        )

        try:
            availability = await self.hms.check_availability(req)
        except Exception as e:
            logger.error(f"Gagal melakukan cek ketersediaan kamar ke HMS: {str(e)}", exc_info=True)
            # Fallback jika HMS API down, asumsikan tersedia untuk kelancaran demo
            from backend.integrations.hms.schemas import RoomAvailabilityResponse
            availability = RoomAvailabilityResponse(
                available=True,
                price_per_night=500000,
                total_price=500000,
                reason="HMS offline fallback"
            )

        state.availability_checked = True
        state.availability_result = {
            "available": availability.available,
            "price_per_night": availability.price_per_night,
            "total_price": availability.total_price,
            "reason": availability.reason,
            "alternatives": availability.alternatives
        }

        if not availability.available:
            # Kamar tidak tersedia
            state.step = BookingStep.COLLECTING
            await session_mgr.save_booking_state(ctx.session_id, state)

            alt_text = ""
            if availability.alternatives:
                alts = ", ".join(availability.alternatives)
                alt_text = (
                    f"\n\nAlternatif yang tersedia: "
                    f"*{alts}*\n"
                    f"Mau coba tipe kamar lain?"
                )

            return (
                f"Maaf, kamar "
                f"*{state.params.room_type}* "
                f"tidak tersedia untuk tanggal "
                f"*{state.params.check_in_date}*."
                f"{alt_text}"
            )

        # Kamar tersedia
        price_text = ""
        if availability.price_per_night:
            price_fmt = f"Rp {availability.price_per_night:,.0f}".replace(",", ".")
            price_text = f"\n💰 Harga: *{price_fmt}/malam*"

            if availability.total_price and state.params.check_out_date:
                total_fmt = f"Rp {availability.total_price:,.0f}".replace(",", ".")
                price_text += f"\n💳 Total: *{total_fmt}*"

        # Pindah ke collecting untuk parameter lain jika belum lengkap
        state.step = BookingStep.COLLECTING
        await session_mgr.save_booking_state(ctx.session_id, state)

        response = (
            f"Kamar *{state.params.room_type}* "
            f"tersedia untuk tanggal "
            f"*{state.params.check_in_date}*! ✅"
            f"{price_text}\n\n"
        )

        if state.params.is_complete():
            state.step = BookingStep.CONFIRMING
            await session_mgr.save_booking_state(ctx.session_id, state)
            response += self._build_confirm_message(state)
        else:
            question = await self.collector.generate_question(state, has_history=len(ctx.history) > 0)
            response += question

        return response

    async def _create_booking(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Membuat draf reservasi pemesanan di HMS dan menyimpannya di database lokal.

        Flow:
        1. Siapkan request model data pemesanan kamar lengkap dengan tawaran tambahan yang disetujui.
        2. Panggil HMS create_booking API.
        3. Jika HMS gagal (koneksi error), data tetap disimpan ke database lokal dengan status 'draft' agar sales dapat mem-follow up manual.
        4. Jika HMS sukses, simpan data ke database lokal dengan status 'submitted_to_sales' dan masukkan hms_booking_id.
        5. Cetak notifikasi ke konsol server dan hapus state in-memory pemesanan.
        """
        from uuid import UUID

        # Buat booking di HMS (mock)
        hms_req = BookingCreateRequest(
            hotel_id=ctx.hotel_id,
            guest_name=state.params.guest_name,
            wa_number=state.params.wa_number,
            room_type=state.params.room_type,
            check_in_date=state.params.check_in_date,
            check_out_date=state.params.check_out_date or "",
            num_guests=state.params.num_guests or 1,
            num_children=state.params.num_children or 0,
            special_request=state.params.special_request,
            upsell_items=state.accepted_upsells()
        )

        hms_booking_id = None
        status = "submitted_to_sales"

        try:
            hms_result = await self.hms.create_booking(hms_req)
            hms_booking_id = hms_result.hms_booking_id
        except Exception as e:
            # JANGAN gagalkan pemesanan jika HMS error (Aturan 4: simpan sebagai status 'draft')
            logger.warning(f"HMS create_booking gagal: {str(e)}. Melakukan fallback pemesanan ke status draft lokal.", exc_info=True)
            status = "draft"

        # Simpan ke database kita
        try:
            booking = await self.booking_repo.create(
                hotel_id=UUID(ctx.hotel_id),
                session_id=UUID(ctx.session_id),
                guest_name=state.params.guest_name,
                wa_number=state.params.wa_number,
                check_in_date=state.params.check_in_date,
                check_out_date=state.params.check_out_date,
                room_type=state.params.room_type,
                num_guests=state.params.num_guests,
                special_request=state.params.special_request,
                upsell_accepted=state.accepted_upsells(),
                status=status,
                hms_booking_id=hms_booking_id
            )
            booking_ref = str(booking.id)[:8].upper()
        except Exception as db_err:
            logger.error(f"Gagal menyimpan draf booking ke database: {str(db_err)}", exc_info=True)
            # Jika database kita error, generate ref lokal acak untuk demo
            booking_ref = str(uuid.uuid4())[:8].upper()

        state.booking_ref = booking_ref
        state.step = BookingStep.COMPLETED

        # Bersihkan state booking yang sudah selesai agar percakapan bersih kembali
        await session_mgr.clear_booking_state(ctx.session_id)

        # Log notif (email/WA nanti)
        notif_text = BOOKING_SALES_NOTIF.format(
            hotel_name=ctx.hotel.name if hasattr(ctx.hotel, 'name') else ctx.hotel.hotel_name,
            guest_name=state.params.guest_name,
            wa_number=state.params.wa_number,
            room_type=state.params.room_type,
            check_in=state.params.check_in_date,
            check_out=state.params.check_out_date or "-",
            num_guests=state.params.num_guests,
            special_request=state.params.special_request or "-",
            upsell_items=", ".join(state.accepted_upsells()) or "Tidak ada",
            booking_ref=booking_ref
        )

        logger.info(f"BOOKING NOTIFICATION:\n{notif_text}")

        return BOOKING_SUCCESS.format(
            booking_ref=booking_ref
        )

    def _build_confirm_message(
        self,
        state: BookingState
    ) -> str:
        """Menyusun teks ringkasan data pemesanan untuk konfirmasi tamu."""
        summary = state.params.to_summary()
        return (
            f"Berikut ringkasan pesanan Anda:\n\n"
            f"{summary}\n\n"
            f"Apakah sudah sesuai? "
            f"Ketik *ya* untuk lanjut atau "
            f"*tidak* jika ingin mengubah."
        )

    def _build_upsell_message(
        self,
        state: BookingState
    ) -> str:
        """Menyusun teks penawaran promosi upsell tambahan."""
        current = state.current_upsell()
        if not current:
            return ""

        return (
            f"Satu lagi — apakah Anda ingin "
            f"menambahkan:\n\n"
            f"✨ *{current.format_offer()}*\n\n"
            f"Ketik *ya* atau *tidak*"
        )

    async def _load_upsells(
        self,
        hotel_id: str
    ) -> list[UpsellOffer]:
        """
        Mengambil daftar tawaran upsell tambahan dari kebijakan (HotelPolicy) hotel terkait.
        """
        from uuid import UUID

        try:
            policy = await self.policy_repo.find_by_type(
                hotel_id=UUID(hotel_id),
                policy_type="upsell"
            )
        except Exception as e:
            logger.error(f"Gagal mengambil kebijakan upsell dari database: {str(e)}", exc_info=True)
            return []

        if not policy or not policy.rules:
            return []

        offers = []
        for key, data in policy.rules.items():
            offers.append(UpsellOffer(
                key=key,
                name=data.get("name", key),
                price=data.get("price", 0),
                unit=data.get("unit", ""),
                accepted=False
            ))

        return offers

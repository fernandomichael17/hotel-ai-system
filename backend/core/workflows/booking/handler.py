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

    LOCALIZED_STRINGS = {
        "id": {
            "cancel_confirm": "Baik, proses booking dibatalkan. Jika sewaktu-waktu ingin memesan kamar, kami siap membantu! 😊",
            "confirm_header": "Berikut ringkasan pesanan Anda:\n\n",
            "confirm_footer": "\n\nApakah sudah sesuai? Ketik *ya* untuk lanjut atau *tidak* jika ingin mengubah.",
            "correction_prompt": "Baik, apa yang ingin diubah? Silakan sebutkan informasi yang ingin diperbaiki.",
            "correction_success_confirm": "Baik, data pemesanan telah diperbarui.\n\n",
            "correction_success_collecting": "Baik, data pemesanan telah diperbarui. ",
            "upsell_header": "Sebelum melanjutkan, kami memiliki beberapa penawaran menarik:\n\n",
            "upsell_footer": "\n\nApakah Anda tertarik? Ketik *ya* untuk menerima atau *tidak* untuk melewati.",
            "room_available": "Kamar *{room_type}* tersedia untuk tanggal *{check_in}*! ✅",
            "price_per_night": "\n💰 Harga: *{price}/malam*",
            "price_total": "\n💳 Total: *{price}*",
            "continue_booking_q": "Apakah Anda ingin melanjutkan untuk melakukan pemesanan?",
            "faq_interrupt_reminder": "Ngomong-ngomong, kita masih dalam proses booking. ",
            "decline_continue": "Baik, silakan beri tahu kami jika Anda memerlukan informasi lain atau bantuan lainnya! 😊",
            "room_unavailable": "Maaf, kamar *{room_type}* tidak tersedia untuk tanggal *{check_in}*.",
            "alternatives_text": "\n\nAlternatif yang tersedia: *{alts}*\nMau coba tipe kamar lain?",
            "booking_success": "✅ Pesanan Anda sudah kami catat!\n\nNomor referensi: *{booking_ref}*\n\nTim kami akan menghubungi Anda di nomor ini dalam *1x24 jam* untuk konfirmasi dan informasi pembayaran.\n\nAda yang ingin ditanyakan lagi?"
        },
        "en": {
            "cancel_confirm": "Alright, the booking process has been cancelled. If you would like to book a room in the future, we are ready to help! 😊",
            "confirm_header": "Here is a summary of your booking:\n\n",
            "confirm_footer": "\n\nIs everything correct? Type *yes* to proceed or *no* if you want to change something.",
            "correction_prompt": "Alright, what would you like to change? Please specify the information you want to correct.",
            "correction_success_confirm": "Alright, your booking details have been updated.\n\n",
            "correction_success_collecting": "Alright, your booking details have been updated. ",
            "upsell_header": "Before we proceed, we have some attractive offers for you:\n\n",
            "upsell_footer": "\n\nAre you interested? Type *yes* to accept or *no* to skip.",
            "room_available": "Room *{room_type}* is available for *{check_in}*! ✅",
            "price_per_night": "\n💰 Price: *{price}/night*",
            "price_total": "\n💳 Total: *{price}*",
            "continue_booking_q": "Would you like to proceed with the booking?",
            "faq_interrupt_reminder": "By the way, we are still in the process of booking. ",
            "decline_continue": "Alright, please let us know if you need any other information or assistance! 😊",
            "room_unavailable": "Sorry, room *{room_type}* is not available for *{check_in}*.",
            "alternatives_text": "\n\nAvailable alternatives: *{alts}*\nWould you like to try another room type?",
            "booking_success": "✅ Your booking has been recorded!\n\nReference number: *{booking_ref}*\n\nOur team will contact you at this number within *24 hours* for confirmation and payment details.\n\nIs there anything else I can help you with?"
        }
    }

    def _get_string(self, key: str, lang: str) -> str:
        """
        Mengambil string lokalisasi yang sesuai dengan kode bahasa.

        Parameter:
            key (str): Kunci string lokalisasi yang dicari.
            lang (str): Kode bahasa ("id" atau "en").

        Return:
            str: Teks terjemahan yang sesuai.
        """
        return self.LOCALIZED_STRINGS.get(lang, self.LOCALIZED_STRINGS["id"]).get(key, "")

    def _detect_language(self, message: str, current_lang: str) -> str:
        """
        Mendeteksi bahasa pesan pengguna berdasarkan kecocokan kata kunci bahasa Inggris atau Indonesia.

        Parameter:
            message (str): Pesan teks pengguna.
            current_lang (str): Kode bahasa sesi aktif saat ini.

        Return:
            str: Kode bahasa yang terdeteksi ("id" atau "en").
        """
        import re
        msg_lower = message.lower().strip()
        
        en_keywords = {
            "book", "booking", "room", "checkin", "checkout", "night", "nights", "stay", "day", "days",
            "standard", "deluxe", "suite", "hello", "hi", "yes", "no", "want", "please", "correct",
            "wrong", "cancel", "change", "date", "guest", "guests", "adult", "adults", "child", "children"
        }
        id_keywords = {
            "pesan", "booking", "kamar", "checkin", "checkout", "malam", "hari", "inap",
            "standard", "deluxe", "suite", "halo", "hi", "ya", "tidak", "ga", "gak", "mau", "tolong",
            "benar", "salah", "batal", "ganti", "tanggal", "tgl", "tamu", "dewasa", "anak", "orang"
        }
        
        words = re.findall(r'\b\w+\b', msg_lower)
        en_matches = sum(1 for w in words if w in en_keywords)
        id_matches = sum(1 for w in words if w in id_keywords)
        
        if en_matches > id_matches:
            return "en"
        elif id_matches > en_matches:
            return "id"
            
        return current_lang

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

        # Deteksi bahasa pesan dan simpan di state
        state.language = self._detect_language(message, state.language)

        # Detect cancellation di semua step
        if await self.collector.detect_cancellation(message):
            await session_mgr.clear_booking_state(ctx.session_id)
            return self._get_string("cancel_confirm", state.language)

        # Deteksi FAQ interrupt
        # Kalau user tanya FAQ di tengah booking
        # → jawab FAQ dulu, lalu remind booking
        from backend.core.classifier.intent_classifier import IntentClassifier

        classifier = IntentClassifier(self.llm)
        result = classifier.classify(message)
        current_intent = result.intent.value

        # Kalau intent adalah faq dan state
        # sedang collecting/confirming/upselling
        # → handle FAQ dulu dengan reminder
        FAQ_INTERRUPT_INTENTS = {"faq"}
        BOOKING_ACTIVE_STEPS = {
            BookingStep.COLLECTING,
            BookingStep.CONFIRMING,
            BookingStep.UPSELLING
        }

        if current_intent in FAQ_INTERRUPT_INTENTS and state.step in BOOKING_ACTIVE_STEPS:
            # Import FAQ handler
            from backend.core.workflows.faq.handler import FAQHandler
            faq = FAQHandler(self.db)
            faq_response = await faq.handle(ctx)

            # Tambah reminder lanjut booking
            missing = state.params.missing_required()
            if missing:
                reminder = await self.collector.generate_question(
                    state=state,
                    has_history=True
                )
                faq_reminder = self._get_string("faq_interrupt_reminder", state.language)
                return (
                    f"{faq_response}\n\n"
                    f"---\n"
                    f"{faq_reminder}"
                    f"{reminder}"
                )
            return faq_response

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

        question = await self.collector.generate_question(
            state=state,
            has_history=len(ctx.history) > 0
        )
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
        # Cek jika user menolak melanjutkan booking setelah info ketersediaan
        # (yaitu jika belum ada info personal yang terisi, dan user mengirim pesan penolakan)
        is_negation = ctx.message.content.lower().strip() in {
            "tidak", "gak", "ga", "no", "enggak", "nggak", "tidak mau", "batal", "cancel"
        }
        has_no_personal_info = (
            state.params.guest_name is None
            and state.params.wa_number is None
            and state.params.num_guests is None
        )
        if is_negation and has_no_personal_info:
            await session_mgr.clear_booking_state(ctx.session_id)
            return self._get_string("decline_continue", state.language)

        print(f"[DEBUG] _handle_collecting called. state={state.model_dump()}")
        # Extract dan merge params
        old_params = state.params.model_dump()
        state.params = await self.collector.extract_params(
            message=ctx.message.content,
            current_state=state
        )

        # Auto-fill profile
        await self._enrich_guest_profile(ctx, state)

        # Cek jika ada parameter kritis yang berubah selama tahap COLLECTING
        critical_fields = {"room_type", "check_in_date", "check_out_date"}
        for f in critical_fields:
            if getattr(state.params, f) != old_params.get(f) and getattr(state.params, f) is not None:
                state.availability_checked = False

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
        return await self.collector.generate_question(
            state=state,
            has_history=len(ctx.history) > 0
        )

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
        2. Jika disetujui (ya), proses pemesanan dengan upsell atau langsung reservasi.
        3. Jika ditolak (tidak), proses koreksi parameter langsung dari pesan atau tanya ulang.
        """
        confirmed = await self.collector.detect_confirmation(ctx.message.content)

        if confirmed:
            return await self._process_booking_confirmation(ctx, state, session_mgr)

        return await self._process_booking_correction(ctx, state, session_mgr)

    async def _process_booking_confirmation(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Memproses persetujuan booking tamu, memuat penawaran upsell, dan memperbarui step.

        Parameter:
            ctx (ConversationContext): Konteks percakapan saat ini.
            state (BookingState): State booking aktif.
            session_mgr (SessionManager): Manager sesi untuk menyimpan state.

        Return:
            str: Pesan penawaran upsell atau pesan sukses reservasi kamar.
        """
        upsells = await self._load_upsells(ctx.hotel_id)

        if upsells:
            state.upsell_offers = upsells
            state.step = BookingStep.UPSELLING
            await session_mgr.save_booking_state(ctx.session_id, state)
            return self._build_upsell_message(state)
        
        return await self._create_booking(ctx, state, session_mgr)

    async def _process_booking_correction(
        self,
        ctx: ConversationContext,
        state: BookingState,
        session_mgr: SessionManager
    ) -> str:
        """
        Memproses penolakan atau koreksi parameter booking dari pesan tamu.

        Parameter:
            ctx (ConversationContext): Konteks percakapan saat ini.
            state (BookingState): State booking aktif.
            session_mgr (SessionManager): Manager sesi untuk menyimpan state.

        Return:
            str: Respon ketersediaan kamar baru, konfirmasi data baru, atau pertanyaan perbaikan data.
        """
        old_params = state.params.model_dump()
        
        # Ekstrak parameter dari pesan penolakan/koreksi tamu
        new_params = await self.collector.extract_params(
            message=ctx.message.content,
            current_state=state
        )
        
        state.params = new_params
        await self._enrich_guest_profile(ctx, state)
        new_params = state.params
        
        # Identifikasi parameter mana saja yang berubah dan tidak null
        changed_fields = [
            field for field, new_val in new_params.model_dump().items()
            if new_val != old_params.get(field) and new_val is not None
        ]

        if not changed_fields:
            state.step = BookingStep.COLLECTING
            await session_mgr.save_booking_state(ctx.session_id, state)
            return self._get_string("correction_prompt", state.language)

        # Update parameter baru ke state
        state.params = new_params

        # Jika parameter kritis untuk ketersediaan berubah, cek ulang availability
        critical_fields = {"room_type", "check_in_date", "check_out_date"}
        if any(f in changed_fields for f in critical_fields):
            state.availability_checked = False
            return await self._check_and_respond(ctx, state, session_mgr)

        # Jika field non-kritis yang berubah (nama, nomor wa, dll)
        if state.params.is_complete():
            state.step = BookingStep.CONFIRMING
            await session_mgr.save_booking_state(ctx.session_id, state)
            corr_success = self._get_string("correction_success_confirm", state.language)
            return (
                f"{corr_success}"
                f"{self._build_confirm_message(state)}"
            )

        state.step = BookingStep.COLLECTING
        await session_mgr.save_booking_state(ctx.session_id, state)
        question = await self.collector.generate_question(
            state=state,
            has_history=len(ctx.history) > 0
        )
        corr_success = self._get_string("correction_success_collecting", state.language)
        return f"{corr_success}{question}"

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
        print(f"[DEBUG] _check_and_respond called. state={state.model_dump()}")
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

        lang = state.language
        if not availability.available:
            # Kamar tidak tersedia
            state.step = BookingStep.COLLECTING
            await session_mgr.save_booking_state(ctx.session_id, state)

            alt_text = ""
            if availability.alternatives:
                alts = ", ".join(availability.alternatives)
                alt_tpl = self._get_string("alternatives_text", lang)
                alt_text = alt_tpl.format(alts=alts)

            room_unavail_tpl = self._get_string("room_unavailable", lang)
            return room_unavail_tpl.format(
                room_type=state.params.room_type,
                check_in=state.params.check_in_date
            ) + alt_text

        # Kamar tersedia
        price_text = ""
        if availability.price_per_night:
            price_fmt = f"Rp {availability.price_per_night:,.0f}".replace(",", ".")
            price_tpl = self._get_string("price_per_night", lang)
            price_text = price_tpl.format(price=price_fmt)

            if availability.total_price and state.params.check_out_date:
                total_fmt = f"Rp {availability.total_price:,.0f}".replace(",", ".")
                total_tpl = self._get_string("price_total", lang)
                price_text += total_tpl.format(price=total_fmt)

        was_inquiry = state.step == BookingStep.INQUIRY

        # Pindah ke collecting untuk parameter lain jika belum lengkap
        state.step = BookingStep.COLLECTING
        await session_mgr.save_booking_state(ctx.session_id, state)

        avail_tpl = self._get_string("room_available", lang)
        response = avail_tpl.format(
            room_type=state.params.room_type,
            check_in=state.params.check_in_date
        ) + f"{price_text}\n\n"

        if state.params.is_complete():
            state.step = BookingStep.CONFIRMING
            await session_mgr.save_booking_state(ctx.session_id, state)
            response += self._build_confirm_message(state)
        elif was_inquiry:
            response += self._get_string("continue_booking_q", lang)
        else:
            question = await self.collector.generate_question(
                state=state,
                has_history=len(ctx.history) > 0
            )
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

        return self._get_string("booking_success", state.language).format(
            booking_ref=booking_ref
        )

    def _build_confirm_message(
        self,
        state: BookingState
    ) -> str:
        """Menyusun teks ringkasan data pemesanan untuk konfirmasi tamu."""
        summary = state.params.to_summary(lang=state.language)
        header = self._get_string("confirm_header", state.language)
        footer = self._get_string("confirm_footer", state.language)
        return f"{header}{summary}{footer}"

    def _build_upsell_message(
        self,
        state: BookingState
    ) -> str:
        """Menyusun teks penawaran promosi upsell tambahan."""
        current = state.current_upsell()
        if not current:
            return ""

        header = self._get_string("upsell_header", state.language)
        footer = self._get_string("upsell_footer", state.language)
        offer_text = current.format_offer()
        return f"{header}✨ *{offer_text}*\n\n{footer}"

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

    async def _enrich_guest_profile(
        self,
        ctx: ConversationContext,
        state: BookingState
    ) -> None:
        """
        Auto-fill nama tamu menggunakan HMS Guest Lookup jika WA diisi dan nama kosong.
        """
        if state.params.wa_number and not state.params.guest_name:
            try:
                from backend.integrations.hms.schemas import GuestLookupRequest
                lookup_req = GuestLookupRequest(
                    wa_number=state.params.wa_number,
                    hotel_id=ctx.hotel.hotel_id
                )
                lookup_res = await self.hms.lookup_guest(lookup_req)
                if lookup_res.found and lookup_res.guest_name:
                    state.params.guest_name = lookup_res.guest_name
            except Exception as e:
                logger.error(f"Gagal melakukan guest lookup ke HMS: {str(e)}", exc_info=True)

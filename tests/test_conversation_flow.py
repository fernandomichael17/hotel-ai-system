import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4, UUID

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.workflows.booking.handler import BookingHandler
from backend.core.workflows.booking.schemas import BookingState, BookingStep, CollectedParams, UpsellOffer
from backend.core.workflows.booking.form_collector import BookingFormCollector
from backend.core.channel.context import ConversationContext
from backend.core.channel.schemas import IncomingMessage, HotelContext, GuestContext
from backend.core.classifier.schemas import IntentType, IntentResult
from backend.integrations.hms.schemas import RoomAvailabilityResponse, BookingCreateResponse

# Mock DB objects
class MockPolicy:
    def __init__(self):
        self.rules = {
            "breakfast": {
                "name": "Breakfast Package",
                "price": 100000,
                "unit": "person"
            }
        }

class MockBookingDraft:
    def __init__(self, id_val):
        self.id = id_val

class TestConversationFlow(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.session_id = str(uuid4())
        self.hotel_id = str(uuid4())
        
        # Mock dependencies
        self.mock_db = MagicMock()
        
        # Mock LLM Client
        self.mock_llm = MagicMock()
        self.mock_llm.generate = MagicMock(side_effect=self.mock_llm_generate)
        
        # Patch get_llm_client to return our mock
        self.patcher_llm = patch("backend.core.workflows.booking.form_collector.get_llm_client", return_value=self.mock_llm)
        self.patcher_llm.start()
        
        # Mock HMS Client
        self.mock_hms = MagicMock()
        self.mock_hms.check_availability = AsyncMock(return_value=RoomAvailabilityResponse(
            available=True,
            room_type="standard",
            check_in_date="2026-07-20",
            price_per_night=500000,
            total_price=1000000,
            reason="Available",
            alternatives=[]
        ))
        self.mock_hms.create_booking = AsyncMock(return_value=BookingCreateResponse(
            success=True,
            status="confirmed",
            message="Booking created successfully",
            hms_booking_id="HMS-99887"
        ))
        
        from backend.integrations.hms.schemas import GuestLookupResponse
        self.mock_hms.lookup_guest = AsyncMock(return_value=GuestLookupResponse(
            found=True,
            guest_name="Fernando Michael",
            wa_number="08123456789"
        ))
        
        self.patcher_hms = patch("backend.core.workflows.booking.handler.get_hms_client", return_value=self.mock_hms)
        self.patcher_hms.start()

        # Patch Repositories
        self.mock_policy_repo = MagicMock()
        self.mock_policy_repo.find_by_type = AsyncMock(return_value=MockPolicy())
        self.patcher_policy = patch("backend.core.workflows.booking.handler.PolicyRepository", return_value=self.mock_policy_repo)
        self.patcher_policy.start()

        self.mock_booking_repo = MagicMock()
        self.mock_booking_repo.create = AsyncMock(return_value=MockBookingDraft(uuid4()))
        self.patcher_booking = patch("backend.core.workflows.booking.handler.BookingRepository", return_value=self.mock_booking_repo)
        self.patcher_booking.start()

    def tearDown(self):
        self.patcher_llm.stop()
        self.patcher_hms.stop()
        self.patcher_policy.stop()
        self.patcher_booking.stop()

    def mock_llm_generate(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        
        # 1. Parameter extraction
        if "ekstraksi data" in prompt_lower or "format output" in prompt_lower:
            import re
            m = re.search(r"pesan user:\s*(.*)", prompt_lower)
            if not m:
                m = re.search(r"pesan:\s*\"(.*)\"", prompt_lower)
            
            user_msg = m.group(1).strip() if m else ""
            user_msg_clean = user_msg.split('\n')[0].strip() # ambil baris pertama saja
            
            print(f"[DEBUG MOCK LLM EXTRACT] user_msg_clean='{user_msg_clean}'")
            
            # Map pesan eksak ke return JSON
            if user_msg_clean == "halo, saya mau pesan untuk tanggal 20 juli":
                return '{"check_in_date": "2026-07-20"}'
            elif user_msg_clean == "hello, i want to book a room for 20 july":
                return '{"check_in_date": "2026-07-20"}'
            elif user_msg_clean == "kamar deluxe":
                return '{"room_type": "deluxe"}'
            elif user_msg_clean == "standard room":
                return '{"room_type": "standard"}'
            elif user_msg_clean == "1 orang kamar deluxe atas nama fernando michael":
                return '{"num_guests": 1, "room_type": "deluxe", "guest_name": "Fernando Michael"}'
            elif user_msg_clean == "1 orang kamar deluxe atas nama fernando michael, minta kamar non-smoking":
                return '{"num_guests": 1, "room_type": "deluxe", "guest_name": "Fernando Michael", "special_request": "minta kamar non-smoking"}'
            elif user_msg_clean == "1 orang kamar deluxe dengan nomor wa 08123456789":
                return '{"num_guests": 1, "room_type": "deluxe", "wa_number": "08123456789"}'
            elif user_msg_clean == "standard room for 2 adults, name is john doe":
                return '{"room_type": "standard", "num_guests": 2, "guest_name": "John Doe"}'
            elif user_msg_clean == "hello, i want to book a standard room for 20 july for 2 nights":
                return '{"room_type": "standard", "check_in_date": "2026-07-20", "check_out_date": "2026-07-22"}'
            elif user_msg_clean == "1 orang atas nama fernando michael, minta kamar non-smoking":
                return '{"num_guests": 1, "guest_name": "Fernando Michael", "special_request": "minta kamar non-smoking"}'
            elif user_msg_clean == "1 orang atas nama fernando michael":
                return '{"num_guests": 1, "guest_name": "Fernando Michael"}'
            elif user_msg_clean == "2 adults, name is john doe":
                return '{"num_guests": 2, "guest_name": "John Doe"}'
            elif user_msg_clean == "08123456789":
                return '{"wa_number": "08123456789"}'
            elif user_msg_clean == "1 orang dengan nomor wa 08123456789":
                return '{"num_guests": 1, "wa_number": "08123456789"}'
            elif user_msg_clean == "1 orang":
                return '{"num_guests": 1}'
            elif user_msg_clean == "saya mau deluxe saja":
                return '{"room_type": "deluxe"}'
            elif user_msg_clean == "deluxe room":
                return '{"room_type": "deluxe"}'
            elif user_msg_clean == "salah, ganti checkin ke tanggal 25 juli bukan 20 juli":
                return '{"check_in_date": "2026-07-25"}'
            elif user_msg_clean == "salah, ganti checkin ke tanggal 20 agustus dan checkout ke tanggal 15 agustus":
                return '{"check_in_date": "2026-08-20", "check_out_date": "2026-08-15"}'
            elif user_msg_clean == "salah, ganti checkin ke tanggal 20 agustus dan checkout ke tanggal 2 agustus":
                return '{"check_in_date": "2026-08-20", "check_out_date": "2026-08-02"}'
            elif user_msg_clean == "salah, ganti checkin ke tanggal 20 agustus":
                return '{"check_in_date": "2026-08-20"}'
            elif user_msg_clean == "pesan kamar tanggal 20 juli":
                return '{"check_in_date": "2026-07-20"}'
            return '{}'

        # 2. Question generation
        if "perlu ditanyakan sekarang" in prompt_lower or "perlu ditanyakan" in prompt_lower:
            # Cari baris setelah "perlu ditanyakan sekarang:"
            lines = prompt_lower.split("perlu ditanyakan sekarang:")
            if len(lines) > 1:
                target_section = lines[1].strip().split("\n")[0].strip()
                print(f"[DEBUG TEST QUESTION] target_section='{target_section}'")
                
                is_en = "room type" in target_section or "number of adult guests" in target_section or "guest name" in target_section or "whatsapp number" in target_section or "check-out date" in target_section
                
                if "check-out" in target_section or "check_out" in target_section or "tanggal check-out" in target_section:
                    return "How many nights do you plan to stay?" if is_en else "Untuk berapa malam Anda berencana menginap?"
                elif "room_type" in target_section or "room type" in target_section or "tipe kamar" in target_section:
                    return "Which room type would you prefer?" if is_en else "Tipe kamar apa yang Anda inginkan?"
                elif "num_guests" in target_section or "number of adult guests" in target_section or "jumlah tamu" in target_section:
                    return "How many adult guests?" if is_en else "Untuk berapa orang tamu?"
                elif "guest_name" in target_section or "guest name" in target_section or "nama tamu" in target_section:
                    return "What is your name?" if is_en else "Bisa sebutkan nama Anda?"
                elif "wa_number" in target_section or "whatsapp" in target_section or "nomor whatsapp" in target_section or "whatsapp number" in target_section:
                    return "What is your WhatsApp number?" if is_en else "Berapa nomor WhatsApp Anda?"
            return "Bisa infokan data berikutnya?"

        return "Unknown prompt"

    def _build_context(self, message: str) -> ConversationContext:
        incoming = IncomingMessage(
            user_identifier="test-user-123",
            content=message,
            channel="web",
            hotel_slug="metland-hotel"
        )
        hotel_ctx = HotelContext(
            hotel_id=self.hotel_id,
            hotel_name="Metland Hotel",
            slug="metland-hotel"
        )
        return ConversationContext(
            message=incoming,
            hotel=hotel_ctx,
            session_id=self.session_id
        )

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_happy_path_indonesian(self, mock_classifier_class):
        """Uji alur bahagia percakapan booking lengkap dalam Bahasa Indonesia."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Turn 1: Pesan checkin -> Memicu pertanyaan durasi menginap
        ctx = self._build_context("Halo, saya mau pesan untuk tanggal 20 juli")
        resp = await handler.handle(ctx)
        self.assertIn("Untuk berapa malam Anda berencana menginap?", resp)

        # Turn 2: Masukkan durasi menginap (2 malam) -> Memicu pertanyaan tipe kamar
        ctx = self._build_context("2 malam")
        resp = await handler.handle(ctx)
        self.assertIn("Tipe kamar apa yang Anda inginkan?", resp)

        # Turn 3: Pilih kamar deluxe -> Ketersediaan dicek untuk rentang 20-22 Juli, memicu info tarif & pertanyaan jumlah tamu
        ctx = self._build_context("Kamar deluxe")
        resp = await handler.handle(ctx)
        self.assertIn("Kamar *deluxe* tersedia untuk tanggal *2026-07-20 s/d 2026-07-22*", resp)
        self.assertIn("Untuk berapa orang tamu?", resp)

        # Turn 4: Masukkan jumlah tamu & nama -> Memicu pertanyaan nomor WhatsApp
        ctx = self._build_context("1 orang atas nama Fernando Michael")
        resp = await handler.handle(ctx)
        self.assertIn("Berapa nomor WhatsApp Anda?", resp)

        # Turn 5: Masukkan nomor WA -> Karena semua field utama lengkap, tampilkan summary
        ctx = self._build_context("08123456789")
        resp = await handler.handle(ctx)
        self.assertIn("Berikut ringkasan pesanan Anda:", resp)
        self.assertIn("Tipe Kamar  : Deluxe", resp)
        self.assertIn("Check-in    : 2026-07-20", resp)
        self.assertIn("Check-out   : 2026-07-22", resp)
        self.assertIn("WhatsApp    : 08123456789", resp)
        self.assertIn("Nama        : Fernando Michael", resp)

        # Turn 6: Konfirmasi "ya" -> Masuk ke UPSELLING
        ctx = self._build_context("ya")
        resp = await handler.handle(ctx)
        self.assertIn("Breakfast Package", resp)
        self.assertIn("Apakah Anda tertarik?", resp)

        # Turn 7: Tolak upsell -> Selesai dan simpan booking draft
        ctx = self._build_context("tidak")
        resp = await handler.handle(ctx)
        self.assertIn("Pesanan Anda sudah kami catat!", resp)
        self.assertIn("Nomor referensi:", resp)

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_dynamic_checkout_shifting_and_corrections(self, mock_classifier_class):
        """Uji alur koreksi parameter di turn konfirmasi dan pergeseran tanggal check-out dinamis."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Setup state langsung ke CONFIRMING dengan check-in 20 Juli, checkout 22 Juli (2 malam)
        from backend.core.session.manager import SessionManager
        session_mgr = SessionManager(self.mock_db)
        state = BookingState(
            step=BookingStep.CONFIRMING,
            params=CollectedParams(
                check_in_date="2026-07-20",
                check_out_date="2026-07-22",
                room_type="standard",
                num_guests=1,
                guest_name="Fernando Michael",
                wa_number="08123456789"
            ),
            availability_checked=True
        )
        await session_mgr.save_booking_state(self.session_id, state)

        # User menolak ringkasan dan mengubah check-in ke 25 Juli
        ctx = self._build_context("salah, ganti checkin ke tanggal 25 juli bukan 20 juli")
        resp = await handler.handle(ctx)

        # Harus otomatis menggeser check-out ke 27 Juli (menjaga durasi stay 2 malam)
        self.assertIn("Check-in    : 2026-07-25", resp)
        self.assertIn("Check-out   : 2026-07-27", resp)

        # Pastikan data check-out yang tersimpan di state juga terupdate menjadi 2026-07-27
        updated_state = await session_mgr.get_booking_state(self.session_id)
        self.assertEqual(updated_state.params.check_in_date, "2026-07-25")
        self.assertEqual(updated_state.params.check_out_date, "2026-07-27")

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_defensive_checkout_clearing_on_invalid_date(self, mock_classifier_class):
        """Uji pembersihan check-out secara defensif jika check-in baru mendahului/sama dengan check-out lama."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Setup state langsung ke CONFIRMING dengan tanggal valid
        from backend.core.session.manager import SessionManager
        session_mgr = SessionManager(self.mock_db)
        state = BookingState(
            step=BookingStep.CONFIRMING,
            params=CollectedParams(
                check_in_date="2026-08-01",
                check_out_date="2026-08-05",  # stay 4 nights
                room_type="standard",
                num_guests=1,
                guest_name="Fernando Michael",
                wa_number="08123456789"
            ),
            availability_checked=True
        )
        await session_mgr.save_booking_state(self.session_id, state)

        # Tamu mengganti check-in ke 20 Agustus dan checkout ke 15 agustus (15 agustus <= 20 agustus)
        ctx = self._build_context("salah, ganti checkin ke tanggal 20 agustus dan checkout ke tanggal 15 agustus")
        resp = await handler.handle(ctx)

        # Karena check-out <= check-in, check-out harus dihapus secara defensif dan ditanyakan kembali
        self.assertIn("Untuk berapa malam Anda berencana menginap?", resp)
        
        updated_state = await session_mgr.get_booking_state(self.session_id)
        self.assertIsNone(updated_state.params.check_out_date)

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_multilingual_english_happy_path(self, mock_classifier_class):
        """Uji pendeteksian bahasa Inggris dan lokalisasi respon bahasa Inggris."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Turn 1: User menyapa/booking dalam Bahasa Inggris -> Tanya durasi stay
        ctx = self._build_context("Hello, I want to book a room for 20 july")
        resp = await handler.handle(ctx)
        
        self.assertIn("How many nights do you plan to stay?", resp)

        # State harus bertuliskan language: "en"
        from backend.core.session.manager import SessionManager
        session_mgr = SessionManager(self.mock_db)
        state = await session_mgr.get_booking_state(self.session_id)
        self.assertEqual(state.language, "en")

        # Turn 2: Masukkan durasi -> Tanya room type
        ctx = self._build_context("2 nights")
        resp = await handler.handle(ctx)
        self.assertIn("Which room type would you prefer?", resp)

        # Turn 3: Masukkan tipe kamar -> Cek availability & tanya jumlah tamu
        ctx = self._build_context("Standard room")
        resp = await handler.handle(ctx)
        self.assertIn("A *standard* room is available for *2026-07-20 s/d 2026-07-22*", resp)
        self.assertIn("How many adult guests?", resp)

        # Turn 4: Masukkan jumlah tamu & nama -> Tanya whatsapp
        ctx = self._build_context("2 adults, name is John Doe")
        resp = await handler.handle(ctx)
        self.assertIn("What is your WhatsApp number?", resp)

        # Turn 5: Masukkan nomor WA -> Tampilkan summary
        ctx = self._build_context("08123456789")
        resp = await handler.handle(ctx)
        self.assertIn("Here is a summary of your booking:", resp)
        self.assertIn("Room Type  : Standard", resp)
        self.assertIn("Name        : John Doe", resp)

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_cancellation_mid_flow(self, mock_classifier_class):
        """Uji pembatalan proses booking di tengah-tengah alur percakapan."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Mulai booking
        ctx = self._build_context("pesan kamar tanggal 20 juli")
        await handler.handle(ctx)

        # Kirim perintah batal
        ctx = self._build_context("batal saja, nevermind")
        resp = await handler.handle(ctx)
        
        self.assertIn("booking dibatalkan", resp)

        # Pastikan state dihapus dari in-memory cache
        from backend.core.session.manager import SessionManager
        session_mgr = SessionManager(self.mock_db)
        state = await session_mgr.get_booking_state(self.session_id)
        self.assertIsNone(state)

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_special_request_and_upsell_accepted(self, mock_classifier_class):
        """Uji pencatatan spesial request dan penerimaan tawaran upsell oleh tamu."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Turn 1: Pesan checkin -> tanya durasi
        ctx = self._build_context("Halo, saya mau pesan untuk tanggal 20 juli")
        await handler.handle(ctx)

        # Turn 2: Durasi menginap (2 malam) -> tanya tipe kamar
        ctx = self._build_context("2 malam")
        await handler.handle(ctx)

        # Turn 3: Pilih kamar deluxe -> tanya jumlah tamu
        ctx = self._build_context("Kamar deluxe")
        await handler.handle(ctx)

        # Turn 4: Masukkan jumlah tamu, nama, DAN spesial request -> tanya WA
        ctx = self._build_context("1 orang atas nama Fernando Michael, minta kamar non-smoking")
        await handler.handle(ctx)

        # Turn 5: Masukkan nomor WA -> summary
        ctx = self._build_context("08123456789")
        resp = await handler.handle(ctx)
        self.assertIn("Deluxe", resp)
        self.assertIn("Fernando Michael", resp)

        # Turn 6: Konfirmasi summary "ya" -> masuk upselling breakfast
        ctx = self._build_context("ya")
        resp = await handler.handle(ctx)
        self.assertIn("Breakfast Package", resp)

        # Turn 7: Terima upsell "ya" -> booking sukses
        ctx = self._build_context("ya")
        resp = await handler.handle(ctx)
        self.assertIn("Pesanan Anda sudah kami catat!", resp)

        # Verifikasi call parameters ke HMS create_booking
        # create_booking dipanggil dengan request yang berisi special_request dan upsell_items
        self.mock_hms.create_booking.assert_called_once()
        create_req = self.mock_hms.create_booking.call_args[0][0]
        self.assertEqual(create_req.special_request, "minta kamar non-smoking")
        self.assertIn("breakfast", create_req.upsell_items)

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_room_unavailable_and_alternative_selection(self, mock_classifier_class):
        """Uji penanganan tipe kamar penuh dan penawaran alternatif dari HMS."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        # Mock HMS check_availability untuk mengembalikan TIDAK TERSEDIA dengan alternatif Deluxe
        self.mock_hms.check_availability = AsyncMock(return_value=RoomAvailabilityResponse(
            available=False,
            room_type="standard",
            check_in_date="2026-07-20",
            check_out_date="2026-07-22",
            reason="Standard room is fully booked",
            alternatives=["deluxe"]
        ))

        handler = BookingHandler(self.mock_db)

        # Turn 1: Sapa & inginkan standard room untuk 2 malam (checkin & checkout terisi)
        ctx = self._build_context("Hello, I want to book a standard room for 20 july for 2 nights")
        resp = await handler.handle(ctx)
        
        self.assertIn("is not available", resp.lower())
        self.assertIn("deluxe", resp.lower())

        # Reset HMS check_availability mock agar mengembalikan tersedia untuk Deluxe pada pengecekan ulang
        self.mock_hms.check_availability = AsyncMock(return_value=RoomAvailabilityResponse(
            available=True,
            room_type="deluxe",
            check_in_date="2026-07-20",
            check_out_date="2026-07-22",
            price_per_night=850000,
            total_price=1700000,
            reason="Deluxe is available",
            alternatives=[]
        ))

        # Turn 2: Tamu menerima alternatif "saya mau deluxe saja"
        ctx = self._build_context("saya mau deluxe saja")
        resp = await handler.handle(ctx)

        # Pengecekan availability terpicu ulang untuk Deluxe, dan lanjut mengumpulkan parameter berikutnya
        self.assertIn("deluxe", resp.lower())

        # Pastikan state tipe kamar terupdate menjadi deluxe
        from backend.core.session.manager import SessionManager
        session_mgr = SessionManager(self.mock_db)
        state = await session_mgr.get_booking_state(self.session_id)
        self.assertEqual(state.params.room_type, "deluxe")

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_recurring_guest_lookup_autofill(self, mock_classifier_class):
        """Uji auto-fill nama tamu berulang menggunakan HMS Guest Lookup ketika nomor WA dimasukkan."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")

        handler = BookingHandler(self.mock_db)

        # Turn 1: Pesan checkin
        ctx = self._build_context("Halo, saya mau pesan untuk tanggal 20 juli")
        await handler.handle(ctx)

        # Turn 2: Masukkan durasi stay (2 malam)
        ctx = self._build_context("2 malam")
        await handler.handle(ctx)

        # Mock HMS lookup_guest agar mengembalikan data tamu terdaftar
        from backend.integrations.hms.schemas import GuestLookupResponse
        self.mock_hms.lookup_guest = AsyncMock(return_value=GuestLookupResponse(
            found=True,
            guest_name="Fernando Michael",
            wa_number="08123456789"
        ))

        # Turn 3: Masukkan jumlah tamu, tipe kamar, DAN nomor WhatsApp -> Memicu Guest Lookup autofill nama "Fernando Michael"
        ctx = self._build_context("1 orang kamar deluxe dengan nomor WA 08123456789")
        resp = await handler.handle(ctx)
        self.assertIn("Berikut ringkasan pesanan Anda:", resp)

        # Pastikan guest_name terisi otomatis menjadi "Fernando Michael" di state
        from backend.core.session.manager import SessionManager
        session_mgr = SessionManager(self.mock_db)
        state = await session_mgr.get_booking_state(self.session_id)
        self.assertEqual(state.params.guest_name, "Fernando Michael")

    @patch("backend.core.classifier.intent_classifier.IntentClassifier")
    async def test_faq_interruption_during_booking(self, mock_classifier_class):
        """Memastikan pertanyaan FAQ di tengah-tengah alur booking dijawab oleh FAQHandler lalu dilanjutkan ke booking."""
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        
        # Turn 1: Intent booking_request, LLM extract tanggal
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.BOOKING_REQUEST, confidence=1.0, raw_response="booking_request")
        handler = BookingHandler(self.mock_db)
        
        ctx1 = self._build_context("Halo, saya mau pesan untuk tanggal 20 juli")
        resp1 = await handler.handle(ctx1)
        self.assertIn("Untuk berapa malam Anda berencana menginap?", resp1)
        
        # Turn 2: Tanya FAQ "Jam berapa kolam renang buka?" -> Intent FAQ
        mock_classifier.classify.return_value = IntentResult(intent=IntentType.FAQ, confidence=1.0, raw_response="faq")
        
        # Mock FAQRetriever inside FAQHandler
        with patch("backend.core.workflows.faq.handler.FAQRetriever") as mock_retriever_class:
            mock_retriever = MagicMock()
            mock_retriever_class.return_value = mock_retriever
            mock_retriever.get_context = AsyncMock(return_value="Kolam renang buka setiap hari dari pukul 06.00 hingga 22.00 WIB.")
            
            ctx2 = self._build_context("Jam berapa kolam renang buka?")
            resp2 = await handler.handle(ctx2)
            
            # Harusnya menjawab FAQ dan juga memberikan reminder/pertanyaan booking berikutnya
            self.assertIn("pukul 06.00 hingga 22.00 WIB", resp2)
            self.assertIn("Ngomong-ngomong, saat ini kita sedang dalam proses pemesanan kamar.", resp2)

if __name__ == "__main__":
    unittest.main()

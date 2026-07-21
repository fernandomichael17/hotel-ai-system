import os
import sys
import unittest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Tambahkan direktori root ke sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.workflows.booking.form_collector import (
    parse_indonesian_date,
    BookingFormCollector
)
from backend.core.workflows.booking.schemas import BookingState, CollectedParams
from backend.core.workflows.booking.handler import BookingHandler
from backend.core.channel.context import ConversationContext
from backend.core.channel.schemas import IncomingMessage, HotelContext, GuestContext

class TestBookingWorkflowCases(unittest.IsolatedAsyncioTestCase):
    """
    Test suite komprehensif untuk memverifikasi alur kerja (workflow) pemesanan hotel,
    termasuk penanganan kasus khusus, koreksi tanggal, dan deteksi bahasa.
    """

    def setUp(self):
        """Inisialisasi objek pengujian sebelum setiap test case dijalankan."""
        self.collector = BookingFormCollector()
        self.today = datetime.now()

    # Skenario 1: Pemesanan Kamar Lengkap & Standar
    async def test_complete_standard_booking(self):
        """Memastikan parameter pemesanan terekstrak secara lengkap jika semua info diberikan sekaligus."""
        state = BookingState()
        # Mocking LLM response untuk mengekstrak data
        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(return_value='{"name": "Budi Santoso", "check_in_date": "2026-08-01", "check_out_date": "2026-08-03", "room_type": "standard"}')
        
        with patch("backend.core.workflows.booking.form_collector.get_llm_client", return_value=mock_llm):
            result = await self.collector.extract_params(
                message="Saya Budi Santoso mau pesan kamar standard dari tanggal 1 agustus sampai 3 agustus",
                current_state=state
            )
            self.assertEqual(result.guest_name, "budi santoso")
            self.assertEqual(result.check_in_date, "2026-08-01")
            self.assertEqual(result.check_out_date, "2026-08-03")
            self.assertEqual(result.room_type, "standard")

    # Skenario 2: Ekstraksi Bertahap (Multi-turn)
    def test_missing_required_fields_detection(self):
        """Memastikan sistem mendeteksi field wajib yang masih kurang pada state pemesanan."""
        # Check-out date dan room_type kosong
        params = CollectedParams(
            guest_name="Ahmad",
            wa_number="081299998888",
            check_in_date="2026-08-01",
            num_guests=2
        )
        missing = params.missing_required()
        self.assertIn("tanggal check-out", missing)
        self.assertIn("tipe kamar", missing)
        self.assertFalse(params.is_complete())

        # Isi field yang kurang, status harus menjadi lengkap (complete)
        params.check_out_date = "2026-08-03"
        params.room_type = "deluxe"
        self.assertTrue(params.is_complete())

    # Skenario 3: Koreksi Tanggal dengan Heuristik "bukan"
    def test_apply_date_heuristics_correction_advanced(self):
        """Memastikan model mengabaikan tanggal salah setelah kata 'bukan'."""
        ci, co = self.collector._apply_date_heuristics(
            message="tanggal checkin saya 25 juli bukan 30 juli",
            current_check_in="2026-07-30"
        )
        self.assertTrue(ci.endswith("-07-25"))
        self.assertIsNone(co)

    # Skenario 4: Ekstraksi Rentang Tanggal
    def test_apply_date_heuristics_range_detection(self):
        """Memastikan pendeteksian rentang tanggal check-in sampai check-out."""
        ci, co = self.collector._apply_date_heuristics(
            message="pesan kamar untuk tanggal 20 juli sampai 22 juli",
            current_check_in=None
        )
        self.assertTrue(ci.endswith("-07-20"))
        self.assertTrue(co.endswith("-07-22"))

    # Skenario 5: Pergeseran Tanggal Dinamis
    async def test_dynamic_checkout_shifting(self):
        """Memastikan pergeseran check-in menggeser check-out dengan durasi stay yang sama."""
        state = BookingState(
            params=CollectedParams(
                check_in_date="2026-08-01",
                check_out_date="2026-08-03", # stay 2 malam
                room_type="standard"
            )
        )
        
        # Simulasi perubahan tanggal check-in ke 20 Agustus
        result = await self.collector.extract_params(
            message="ubah tanggal checkin ke 20 agustus",
            current_state=state
        )
        self.assertEqual(result.check_in_date, "2026-08-20")
        self.assertEqual(result.check_out_date, "2026-08-22") # check-out otomatis bergeser tetap 2 malam

    # Skenario 6: Tanggal Relatif ("hari ini", "besok", "lusa")
    def test_relative_date_parsing(self):
        """Memastikan kata-kata hari relatif diterjemahkan menjadi tanggal ISO dengan benar."""
        tomorrow_str = (self.today + timedelta(days=1)).strftime("%Y-%m-%d")
        lusa_str = (self.today + timedelta(days=2)).strftime("%Y-%m-%d")

        ci_tomorrow, _ = self.collector._apply_date_heuristics("saya checkin besok", None)
        ci_lusa, _ = self.collector._apply_date_heuristics("checkin lusa", None)

        self.assertEqual(ci_tomorrow, tomorrow_str)
        self.assertEqual(ci_lusa, lusa_str)

        # Uji "weekend ini" (akhir pekan ini)
        today_wd = self.today.weekday()
        if today_wd == 6:
            expected_sat = (self.today - timedelta(days=1)).strftime("%Y-%m-%d")
            expected_sun = self.today.strftime("%Y-%m-%d")
        else:
            expected_sat = (self.today + timedelta(days=(5 - today_wd))).strftime("%Y-%m-%d")
            expected_sun = (self.today + timedelta(days=(6 - today_wd))).strftime("%Y-%m-%d")
            
        ci_wk, co_wk = self.collector._apply_date_heuristics("booking weekend ini", None)
        self.assertEqual(ci_wk, expected_sat)
        self.assertEqual(co_wk, expected_sun)

        # Uji "akhir pekan depan"
        expected_sat_next = (datetime.strptime(expected_sat, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        expected_sun_next = (datetime.strptime(expected_sun, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        
        ci_wk_next, co_wk_next = self.collector._apply_date_heuristics("mau pesan akhir pekan depan", None)
        self.assertEqual(ci_wk_next, expected_sat_next)
        self.assertEqual(co_wk_next, expected_sun_next)

    # Skenario 7: Deteksi Pembatalan
    async def test_cancel_intent_detection(self):
        """Memastikan kata kunci pembatalan terdeteksi dengan tepat."""
        self.assertTrue(await self.collector.detect_cancellation("saya mau batal pesan kamar"))
        self.assertTrue(await self.collector.detect_cancellation("cancel booking aja mas"))
        self.assertFalse(await self.collector.detect_cancellation("apakah bisa bayar di tempat"))

    # Skenario 8: Pembersihan Nama Tamu Defensif
    async def test_defensive_guest_name_filtering(self):
        """Memastikan sistem membersihkan nama tamu jika terdeteksi kalimat penolakan atau kalimat tanya."""
        state = BookingState()
        # Mock LLM mendeteksi nama "bukan"
        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(return_value='{"name": "bukan saya"}')
        
        with patch("backend.core.workflows.booking.form_collector.get_llm_client", return_value=mock_llm):
            result = await self.collector.extract_params(
                message="bukan saya yang menginap",
                current_state=state
            )
            # Karena nama mengandung "bukan", ia disaring agar tidak menjadi nama tamu terdaftar
            self.assertIsNone(result.guest_name)

    # Skenario 9: Deteksi Bahasa & Lokalisasi Bilingual
    def test_language_detection_and_localization(self):
        """Memastikan sistem mendeteksi bahasa pengguna dan memberikan rangkuman terlokalisasi."""
        mock_db = MagicMock()
        handler = BookingHandler(mock_db)
        
        # Deteksi bahasa
        self.assertEqual(handler._detect_language("I want to make a reservation", "id"), "en")
        self.assertEqual(handler._detect_language("mau booking kamar dong", "en"), "id")
        
        # Summary bilingual
        params = CollectedParams(
            room_type="suite",
            check_in_date="2026-10-10",
            check_out_date="2026-10-12",
            num_guests=2,
            guest_name="John Wick"
        )
        self.assertIn("Room Type", params.to_summary("en"))
        self.assertIn("Tipe Kamar", params.to_summary("id"))

    # Skenario 10: Penanganan Kasus Ekstrim (Edge Cases)
    def test_invalid_date_formats_handling(self):
        """Memastikan format tanggal yang salah atau tidak realistis tidak menyebabkan sistem crash."""
        ci, co = self.collector._apply_date_heuristics(
            message="saya mau checkin tanggal 32 desember",
            current_check_in=None
        )
        self.assertIsNone(ci)
        self.assertIsNone(co)

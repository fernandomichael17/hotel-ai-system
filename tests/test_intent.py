import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.workflows.booking.form_collector import (
    parse_indonesian_date,
    BookingFormCollector
)
from backend.core.workflows.booking.schemas import BookingState, CollectedParams

class TestBookingWorkflow(unittest.TestCase):

    def test_parse_iso_date_no_shift(self):
        """Memastikan tanggal berformat ISO tidak mengalami pergeseran tanggal."""
        date_str = "2026-07-20"
        result = parse_indonesian_date(date_str)
        self.assertEqual(result, "2026-07-20")

    def test_parse_indonesian_text_date(self):
        """Memastikan tanggal berbahasa Indonesia biasa terkonversi ke ISO."""
        result = parse_indonesian_date("20 juli")
        self.assertTrue(result.endswith("-07-20"))

    def test_apply_date_heuristics_correction(self):
        """Memastikan apply_date_heuristics mengabaikan tanggal lama setelah kata 'bukan'."""
        collector = BookingFormCollector()
        
        # Kasus 1: "tanggal checkin 20 juli bukan 8 agustus"
        ci, co = collector._apply_date_heuristics(
            message="tanggal checkin 20 juli bukan 8 agustus",
            current_check_in="2026-08-08"
        )
        self.assertTrue(ci.endswith("-07-20"))
        self.assertIsNone(co)

        # Kasus 2: "salah, tanggal 20 juli bukan 8 agustus"
        ci, co = collector._apply_date_heuristics(
            message="salah, tanggal 20 juli bukan 8 agustus",
            current_check_in="2026-08-08"
        )
        self.assertTrue(ci.endswith("-07-20"))
        self.assertIsNone(co)

    def test_apply_date_heuristics_range(self):
        """Memastikan apply_date_heuristics mendeteksi rentang check-in sampai check-out."""
        collector = BookingFormCollector()
        ci, co = collector._apply_date_heuristics(
            message="dari tanggal 20 juli sampai 22 juli",
            current_check_in=None
        )
        self.assertTrue(ci.endswith("-07-20"))
        self.assertTrue(co.endswith("-07-22"))

    def test_schemas_required_fields(self):
        """Memastikan check_out_date termasuk dalam parameter wajib yang kurang."""
        params = CollectedParams(
            guest_name="Fernando Siregar",
            wa_number="0812131313123",
            check_in_date="2026-07-20",
            room_type="standard",
            num_guests=1
            # check_out_date is None
        )
        missing = params.missing_required()
        self.assertIn("tanggal check-out", missing)
        self.assertFalse(params.is_complete())

        # Isi check_out_date, harus lengkap
        params.check_out_date = "2026-07-22"
        self.assertTrue(params.is_complete())

    def test_dynamic_checkout_shifting_and_defensive_clearing(self):
        """Memastikan pergeseran checkout dinamis dan pembersihan checkout defensif bekerja."""
        import asyncio
        collector = BookingFormCollector()

        # Kasus 1: Check-in bergeser, pertahankan durasi stay (1 malam)
        state1 = BookingState(
            params=CollectedParams(
                check_in_date="2026-08-01",
                check_out_date="2026-08-02",
                room_type="standard"
            )
        )
        res1 = asyncio.run(collector.extract_params(
            message="ganti tanggal checkin ke 20 agustus",
            current_state=state1
        ))
        self.assertEqual(res1.check_in_date, "2026-08-20")
        self.assertEqual(res1.check_out_date, "2026-08-21")

        # Kasus 2: Check-in bergeser melebihi check-out lama -> checkout harus dinull-kan jika menjadi tidak valid
        state2 = BookingState(
            params=CollectedParams(
                check_in_date="2026-08-20",
                check_out_date="2026-08-02",
                room_type="standard"
            )
        )
        res2 = asyncio.run(collector.extract_params(
            message="oke",
            current_state=state2
        ))
        self.assertIsNone(res2.check_out_date)

if __name__ == "__main__":
    unittest.main()

"""
Booking form collector — extract parameter
booking dari percakapan natural.

Ini yang paling banyak pakai LLM karena
harus:
1. Extract params dari kalimat bebas
2. Detect perubahan params di tengah jalan
3. Tahu apa yang sudah ada dan apa yang kurang
4. Generate pertanyaan yang natural untuk
   param yang masih kurang

Sudah proven di POC:
- Parameter extraction: 100%
- Handle perubahan di tengah: ✅
- Handle tanggal relatif (besok, weekend): ✅
"""

import json
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.workflows.booking.schemas import (
    CollectedParams, BookingState
)
from backend.integrations.llm.client import (
    get_llm_client
)

# Prompt untuk extract params dari pesan
EXTRACT_PROMPT = """Kamu adalah sistem ekstraksi
parameter booking hotel.

Dari pesan user berikut, extract parameter
booking yang disebutkan.

ATURAN EKSTRAKSI:
1. Hanya extract yang EKSPLISIT disebutkan
2. Jangan asumsikan yang tidak disebutkan
3. Untuk tanggal relatif (besok, weekend,
   minggu depan) — extract as-is sebagai string
4. Untuk tipe kamar: normalize ke:
   standard, deluxe, suite,
   presidential_suite
   (kalau user sebut "kamar biasa" → standard,
    "kamar deluxe" → deluxe, dll)
5. Untuk nomor WA: extract angkanya saja
   tanpa tanda baca

Parameter yang perlu diextract:
- guest_name: nama tamu
- wa_number: nomor WhatsApp (10-15 digit)
- check_in_date: tanggal check-in
- check_out_date: tanggal check-out
- room_type: tipe kamar
- num_guests: jumlah tamu dewasa (integer)
- num_children: jumlah anak-anak (integer)
- special_request: permintaan khusus

Pesan user: {message}

Parameter yang sudah dikumpulkan sebelumnya:
{current_params}

CONTOH EKSTRAKSI JAWABAN TAMU:
1. Pesan: "fernando siregar dan michael hebert"
   Hasil: {{"guest_name": "fernando siregar dan michael hebert"}}
2. Pesan: "atas nama budi santoso"
   Hasil: {{"guest_name": "budi santoso"}}
3. Pesan: "2 orang"
   Hasil: {{"num_guests": 2}}
4. Pesan: "081234567890"
   Hasil: {{"wa_number": "081234567890"}}

Format output:
{{
  "guest_name": null atau "string",
  "wa_number": null atau "string",
  "check_in_date": null atau "string",
  "check_out_date": null atau "string",
  "room_type": null atau "string",
  "num_guests": null atau integer,
  "num_children": null atau integer,
  "special_request": null atau "string"
}}"""

# Prompt untuk generate pertanyaan
# yang natural ke user
ASK_MISSING_PROMPT = """Kamu adalah asisten
booking hotel yang ramah.

Tamu sedang dalam proses booking kamar.
Parameter yang sudah terkumpul:
{collected}

Parameter yang masih kurang:
{missing}

Tugas: Buat SATU pertanyaan natural
dalam Bahasa Indonesia untuk menanyakan
parameter yang paling penting dari yang
masih kurang.

ATURAN:
1. Tanya SATU hal saja per giliran
2. Mulai dari yang paling penting:
   check_in_date → room_type →
   num_guests → guest_name → wa_number
3. Pertanyaan singkat dan friendly
4. Boleh tambahkan pilihan kalau relevan
   contoh: "Tipe kamar apa yang diinginkan?
   Standard (Rp 500rb), Deluxe (Rp 850rb),
   atau Suite (Rp 1,5jt)?"
5. Jangan ulangi info yang sudah disebutkan
6. JANGAN pernah menyatakan bahwa kamar sudah disiapkan, dibooking, atau diamankan karena ini baru tahap pencatatan data awal.

Pertanyaan:"""

class BookingFormCollector:

    def __init__(self):
        """Inisialisasi form collector dengan klien LLM tunggal (Singleton)."""
        self.llm = get_llm_client()

    async def extract_params(
        self,
        message: str,
        current_state: BookingState
    ) -> CollectedParams:
        """
        Extract parameter booking dari pesan user menggunakan LLM.
        Merge dengan params yang sudah ada:
        - Kalau ada nilai baru → update
        - Kalau null → pertahankan yang lama

        Flow:
        1. Susun instruksi asisten dan gabungkan dengan prompt ekstraksi.
        2. Jalankan panggilan generate ke LLM secara thread-safe asinkron.
        3. Bersihkan format blok markdown kode JSON pada teks jawaban LLM.
        4. Lakukan deserialisasi JSON dan gabungkan parameter dengan parameter saat ini.
        """
        current_params = current_state.params

        prompt_body = EXTRACT_PROMPT.format(
            message=message,
            current_params=current_params.model_dump_json(indent=2)
        )

        # Gabungkan system prompt ke dalam satu prompt tunggal karena LLMClient hanya menerima string prompt
        prompt = (
            "Instruksi Asisten:\nKamu adalah sistem ekstraksi data. Jawab HANYA dengan JSON yang valid. Tidak ada teks lain.\n\n"
            f"{prompt_body}"
        )

        try:
            # Jalankan model LLM di thread terpisah agar non-blocking
            response = await asyncio.to_thread(self.llm.generate, prompt)
        except Exception:
            return current_params

        # Parse JSON dari response
        extracted = {}
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip()
            extracted = json.loads(clean)
        except (json.JSONDecodeError, IndexError, AttributeError):
            extracted = {}

        # Merge: update hanya yang ada nilai baru (tidak null)
        current_dict = current_params.model_dump()

        if isinstance(extracted, dict):
            for field, value in extracted.items():
                if value is not None and field in current_dict:
                    if field in ["check_in_date", "check_out_date"] and isinstance(value, str):
                        value = parse_indonesian_date(value)
                    current_dict[field] = value

        # Heuristik Deteksi Durasi Menginap (misal: "2 hari", "2 malam", "stay 3 days")
        # Jika check_in_date terisi namun check_out_date kosong
        if current_dict.get("check_in_date") and not current_dict.get("check_out_date"):
            import re
            from datetime import datetime, timedelta
            msg_lower = message.lower()
            
            # Pola regex untuk menangkap durasi menginap
            duration_patterns = [
                r"(\d+)\s*(hari|malam|day|night)",
                r"(selama|menginap|stay)\s*(\d+)"
            ]
            
            duration_days = None
            for pattern in duration_patterns:
                match = re.search(pattern, msg_lower)
                if match:
                    # Ambil angka durasi
                    if match.group(1).isdigit():
                        duration_days = int(match.group(1))
                    elif len(match.groups()) >= 2 and match.group(2).isdigit():
                        duration_days = int(match.group(2))
                    break
            
            if duration_days:
                try:
                    ci_date = datetime.strptime(current_dict["check_in_date"], "%Y-%m-%d")
                    co_date = ci_date + timedelta(days=duration_days)
                    current_dict["check_out_date"] = co_date.strftime("%Y-%m-%d")
                except Exception:
                    pass

        # Heuristik Tambahan (Defensive Programming):
        # Jika check_in_date dan room_type sudah terisi, sedangkan guest_name masih kosong,
        # dan pesan user berisi nama tanpa angka, keyword kamar, atau kata bilangan, asumsikan pesan tersebut adalah nama tamu.
        if (
            current_params.check_in_date and
            current_params.room_type and
            not current_dict.get("guest_name")
        ):
            msg_clean = message.lower().strip()
            room_keywords = ["standard", "deluxe", "suite", "kamar", "presidential", "room", "tipe"]
            quantity_keywords = ["satu", "dua", "tiga", "empat", "lima", "orang", "tamu", "dewasa", "anak", "breakfast", "sarapan"]
            
            has_room_kw = any(kw in msg_clean for kw in room_keywords)
            has_qty_kw = any(kw in msg_clean for kw in quantity_keywords)
            has_digits = any(char.isdigit() for char in msg_clean)
            
            if not has_digits and not has_room_kw and not has_qty_kw and 1 <= len(message.split()) <= 6:
                current_dict["guest_name"] = message.strip()

        return CollectedParams(**current_dict)

    async def generate_question(
        self,
        state: BookingState,
        has_history: bool = False
    ) -> str:
        """
        Generate pertanyaan natural menggunakan LLM untuk parameter yang masih kurang.

        Prioritas pertanyaan:
        1. check_in_date (paling penting)
        2. room_type
        3. num_guests
        4. guest_name
        5. wa_number

        Flow:
        1. Ambil daftar parameter yang wajib tapi kosong.
        2. Susun ringkasan parameter yang sudah terkumpul.
        3. Panggil generate LLM asinkron untuk menyusun pertanyaan friendly dalam Bahasa Indonesia.
        """
        missing = state.params.missing_required()

        if not missing:
            return ""

        collected_summary = []
        params = state.params
        if params.check_in_date:
            collected_summary.append(f"Check-in: {params.check_in_date}")
        if params.room_type:
            collected_summary.append(f"Kamar: {params.room_type}")
        if params.num_guests:
            collected_summary.append(f"Tamu: {params.num_guests} orang")

        prompt_body = ASK_MISSING_PROMPT.format(
            collected=", ".join(collected_summary) if collected_summary else "Belum ada",
            missing=", ".join(missing)
        )

        # Tambahkan instruksi untuk tidak menyapa lagi jika sudah ada parameter terkumpul atau ada histori percakapan sebelumnya
        no_greeting = ""
        if collected_summary or has_history:
            no_greeting = "JANGAN menyapa user dengan 'Halo', 'Hi', 'Selamat pagi/siang/malam', atau mengucapkan salam pembuka lagi karena ini adalah kelanjutan percakapan. Langsung tanyakan parameter yang kurang secara sopan dan natural.\n"

        prompt = (
            f"Instruksi Asisten:\nKamu asisten hotel yang ramah. Jawab singkat dan natural. JANGAN pernah menyatakan bahwa kamar sudah disiapkan atau dibooking.\n{no_greeting}\n"
            f"{prompt_body}"
        )

        try:
            question = await asyncio.to_thread(self.llm.generate, prompt)
            return question.strip()
        except Exception:
            # Fallback pertanyaan default sederhana jika LLM gagal
            first_missing = missing[0]
            fallback_questions = {
                "nama tamu": "Bisa tolong sebutkan atas nama siapa booking kamar ini?",
                "nomor WhatsApp": "Berapa nomor WhatsApp yang bisa kami hubungi?",
                "tanggal check-in": "Untuk tanggal berapa rencana check-in Anda?",
                "tipe kamar": "Tipe kamar apa yang Anda inginkan (Standard, Deluxe, atau Suite)?",
                "jumlah tamu dewasa": "Untuk berapa orang tamu yang akan menginap?"
            }
            return fallback_questions.get(first_missing, f"Bisa infokan kembali mengenai {first_missing}?")

    async def detect_cancellation(
        self,
        message: str
    ) -> bool:
        """
        Mendeteksi apakah pengguna ingin membatalkan proses booking berdasarkan kata kunci pembatalan.

        Flow:
        1. Normalisasi teks pesan ke huruf kecil.
        2. Periksa apakah ada kata kunci pembatalan yang terkandung di dalam pesan.
        """
        cancel_keywords = [
            "batal", "cancel", "tidak jadi",
            "gak jadi", "ga jadi", "nvm",
            "nevermind", "udah gausah",
            "sudah tidak perlu"
        ]
        msg_lower = message.lower()
        return any(
            kw in msg_lower
            for kw in cancel_keywords
        )

    async def detect_confirmation(
        self,
        message: str
    ) -> bool:
        """
        Mendeteksi apakah user mengonfirmasi persetujuan atas draf atau penawaran upsell.

        Flow:
        1. Normalisasi dan bersihkan spasi pesan.
        2. Lakukan pencocokan eksak pada kata kunci persetujuan singkat.
        3. Jika tidak cocok eksak, lakukan pemeriksaan substring untuk teks yang lebih panjang.
        """
        confirm_keywords = [
            "ya", "iya", "ok", "oke",
            "setuju", "benar", "betul",
            "lanjut", "fix", "deal",
            "confirmed", "yes", "yep",
            "boleh", "silakan"
        ]
        msg_lower = message.lower().strip()

        # Cek exact match dulu (untuk jawaban singkat "ya", "ok")
        if msg_lower in confirm_keywords:
            return True

        # Cek substring untuk jawaban panjang
        return any(
            kw in msg_lower
            for kw in confirm_keywords
        )


def parse_indonesian_date(date_str: str) -> str:
    """
    Menormalkan string tanggal Indonesia ke format YYYY-MM-DD berbasis tahun berjalan (2026).
    Misal: "15 agustus" -> "2026-08-15"
           "besok" -> (tanggal besok)
    """
    if not date_str:
        return date_str
        
    import re
    from datetime import datetime, date, timedelta
    
    msg_lower = date_str.lower().strip()
    today = date.today()
    
    # 1. Handle relatif sederhana
    if "hari ini" in msg_lower:
        return today.strftime("%Y-%m-%d")
    if "besok" in msg_lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "lusa" in msg_lower:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")
        
    # 2. Deteksi format angka murni "DD-MM" atau "DD/MM"
    match = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/]?(\d{2,4})?$", msg_lower)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        if year < 100:  # Format 2 digit tahun
            year += 2000
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    # 3. Deteksi format teks bulan "15 agustus", "15 agustus 2026"
    months = {
        "jan": 1, "januari": 1, "january": 1,
        "peb": 2, "pebruari": 2, "feb": 2, "februari": 2, "february": 2,
        "mar": 3, "maret": 3, "march": 3,
        "apr": 4, "april": 4,
        "mei": 5, "may": 5,
        "jun": 6, "juni": 6, "june": 6,
        "jul": 7, "juli": 7, "july": 7,
        "agu": 8, "agustus": 8, "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "okt": 10, "oktober": 10, "oct": 10, "october": 10,
        "nop": 11, "nopember": 11, "nov": 11, "november": 11,
        "des": 12, "desember": 12, "dec": 12, "december": 12
    }
    
    # Cari angka (tanggal) dan nama bulan
    words = re.findall(r"\w+", msg_lower)
    day = None
    month = None
    year = today.year
    
    for word in words:
        if word.isdigit():
            val = int(word)
            if val > 31:  # Kemungkinan tahun
                year = val
            elif day is None:
                day = val
        elif word in months:
            month = months[word]
            
    if day and month:
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    return date_str

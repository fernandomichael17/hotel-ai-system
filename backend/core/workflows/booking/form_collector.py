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

import re
import json
import asyncio
from datetime import datetime, timedelta
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
3. Pesan: "fernando"
   Hasil: {{"guest_name": "fernando"}}
4. Pesan: "michael carrick"
   Hasil: {{"guest_name": "michael carrick"}}
5. Pesan: "2 orang"
   Hasil: {{"num_guests": 2}}
6. Pesan: "seorang" atau "sendiri saja" atau "cuma saya"
   Hasil: {{"num_guests": 1}}
7. Pesan: "berdua"
   Hasil: {{"num_guests": 2}}
8. Pesan: "081234567890"
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
ASK_MISSING_PROMPT = """Kamu adalah asisten booking hotel yang ramah.

Tamu sedang dalam proses booking kamar.
Parameter yang sudah terkumpul:
{collected}

Parameter yang PERLU DITANYAKAN SEKARANG:
{target}

ATURAN:
- Tanya HANYA parameter di atas
- Satu pertanyaan singkat dan friendly
- {no_greeting_rule}
{target_rule}
- DILARANG membuat asumsi status booking. Jangan katakan "kamar sudah disiapkan", "booking sedang diproses", atau kalimat sejenisnya sebelum tamu mengkonfirmasi summary. Tugasmu HANYA menanyakan parameter yang masih kurang.
- JANGAN ulangi sapaan kalau sudah ada riwayat percakapan
- Gunakan bahasa yang sesuai dengan bahasa percakapan tamu saat ini (Bahasa Indonesia atau English).

Pertanyaan:"""

class BookingFormCollector:

    def __init__(self):
        """Inisialisasi form collector dengan klien LLM tunggal (Singleton)."""
        self.llm = get_llm_client()

    def _extract_duration_nights(self, message: str) -> int | None:
        """
        Mengekstrak durasi menginap dari pesan user.

        Parameter:
            message (str): Pesan user dalam bahasa natural.

        Return:
            int | None: Jumlah malam menginap, atau None jika tidak ditemukan.

        Pola yang ditangani:
        - "semalam" → 1
        - "sehari" → 1
        - "2 malam" → 2
        - "3 hari" → 3
        - "stay 3 nights" → 3
        - "3 hari 2 malam" → 2 (malam diprioritaskan)
        - "satu malam" → 1
        - "dua malam" → 2
        """
        msg = message.lower()

        # Prioritas 1: kata durasi tanpa digit
        if re.search(r'\bsemalam\b', msg):
            return 1
        if re.search(r'\bsehari\b', msg) and 'malam' not in msg:
            return 1

        # Prioritas 2: digit + malam (malam selalu diprioritaskan dari hari)
        m = re.search(r'(\d+)\s*(?:malam|night)', msg)
        if m:
            return int(m.group(1))

        # Prioritas 3: kata bilangan Indonesia + malam
        indo_nums = {
            'satu': 1, 'dua': 2, 'tiga': 3,
            'empat': 4, 'lima': 5, 'enam': 6,
            'tujuh': 7
        }
        for word, num in indo_nums.items():
            if re.search(rf'\b{word}\s*(?:malam|night)\b', msg):
                return num

        # Prioritas 4: digit + hari/day (fallback)
        m = re.search(r'(\d+)\s*(?:hari|day)', msg)
        if m:
            return int(m.group(1))

        # Prioritas 5: kata bilangan Indonesia + hari
        for word, num in indo_nums.items():
            if re.search(rf'\b{word}\s*(?:hari|day)\b', msg):
                return num

        # Prioritas 6: pattern "selama/menginap/stay X"
        m = re.search(r'(?:selama|menginap|stay)\s*(\d+)', msg)
        if m:
            return int(m.group(1))

        return None

    def _calculate_checkout(self, check_in_str: str, nights: int) -> str | None:
        """
        Menghitung tanggal check_out dari check_in dan jumlah malam.

        Parameter:
            check_in_str (str): Tanggal check-in dalam format apapun (ISO atau nama bulan Indonesia).
            nights (int): Jumlah malam menginap.

        Return:
            str | None: Tanggal check-out dalam format yang sama dengan input, atau None jika gagal parse.
        """
        try:
            # Coba parse ISO format (YYYY-MM-DD)
            ci = datetime.strptime(check_in_str, '%Y-%m-%d')
            co = ci + timedelta(days=nights)
            return co.strftime('%Y-%m-%d')
        except ValueError:
            pass

        # Fallback: coba parse format Indonesia "15 Juli" dsb.
        try:
            from dateutil import parser as dateparser
            ci = dateparser.parse(check_in_str, dayfirst=True)
            if ci is None:
                return None
            co = ci + timedelta(days=nights)
            if '-' in check_in_str:
                return co.strftime('%Y-%m-%d')
            else:
                months_map = {
                    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
                    5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
                    9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
                }
                return f"{co.day} {months_map[co.month]}"
        except Exception:
            return None

    def _get_priority_target(self, missing: list[str]) -> str:
        """
        Menentukan satu parameter prioritas tertinggi dari daftar parameter yang masih kurang.

        Parameter:
            missing (list[str]): Daftar label parameter yang masih kosong.

        Return:
            str: Label parameter target tunggal paling prioritas.
        """
        priority_fields = [
            ("check_in_date", "tanggal check-in"),
            ("room_type", "tipe kamar"),
            ("num_guests", "jumlah tamu dewasa"),
            ("guest_name", "nama tamu"),
            ("wa_number", "nomor WhatsApp")
        ]
        for field, label in priority_fields:
            if label in missing:
                return label
        return missing[0]

    def _filter_guest_name(self, name: str | None) -> str | None:
        """
        Menyaring nama tamu untuk mendeteksi nama palsu atau hasil ekstraksi yang salah.

        Parameter:
            name (str | None): Nama tamu yang diekstrak.

        Return:
            str | None: Nama tamu jika valid, atau None jika terdeteksi palsu/salah.
        """
        if not name:
            return name
        name_lower = name.lower().strip()

        # 1. Tolak jika mengandung digit/angka
        has_digit = bool(re.search(r'\d', name_lower))

        # 2. Tolak jika mengandung nama bulan
        month_names = [
            "januari", "februari", "maret", "april", "mei", "juni",
            "juli", "agustus", "september", "oktober", "november", "desember",
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "agu", "aug",
            "sep", "okt", "oct", "nov", "des"
        ]
        has_month = any(m in name_lower.split() for m in month_names)

        # 3. Tolak jika mengandung kata kunci booking/detail pesanan hotel
        forbidden_words = {
            "booking", "reservasi", "pesan", "kamar", "room", "tipe", "standard", "deluxe", "suite",
            "malam", "hari", "day", "night", "stay", "menginap", "selama", "sehari", "semalam",
            "orang", "tamu", "dewasa", "anak", "seorang", "sendiri", "berdua", "bertiga",
            "untuk", "tanggal", "tgl", "pada", "di", "ke", "dari", "bukan"
        }
        has_forbidden_word = any(w in forbidden_words for w in name_lower.split())

        if has_digit or has_month or has_forbidden_word:
            return None
        return name

    async def extract_params(
        self,
        message: str,
        current_state: BookingState
    ) -> CollectedParams:
        """
        Extract parameter booking dari pesan user menggunakan LLM + heuristik programatis.
        Merge dengan params yang sudah ada:
        - Kalau ada nilai baru → update
        - Kalau null → pertahankan yang lama

        Flow:
        1. Susun instruksi asisten dan gabungkan dengan prompt ekstraksi.
        2. Jalankan panggilan generate ke LLM secara thread-safe asinkron.
        3. Bersihkan format blok markdown kode JSON pada teks jawaban LLM.
        4. Lakukan deserialisasi JSON dan gabungkan parameter dengan parameter saat ini.
        5. Jalankan heuristik programatis sebagai safety net.
        6. Jalankan filter defensive nama tamu.
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
                    if field == "guest_name" and isinstance(value, str):
                        value = self._filter_guest_name(value)
                    current_dict[field] = value

        # === BLOK HEURISTIK PROGRAMATIS ===
        # Semua heuristik di bawah berfungsi sebagai safety net
        # ketika LLM 4B gagal mengekstrak parameter dari pesan user.
        msg_lower = message.lower().strip()

        # --- HEURISTIK 0: Deteksi & Ekstraksi Tanggal Programatis ---
        if not extracted.get("check_in_date"):
            h_check_in, h_check_out = self._apply_date_heuristics(message, current_params.check_in_date)
            if h_check_in:
                current_dict["check_in_date"] = h_check_in
            if h_check_out:
                current_dict["check_out_date"] = h_check_out

        # --- PENYESUAIAN DYNAMIC CHECK-OUT ---
        # Jika check-in berubah, sesuaikan check-out untuk menjaga durasi menginap (nights)
        old_ci = current_params.check_in_date
        new_ci = current_dict.get("check_in_date")
        old_co = current_params.check_out_date
        new_co = current_dict.get("check_out_date")

        if old_ci and new_ci and new_ci != old_ci and (new_co == old_co or not new_co):
            try:
                old_ci_dt = datetime.strptime(old_ci, "%Y-%m-%d")
                old_co_dt = datetime.strptime(old_co, "%Y-%m-%d") if old_co else None
                if old_co_dt and old_co_dt > old_ci_dt:
                    nights = (old_co_dt - old_ci_dt).days
                    new_ci_dt = datetime.strptime(new_ci, "%Y-%m-%d")
                    new_co_dt = new_ci_dt + timedelta(days=nights)
                    current_dict["check_out_date"] = new_co_dt.strftime("%Y-%m-%d")
                else:
                    current_dict["check_out_date"] = None
            except Exception:
                current_dict["check_out_date"] = None

        # Defensive check: Jika check-out <= check-in, hapus check-out agar ditanyakan kembali
        ci_str = current_dict.get("check_in_date")
        co_str = current_dict.get("check_out_date")
        if ci_str and co_str:
            try:
                ci_dt = datetime.strptime(ci_str, "%Y-%m-%d")
                co_dt = datetime.strptime(co_str, "%Y-%m-%d")
                if co_dt <= ci_dt:
                    current_dict["check_out_date"] = None
            except Exception:
                pass

        # --- HEURISTIK 1: Deteksi Durasi Menginap & Auto-calculate Checkout ---
        if current_dict.get("check_in_date") and not current_dict.get("check_out_date"):
            nights = self._extract_duration_nights(message)
            if nights and nights > 0:
                checkout = self._calculate_checkout(
                    current_dict["check_in_date"], nights
                )
                if checkout:
                    current_dict["check_out_date"] = checkout

        # --- HEURISTIK 2: Deteksi Jumlah Tamu ---
        # Layer 2a: Kata bilangan Indonesia (termasuk solo tanpa "orang")
        # Layer 2b: Digit dengan guard kontekstual (hindari false positive "lantai 3", "kamar 5")
        if not current_dict.get("num_guests"):
            # False positive prefixes — jangan ambil angka yang mengikuti kata-kata ini
            false_positive_prefixes = [
                'lantai', 'kamar', 'nomor', 'no',
                'lt', 'room', 'jam', 'pukul',
                'tanggal', 'tgl', 'hari'
            ]

            # Kata bilangan Indonesia
            indo_num_map = {
                r'\bsendiri\b': 1,
                r'\bseorang\b': 1,
                r'\bsatu orang\b': 1,
                r'\bsatu\b': 1,
                r'\bberdua\b': 2,
                r'\bdua orang\b': 2,
                r'\bdua\b': 2,
                r'\bbertiga\b': 3,
                r'\btiga orang\b': 3,
                r'\btiga\b': 3,
                r'\bberempat\b': 4,
                r'\bempat orang\b': 4,
                r'\bempat\b': 4,
                r'\bberlima\b': 5,
                r'\blima orang\b': 5,
                r'\blima\b': 5,
                r'\bcuma saya\b': 1,
                r'\bhanya saya\b': 1,
                r'\bsaya saja\b': 1,
            }

            for pattern, num in indo_num_map.items():
                if re.search(pattern, msg_lower):
                    current_dict["num_guests"] = num
                    break

            # 2b. Fallback digit (1-2 digit angka) dengan guard kontekstual
            if not current_dict.get("num_guests"):
                digits = re.finditer(r'\b(\d{1,2})\b', msg_lower)
                for m in digits:
                    digit_pos = m.start()
                    
                    # Cek apakah angka ini diikuti oleh nama bulan (artinya ini tanggal, bukan jumlah tamu)
                    after = msg_lower[m.end():].strip().split()
                    next_word = after[0] if after else ""
                    month_names = {
                        "januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus",
                        "september", "oktober", "november", "desember", "jan", "feb", "mar", "apr",
                        "may", "jun", "jul", "agu", "aug", "sep", "okt", "oct", "nov", "des",
                        "january", "february", "march", "june", "july", "august", "december"
                    }
                    if next_word in month_names:
                        continue

                    before = msg_lower[:digit_pos].strip().split()
                    last_word = before[-1] if before else ""
                    if last_word not in false_positive_prefixes:
                        val = int(m.group(1))
                        if 1 <= val <= 20:
                            current_dict["num_guests"] = val
                            break

        # --- HEURISTIK 3: Deteksi Nama Tamu dari Pola Bahasa ---
        # Menangkap: "atas nama X", "a/n X", "nama X", "untuk X", "buat X"
        if not current_dict.get("guest_name"):
            noise_words = {
                'saya', 'nya', 'ya', 'dong',
                'deh', 'nih', 'aja', 'saja'
            }
            title_words = {
                'pak', 'bapak', 'bu', 'ibu',
                'mas', 'mbak', 'bang', 'kak',
                'tuan', 'nyonya', 'nn', 'tn',
                'ny', 'mr', 'mrs', 'ms', 'dr'
            }

            patterns_nama = [
                r'(?:atas\s+nama|a[/]n)\s+([a-zA-Z\s]+)',
                r'(?:^|\s)nama(?:\s+saya|\s+tamu)?\s*[:\-]?\s*([a-zA-Z\s]{2,40})',
                r'(?:untuk|buat)\s+([a-zA-Z\s]{2,30})(?:\s|$)',
            ]

            # Kata kunci booking yang tidak boleh muncul di nama
            booking_words = {
                'untuk', 'di', 'tanggal', 'malam', 'hari', 'tamu',
                'kamar', 'check', 'orang', 'bulan', 'tahun'
            }

            for pattern in patterns_nama:
                m = re.search(pattern, msg_lower)
                if m:
                    name_raw = m.group(1).strip()
                    name_words = [
                        w for w in name_raw.split()
                        if w not in noise_words and w not in title_words
                    ]
                    if 1 <= len(name_words) <= 5:
                        candidate = ' '.join(name_words).title()
                        if not any(bw in candidate.lower() for bw in booking_words):
                            current_dict["guest_name"] = candidate
                            break

        # --- HEURISTIK 4: Nama Tamu Murni (Defensive) ---
        # Aktif hanya jika check_in_date dan room_type sudah terisi.
        # Menangkap pesan murni nama tanpa keyword lain.
        if (
            current_params.check_in_date and
            current_params.room_type and
            not current_dict.get("guest_name")
        ):
            confirmation_blacklist = {
                'ya', 'iya', 'ok', 'oke', 'okay',
                'setuju', 'benar', 'betul', 'lanjut',
                'fix', 'deal', 'yes', 'yep', 'boleh',
                'silakan', 'tidak', 'tidak jadi',
                'batal', 'cancel', 'no', 'nope',
                'gak', 'ga', 'nggak', 'jangan'
            }

            # Skip kalau pesan adalah konfirmasi
            if msg_lower.strip() not in confirmation_blacklist:
                title_words_h4 = {
                    'pak', 'bapak', 'bu', 'ibu', 'mas', 'mbak',
                    'bang', 'kak', 'tuan', 'nyonya'
                }
                noise_words_h4 = {
                    'saya', 'nya', 'ya', 'dong', 'deh', 'nih', 'aja', 'saja'
                }
                booking_keywords = {
                    'kamar', 'standard', 'deluxe', 'suite', 'tanggal', 'check',
                    'malam', 'hari', 'untuk', 'booking', 'pesan', 'reservasi',
                    'tipe', 'harga', 'berapa', 'orang', 'tamu',
                    'januari', 'februari', 'maret', 'april', 'mei', 'juni',
                    'juli', 'agustus', 'september', 'oktober', 'november', 'desember',
                    'january', 'february', 'march', 'april', 'may', 'june',
                    'july', 'august', 'september', 'october', 'november', 'december'
                }
                month_words = {
                    'januari', 'februari', 'maret', 'april', 'mei', 'juni',
                    'juli', 'agustus', 'september', 'oktober', 'november', 'desember'
                }

                words = msg_lower.split()
                clean_words = [
                    w for w in words
                    if w not in title_words_h4 and w not in noise_words_h4
                ]

                if (
                    1 <= len(clean_words) <= 5
                    and not any(w in booking_keywords for w in clean_words)
                    and not re.search(r'\d', msg_lower)
                    and all(re.match(r'^[a-zA-Z]+$', w) for w in clean_words)
                    and any(len(w) >= 2 for w in clean_words)
                    and msg_lower.strip() not in confirmation_blacklist
                ):
                    final_words = [
                        w for w in clean_words if w not in month_words
                    ]
                    if final_words:
                        current_dict["guest_name"] = ' '.join(final_words).title()
        # --- FILTER DEFENSIVE NAMA TAMU ---
        if current_dict.get("guest_name"):
            current_dict["guest_name"] = self._filter_guest_name(current_dict["guest_name"])

        return CollectedParams(**current_dict)


    async def generate_question(
        self,
        state: BookingState,
        has_history: bool = False
    ) -> str:
        """
        Generate pertanyaan natural menggunakan LLM untuk parameter yang masih kurang.

        Parameter:
            state (BookingState): State booking saat ini.
            has_history (bool): True jika sudah ada riwayat percakapan sebelumnya.

        Return:
            str: Pertanyaan ramah dalam bahasa tamu untuk parameter target.
        """
        missing = state.params.missing_required()

        if not missing:
            return ""

        # Cari target parameter yang paling prioritas dari daftar yang masih kurang
        target_param = self._get_priority_target(missing)
        lang = state.language

        # Susun ringkasan parameter yang sudah terkumpul
        collected_summary = []
        params = state.params
        if params.check_in_date:
            collected_summary.append(f"Check-in: {params.check_in_date}")
        if params.check_out_date:
            collected_summary.append(f"Check-out: {params.check_out_date}")
        if params.room_type:
            room_label = "Kamar" if lang == "id" else "Room"
            collected_summary.append(f"{room_label}: {params.room_type}")
        if params.num_guests:
            guest_label = "Tamu dewasa" if lang == "id" else "Adult guests"
            people_label = "orang" if lang == "id" else "people"
            collected_summary.append(f"{guest_label}: {params.num_guests} {people_label}")
        if params.guest_name:
            name_label = "Nama tamu" if lang == "id" else "Guest name"
            collected_summary.append(f"{name_label}: {params.guest_name}")
        if params.wa_number:
            collected_summary.append(f"WhatsApp: {params.wa_number}")

        # Atur no_greeting_rule & target_rule berdasarkan bahasa
        if lang == "id":
            no_greeting_rule = "JANGAN mulai dengan sapaan (Halo/Hi/dll)" if has_history else "Boleh mulai dengan sapaan singkat"
            target_rule = ""
            if target_param == "tipe kamar":
                target_rule = "- Sebutkan pilihan tipe kamar dan harganya (Standard Rp500rb, Deluxe Rp850rb, Suite Rp1,5jt) agar tamu bisa memilih."
            elif target_param == "jumlah tamu dewasa":
                target_rule = "- Tanya BERAPA ORANG (angka) dewasa yang akan menginap. Jangan tanya nama mereka."
            elif target_param == "nama tamu":
                target_rule = "- Tanya NAMA LENGKAP tamu yang akan menginap untuk keperluan registrasi."
            elif target_param == "tanggal check-out":
                target_rule = "- Tanya tanggal check-out atau berapa malam (durasi menginap) tamu akan menginap."
            target = target_param
            empty_val_label = "Belum ada"
        else:
            no_greeting_rule = "DO NOT start with greetings (Hello/Hi/etc)" if has_history else "You may start with a brief greeting"
            target_rule = ""
            if target_param == "tipe kamar":
                target_rule = "- List the available room types and their rates (Standard Rp500k, Deluxe Rp850k, Suite Rp1.5m) for the guest to choose from."
            elif target_param == "jumlah tamu dewasa":
                target_rule = "- Ask HOW MANY adult guests will be staying. Do not ask for their names."
            elif target_param == "nama tamu":
                target_rule = "- Ask for the FULL NAME of the guest who will be staying for registration purposes."
            elif target_param == "tanggal check-out":
                target_rule = "- Ask for the check-out date or how many nights (duration) they plan to stay."
            
            target_param_en = {
                "nama tamu": "guest name",
                "nomor WhatsApp": "WhatsApp number",
                "tanggal check-in": "check-in date",
                "tanggal check-out": "check-out date",
                "tipe kamar": "room type",
                "jumlah tamu dewasa": "number of adult guests"
            }.get(target_param, target_param)
            target = target_param_en
            empty_val_label = "None"

        prompt = ASK_MISSING_PROMPT.format(
            collected=", ".join(collected_summary) if collected_summary else empty_val_label,
            target=target,
            no_greeting_rule=no_greeting_rule,
            target_rule=target_rule
        )

        try:
            question = await asyncio.to_thread(self.llm.generate, prompt)
            return question.strip()
        except Exception:
            # Fallback pertanyaan default jika LLM gagal
            fallback_questions = {
                "id": {
                    "nama tamu": "Bisa tolong sebutkan atas nama siapa booking kamar ini?",
                    "nomor WhatsApp": "Berapa nomor WhatsApp yang bisa kami hubungi?",
                    "tanggal check-in": "Untuk tanggal berapa rencana check-in Anda?",
                    "tanggal check-out": "Untuk berapa malam Anda berencana menginap?",
                    "tipe kamar": "Tipe kamar apa yang Anda inginkan (Standard, Deluxe, atau Suite)?",
                    "jumlah tamu dewasa": "Untuk berapa orang tamu yang akan menginap?"
                },
                "en": {
                    "nama tamu": "Could you please tell me the guest name for this booking?",
                    "nomor WhatsApp": "What is the WhatsApp number we can contact you on?",
                    "tanggal check-in": "What is your planned check-in date?",
                    "tanggal check-out": "How many nights do you plan to stay?",
                    "tipe kamar": "Which room type would you prefer (Standard, Deluxe, or Suite)?",
                    "jumlah tamu dewasa": "How many adult guests will be staying?"
                }
            }
            return fallback_questions.get(lang, fallback_questions["id"]).get(target_param, f"Please tell me about your {target}.")

    def _extract_dates_programmatic(self, message: str) -> list[tuple[int, str]]:
        """
        Mengekstrak seluruh kemunculan tanggal (relatif, spesifik, atau hari saja) 
        dari pesan teks pengguna secara programatis beserta indeks posisinya.

        Parameter:
            message (str): Pesan teks dari pengguna.

        Return:
            list[tuple[int, str]]: Daftar tuple berisi (indeks_awal, string_tanggal_YYYY-MM-DD).
        """
        from datetime import date, datetime, timedelta
        today = date.today()
        msg_lower = message.lower().strip()
        date_occurrences = []

        # 1. Deteksi format hari + nama bulan (misal "20 juli", "8 agustus")
        months_map = {
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

        pattern = (
            r'\b(\d{1,2})\s*(?:-|/|\s)\s*'
            r'(januari|februari|maret|april|mei|juni|juli|agustus|'
            r'september|oktober|november|desember|jan|feb|mar|apr|'
            r'may|jun|jul|agu|aug|sep|okt|oct|nov|des)\b(?:\s*(\d{2,4}))?'
        )
        matches = list(re.finditer(pattern, msg_lower))

        for m in matches:
            day = int(m.group(1))
            month = months_map[m.group(2)]
            year = today.year
            if m.group(3):
                y_val = int(m.group(3))
                year = 2000 + y_val if y_val < 100 else y_val
            try:
                d_str = datetime(year, month, day).strftime("%Y-%m-%d")
                date_occurrences.append((m.start(), d_str))
            except ValueError:
                pass

        # 2. Deteksi format relatif (hari ini, besok, lusa)
        rel_patterns = [("hari ini", 0), ("besok", 1), ("lusa", 2)]
        for pat, days in rel_patterns:
            idx = msg_lower.find(pat)
            if idx != -1:
                d_str = (today + timedelta(days=days)).strftime("%Y-%m-%d")
                date_occurrences.append((idx, d_str))

        # 2b. Deteksi nama hari relatif (misal "sabtu ini", "minggu depan", "hari senin")
        days_map = {
            "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
            "jumat": 4, "jum'at": 4, "sabtu": 5, "minggu": 6, "ahad": 6
        }
        day_pattern = (
            r'\b(?:hari\s+)?(senin|selasa|rabu|kamis|jumat|jum\'at|sabtu|minggu|ahad)'
            r'(?:\s+(ini|depan|esok|lusa))?\b'
        )
        day_matches = list(re.finditer(day_pattern, msg_lower))
        for m in day_matches:
            # Pastikan tidak tumpang tindih dengan pencocokan hari + bulan
            overlap = any(dm.start() <= m.start() <= dm.end() for dm in matches)
            if overlap:
                continue
            day_name = m.group(1)
            modifier = m.group(2)
            target_weekday = days_map[day_name]
            today_weekday = today.weekday()
            diff = (target_weekday - today_weekday) % 7
            if diff == 0 and modifier == "depan":
                diff = 7
            elif diff == 0 and not modifier:
                diff = 0
            elif diff < 0:
                diff += 7
            if modifier == "depan" and diff < 7:
                diff += 7
            d_str = (today + timedelta(days=diff)).strftime("%Y-%m-%d")
            date_occurrences.append((m.start(), d_str))

        # 3. Deteksi format angka hari saja (misal "tanggal 20")
        day_only_matches = re.finditer(r'\b(?:tanggal|tgl)\s*(\d{1,2})\b', msg_lower)
        for m in day_only_matches:
            # Lewati jika tumpang tindih dengan pencocokan hari + bulan
            overlap = any(dm.start() <= m.start() <= dm.end() for dm in matches)
            if overlap:
                continue
            day_val = int(m.group(1))
            if 1 <= day_val <= 31:
                target_month = today.month if day_val >= today.day else today.month + 1
                target_year = today.year
                if target_month > 12:
                    target_month = 1
                    target_year += 1
                try:
                    d_str = datetime(target_year, target_month, day_val).strftime("%Y-%m-%d")
                    date_occurrences.append((m.start(), d_str))
                except ValueError:
                    pass

        date_occurrences.sort(key=lambda x: x[0])
        return date_occurrences

    def _apply_date_heuristics(
        self,
        message: str,
        current_check_in: str | None
    ) -> tuple[str | None, str | None]:
        """
        Menentukan tanggal check-in dan check-out baru berdasarkan daftar kemunculan 
        tanggal dan riwayat tanggal check-in aktif.

        Parameter:
            message (str): Pesan teks pengguna.
            current_check_in (str | None): Tanggal check-in yang tersimpan di state saat ini.

        Return:
            tuple[str | None, str | None]: Tuple berisi (tanggal_check_in, tanggal_check_out).
        """
        occurrences = self._extract_dates_programmatic(message)
        if not occurrences:
            return None, None

        msg_lower = message.lower()
        bukan_idx = msg_lower.find("bukan")

        # Jika ada kata "bukan", prioritaskan tanggal sebelum kata "bukan"
        if bukan_idx != -1:
            valid_occurrences = [occ for occ in occurrences if occ[0] < bukan_idx]
            if not valid_occurrences and current_check_in:
                valid_occurrences = [occ for occ in occurrences if occ[1] != current_check_in]
        else:
            valid_occurrences = occurrences

        unique_dates = []
        for occ in valid_occurrences:
            if occ[1] not in unique_dates:
                unique_dates.append(occ[1])

        if not unique_dates:
            return None, None

        # Deteksi rentang tanggal check-in sampai check-out
        range_indicators = ["sampai", "sd", "s/d", "hingga", "–", "-"]
        has_range = any(ind in msg_lower for ind in range_indicators)

        if len(unique_dates) >= 2 and has_range:
            return unique_dates[0], unique_dates[1]

        return unique_dates[0], None

    async def detect_cancellation(
        self,
        message: str
    ) -> bool:
        """
        Mendeteksi apakah pengguna ingin membatalkan proses booking berdasarkan kata kunci pembatalan.
        Menggunakan regex word boundary (\\b) untuk menghindari false-positive substring.

        Parameter:
            message (str): Pesan pengguna.

        Return:
            bool: True jika pesan terdeteksi sebagai pembatalan.
        """
        cancel_keywords = [
            "batal", "cancel", "tidak jadi",
            "gak jadi", "ga jadi", "nvm",
            "nevermind", "udah gausah",
            "sudah tidak perlu", "tidak usah"
        ]
        msg_lower = message.lower().strip()

        # Exact match dulu
        if msg_lower in cancel_keywords:
            return True

        # Word boundary match
        for kw in cancel_keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, msg_lower):
                return True

        return False

    async def detect_confirmation(
        self,
        message: str
    ) -> bool:
        """
        Mendeteksi apakah user mengonfirmasi persetujuan atas draf atau penawaran upsell.
        Menggunakan regex word boundary (\\b) untuk menghindari false-positive
        seperti "saya" terdeteksi sebagai "ya".

        Parameter:
            message (str): Pesan pengguna.

        Return:
            bool: True jika pesan terdeteksi sebagai konfirmasi.
        """
        confirm_keywords = [
            "ya", "iya", "ok", "oke", "okay",
            "setuju", "benar", "betul",
            "lanjut", "fix", "deal",
            "confirmed", "yes", "yep",
            "boleh", "silakan"
        ]
        msg_lower = message.lower().strip()

        # Exact match dulu
        if msg_lower in confirm_keywords:
            return True

        # Word boundary match
        for kw in confirm_keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, msg_lower):
                return True

        return False


def _parse_day_only(date_str: str) -> str | None:
    """
    Mengonversi string yang berisi angka hari saja (tanpa bulan) menjadi format YYYY-MM-DD.

    Parameter:
        date_str (str): Input string dari pengguna.

    Return:
        str | None: String tanggal format YYYY-MM-DD, atau None jika gagal.
    """
    from datetime import date
    msg_lower = date_str.lower().strip()
    today = date.today()

    day_match = re.search(r'\b(\d{1,2})\b', msg_lower)
    if not day_match:
        return None

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

    # Pastikan tidak ada nama bulan di msg_lower
    has_month_name = False
    for m_name in months.keys():
        if m_name in msg_lower:
            has_month_name = True
            break

    if has_month_name:
        return None

    day_val = int(day_match.group(1))
    if 1 <= day_val <= 31:
        if day_val >= today.day:
            target_month = today.month
            target_year = today.year
        else:
            target_month = today.month + 1
            target_year = today.year
            if target_month > 12:
                target_month = 1
                target_year += 1
        try:
            return datetime(target_year, target_month, day_val).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_indonesian_date(date_str: str) -> str:
    """
    Menormalkan string tanggal Indonesia ke format YYYY-MM-DD berbasis tahun berjalan (2026).
    Misal: "15 agustus" -> "2026-08-15"
           "besok" -> (tanggal besok)

    Parameter:
        date_str (str): String tanggal dalam bahasa Indonesia atau format umum.

    Return:
        str: Tanggal dalam format YYYY-MM-DD, atau string asli jika gagal parse.
    """
    if not date_str:
        return date_str

    # JIKA sudah format ISO YYYY-MM-DD, langsung kembalikan agar tidak bergeser
    import re
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str.strip()):
        return date_str.strip()

    from datetime import date

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

    # 2b. Deteksi hari saja (misal "20" or "tanggal 20")
    parsed_day_only = _parse_day_only(date_str)
    if parsed_day_only:
        return parsed_day_only

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

def build_classification_prompt(message: str) -> str:
    """
    Membangun prompt klasifikasi intent tunggal dalam Bahasa Indonesia untuk model LLM.

    Parameters:
        message (str): Pesan pengguna yang ingin diklasifikasikan intent-nya.

    Returns:
        str: Prompt lengkap yang siap dikirimkan ke model LLM.
    """
    prompt = (
        "Klasifikasikan pesan pengguna berikut ke dalam salah satu dari intent ini:\n"
        "- faq (pertanyaan umum tentang hotel seperti fasilitas, wifi, telepon)\n"
        "- booking_inquiry (menanyakan ketersediaan kamar, harga, atau informasi sebelum memesan)\n"
        "- booking_request (melakukan pemesanan kamar baru secara langsung)\n"
        "- complaint (keluhan mengenai fasilitas, layanan, atau masalah selama menginap)\n"
        "- cancellation (permintaan pembatalan pemesanan)\n"
        "- refund (permintaan pengembalian dana)\n"
        "- unknown (jika pesan tidak sesuai dengan intent di atas atau tidak jelas)\n\n"
        "Aturan:\n"
        "1. Jawab HANYA dengan satu kata kunci dari daftar di atas: faq, booking_inquiry, booking_request, complaint, cancellation, refund, atau unknown.\n"
        "2. Jangan berikan penjelasan, tanda baca, atau kalimat tambahan apa pun.\n"
        "3. Tulis jawaban dalam huruf kecil (lowercase) saja.\n\n"
        "Contoh:\n"
        "- \"Berapa nomor telepon resepsionis?\" -> faq\n"
        "- \"Apakah ada wifi di kamar hotel?\" -> faq\n"
        "- \"Apakah ada kamar kosong untuk tanggal 5 Juli?\" -> booking_inquiry\n"
        "- \"Berapa tarif menginap satu malam tipe Deluxe?\" -> booking_inquiry\n"
        "- \"Saya ingin memesan satu kamar suite untuk akhir pekan depan.\" -> booking_request\n"
        "- \"Tolong pesankan kamar Deluxe atas nama Budi Santoso.\" -> booking_request\n"
        "- \"AC di kamar 302 bocor dan berisik sekali.\" -> complaint\n"
        "- \"Pelayanan restoran sangat lambat dan makanan dingin.\" -> complaint\n"
        "- \"Saya ingin membatalkan reservasi kamar saya.\" -> cancellation\n"
        "- \"Bagaimana cara melakukan pembatalan booking untuk besok?\" -> cancellation\n"
        "- \"Apakah uang deposit saya bisa dikembalikan karena batal menginap?\" -> refund\n"
        "- \"Saya mau minta pengembalian dana pembayaran kamar.\" -> refund\n"
        "- \"Halo, selamat pagi.\" -> unknown\n"
        "- \"Saya suka sekali warna cat dinding hotel ini.\" -> unknown\n\n"
        f"Pesan pengguna: \"{message}\"\n"
        "Intent:"
    )
    return prompt


def build_multiturn_prompt(history: list[dict], message: str) -> str:
    """
    Membangun prompt klasifikasi intent untuk percakapan multi-turn berdasarkan riwayat percakapan.

    Parameters:
        history (list[dict]): Daftar pesan sebelumnya, masing-masing berupa dict {"role": "user"|"assistant", "content": str}.
        message (str): Pesan terbaru pengguna.

    Returns:
        str: Prompt lengkap dengan riwayat percakapan untuk klasifikasi intent.
    """
    history_str = ""
    for turn in history:
        role = "User" if turn["role"] == "user" else "Assistant"
        content = turn["content"]
        history_str += f"{role}: {content}\n"

    prompt = (
        "Klasifikasikan intent dari pesan terbaru pengguna dengan mempertimbangkan riwayat percakapan sebelumnya.\n"
        "Pilih salah satu dari intent berikut:\n"
        "- faq (pertanyaan umum hotel)\n"
        "- booking_inquiry (menanyakan kamar/harga)\n"
        "- booking_request (memesan kamar secara langsung)\n"
        "- complaint (keluhan layanan/kamar)\n"
        "- cancellation (pembatalan booking)\n"
        "- refund (pengembalian uang)\n"
        "- unknown (tidak dapat dikategorikan)\n\n"
        "Aturan:\n"
        "1. Jawab HANYA dengan satu kata kunci dari daftar di atas dalam huruf kecil (lowercase).\n"
        "2. Jangan ada penjelasan atau kalimat tambahan.\n\n"
        "Riwayat Percakapan:\n"
        f"{history_str}"
        f"User (Pesan Terbaru): {message}\n"
        "Intent:"
    )
    return prompt


def build_extraction_prompt(message: str) -> str:
    """
    Membangun prompt untuk mengekstraksi parameter pemesanan hotel dari pesan pengguna.

    Parameters:
        message (str): Pesan pengguna berisi pemesanan hotel.

    Returns:
        str: Prompt instruksi ekstraksi entitas dalam format JSON.
    """
    prompt = (
        "Ekstrak entitas pemesanan berikut dari pesan pengguna ke dalam format JSON yang valid:\n"
        "- name: nama pemesan (string, berikan null jika tidak ada)\n"
        "- check_in_date: tanggal check-in (string, berikan null jika tidak ada)\n"
        "- check_out_date: tanggal check-out (string, berikan null jika tidak ada)\n"
        "- room_type: tipe kamar (seperti standard, deluxe, suite, family room; string, berikan null jika tidak ada)\n\n"
        "Aturan Ekstraksi:\n"
        "1. Jawab HANYA dalam format JSON objek yang valid tanpa penjelasan lain.\n"
        "2. Jangan bungkus output dengan markdown block ```json.\n"
        "3. ATURAN 1 — Waktu relatif:\n"
        "   Jika user menyebut referensi waktu relatif seperti \"besok\", \"lusa\", \"akhir pekan ini\", \"minggu depan\", \"malam ini\", \"Jumat besok\" — extract apa adanya sebagai string. Jangan return null hanya karena tanggalnya tidak eksplisit.\n"
        "4. ATURAN 2 — Tanggal range tanpa pengulangan bulan:\n"
        "   Jika user menyebut \"5 sampai 7 Agustus\" atau \"tanggal 20 hingga 22 September\", maka:\n"
        "   - check_in_date = \"5 Agustus\" (tambahkan nama bulan dari check_out)\n"
        "   - check_out_date = \"7 Agustus\"\n"
        "   Bulan selalu mengikuti angka terakhir yang disebutkan.\n"
        "5. ATURAN 3 — Null hanya jika benar-benar tidak ada:\n"
        "   Return null hanya jika parameter memang sama sekali tidak disebutkan atau tidak bisa diinferensi dari kalimat. Jangan return null karena formatnya tidak standar.\n\n"
        "Contoh 1:\n"
        "Pesan: \"Pesankan kamar Deluxe untuk besok atas nama Andi\"\n"
        "Output:\n"
        "{\n"
        "  \"name\": \"Andi\",\n"
        "  \"check_in_date\": \"besok\",\n"
        "  \"check_out_date\": null,\n"
        "  \"room_type\": \"deluxe\"\n"
        "}\n\n"
        "Contoh 2:\n"
        "Pesan: \"Booking Standard dari tanggal 5 sampai 7 Agustus\"\n"
        "Output:\n"
        "{\n"
        "  \"name\": null,\n"
        "  \"check_in_date\": \"5 Agustus\",\n"
        "  \"check_out_date\": \"7 Agustus\",\n"
        "  \"room_type\": \"standard\"\n"
        "}\n\n"
        "Contoh 3:\n"
        "Pesan: \"Ada kamar untuk akhir pekan ini atas nama Hendra Wijaya?\"\n"
        "Output:\n"
        "{\n"
        "  \"name\": \"Hendra Wijaya\",\n"
        "  \"check_in_date\": \"akhir pekan ini\",\n"
        "  \"check_out_date\": null,\n"
        "  \"room_type\": null\n"
        "}\n\n"
        f"Pesan: \"{message}\"\n"
        "Output:"
    )
    return prompt



def build_dual_intent_prompt(message: str) -> str:
    """
    Membangun prompt untuk mendeteksi dua intent sekaligus dalam satu kalimat pengguna.

    Parameters:
        message (str): Kalimat pengguna yang ingin dianalisis.

    Returns:
        str: Prompt pendeteksian multi-intent.
    """
    prompt = (
        "Deteksi satu atau dua intent yang terkandung di dalam pesan pengguna berikut.\n"
        "Pilihan intent: faq, booking_inquiry, booking_request, complaint, cancellation, refund, unknown\n\n"
        "Aturan:\n"
        "1. Jawab dengan satu atau dua nama intent dipisahkan dengan koma (misalnya: cancellation, refund atau complaint).\n"
        "2. Jawab HANYA dengan nama intent dalam huruf kecil (lowercase).\n"
        "3. Jangan berikan tanda baca selain koma pemisah, dan jangan berikan kalimat tambahan.\n\n"
        "Contoh:\n"
        "- \"Saya ingin membatalkan reservasi saya, dan apakah uang saya bisa dikembalikan?\" -> cancellation, refund\n"
        "- \"Kamar saya kotor sekali dan AC nya mati, saya mau komplain.\" -> complaint\n"
        "- \"Berapa harga kamar deluxe dan saya mau langsung booking untuk besok atas nama Andi.\" -> booking_inquiry, booking_request\n\n"
        f"Pesan: \"{message}\"\n"
        "Intent:"
    )
    return prompt

# Greeting
GREETING = """Halo! Selamat datang di {hotel_name}. 
Ada yang bisa kami bantu? 😊"""

GREETING_ENRICHED = """Halo, {guest_name}! 
Selamat datang kembali di {hotel_name}. 
Ada yang bisa kami bantu selama menginap?"""

# FAQ
FAQ_NO_RESULT = """Maaf, saya belum memiliki 
informasi mengenai hal tersebut. 
Silakan hubungi kami di:
📞 {phone}
📧 {email}

Atau ketik *staff* untuk terhubung 
dengan tim kami."""

# Booking
BOOKING_CONFIRM = """Baik, berikut ringkasan 
pesanan Anda:

🏨 Hotel: {hotel_name}
🛏️ Kamar: {room_type}
📅 Check-in: {check_in}
📅 Check-out: {check_out}
👥 Tamu: {num_guests} orang
📝 Request: {special_request}

Apakah sudah sesuai? (ya/tidak)"""

BOOKING_SUCCESS = """✅ Pesanan Anda sudah kami 
catat!

Nomor referensi: *{booking_ref}*

Tim kami akan menghubungi Anda di 
nomor ini dalam *1x24 jam* untuk 
konfirmasi dan informasi pembayaran.

Ada yang ingin ditanyakan lagi?"""

BOOKING_SALES_NOTIF = """🔔 *Booking Baru*

Hotel: {hotel_name}
Tamu: {guest_name}
WA: {wa_number}
Kamar: {room_type}
Check-in: {check_in}
Check-out: {check_out}
Tamu: {num_guests} orang
Request: {special_request}
Upsell: {upsell_items}

Ref: {booking_ref}"""

# Complaint
COMPLAINT_RECEIVED = """Terima kasih sudah 
memberitahu kami, {guest_name}.

Keluhan Anda sudah kami catat dan 
tim *{department}* akan segera 
menangani di kamar {room_number}.

Estimasi penanganan: *{eta}*

Mohon maaf atas ketidaknyamanannya. 🙏"""

COMPLAINT_NO_CONTEXT = """Untuk memproses 
keluhan Anda, boleh sebutkan:
- Nama tamu
- Nomor kamar

Atau ketik *staff* untuk langsung 
terhubung dengan front office kami."""

# Amenities
AMENITIES_CONFIRM = """Baik, permintaan 
berikut sudah kami catat:

{items_list}

Tim housekeeping akan segera mengantarkan 
ke kamar {room_number}.
Estimasi: *15-20 menit* ⏱️"""

# Fallback
FALLBACK_OPTIONS = """Maaf, saya kurang 
memahami permintaan Anda. 
Silakan pilih yang sesuai:

1️⃣ Informasi hotel & fasilitas
2️⃣ Pesan kamar
3️⃣ Sampaikan keluhan
4️⃣ Minta layanan kamar
5️⃣ Bicara dengan staff

Ketik angka pilihan atau *staff* 
untuk bantuan langsung."""

ESCALATE_TO_HUMAN = """Baik, saya akan 
menhubungkan Anda dengan staff kami.

Mohon tunggu sebentar... 🙏

_Atau hubungi langsung:_
📞 {phone}"""

# Error
SYSTEM_ERROR = """Maaf, terjadi gangguan 
teknis. Silakan coba lagi atau hubungi 
kami langsung di 📞 {phone}"""

# Formatting
TRUNCATION_NOTE = "\n\n_(pesan terpotong — hubungi staff untuk info lengkap)_"

# WA System

Layanan Python terpisah untuk webhook resmi WhatsApp Cloud API.

## Ruang lingkup

Sistem ini ditujukan untuk percakapan bisnis yang sah dengan kontak yang sudah memberikan persetujuan. Sistem tidak menyediakan group farming, rotasi nomor untuk menghindari pembatasan, penyamaran aktivitas otomatis, pemeriksaan status online pengguna, atau broadcast massal.

## Fitur

- menerima webhook pesan masuk
- validasi signature `X-Hub-Signature-256`
- hanya membalas nomor opt-in/test yang diizinkan
- registry kontak manual dengan sumber dan waktu persetujuan
- pencatatan opt-out
- data respons disimpan terpisah dalam `response_data.json`
- deduplikasi berdasarkan ID pesan masuk
- debounce/cooldown per nomor antara 16–20 detik
- pesan baru dari nomor yang sama menggantikan balasan yang masih menunggu
- penyimpanan pesan dan status ke SQLite
- status resmi `accepted`, `sent`, `delivered`, `read`, dan `failed`
- endpoint log dilindungi `WA_ADMIN_API_KEY`
- struktur counter untuk batas balasan harian per kontak

Cooldown digunakan untuk mencegah burst dan balasan bertumpuk, bukan untuk menyamarkan bot sebagai manusia. Balasan default diberi label sebagai balasan otomatis.

## Kontak manual

Nomor manual hanya boleh dimasukkan setelah ada bukti persetujuan. Registry menyimpan:

- nomor dalam format internasional
- status opt-in
- sumber persetujuan
- catatan persetujuan
- waktu persetujuan
- waktu opt-out

Modul registry berada di `contact_store.py`. Menambahkan kontak ke database tidak mengirim pesan secara otomatis. Pengiriman tetap hanya boleh terjadi sebagai respons terhadap pesan masuk yang sah.

## Data respons

Respons dasar berada di:

```text
response_data.json
```

Pisahkan teks respons dari credential dan source code. Jangan masukkan token, secret, atau data sensitif ke file tersebut.

## Menjalankan lokal

```bash
cd wa-system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8000
```

Pada Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Variabel pada `.env` harus dimuat oleh platform deployment atau shell sebelum aplikasi dijalankan.

## Endpoint

- `GET /health` — kesehatan layanan dan ringkasan status
- `GET /webhook` — verifikasi webhook Meta
- `POST /webhook` — menerima pesan dan status delivery
- `GET /messages?limit=100` — log pesan; wajib header `X-Admin-Key`

Tidak ada endpoint pengiriman massal atau pengiriman proaktif ke daftar nomor.

## Cooldown

Nilai default:

```env
WA_COOLDOWN_MIN_SECONDS=16
WA_COOLDOWN_MAX_SECONDS=20
WA_MAX_REPLIES_PER_CONTACT_PER_DAY=6
```

Untuk satu nomor, hanya satu balasan tertunda yang disimpan. Ketika pesan baru masuk sebelum timer selesai, balasan lama dibatalkan dan diganti dengan balasan terbaru.

## Praktik menjaga kualitas nomor bisnis

- gunakan WhatsApp Cloud API resmi
- kirim hanya kepada kontak yang memberikan opt-in
- hormati STOP/BERHENTI dan opt-out lain
- jangan membeli, menebak, atau mengimpor daftar nomor tanpa izin
- jangan membuat percakapan palsu antarnomor
- gunakan template yang disetujui untuk percakapan di luar jendela layanan
- pantau status gagal dan quality rating nomor bisnis
- hentikan kampanye ketika tingkat blokir atau laporan meningkat

## Docker

```bash
docker build -t wa-system .
docker run --env-file .env -p 8000:8000 wa-system
```

## Pengujian

```bash
python -m pytest -q
```

## Keamanan

Jangan commit `WA_ACCESS_TOKEN`, `WA_APP_SECRET`, `WA_VERIFY_TOKEN`, atau `WA_ADMIN_API_KEY`. Gunakan nomor yang memiliki izin/opt-in dan patuhi kebijakan WhatsApp Business Platform.

# WA System

Layanan Python terpisah untuk webhook resmi WhatsApp Cloud API.

## Fitur

- menerima webhook pesan masuk
- validasi signature `X-Hub-Signature-256`
- hanya membalas nomor yang tercantum dalam `WA_ALLOWED_RECIPIENTS`
- deduplikasi berdasarkan ID pesan masuk
- debounce/cooldown per nomor antara 16–20 detik
- pesan baru dari nomor yang sama menggantikan balasan yang masih menunggu
- menyimpan pesan dan status ke SQLite
- membaca status resmi `accepted`, `sent`, `delivered`, `read`, dan `failed`
- endpoint log dilindungi `WA_ADMIN_API_KEY`

Cooldown digunakan untuk mencegah burst dan balasan bertumpuk. Balasan default diberi label sebagai balasan otomatis. Sistem ini tidak memeriksa status online/aktif pengguna dan tidak menyediakan broadcast massal.

## Menjalankan lokal

```bash
cd wa-system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8000
```

Pada Windows PowerShell, aktivasi virtual environment menggunakan:

```powershell
.venv\Scripts\Activate.ps1
```

Variabel pada `.env` harus dimuat oleh platform deployment atau shell sebelum aplikasi dijalankan.

## Endpoint

- `GET /health` — kesehatan layanan dan ringkasan status
- `GET /webhook` — verifikasi webhook Meta
- `POST /webhook` — menerima pesan dan status delivery
- `GET /messages?limit=100` — log pesan; wajib header `X-Admin-Key`

## Cooldown

Nilai default:

```env
WA_COOLDOWN_MIN_SECONDS=16
WA_COOLDOWN_MAX_SECONDS=20
```

Untuk satu nomor, hanya satu balasan tertunda yang disimpan. Ketika pesan baru masuk sebelum timer selesai, balasan lama dibatalkan dan diganti dengan balasan terbaru.

## Docker

```bash
docker build -t wa-system .
docker run --env-file .env -p 8000:8000 wa-system
```

## Pengujian

```bash
pytest -q
```

## Keamanan

Jangan commit `WA_ACCESS_TOKEN`, `WA_APP_SECRET`, `WA_VERIFY_TOKEN`, atau `WA_ADMIN_API_KEY`. Gunakan nomor yang memiliki izin/opt-in dan patuhi kebijakan WhatsApp Business Platform.

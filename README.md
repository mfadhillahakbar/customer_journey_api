# Customer Journey Analytics API

REST API untuk analitik customer journey aplikasi mobile menggunakan **Python 3.11, FastAPI, dan Google BigQuery**. Mendukung filter dinamis, pagination, autentikasi API Key, dan integrasi dashboard Metabase.

## 1. Fitur

- Statistik klik berdasarkan screen, button, dan event.
- Daftar pengguna yang berinteraksi dengan tombol.
- Detail event mentah dengan pagination.
- Filter tanggal dan multiple values dipisahkan koma.
- Validasi request menggunakan Pydantic v2.
- Query BigQuery terparameterisasi, deduplikasi customer, dan pembatasan biaya query.
- Autentikasi melalui header `X-API-Key`.

## 2. Teknologi

- Python 3.11+
- FastAPI dan Uvicorn
- Google Cloud BigQuery Client
- Pydantic Settings
- Pytest
- PostgreSQL tidak diperlukan untuk penyimpanan API ini.

## 3. Struktur Project

```text
customer-journey-api/
├── app/
│   ├── api/v1/endpoints/
│   ├── core/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   └── main.py
├── tests/
├── deployment/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 4. Konfigurasi

Buat file environment lokal:

```bash
cp .env.example .env
```

Isi konfigurasi sesuai environment masing-masing:

```dotenv
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8000

API_KEY=<GUNAKAN_SECRET_KEY_YANG_KUAT>

GCP_PROJECT_ID=<GCP_PROJECT_ID>
GOOGLE_APPLICATION_CREDENTIALS=<PATH_CREDENTIAL_JSON>

BQ_EVENTS_TABLE=<PROJECT.DATASET.EVENTS_TABLE>
BQ_CUSTOMERS_TABLE=<PROJECT.DATASET.CUSTOMERS_TABLE>
BQ_MAX_BYTES_BILLED=10737418240
BQ_QUERY_TIMEOUT_SECONDS=60

DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=100
```

Sesuaikan nama tabel dan pemetaan kolom customer dengan skema BigQuery aktual.

**Keamanan credential:**
- Jangan commit `.env`, file Service Account JSON, atau API Key ke Git.
- Masukkan `.env` dan file credential ke `.gitignore`.
- Gunakan placeholder pada `.env.example`, bukan credential aktif.
- Batasi permission file credential dan gunakan Google Application Default Credentials (ADC) bila sesuai dengan lingkungan deployment.
- Berikan Service Account hanya izin BigQuery yang diperlukan: `BigQuery Job User` pada project dan `BigQuery Data Viewer` pada dataset terkait.
- Gunakan API Key yang berbeda untuk setiap environment. Jangan gunakan key development di production.

## 5. Instalasi dan Menjalankan API

```bash
python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Dokumentasi API:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## 6. Endpoint

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/health/ready` | Memeriksa kesiapan koneksi BigQuery |
| GET | `/api/v1/button-clicks` | Ringkasan statistik klik |
| GET | `/api/v1/button-clicks/users` | Daftar pengguna berdasarkan tombol |
| GET | `/api/v1/button-clicks/events` | Detail event mentah |
| GET | `/api/v1/filters/{field}` | Opsi filter unik untuk checkbox atau multi-select |

Endpoint selain health check menggunakan header autentikasi:

```http
X-API-Key: <API_KEY>
```

### Filter dan Pagination

Parameter yang tersedia menyesuaikan endpoint:

- Tanggal: `start_date`, `end_date`
- Customer: `role`, `depo`, `region`, `area`, `user_id`
- Interaksi: `screen_name`, `button_name`, `event_name`
- Pagination: `page`, `page_size`

Filter teks mendukung multiple values yang dipisahkan koma:

```text
?role=Sales,Admin
&depo=Depo%20Jakarta,Depo%20Bandung
&region=Jawa%20Barat,Jawa%20Tengah
&screen_name=RBSheetProductDetail,HomeScreen
&button_name=AddToCart,Checkout
```

Spasi di sekitar koma diabaikan dan nilai kosong dilewati. Filter tunggal tetap berfungsi seperti sebelumnya. Parameter `button_name` wajib pada endpoint `/api/v1/button-clicks/users`.

`button_name` menggunakan partial match tanpa membedakan huruf besar-kecil. Beberapa keyword
digabung dengan logika OR, sehingga `?button_name=Product,Checkout` mencocokkan nama tombol
yang mengandung `Product` atau `Checkout`.

### Opsi Filter Master dan Event

Gunakan endpoint berikut untuk mengisi checkbox atau multi-select:

```bash
curl -G "http://127.0.0.1:8000/api/v1/filters/button_name" \
  -H "X-API-Key: ${API_KEY}" \
  --data-urlencode "search=checkout" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=50"
```

Field yang didukung mencakup `role`, `depo`, `region`, `area`, `user_id`, `screen_name`,
`button_name`, `event_name`, `event_date`, `event_timestamp`, `user_pseudo_id`,
`ga_session_id`, `ga_session_number`, `platform`, `device_category`, `device_brand`,
`device_model`, `os_version`, `city`, dan `app_version`. Nilai dikembalikan unik,
tidak null/kosong, sudah di-trim, diurutkan alfabetis, dan mendukung `search`, `page`,
serta `page_size`.

Contoh request:

```bash
curl -G "http://127.0.0.1:8000/api/v1/button-clicks" \
  -H "X-API-Key: ${API_KEY}" \
  --data-urlencode "start_date=2026-09-01" \
  --data-urlencode "end_date=2026-09-30" \
  --data-urlencode "screen_name=RBSheetProductDetail,HomeScreen" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=50"
```

Pastikan variabel `API_KEY` telah disediakan secara aman di environment shell sebelum menjalankan request.

## 7. Testing

Jalankan unit test:

```bash
pytest -v
```

Test mencakup autentikasi, validasi tanggal, pagination, multiple filters, agregasi, dan integritas deduplikasi SQL. Gunakan mock BigQuery agar unit test tidak memerlukan credential aktif.

## 8. Deployment Production

Deployment menggunakan Linux, virtual environment, Systemd, dan Nginx sebagai reverse proxy HTTPS.

1. Pasang Python dan dependensi.
2. Salin source code ke direktori aplikasi.
3. Simpan `.env` dan credential di lokasi dengan permission terbatas.
4. Konfigurasikan Systemd dengan user non-root.
5. Aktifkan HTTPS dan konfigurasi Nginx.
6. Jalankan test dan verifikasi `/health/ready`.
7. Monitor log melalui `journalctl`.

Jangan expose port internal Uvicorn secara publik jika akses seharusnya melalui Nginx.

## 9. Optimasi dan Keamanan

- Gunakan parameter query BigQuery untuk nilai filter.
- Terapkan filter tanggal langsung pada `event_date`.
- Deduplicasi data customer sebelum join untuk mencegah penggandaan event.
- Batasi biaya melalui `BQ_MAX_BYTES_BILLED`.
- Gunakan pagination dan batas maksimum `page_size`.
- Hindari mencatat API Key, credential, atau data customer sensitif pada log.
- Jangan mengembalikan detail internal BigQuery kepada client saat terjadi error.
- Validasi konfigurasi production agar aplikasi menolak secret default atau konfigurasi yang tidak aman.

## 10. Checklist Pra-Produksi

- [ ] API Key production menggunakan secret yang kuat.
- [ ] Tidak ada credential aktif di repository Git.
- [ ] Service Account memiliki izin minimum yang diperlukan.
- [ ] HTTPS dan konfigurasi Nginx sudah aktif.
- [ ] Semua unit test lulus.
- [ ] Endpoint health dan readiness berfungsi.
- [ ] Batas biaya query dan pagination sudah dikonfigurasi.

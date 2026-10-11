# Customer Journey Analytics API (Google BigQuery & FastAPI)

REST API berkinerja tinggi berbasis **Python 3.11**, **FastAPI**, dan **Google Cloud BigQuery Client** untuk menyajikan data analitik customer journey dari interaksi pengguna terhadap tombol di aplikasi mobile.

API ini dirancang untuk backend production pada server Linux: modular, aman, teruji penuh, efisien biaya BigQuery, serta mendukung filter dinamis Metabase (`start_date`, `end_date`, `role`, `depo`, `region`, `area`, `screen_name`, `button_name`, `event_name`).

---

## Daftar Isi

1. [Fitur Utama & Arsitektur](#1-fitur-utama--arsitektur)
2. [Identifikasi Skema BigQuery & Asumsi](#2-identifikasi-skema-bigquery--asumsi)
3. [Struktur Project](#3-struktur-project)
4. [Persyaratan Sistem](#4-persyaratan-sistem)
5. [Konfigurasi Environment (.env)](#5-konfigurasi-environment-env)
6. [Autentikasi & Least Privilege Google Cloud](#6-autentikasi--least-privilege-google-cloud)
7. [Menjalankan Aplikasi secara Lokal](#7-menjalankan-aplikasi-secara-lokal)
8. [Menjalankan Unit Test](#8-menjalankan-unit-test)
9. [Dokumentasi Endpoint & Contoh cURL](#9-dokumentasi-endpoint--contoh-curl)
10. [Panduan Deployment Server Linux (Systemd & Nginx)](#10-panduan-deployment-server-linux-systemd--nginx)
11. [Monitoring, Log, dan Troubleshooting](#11-monitoring-log-dan-troubleshooting)
12. [Optimasi Biaya BigQuery](#12-optimasi-biaya-bigquery)
13. [Checklist Verifikasi Pra-Produksi](#13-checklist-verifikasi-pra-produksi)

---

## 1. Fitur Utama & Arsitektur

### Prinsip Desain
- **Pemisahan Tanggung Jawab (Separation of Concerns):**
  - **Router / Endpoints:** Menangani deserialisasi HTTP request, HTTP status code, dan otorisasi API Key.
  - **Schemas (Pydantic v2):** Validasi format input, rentang tanggal inklusif, pagination, dan serialisasi response.
  - **Services:** Mengorkestrasi aturan bisnis, perhitungan halaman, serta transformasi data.
  - **Repositories:** Berinteraksi langsung dengan Google BigQuery menggunakan parameterisasi resmi (`ScalarQueryParameter`).
  - **Core Config & Security:** Pengelolaan environment variable via Pydantic Settings dan proteksi akses via `X-API-Key`.
- **Integritas Join (Pencegahan Penggandaan Event):**
  Tabel master customer (`all_customer_rangkul`) berpotensi mengandung record ganda untuk satu `user_id`. Repository menggunakan CTE deduplikasi berbasis window function `ROW_NUMBER() OVER(PARTITION BY user_id)` sebelum proses join. Hal ini menjamin 1 event klik **tidak pernah digandakan** saat dihitung (`COUNT(*)` tetap akurat).
- **Efisiensi Query BigQuery:**
  - Menghitung `total_records` untuk pagination dalam 1 kali eksekusi query menggunakan window function `COUNT(*) OVER()`, menghilangkan kebutuhan full-scan ganda.
  - Pembatasan biaya scanning melalui konfigurasi `BQ_MAX_BYTES_BILLED`.
  - Filter tanggal dieksekusi sedini mungkin pada kolom `event_date`.

---

## 2. Identifikasi Skema BigQuery & Asumsi

Sumber data di Google Cloud Project: `rangkul-355bb`, Dataset: `analytics_journey`.

### 2.1. Tabel Event: `raw_events_agustus_september`
Kolom yang digunakan dalam query:
- `event_date`: Tanggal event (format `YYYY-MM-DD`).
- `event_timestamp`: Timestamp presisi waktu event (`TIMESTAMP`).
- `user_id`: ID unik pengguna (dikecualikan jika `NULL` atau string kosong `''`).
- `button_name`: Nama tombol (dikecualikan jika `NULL` atau string kosong `''`).
- `screen_name`: Nama layar aplikasi (tetap dipertahankan meskipun `NULL`).
- `event_name`: Nama event interaksi.

### 2.2. Tabel Master Customer: `all_customer_rangkul`
Kolom yang digunakan dalam query:
- `user_id`: Kunci relasi join (`e.user_id = c.user_id`).
- `role`, `depo`, `region`, `area`: Digunakan untuk filter dan payload detail customer.

> **PENTING — Verifikasi Skema di BigQuery:**
> Jika skema tabel master customer memiliki penamaan kolom yang berbeda (misalnya `customer_role` alih-alih `role`, atau memiliki kolom timestamp update seperti `updated_at` untuk menentukan baris master paling mutakhir), Anda dapat menyesuaikan konfigurasi `CUSTOMER_COLUMN_MAPPING` di file `.env` tanpa mengubah kode aplikasi.
>
> Periksa skema aktual menggunakan query SQL berikut di BigQuery Console:
> ```sql
> SELECT column_name, data_type, is_nullable
> FROM `rangkul-355bb.analytics_journey.INFORMATION_SCHEMA.COLUMNS`
> WHERE table_name IN ('raw_events_agustus_september', 'all_customer_rangkul')
> ORDER BY table_name, ordinal_position;
> ```

---

## 3. Struktur Project

```text
customer-journey-api/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app instance, CORS, middleware, lifecycle
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                    # Pydantic Settings & environment validation
│   │   ├── exceptions.py                # Custom exceptions & standardized error handlers
│   │   ├── logging.py                   # Structured logger with request ID correlation
│   │   └── security.py                  # API Key (X-API-Key) constant-time authentication
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py                # Aggregator rute API v1
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── health.py            # /health (liveness) & /health/ready (readiness)
│   │           └── button_clicks.py     # Endpoints B, C, dan D
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py                    # Pagination & Health schemas
│   │   └── button_clicks.py             # Button analytics request & response models
│   ├── services/
│   │   ├── __init__.py
│   │   └── button_clicks_service.py     # Business logic & data transformations
│   └── repositories/
│       ├── __init__.py
│       └── bigquery_repository.py       # BigQuery Client, SQL builder, deduplikasi
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Fixtures, Mock BigQuery Repository
│   ├── test_health.py                   # Test probe /health & /health/ready
│   ├── test_button_clicks.py            # Test agregasi, filter, dedup SQL
│   ├── test_users.py                    # Test endpoint users & required button_name
│   └── test_validation.py               # Test start_date > end_date, pagination, auth
├── deployment/
│   ├── customer-journey-api.service     # Systemd service unit file
│   └── nginx.conf.example               # Nginx reverse proxy dengan HTTPS & rate limit
├── .env.example                         # Template konfigurasi environment
├── .gitignore                           # Proteksi credential & ignore file
├── pytest.ini                           # Konfigurasi runner pytest
├── requirements.txt                     # Pinned dependencies
└── README.md                            # Dokumentasi teknis lengkap
```

---

## 4. Persyaratan Sistem

- Server: Linux (Ubuntu 22.04 LTS / Debian 12 / Rocky Linux 9 / RHEL 9) atau macOS untuk development.
- Python: **Python 3.11** (disarankan) atau versi stabil 3.11+.
- Akses ke GCP Project: `rangkul-355bb`.
- Port default: `8000` (internal) dan `80/443` (via Nginx reverse proxy).

---

## 5. Konfigurasi Environment (`.env`)

Buat salinan file `.env` dari `.env.example`:
```bash
cp .env.example .env
```

Daftar parameter konfigurasi:

| Parameter | Default | Keterangan |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `staging`, atau `production`. |
| `HOST` | `0.0.0.0` | Bind IP server uvicorn. |
| `PORT` | `8000` | Port listen server uvicorn. |
| `API_TITLE` | `Customer Journey Analytics API` | Nama layanan pada dokumentasi OpenAPI. |
| `API_VERSION` | `1.0.0` | Versi API. |
| `API_KEY` | *(Secret)* | Kunci rahasia untuk header `X-API-Key`. Pada production, server menolak jalan jika memakai default. |
| `API_KEY_NAME` | `X-API-Key` | Nama HTTP Header autentikasi. |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Daftar origin CORS frontend terdaftar (dipisahkan koma). |
| `GCP_PROJECT_ID` | `rangkul-355bb` | ID Project Google Cloud. |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/path/to/key.json` | Path absolut ke file JSON Service Account. Kosongkan jika pakai ADC. |
| `BQ_DATASET` | `analytics_journey` | Dataset BigQuery. |
| `BQ_EVENTS_TABLE` | `rangkul-355bb.analytics_journey.raw_events_agustus_september` | Nama tabel event lengkap. |
| `BQ_CUSTOMERS_TABLE` | `rangkul-355bb.analytics_journey.all_customer_rangkul` | Nama tabel master customer lengkap. |
| `BQ_MAX_BYTES_BILLED` | `10737418240` (10 GB) | Pembatasan biaya scan BigQuery per query. |
| `BQ_QUERY_TIMEOUT_SECONDS` | `60` | Batas timeout eksekusi query (detik). |
| `DEFAULT_PAGE_SIZE` | `50` | Ukuran data pagination default. |
| `MAX_PAGE_SIZE` | `100` | Batas maksimum data per halaman. |

---

## 6. Autentikasi & Least Privilege Google Cloud

Service Account digunakan secara eksklusif untuk otorisasi API ke BigQuery. Terapkan prinsip **Least Privilege**:

### Hak Akses (IAM Roles) Minimal:
1. **BigQuery Job User (`roles/bigquery.jobUser`):**
   Diberikan pada tingkat Project (`rangkul-355bb`). Izin ini mengizinkan Service Account menjalankan query job.
2. **BigQuery Data Viewer (`roles/bigquery.dataViewer`):**
   Diberikan **hanya pada level Dataset** `analytics_journey`, bukan pada seluruh project:
   ```bash
   gcloud datasets add-iam-policy-binding analytics_journey \
       --project=rangkul-355bb \
       --member="serviceAccount:sa-journey-api@rangkul-355bb.iam.gserviceaccount.com" \
       --role="roles/bigquery.dataViewer"
   ```

### Keamanan File Kunci Credential:
- Simpan file JSON service account di direktori terisolasi server Linux, misal: `/opt/customer-journey-api/credentials/service-account.json`.
- Atur permission kepemilikan file secara ketat:
  ```bash
  sudo chown -R www-data:www-data /opt/customer-journey-api/credentials
  sudo chmod 600 /opt/customer-journey-api/credentials/service-account.json
  ```
- **JANGAN PERNAH** melakukan commit file credential ke Git repository.

---

## 7. Menjalankan Aplikasi secara Lokal

### 1. Buat Virtual Environment dan Install Dependensi
```bash
cd /Users/mfdhllhakbr/customer-journey-api
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Konfigurasi .env Lokal
```bash
cp .env.example .env
# Edit .env dan sesuaikan nilai API_KEY atau GOOGLE_APPLICATION_CREDENTIALS
```

### 3. Jalankan Server Development
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Akses dokumentasi interaktif:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

---

## 8. Menjalankan Unit Test

Unit test dirancang menggunakan mock repository BigQuery sehingga dapat berjalan 100% cepat dan stabil tanpa membutuhkan koneksi internet atau credential Google Cloud:

```bash
source .venv/bin/activate
pytest -v
```

Hasil eksekusi test suite mencakup:
- Health check & BigQuery readiness probe.
- Agregasi statistik klik tanpa filter dan dengan filter kombinasi.
- Validasi integer division `user_avg_clicks`.
- Integritas deduplikasi query SQL.
- Validasi parameter wajib `button_name` pada endpoint `/users`.
- Validasi rentang tanggal `start_date > end_date` (Error `INVALID_DATE_RANGE`).
- Pembatasan pagination `page_size > 100`.
- Otorisasi API Key `X-API-Key` (401 Unauthorized saat tidak valid/absen).

---

## 9. Dokumentasi Endpoint & Contoh cURL

Prefix rute API: `/api/v1`.

### 9.1. Endpoint A — Health Check & Readiness

#### Liveness Probe (Tidak memicu query BigQuery)
```bash
curl -X GET "http://127.0.0.1:8000/health"
```
**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "Customer Journey Analytics API",
  "version": "1.0.0",
  "environment": "development"
}
```

#### Readiness Probe (Memverifikasi koneksi BigQuery)
```bash
curl -X GET "http://127.0.0.1:8000/health/ready"
```
**Response (200 OK):**
```json
{
  "status": "ready",
  "bigquery": "connected",
  "project_id": "rangkul-355bb"
}
```

---

### 9.2. Endpoint B — Ringkasan Statistik Tombol (`GET /api/v1/button-clicks`)

Mengembalikan daftar statistik klik per kombinasi screen, tombol, dan event.

#### Contoh Request:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/button-clicks?start_date=2026-09-01&end_date=2026-09-30&role=Sales&region=Jawa%20Barat&page=1&page_size=50" \
     -H "X-API-Key: development-secret-key-change-in-production"
```

#### Contoh Response (200 OK):
```json
{
  "data": [
    {
      "screen_name": "checkout",
      "button_name": "checkout_submit",
      "event_name": "begin_checkout",
      "total_clicks": 1500,
      "total_users": 750,
      "user_avg_clicks": 2
    },
    {
      "screen_name": "home_page",
      "button_name": "promo_banner_click",
      "event_name": "banner_click",
      "total_clicks": 800,
      "total_users": 400,
      "user_avg_clicks": 2
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_records": 2,
    "total_pages": 1
  },
  "filters_applied": {
    "start_date": "2026-09-01",
    "end_date": "2026-09-30",
    "role": "Sales",
    "region": "Jawa Barat",
    "depo": null,
    "area": null,
    "screen_name": null,
    "button_name": null,
    "event_name": null
  }
}
```

---

### 9.3. Endpoint C — Daftar Pengguna yang Mengklik Tombol (`GET /api/v1/button-clicks/users`)

Mengembalikan daftar pengguna unik untuk tombol yang dipilih, beserta jumlah klik pengguna dan detail customer.
**Parameter `button_name` wajib diisi.**

#### Contoh Request:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/button-clicks/users?button_name=checkout_submit&screen_name=checkout&start_date=2026-09-01&end_date=2026-09-30&role=Sales&page=1&page_size=50" \
     -H "X-API-Key: development-secret-key-change-in-production"
```

#### Contoh Response (200 OK):
```json
{
  "data": [
    {
      "user_id": "EX09202601674",
      "user_clicks": 5,
      "last_event_timestamp": "2026-09-16T12:57:19.821000",
      "customer": {
        "role": "Sales",
        "depo": "Depo Tangerang",
        "region": "Jawa Barat",
        "area": "Tangerang Kota"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_records": 1,
    "total_pages": 1
  },
  "filters_applied": {
    "start_date": "2026-09-01",
    "end_date": "2026-09-30",
    "role": "Sales",
    "region": null,
    "depo": null,
    "area": null,
    "screen_name": "checkout",
    "button_name": "checkout_submit",
    "event_name": null
  }
}
```

---

### 9.4. Endpoint D — Detail Event Mentah Opsional (`GET /api/v1/button-clicks/events`)

Inspeksi event individual dengan pagination terkontrol.

#### Contoh Request:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/button-clicks/events?button_name=checkout_submit&page=1&page_size=10" \
     -H "X-API-Key: development-secret-key-change-in-production"
```

---

### 9.5. Format Error Standar

Semua error dikembalikan dalam format JSON terstruktur:

#### Error Rentang Tanggal Tidak Valid (HTTP 400):
```json
{
  "error": {
    "code": "INVALID_DATE_RANGE",
    "message": "start_date harus lebih awal dari atau sama dengan end_date."
  }
}
```

#### Error Autentikasi API Key (HTTP 401):
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Header X-API-Key wajib disertakan."
  }
}
```

#### Error Validasi Request Parameter (HTTP 422):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Format parameter request tidak valid.",
    "details": [
      {
        "field": "button_name",
        "issue": "Field required"
      }
    ]
  }
}
```

---

## 10. Panduan Deployment Server Linux (Systemd & Nginx)

Langkah deployment siap pakai pada server Linux (Ubuntu/Debian):

### Langkah 1: Persiapan Server & User Non-Root
Pastikan Python 3.11 terinstall:
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip nginx
```

### Langkah 2: Setup Direktori Aplikasi
```bash
sudo mkdir -p /opt/customer-journey-api/credentials
sudo chown -R www-data:www-data /opt/customer-journey-api
```

Salin source code aplikasi ke direktori `/opt/customer-journey-api`.

### Langkah 3: Setup Virtual Environment & Dependensi
```bash
cd /opt/customer-journey-api
sudo -u www-data python3.11 -m venv .venv
sudo -u www-data /opt/customer-journey-api/.venv/bin/pip install --upgrade pip
sudo -u www-data /opt/customer-journey-api/.venv/bin/pip install -r requirements.txt
```

### Langkah 4: Simpan File Kunci Service Account & File .env
1. Simpan file JSON Service Account:
   ```bash
   sudo cp /path/to/source-key.json /opt/customer-journey-api/credentials/service-account.json
   sudo chown www-data:www-data /opt/customer-journey-api/credentials/service-account.json
   sudo chmod 600 /opt/customer-journey-api/credentials/service-account.json
   ```

2. Konfigurasi file `.env` production:
   ```bash
   sudo cp /opt/customer-journey-api/.env.example /opt/customer-journey-api/.env
   sudo nano /opt/customer-journey-api/.env
   ```
   Pastikan mengatur:
   ```dotenv
   ENVIRONMENT=production
   API_KEY=GANTI_DENGAN_RANDOM_HASH_HEX_YANG_KUAT
   ALLOWED_ORIGINS=https://app.yourcompany.com
   GOOGLE_APPLICATION_CREDENTIALS=/opt/customer-journey-api/credentials/service-account.json
   GCP_PROJECT_ID=rangkul-355bb
   ```
   Kunci permission file `.env`:
   ```bash
   sudo chown www-data:www-data /opt/customer-journey-api/.env
   sudo chmod 600 /opt/customer-journey-api/.env
   ```

### Langkah 5: Pasang dan Jalankan Systemd Service
Salin file service unit:
```bash
sudo cp /opt/customer-journey-api/deployment/customer-journey-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable customer-journey-api
sudo systemctl start customer-journey-api
```

Periksa status service:
```bash
sudo systemctl status customer-journey-api
```

### Langkah 6: Konfigurasi Nginx Reverse Proxy (HTTPS)
Salin template konfigurasi:
```bash
sudo cp /opt/customer-journey-api/deployment/nginx.conf.example /etc/nginx/sites-available/customer-journey-api.conf
sudo ln -s /etc/nginx/sites-available/customer-journey-api.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 11. Monitoring, Log, dan Troubleshooting

### Membaca Log Service Systemd
Melihat log aplikasi secara realtime:
```bash
sudo journalctl -u customer-journey-api -f
```

Melihat log error terbaru:
```bash
sudo journalctl -u customer-journey-api -p err -n 50
```

### Melakukan Restart & Update Kode Tanpa Mengubah Credential
Saat memperbarui source code aplikasi:
```bash
cd /opt/customer-journey-api
git pull origin main
sudo -u www-data /opt/customer-journey-api/.venv/bin/pip install -r requirements.txt
sudo systemctl restart customer-journey-api
```

---

## 12. Optimasi Biaya BigQuery

1. **Windowed Total Records:**
   Total records dihitung langsung melalui window function `COUNT(*) OVER()` dari CTE agregasi. Ini menghindari scanning ulang jutaan baris event mentah.
2. **Proteksi Biaya `BQ_MAX_BYTES_BILLED`:**
   Dibatasi pada 10 GB per query secara default untuk mencegah query yang tidak sengaja memindai tabel tanpa batas.
3. **Partition Pruning:**
   Filter `start_date` dan `end_date` diterapkan langsung pada kolom `event_date` menggunakan query parameter string ISO `YYYY-MM-DD`. BigQuery secara otomatis mengkoersikannya ke tipe `DATE` untuk partisi tabel.
4. **Query Cache:**
   Flag `use_query_cache = True` diaktifkan agar request dengan filter identik dalam 24 jam memanfaatkan BigQuery Cache (bebas biaya scan tambahan).

---

## 13. Checklist Verifikasi Pra-Produksi

Sebelum menghubungkan aplikasi web / frontend ke API ini:

- [ ] File `.env` sudah diatur ke `ENVIRONMENT=production`.
- [ ] `API_KEY` production telah diganti menggunakan string acak (misal: `openssl rand -hex 32`).
- [ ] `ALLOWED_ORIGINS` hanya memuat domain resmi aplikasi web frontend.
- [ ] File credential `service-account.json` memiliki hak akses file `600` dan dimiliki oleh user `www-data`.
- [ ] Endpoint probe `GET /health/ready` menghasilkan status `"ready"` dan `"bigquery": "connected"`.
- [ ] Endpoint `GET /health` dapat diakses dari load balancer / monitoring uptime tanpa otorisasi API key.
- [ ] Sertifikat SSL/TLS HTTPS telah aktif pada Nginx reverse proxy.
- [ ] Seluruh unit test lulus dijalankan (`pytest -v`).

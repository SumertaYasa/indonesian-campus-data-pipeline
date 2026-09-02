# 🎓 Indonesian Campus Data Pipeline

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated_Scraping-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Google Maps](<https://img.shields.io/badge/Google_Maps_Platform-Places_API_(New)-4285F4?logo=googlemaps&logoColor=white>)](https://developers.google.com/maps)
[![PostGIS](<https://img.shields.io/badge/PostGIS-Geography(Point,_4326)-336791?logo=postgresql&logoColor=white>)](https://postgis.net/)
[![Wikimedia](https://img.shields.io/badge/Wikimedia_Commons-HD_Logos-006699?logo=wikimedia-commons&logoColor=white)](https://commons.wikimedia.org/)

**Indonesian Campus Data Pipeline** adalah sistem otomatisasi penarikan (_scraping_), penyaringan (_filtering_), deduplikasi, dan pengayaan data multi-sumber (_multi-source enrichment engine_) untuk seluruh institusi perguruan tinggi di Indonesia.

Pipeline ini mentransformasi data mentah dari **PDDIKTI Kemdiktisaintek** dan memperkayanya secara otomatis menggunakan **Google Maps Platform (Places API New & Geocoding)**, **Wikipedia & Wikimedia Commons API**, serta **Crawler Website Resmi Kampus** guna menghasilkan dataset berstandar industri dengan format geospasial **PostGIS WKT** yang siap diintegrasikan ke dalam basis data produksi.

---

## 🌟 Fitur Utama (_Key Capabilities_)

1. **Cakupan Skala Nasional (~6.765 Kampus):**
   - Mampu menarik seluruh data institusi pendidikan tinggi se-Indonesia via Playwright Network Interceptor tanpa terhalang proteksi Cloudflare atau CAPTCHA.
2. **Penyaringan Status Operasional Cerdas:**
   - **Prioritas 1 (Aktif):** Menyaring $\approx 4.303$ kampus yang beroperasi aktif secara normal.
   - **Prioritas 2 (Pembinaan):** Menyaring $\approx 25$ kampus yang masih berdiri di bawah pembinaan administratif kementerian.
   - **Eksklusi Bersih:** Mengeliminasi otomatis $\approx 2.437$ entitas yang berstatus _Alih Bentuk_, _Tutup_, dan _Alih Kelola_.
3. **Deduplikasi Entitas Presisi:**
   - **Kode PT Kembar:** Dideduplikasi otomatis menjadi 1 baris bersih.
   - **Nama Sama, Beda Kode PT:** Tetap dipertahankan (karena entitas legal mandiri / kampus cabang PSDKU / dualisme pencatatan kementerian).
4. **Koordinat Geospasial Standar PostGIS:**
   - Menghasilkan koordinat OGC WKT standar: `POINT(longitude latitude)` (SRID 4326) yang langsung kompatibel dengan tipe data PostgreSQL/PostGIS `geography(Point, 4326)`.
5. **Website Segar & Terverifikasi:**
   - Menolak website usang/mati dari raw data PDDIKTI, murni mengambil tautan aktif yang diverifikasi langsung oleh Google Maps API (`websiteUri`) atau Wikipedia.
6. **Ekstraksi Logo Hybrid Bertingkat:**
   - **Tier 1:** Logo vektor/PNG transparan resolusi tinggi dari Wikimedia Commons.
   - **Tier 2:** Crawler HTML homepage kampus (`apple-touch-icon`, logo navbar, `og:image`, `favicon`).
7. **4 Lapis Guardrail Wikipedia (Anti-Salah Cocok):**
   - Memvalidasi bahwa artikel Wikipedia benar-benar institusi pendidikan tinggi dan menolak keras pencocokan foto/biografi politisi, tokoh, atau wilayah.
8. **Narasi Deskripsi 100% Terisi:**
   - Mengambil narasi sejarah resmi dari Wikipedia dengan _fallback_ otomatis ke **Factual Description Generator** berbasis metadata resmi PDDIKTI.
9. **Toleransi Kesalahan & Checkpoint Resume:**
   - Dilengkapi penulisan _atomic streaming write_ dan file _checkpoint_ (`kampus_extracted_checkpoint.json`). Proses yang terputus dapat dilanjutkan seketika dengan flag `--resume`.

---

## 📋 Struktur Data Output (10 Kolom Presisi Tabel `KAMPUS`)

Format luaran (`data/output/kampus_extracted.csv` dan `.json`) dirancang presisi mengikuti **Tabel 3.1 Entitas KAMPUS** pada [`docs/data-structure.md`](docs/data-structure.md):

| No  | Kolom Target           | Tipe Data               | Keterangan & Contoh                                                     |
| :-: | :--------------------- | :---------------------- | :---------------------------------------------------------------------- |
|  1  | **`kode_kampus`**      | `varchar(20)`           | Kode unik registrasi PT Kemendikbud (Contoh: `"053019"`)                |
|  2  | **`nama_kampus`**      | `varchar(255)`          | Nama resmi institusi (Contoh: `"Sekolah Tinggi Ilmu Administrasi Aan"`) |
|  3  | **`singkatan_kampus`** | `varchar(50)`           | Akronim / nama singkatan resmi (Contoh: `"STIA AAN"`)                   |
|  4  | **`akreditasi`**       | `varchar(20)`           | Akreditasi BAN-PT (Contoh: `"Unggul"`, `"Baik Sekali"`, `"Baik"`)       |
|  5  | **`alamat`**           | `text`                  | Alamat fisik terstandarisasi dari Google Maps Platform                  |
|  6  | **`website_url`**      | `varchar(500)`          | Website resmi terverifikasi dari Google Maps / Wikipedia                |
|  7  | **`logo_url`**         | `varchar(500)`          | URL logo resmi HD (Wikimedia Commons / Website Kampus)                  |
|  8  | **`banner_url`**       | `varchar(500)`          | _NULL_ (Ditunda untuk migrasi Cloud Object Storage)                     |
|  9  | **`deskripsi`**        | `text`                  | Narasi sejarah/profil resmi kampus (Wikipedia / Factual Generator)      |
| 10  | **`koordinat`**        | `geography(Point,4326)` | PostGIS WKT Point: `"POINT(110.366156 -7.770319)"`                      |

---

## 🚀 Panduan Memulai Cepat (_Quickstart in 3 Minutes_)

### 1. Persiapan Lingkungan (_Setup Virtual Environment_)

```bash
# Clone repositori
git clone <URL_REPOSITORY_ANDA>
cd top-hundred-indonesian-campus

# Buat & aktifkan virtual environment (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependensi & browser Playwright
pip install -r requirements.txt
playwright install chromium
```

### 2. Konfigurasi Kunci API (`.env`)

Salin file `.env.example` menjadi `.env`, lalu masukkan API Key Google Maps Platform Anda:

```bash
cp .env.example .env
```

Isi file `.env`:

```env
GOOGLE_MAPS_API_KEY="your_google_maps_api_key_here"
```

### 3. Jalankan Pengujian Sampel (5 Kampus)

```bash
python -m src.main --enrich-kampus --target-count 5
```

_Hasil akan langsung terbentuk di `data/output/kampus_extracted.csv`._

---

## 💻 Panduan Perintah CLI (_Command Cheatsheet_)

| Kebutuhan Operasional                                          | Perintah CLI                                          |
| :------------------------------------------------------------- | :---------------------------------------------------- |
| **Uji Coba Pengayaan Sampel Kecil (5 Kampus)**                 | `python -m src.main --enrich-kampus --target-count 5` |
| **Eksekusi Pengayaan Penuh Seluruh Indonesia (~4.326 Kampus)** | `python -m src.main --enrich-kampus`                  |
| **Melanjutkan Proses yang Terputus (_Resume Checkpoint_)**     | `python -m src.main --enrich-kampus --resume`         |
| **Audit Indikator Duplikasi Nama Kampus Saja**                 | `python -m src.main --audit-duplicates`               |
| **Tarik Ulang Data Mentah dari Server PDDIKTI**                | `python -m src.main --pddikti-api`                    |
| **Ekspor Data Mentah PDDIKTI ke CSV 23 Kolom**                 | `python -m src.main --pddikti-export-csv`             |

---

## 📚 Indeks Dokumentasi Lengkap (_Documentation Hub_)

Semua rincian teknis telah didokumentasikan secara menyeluruh di folder [`docs/`](docs/):

- 📖 **[Panduan Instalasi & Setup Lengkap (`docs/SETUP_GUIDE.md`)](docs/SETUP_GUIDE.md)**: Tutorial instalasi OS Windows/macOS/Linux, aktivasi script PowerShell, dan panduan API Key GCP.
- 🏛️ **[Arsitektur Sistem & Alur Data (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md)**: Diagram alur data Mermaid, struktur modul, strategi multi-tier fallback, dan toleransi kesalahan.
- 💻 **[Panduan Lengkap Antarmuka CLI (`docs/CLI_USAGE_GUIDE.md`)](docs/CLI_USAGE_GUIDE.md)**: Referensi lengkap seluruh opsi flag, parameter, skenario penggunaan, dan arti tag status terminal.
- 📄 **[Dokumentasi Proses Ekstraksi Formal (`docs/data_extraction_process.md`)](docs/data_extraction_process.md)**: Laporan proses ekstraksi data kampus resmi Sprint 1.
- 🗄️ **[Spesifikasi Skema Data (`docs/data-structure.md`)](docs/data-structure.md)**: Definisi skema tabel basis data relasional PostgreSQL.

---

## 📁 Struktur Direktori Proyek

```text
top-hundred-indonesian-campus/
├── data/
│   ├── input/               # Master wilayah & referensi CSV
│   ├── output/              # Luaran hasil ekstraksi (kampus_extracted.csv / .json)
│   └── reference/           # Referensi skema respons HTML/JSON
├── docs/                    # Dokumentasi lengkap arsitektur, setup, & CLI
│   ├── ARCHITECTURE.md
│   ├── CLI_USAGE_GUIDE.md
│   ├── SETUP_GUIDE.md
│   ├── data-structure.md
│   └── data_extraction_process.md
├── src/
│   ├── extractors/          # Google Maps, Wikipedia, & Web Logo Extractor
│   ├── loaders/             # CSV Data Loader
│   ├── models/              # Dataclasses & Data Model
│   ├── scrapers/            # Playwright PDDIKTI Network Interceptor
│   ├── storage/             # Streaming CSV/JSON Storage & Checkpoint Handler
│   ├── utils/               # Factual Generator, Logger, Area Matcher
│   ├── validators/          # Duplicate Auditor & Data Validator
│   ├── config.py            # Konfigurasi Path Proyek
│   └── main.py              # Entry Point CLI Orkestrator Utama
├── .env.example             # Template Environment Variables
├── requirements.txt         # Daftar Dependensi Pustaka Python
└── README.md                # Dokumentasi Utama Repositori
```

---

## 👥 Tim & Handover

- **Proyek:** Indonesian Campus Data Pipeline & Enrichment Engine
- **Sprint:** Sprint 1 – _Scrapping & Build Data Structure_
- **Author / Data Engineer:** Yasa
- **Kontak & Kontribusi:** Silakan ajukan _Pull Request_ atau diskusikan pada channel komunikasi tim untuk pengembangan fitur berikutnya.

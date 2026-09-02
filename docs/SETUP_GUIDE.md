# 🚀 Panduan Setup & Instalasi Lingkungan (*Setup Guide*)

Panduan ini ditujukan bagi anggota tim, *developer*, atau *collaborator* baru yang akan menjalankan, mengembangkan, atau menguji pipeline data **Indonesian Higher Education Data Engine** pada mesin lokal.

---

## 📋 1. Persyaratan Sistem (*System Prerequisites*)

Sebelum memulai, pastikan perangkat Anda telah terpasang perangkat lunak berikut:
* **Sistem Operasi:** Windows 10/11, macOS (Intel/Apple Silicon), atau Linux (Ubuntu 20.04+).
* **Python:** Versi `3.10` atau `3.11` (Disarankan).
* **Git:** Versi terbaru.
* **Koneksi Internet:** Diperlukan untuk mengakses API PDDIKTI, Google Cloud, Wikipedia, dan mengunduh browser Chromium Playwright.

---

## 🛠️ 2. Langkah-Langkah Instalasi (*Step-by-Step Setup*)

### Langkah 1: Clone Repositori
Buka terminal Anda (Command Prompt / PowerShell / Bash) lalu clone repositori ke direktori kerja Anda:

```bash
git clone <URL_REPOSITORY_ANDA>
cd top-hundred-indonesian-campus
```

---

### Langkah 2: Buat & Aktifkan Virtual Environment (*venv*)

Sangat disarankan menggunakan virtual environment agar dependensi proyek terisolasi dengan rapi:

#### Di Windows (PowerShell / Command Prompt):
```bash
# Membuat virtual environment bernama 'venv'
python -m venv venv

# Mengaktifkan virtual environment di PowerShell
.\venv\Scripts\Activate.ps1

# ATAU jika menggunakan Command Prompt (cmd.exe):
.\venv\Scripts\activate.bat
```

> **Catatan Windows PowerShell:** Jika muncul pesan error `execution of scripts is disabled on this system`, jalankan perintah berikut di PowerShell (Run as Administrator):
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

#### Di macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Langkah 3: Install Dependensi Python

Pasang seluruh pustaka yang tercantum dalam `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Langkah 4: Install Browser Engine Playwright

Pipeline scraping PDDIKTI menggunakan Playwright. Anda perlu mengunduh binary browser Chromium yang diperlukan:

```bash
playwright install chromium
```

*(Opsional untuk Linux server/CI: jika ada dependensi sistem OS yang kurang, jalankan `playwright install-deps chromium`).*

---

## 🔑 3. Konfigurasi File Environment (`.env`)

Pipeline memerlukan Google Maps API Key untuk pengayaan koordinat geospasial dan resolusi website terverifikasi.

1. Salin template `.env.example` menjadi `.env`:
   ```bash
   # Di Windows (CMD):
   copy .env.example .env

   # Di Windows (PowerShell) / macOS / Linux:
   cp .env.example .env
   ```

2. Buka file `.env` di text editor (VS Code / Notepad) dan sesuaikan nilainya:
   ```env
   # [WAJIB] API Key Google Cloud Platform dengan akses ke:
   # 1. Places API (New)
   # 2. Geocoding API
   GOOGLE_MAPS_API_KEY="your_google_maps_api_key_here"

   # [OPSIONAL] Cloudinary (Hanya jika ingin upload otomatis banner ke Cloud Storage)
   CLOUDINARY_CLOUD_NAME=""
   CLOUDINARY_API_KEY=""
   CLOUDINARY_API_SECRET=""
   ```

> **Cara Memperoleh Google Maps API Key:**
> 1. Buka [Google Cloud Console](https://console.cloud.google.com/).
> 2. Buat project baru (misal: `Campus-Data`).
> 3. Buka menu **APIs & Services** $\rightarrow$ **Library**, lalu aktifkan **Places API (New)** dan **Geocoding API**.
> 4. Buat kredensial **API Key** di menu **Credentials**, lalu tempelkan kuncinya ke file `.env`.

---

## 🧪 4. Uji Coba Verifikasi Instalasi (*Verification Test*)

Jalankan perintah pengujian sampel kecil (5 kampus) untuk memastikan semua komponen (Google Maps, Wikipedia, Parser, dan Storage) berfungsi normal:

```bash
python -m src.main --enrich-kampus --target-count 5
```

### Indikator Keberhasilan:
Terminal akan menampilkan log proses seperti berikut:
```text
============================================================
GOOGLE MAPS, WIKIPEDIA & WEBSITE LOGO CAMPUS ENRICHMENT
============================================================
Source Records  : 6765
├─ Status Aktif      : 4303 (Priority 1)
├─ Status Pembinaan  : 25 (Priority 2)
├─ Total Eligible    : 4328
├─ Deduped Identical : 2 duplicate rows (same kode_pt) removed
├─ Total Unique PT   : 4326 to be processed
└─ Excluded (Other)  : 2437 (Tutup, Alih Bentuk, Alih Kelola)

[0001/0005] Sekolah Tinggi Ilmu Administrasi Aan (Kode: 053019, Status: Aktif)
    Status: ENRICHED (Coords ✓, Web (GMaps) ✓, Logo (Web) ✓, Desc (Factual) ✓)
...
============================================================
CAMPUS ENRICHMENT SUMMARY (10-COLUMN STRICT SCHEMA)
============================================================
Processed   : 5
Output CSV  : data/output/kampus_extracted.csv
Output JSON : data/output/kampus_extracted.json
============================================================
```

Periksa file hasil di `data/output/kampus_extracted.csv`. Jika file terisi dengan 10 kolom rapi, instalasi Anda **100% Berhasil!** 🎉

---

## ❓ 5. Pemecahan Masalah (*Troubleshooting*)

| Gejala Masalah | Penyebab Umum | Solusi |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'playwright'` | Virtual environment belum aktif atau dependensi belum terinstall. | Jalankan `.\venv\Scripts\activate` lalu `pip install -r requirements.txt`. |
| `Error: Google Maps API Key not found!` | File `.env` belum dibuat atau key kosong. | Pastikan file `.env` ada di root folder dan memuat `GOOGLE_MAPS_API_KEY="AIza..."`. |
| `Places API HTTPError 403 / REQUEST_DENIED` | API Key belum diaktifkan untuk Places API (New). | Buka Google Cloud Console, pastikan **Places API (New)** dan **Geocoding API** berstatus *Enabled*. |
| Ekstraksi terhenti di tengah jalan (*Network Disconnect*) | Koneksi internet terputus atau batas kuota API tercapai sementara. | Jalankan kembali perintah dengan flag `--resume`: `python -m src.main --enrich-kampus --resume`. |

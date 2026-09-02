# 💻 Panduan Antarmuka CLI (*CLI Usage Guide*)

Dokumen ini berisi referensi lengkap perintah baris perintah (*Command Line Interface*), opsi flag, parameter input, serta contoh skenario penggunaan untuk menjalankan pipeline **Indonesian Campus Data Pipeline**.

---

## 1. Perintah Dasar (*Basic Command Structure*)

Pipeline dijalankan melalui modul utama Python:

```bash
python -m src.main [MODE_UTAMA] [PILIHAN_TAMBAHAN]
```

---

## 2. Pilihan Mode Utama (*Mutually Exclusive Modes*)

Anda wajib memilih salah satu mode utama berikut saat menjalankan pipeline:

| Flag Perintah | Deskripsi Mode | Kapan Digunakan |
| :--- | :--- | :--- |
| **`--enrich-kampus`** | **Pipeline Utama Pengayaan Kampus (10 Kolom Presisi).** Memfilter kampus aktif/pembinaan dari master PDDIKTI, lalu memperkayanya via Google Maps, Wikipedia, dan Web Logo Extractor. | **Mode operasional harian / produksi.** Menghasilkan `kampus_extracted.csv`. |
| **`--audit-duplicates`** | Menjalankan audit analitik duplikasi nama kampus dan kode PT tanpa mengubah data apa pun. Menghasilkan laporan indikator JSON. | Untuk diagnostik integritas data dan mengecek frekuensi nama kampus ganda. |
| **`--pddikti-api`** | Menjalankan penarikan data mentah dari seluruh kampus se-Indonesia langsung melalui portal resmi PDDIKTI via Playwright API Interceptor. | Untuk memperbarui data master dari server PDDIKTI (menghasilkan 6.765 data mentah). |
| **`--pddikti-export-csv`** | Mengekspor berkas mentah `pddikti_campuses.json` menjadi berkas CSV 23 kolom lengkap `pddikti_campuses.csv`. | Saat ingin mengubah format data mentah JSON ke CSV tabular. |
| **`--pddikti-dir`** | Scraper kartu pencarian PDDIKTI berbasis DOM halaman web. | Mode diagnostik alternatif. |
| **`--pddikti-poc`** | Proof of Concept scraper pencarian keyword PDDIKTI. | Pengujian awal modul pencarian. |
| **`--master`** | Mode pemuatan data target menggunakan file master CSV lokal (Legacy Quipper). | Mode historis / pengujian master CSV. |
| **`--discover`** | Mode penelusuran direktori kampus (Legacy Quipper). | Mode historis penelusuran web directory. |

---

## 3. Opsi Parameter Tambahan (*Optional Flags*)

| Parameter | Tipe | Nilai Default | Penjelasan |
| :--- | :---: | :---: | :--- |
| **`--target-count <N>`** | Integer | `None` (Semua data) | Membatasi jumlah kampus yang diproses sebanyak $N$ kampus pertama. Sangat berguna untuk pengujian cepat (misal: `--target-count 5`). |
| **`--resume`** | Flag | `False` | Melanjutkan proses ekstraksi dari titik *checkpoint* terakhir yang tersimpan di `kampus_extracted_checkpoint.json`. |
| **`--gmaps-key <KEY>`** | String | Membaca dari `.env` | Menyediakan Google Maps API Key langsung via argumen CLI tanpa harus menulis di `.env`. |
| **`--headless`** | Flag | `False` (Headful) | Menjalankan browser Playwright dalam mode latar belakang (*headless*). Defaultnya `headful` agar pengguna dapat menyelesaikan verifikasi CAPTCHA jika diperlukan. |
| **`--pddikti-url <URL>`** | String | URL pencarian PT Universitas | Mengatur custom endpoint URL pencarian pada portal resmi PDDIKTI. |
| **`--json`** | Flag | `False` | Hanya menghasilkan file output berekstensi JSON. |
| **`--csv`** | Flag | `False` | Hanya menghasilkan file output berekstensi CSV. |
| **`--all`** | Flag | `True` (Default) | Menghasilkan file luaran dalam format CSV dan JSON sekaligus. |

---

## 4. Contoh Skenario Penggunaan (*Practical Scenarios*)

### Skenario 1: Uji Coba Cepat Pengayaan 5 Kampus
Gunakan perintah ini untuk memvalidasi bahwa API Key Google Maps, koneksi internet, dan parser berjalan normal:
```bash
python -m src.main --enrich-kampus --target-count 5
```

---

### Skenario 2: Menjalankan Pengayaan Penuh Seluruh Kampus Indonesia
Memproses seluruh $\approx 4.326$ kampus berstatus Aktif dan Pembinaan di seluruh Indonesia:
```bash
python -m src.main --enrich-kampus
```

---

### Skenario 3: Melanjutkan Proses yang Terputus (*Resume Checkpoint*)
Jika proses sempat terhenti di tengah jalan karena koneksi internet terputus atau komputer dimatikan:
```bash
python -m src.main --enrich-kampus --resume
```
*Sistem akan otomatis melewati seluruh kampus yang sudah tersimpan dan melanjutkan ke kampus berikutnya.*

---

### Skenario 4: Menjalankan Audit Duplikasi Saja
Menghasilkan ringkasan dan file diagnosa duplikasi di `data/output/duplicate_campus_indicator.json`:
```bash
python -m src.main --audit-duplicates
```

---

### Skenario 5: Menarik Ulang Data Mentah dari Server PDDIKTI
Melakukan scrape ulang dari portal Kemendiktisaintek untuk seluruh Indonesia:
```bash
# Menjalankan scraper (akan membuka browser interaktif Playwright)
python -m src.main --pddikti-api

# Setelah selesai, ekspor ke CSV 23 kolom
python -m src.main --pddikti-export-csv
```

---

## 5. Memahami Indikator Status pada Log Terminal

Saat pipeline `--enrich-kampus` berjalan, setiap baris kampus akan menampilkan status pengayaan data:

```text
[0001/4326] Sekolah Tinggi Ilmu Administrasi Aan (Kode: 053019, Status: Aktif)
    Status: ENRICHED (Coords ✓, Web (GMaps) ✓, Logo (Web) ✓, Desc (Factual) ✓)

[0003/4326] Universitas Islam Negeri Ar-Raniry Banda Aceh (Kode: 201011, Status: Aktif)
    Status: ENRICHED (Coords ✓, Web (GMaps) ✓, Logo (Wiki) ✓, Desc (Wiki) ✓)
```

### Arti Tag Status:
* **`Coords ✓`**: Koordinat spasial PostGIS WKT `POINT(lng lat)` berhasil diperoleh dari Google Places / Geocoding API.
* **`Web (GMaps) ✓`**: Website terverifikasi berhasil diambil dari Google Places API `websiteUri`.
* **`Logo (Wiki) ✓`**: Logo resmi resolusi tinggi berhasil diperoleh dari artikel Wikipedia / Wikimedia Commons.
* **`Logo (Web) ✓`**: Logo resmi berhasil diekstrak langsung dari website resmi kampus via crawler HTML.
* **`Desc (Wiki) ✓`**: Narasi sejarah/profil asli berhasil diambil dari Wikipedia.
* **`Desc (Factual) ✓`**: Narasi profil disusun secara otomatis melalui *Factual Description Generator* berbasis metadata resmi PDDIKTI.

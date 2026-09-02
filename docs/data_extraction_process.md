# Dokumentasi Proses Ekstraksi Data Kampus (EduGates)

## 1. Kontrol Dokumen

| Metadata                        | Keterangan                                    |
| :------------------------------ | :-------------------------------------------- |
| **Nama Proyek**                 | **EduGates**                                  |
| **Sprint**                      | Sprint 1 – _Scrapping & Build Data Structure_ |
| **Nama Tugas**                  | Extract Data Campuss                          |
| **Penanggung Jawab / Engineer** | **I Nengah Sumerta Yasa (Yasa)**              |
| **Peran**                       | Technical Data Engineer                       |
| **Status Dokumen**              | **Final / Approved**                          |
| **Versi Dokumen**               | 1.0.0                                         |
| **Terakhir Diperbarui**         | 20 Agustus 2026                               |

---

## 2. Tujuan (_Objectives_)

Tujuan dari proses ekstraksi data ini adalah:

1. **Membangun Master Dataset Kampus Indonesia:** Mengumpulkan, memfilter, dan menstandarisasi data seluruh perguruan tinggi di Indonesia yang berstatus operasional resmi (**Aktif** dan **Pembinaan**) untuk kebutuhan basis data platform EduGates.
2. **Pengayaan Data Multi-Sumber (_Multi-Source Enrichment_):** Memperkaya data legalitas dasar dari PDDIKTI dengan titik koordinat spasial (_PostGIS WKT_), website resmi terverifikasi, logo institusi beresolusi tinggi, serta narasi profil sejarah kelembagaan.
3. **Kepatuhan Skema Basis Data:** Memastikan struktur dataset akhir selaras 100% dengan skema tabel relasional `KAMPUS` (Tabel 3.1 pada `docs/data-structure.md`) tanpa ada anomali format data (_missing coordinates_, _broken images_, atau _inaccurate biographies_).

---

## 3. Sumber Data & URL Target

Pipeline ekstraksi memanfaatkan 4 sumber data utama yang saling melengkapi:

| Sumber Data                       | Peran / Entitas Data                                                                                           | Endpoint / URL Target                                         |
| :-------------------------------- | :------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------ |
| **PDDIKTI Kemdiktisaintek**       | _Source of Truth_ identitas kampus, kode PT, akreditasi, jenis PT, dan pembina                                 | `https://pddikti.kemdiktisaintek.go.id/search/pt/Universitas` |
| **Google Places API (New)**       | Titik koordinat spasial (`location`), alamat terstandar (`formattedAddress`), dan website segar (`websiteUri`) | `https://places.googleapis.com/v1/places:searchText`          |
| **Google Geocoding API**          | _Fallback_ resolusi koordinat berbasis alamat wilayah                                                          | `https://maps.googleapis.com/maps/api/geocode/json`           |
| **Wikipedia & Wikimedia Commons** | Narasi profil/sejarah resmi kampus (`extract`) dan logo vektor/PNG transparan HD (`originalimage`)             | `https://id.wikipedia.org/api/rest_v1/page/summary/{title}`   |
| **Official Campus Websites**      | _Fallback_ ekstraksi aset logo langsung dari tag HTML (`apple-touch-icon`, `og:image`, `favicon`)              | `website_url` terverifikasi dari masing-masing kampus         |

---

## 4. Metodologi Ekstraksi & Alat yang Digunakan

```
   ┌────────────────────────┐
   │  PDDIKTI Master Scrape │  (Playwright API Interceptor)
   └───────────┬────────────┘
               │ 6.765 Kampus Mentah
               ▼
   ┌────────────────────────┐
   │   Filter & Deduplikasi │  (Aktif = P1, Pembinaan = P2, Exclude Identical Kode PT)
   └───────────┬────────────┘
               │ ~4.300 Kampus Layak
               ▼
   ┌──────────────────────────────────────────────────────────┐
   │             Pipeline Pengayaan Data (Enrichment)         │
   ├──────────────────────────┬───────────────────────────────┤
   │ Google Places API (New)  │ Koordinat WKT, Alamat, Web    │
   │ Wikipedia REST API       │ Narasi Sejarah & Logo HD      │
   │ Campus Logo Extractor    │ Fallback Logo dari Web Resmi  │
   │ Factual Generator        │ Fallback Narasi PDDIKTI       │
   └───────────┬──────────────────────────────────────────────┘
               │
               ▼
   ┌────────────────────────┐
   │  Output Bersih (10 Col)│  data/output/kampus_extracted.csv (.json)
   └────────────────────────┘
```

### Alat & Teknologi (_Technology Stack_):

- **Bahasa Pemrograman:** Python 3.11+
- **Browser Automation & Network Interceptor:** `Playwright` (mengekstrak data tabular PDDIKTI melalui intersepsi HTTP API browser untuk melewati proteksi bot).
- **API Integration:** `urllib.request` dengan _Field Masking_ ketat (`places.displayName,places.formattedAddress,places.location,places.websiteUri`) guna menghemat kuota Google Cloud.
- **HTML & Web Asset Parser:** `BeautifulSoup4` & `urllib.parse` untuk ekstraksi favicon dan logo resolusi tinggi.
- **Storage Handler:** Modul `csv` (dengan encoding `utf-8-sig`) dan `json` dengan mekanisme _atomic streaming write_.

---

## 5. Kriteria & Parameter Data

### A. Kriteria Penyaringan Status Institusi (_Status PT Filter_)

Dataset master hasil scrape awal memuat **6.765 baris institusi**. Diterapkan aturan filter selektif:

1. **Prioritas 1 (`status_pt == 'Aktif'`):** $\approx 4.303$ kampus yang beroperasi aktif secara normal.
2. **Prioritas 2 (`status_pt == 'Pembinaan'`):** $\approx 25$ kampus yang masih berdiri dan beroperasi di bawah evaluasi/pembinaan administratif kementerian.
3. **Eksklusi Bersih:** $\approx 2.437$ kampus berstatus _Alih Bentuk_, _Tutup_, dan _Alih Kelola_ otomatis dilewati (_filtered out_).

### B. Aturan Penanganan Duplikasi (_Deduplication Rules_)

- **Kasus Nama Sama, Kode PT Berbeda:** **Tetap dipertahankan.** (Merupakan entitas legal mandiri, kampus cabang PSDKU, atau dualisme pencatatan lintas kementerian seperti UKI Tomohon).
- **Kasus Kode PT Sama Persis:** **Dideduplikasi.** (Hanya 1 baris pertama yang disimpan guna membersihkan duplikasi teknis hasil scraping).

### C. Alur Bertingkat Resolusi Data (_Multi-Tier Resolution_)

1. **`website_url`:** Menolak website usang dari PDDIKTI mentah. Murni mengambil website segar yang terverifikasi dari **Google Places API (`websiteUri`)** atau **Wikipedia**.
2. **`logo_url`:**
   - _Tier 1:_ Ambil dari **Wikimedia Commons / Wikipedia API** (aset vektor PNG transparan HD).
   - _Tier 2 (Fallback):_ Ekstrak langsung dari **Website Resmi Kampus** via `CampusLogoExtractor`.
   - _Tier 3:_ Jika tidak ditemukan di kedua sumber $\rightarrow$ `NULL` / string kosong.
3. **`deskripsi`:**
   - _Tier 1:_ Ambil narasi sejarah/profil asli dari **Wikipedia API**.
   - _Tier 2 (Fallback):_ Buat deskripsi berbasis **Factual Description Generator** dari metadata resmi PDDIKTI (menjamin tidak ada narasi kosong).
4. **`koordinat`:** Disimpan dalam standar OGC PostGIS `geography(Point, 4326)`: **`POINT(longitude latitude)`**.
5. **`banner_url`:** Ditunda pada fase ini (_diisi NULL_).

---

## 6. Proses Verifikasi & Kontrol Kualitas (_QA & Validation_)

Untuk memastikan integritas data terbebas dari anomali, diterapkan mekanisme kontrol kualitas berikut:

### 1. 4 Lapis Guardrail Wikipedia (_Anti-False Positive_)

Mencegah kesalahan pencocokan artikel (misalnya nama kampus pendek mencocokkan artikel tokoh/politisi):

- **Guardrail 1 (Konteks Pendidikan):** Ekstrak artikel wajib memuat kata kunci institusi (`universitas`, `institut`, `sekolah tinggi`, `akademi`, `politeknik`, `kampus`).
- **Guardrail 2 (Penolakan Biografi):** Menolak artikel yang dominan dengan kata kunci politisi (`politisi`, `gubernur`, `anggota dpr`, `partai`, `kelahiran`, `meninggal`).
- **Guardrail 3 (Kemiripan Judul):** Judul artikel Wikipedia wajib memiliki irisan kata kunci signifikan dengan nama kampus yang dicari.
- **Guardrail 4 (Filter Foto Tokoh):** Menolak file gambar bertema potret manusia (`kpu_`, `portrait`, `potret`, `foto_`, `face`, `headshot`).

### 2. Validasi Geospasial PostGIS

- Koordinat divalidasi dalam batas koordinat astronomis Indonesia: $\text{Longitude } (95.0^{\circ} \text{ s.d. } 141.0^{\circ})$ dan $\text{Latitude } (-11.0^{\circ} \text{ s.d. } 6.0^{\circ})$.
- Urutan koordinat dipastikan memenuhi kaidah $(X, Y) = (\text{Bujur, Lintang})$.

### 3. Checkpoint & Resume Mechanism

Pipeline dilengkapi dengan `kampus_extracted_checkpoint.json`. Jika terjadi kendala jaringan (koneksi terputus / _rate limit_), proses dapat dilanjutkan kembali (`--resume`) tanpa mengulang ekstraksi kampus yang sudah tersimpan.

---

## 7. Struktur Data Akhir & Penyimpanan

Dataset akhir diekspor ke dalam direktori `data/output/` dengan format **CSV (`utf-8-sig`)** dan **JSON**, memuat **tepat 10 kolom presisi** sesuai Tabel 3.1 Entitas `KAMPUS`:

| No  | Nama Kolom         | Tipe Data Target        | Nullable | Deskripsi & Contoh Nilai                                                                    |
| :-: | :----------------- | :---------------------- | :------: | :------------------------------------------------------------------------------------------ |
|  1  | `kode_kampus`      | `varchar(20)`           |    NO    | Kode unik registrasi PT Kemendikbud (Contoh: `"053019"`)                                    |
|  2  | `nama_kampus`      | `varchar(255)`          |    NO    | Nama resmi perguruan tinggi (Contoh: `"Sekolah Tinggi Ilmu Administrasi Aan"`)              |
|  3  | `singkatan_kampus` | `varchar(50)`           |   YES    | Akronim / nama singkatan resmi (Contoh: `"STIA AAN"`)                                       |
|  4  | `akreditasi`       | `varchar(20)`           |   YES    | Peringkat akreditasi BAN-PT (Contoh: `"Baik Sekali"`, `"Unggul"`)                           |
|  5  | `alamat`           | `text`                  |   YES    | Alamat fisik terstandarisasi dari Google Maps (Contoh: `"Jl. Blunyah Gede Blunyahrejo..."`) |
|  6  | `website_url`      | `varchar(500)`          |   YES    | URL website aktif terverifikasi (Contoh: `"https://stia-aan.ac.id/"`)                       |
|  7  | `logo_url`         | `varchar(500)`          |   YES    | URL aset logo resolusi tinggi Wikimedia / Web resmi                                         |
|  8  | `banner_url`       | `varchar(500)`          |   YES    | _NULL_ (Ditunda untuk migrasi cloud storage)                                                |
|  9  | `deskripsi`        | `text`                  |   YES    | Narasi profil/sejarah resmi kampus                                                          |
| 10  | `koordinat`        | `geography(Point,4326)` |   YES    | Format WKT PostGIS: `"POINT(110.366156 -7.770319)"`                                         |

### Lokasi Berkas Output:

- **CSV File:** `data/output/kampus_extracted.csv` _(Siap di-import via PostgreSQL `COPY` command)_
- **JSON File:** `data/output/kampus_extracted.json`
- **Laporan Audit Duplikasi:** `data/output/duplicate_campus_indicator.json`

---

## 8. Panduan Eksekusi Pipeline

Untuk menjalankan kembali atau memvalidasi pipeline ekstraksi, jalankan perintah berikut pada terminal:

```bash
# 1. Menjalankan audit indikator duplikasi nama kampus:
python -m src.main --audit-duplicates

# 2. Uji coba pengayaan pada sampel kecil (5 kampus):
python -m src.main --enrich-kampus --target-count 5

# 3. Menjalankan ekstraksi menyeluruh untuk seluruh kampus aktif/pembinaan se-Indonesia:
python -m src.main --enrich-kampus

# 4. Melanjutkan proses jika sempat terhenti (Resume Checkpoint):
python -m src.main --enrich-kampus --resume
```

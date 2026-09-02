# Project Agents Context

## Tujuan Project
Project ini akan melakukan web scraping ke `https://campus.quipper.com/directory/{slug}` untuk mengambil profil 100 kampus Indonesia berdasarkan master data CSV.

## Arsitektur Saat Ini
Data flow berjalan sebagai berikut:
`CSV Master Data` -> `CSV Loader` -> `Campus Name` -> `Slug Generator` -> `Target URL` -> `HTTP Scraper` -> `Quipper Extractor` -> `Quipper Mapper` -> `Data Validator` -> `JSON Storage`

Tanggung jawab utama:
- Target utama mapping data adalah mengikuti skema yang ada pada `docs/data-structure.md`.
- File CSV `master_data_area_code.csv` adalah source of truth untuk penamaan kode wilayah.

## Struktur Project Aktual
- `data/input/`: Berisi CSV input dan master wilayah.
- `data/reference/`: Referensi format respons HTML dan JSON Quipper.
- `data/output/`: Tempat output JSON proof of concept.
- `src/loaders/`: Fungsi load CSV (CSV Loader).
- `src/utils/`: Helper functions (Slug Generator, Area Matcher).
- `src/scrapers/`: Bertugas melakukan HTTP request ke target url tanpa DOM parsing.
- `src/extractors/`: Bertugas mencari tag `<script>` dengan `data-hypernova-key="SiteRoot"`, mengambil isi JSON mentah.
- `src/models/`: Menampung representasi Mapped Data menggunakan dataclasses.
- `src/mappers/`: Berisi logic memetakan raw JSON Quipper ke skema `docs/data-structure.md` (mengubah jenis kampus, ekstrak akreditasi dari pola nama prodi, memilih URL image).
- `src/validators/`: Memvalidasi kelengkapan data (mengeluarkan status `VALID`, `WARNING`, atau `ERROR`).
- `src/storage/`: Logic penyimpanan object python menjadi JSON.

## Batasan dan Aturan Khusus Project (Tahap Saat Ini)
- **Database:** Tidak ada integrasi database, primary key, atau foreign key. Foreign Key diwakili oleh kode asli (seperti `kode_wilayah` atau `nama` jenis kampus).
- **DOM Parsing:** Sebisa mungkin menggunakan JSON embedded di dalam `<script>`, hindari CSS/DOM scraping jika data sudah ada di JSON.
- **Akreditasi:** Untuk prodi, jika akreditasi disematkan dalam nama prodi dengan format "(A)", ekstrak dan hilangkan dari nama.
- **Wilayah:** Cari wilayah melalui normalisasi dan pencocokan kandidat dengan `master_data_area_code.csv`. Gunakan pesan `UNMATCHED_WILAYAH` atau `AMBIGUOUS_WILAYAH` bila terjadi ketidaksesuaian.
- **Data Kosong:** Jika tidak ada data di resource Quipper (seperti daya_tampung, banner), kosongkan data (berikan null) dan catat warning. Jangan pernah mengarang data (menebak).
- **Development Workflow:** Proof of Concept saat ini hanya dilakukan pada *SATU* kampus untuk memvalidasi alur secara lengkap, sebelum dijalankan massal ke seluruh daftar kampus.

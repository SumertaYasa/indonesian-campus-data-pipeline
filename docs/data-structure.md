## 2.1 MASTER_WILAYAH

Menyimpan data wilayah administratif (Provinsi, Kabupaten/Kota) mengikuti kode resmi Kemendagri/BPS.

| Field        | Tipe         | Keterangan                                                        |
| ------------ | ------------ | ----------------------------------------------------------------- |
| id           | bigint       | Primary Key                                                       |
| kode_wilayah | varchar(15)  | Unik, kode resmi Kemendagri/BPS                                   |
| nama         | varchar(100) | Nama wilayah                                                      |
| tingkat      | varchar(20)  | "Provinsi" atau "Kabupaten-Kota"                                  |
| parent_id    | bigint (FK)  | Merujuk ke wilayah induk (Provinsi), nullable untuk data Provinsi |

---

## 2.2 MASTER_JENIS_KAMPUS

Menyimpan jenis kampus, misalnya Negeri, Swasta, atau Kedinasan.

| Field | Tipe        | Keterangan                                 |
| ----- | ----------- | ------------------------------------------ |
| id    | bigint      | Primary Key                                |
| nama  | varchar(50) | Unik — contoh: Negeri / Swasta / Kedinasan |

---

### 3.1 KAMPUS

Data utama sebuah kampus/universitas.

| Field            | Tipe                   | Keterangan                                             |
| :--------------- | :--------------------- | :----------------------------------------------------- |
| id               | bigint                 | Primary Key                                            |
| nama_kampus      | varchar(255)           | Nama kampus                                            |
| slug             | varchar(280)           | Unik, untuk URL                                        |
| id_jenis_kampus  | bigint (FK)            | Merujuk ke MASTER_JENIS_KAMPUS                         |
| akreditasi       | varchar(20)            | Nilai akreditasi kampus                                |
| wilayah_id       | bigint (FK)            | Merujuk ke MASTER_WILAYAH                              |
| alamat           | text                   | Alamat lengkap                                         |
| website_url      | varchar(255)           | URL website resmi                                      |
| logo_url         | varchar(500)           | URL logo                                               |
| banner_url       | varchar(500)           | URL gambar banner                                      |
| deskripsi        | text                   | Deskripsi kampus                                       |
| search_vector    | tsvector               | Index pencarian teks (full-text search, GIN index)     |
| singkatan_kampus | varchar(10)            | Singkatan kampus terkait                               |
| kode_kampus      | bigint                 | Kode kampus terkait                                    |
| koordinat        | geography(Point, 4326) | Titik koordinat spasial kampus. Membutuhkan GiST index |

### Data yang Perlu Disiapkan

Data utama yang perlu dikumpulkan oleh tim untuk setiap kampus:

- **nama_kampus**: Nama lengkap kampus.
- **id_jenis_kampus**: Kategori atau jenis kampus (merujuk ke MASTER_JENIS_KAMPUS).
- **wilayah_id**: Wilayah lokasi kampus (merujuk ke MASTER_WILAYAH).
- **akreditasi**: Nilai akreditasi kampus.
- **alamat**: Alamat lengkap kampus.
- **logo_url**: URL gambar logo kampus.
- **banner_url**: URL gambar banner kampus.
- **singkatan_kampus**: Singkatan resmi kampus.
- **kode_kampus**: Kode identitas kampus.

### Catatan Penting

- **Koordinat**: Data latitude dan longitude perlu diekstraksi/dikonversi dari alamat kampus untuk mengisi field `koordinat` (tipe `geography(Point, 4326)`).
- **Deskripsi**: Konten untuk `deskripsi` kampus perlu didiskusikan lebih lanjut.

---

## 3.2 FAKULTAS

Fakultas yang dimiliki sebuah kampus.

| Field      | Tipe         | Keterangan                                                                              |
| ---------- | ------------ | --------------------------------------------------------------------------------------- |
| id         | bigint       | Primary Key                                                                             |
| kampus_id  | bigint (FK)  | Merujuk ke KAMPUS. Jika kampus dihapus, data fakultas ikut terhapus (ON DELETE CASCADE) |
| nama       | varchar(255) | Nama fakultas                                                                           |
| keterangan | text         | Keterangan tambahan                                                                     |

---

## 3.3 PRODI

Program studi di bawah sebuah fakultas.

| Field        | Tipe         | Keterangan                                                                          |
| ------------ | ------------ | ----------------------------------------------------------------------------------- |
| id           | bigint       | Primary Key                                                                         |
| fakultas_id  | bigint (FK)  | Merujuk ke FAKULTAS. Jika fakultas dihapus, prodi ikut terhapus (ON DELETE CASCADE) |
| nama         | varchar(255) | Nama program studi                                                                  |
| jenjang      | varchar(5)   | D3 / D4 / S1 / S2 / S3                                                              |
| akreditasi   | varchar(20)  | Nilai akreditasi prodi                                                              |
| daya_tampung | integer      | Kuota penerimaan mahasiswa                                                          |
| keterangan   | text         | Keterangan tambahan                                                                 |

**Alur data:** `KAMPUS` → punya banyak `FAKULTAS` → tiap fakultas punya banyak `PRODI`.

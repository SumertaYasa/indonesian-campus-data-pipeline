from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LokasiMapped:
    alamat: str

@dataclass
class ProdiMapped:
    nama: str
    jenjang: str
    scraped_at: str
    akreditasi: Optional[str] = None
    daya_tampung: Optional[int] = None
    keterangan: Optional[str] = None

@dataclass
class FakultasMapped:
    nama: str
    scraped_at: str
    keterangan: Optional[str] = None
    prodi: List[ProdiMapped] = field(default_factory=list)

@dataclass
class KampusMapped:
    nama: str
    slug: str
    scraped_at: str
    jenis_kampus: Optional[str] = None  # Natural key mapped to MASTER_JENIS_KAMPUS
    akreditasi: Optional[str] = None
    location_type: str = "UNKNOWN"
    alamat: List[LokasiMapped] = field(default_factory=list)
    website: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    deskripsi: Optional[str] = None
    fakultas: List[FakultasMapped] = field(default_factory=list)

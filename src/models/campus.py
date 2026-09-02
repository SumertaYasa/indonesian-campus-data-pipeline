from dataclasses import dataclass
from typing import Optional

@dataclass
class Campus:
    """
    Data model representing an Indonesian Campus.
    Fields to be extracted: nama, jenis, wilayah, akreditasi, alamat, logo, banner
    """
    nama: str
    jenis: Optional[str] = None
    wilayah: Optional[str] = None
    akreditasi: Optional[str] = None
    alamat: Optional[str] = None
    logo: Optional[str] = None
    banner: Optional[str] = None

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

class PddiktiCsvStorage:
    """
    Dedicated CSV Storage and Exporter for PDDIKTI campus data.
    Flattens and prunes nested discovery & detail structures into 23 clean tabular columns.
    """

    HEADERS = [
        'kode_pt',
        'nama_pt',
        'singkatan',
        'jenis_pt',
        'pembina',
        'status_pt',
        'akreditasi',
        'jumlah_prodi',
        'range_biaya_kuliah',
        'sk_pendirian',
        'tgl_sk_pendirian',
        'tgl_berdiri',
        'alamat',
        'kecamatan',
        'kab_kota',
        'provinsi',
        'kode_pos',
        'telepon',
        'fax',
        'email',
        'website',
        'id_sp',
        'scraped_at'
    ]

    def __init__(self, output_dir: Path, filename: str = "pddikti_campuses.csv"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.output_dir / filename

    @staticmethod
    def _clean_date(date_str: Optional[str]) -> str:
        """Normalizes ISO timestamp strings (e.g. '2005-03-03T00:00:00Z') to 'YYYY-MM-DD'."""
        if not date_str or not isinstance(date_str, str):
            return ""
        s = date_str.strip()
        if not s or s == "-":
            return ""
        # Match YYYY-MM-DD prefix
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
        if match:
            return match.group(1)
        return s

    @staticmethod
    def _normalize_text(val: Any) -> str:
        """Strips excess whitespace and normalizes empty indicators."""
        if val is None:
            return ""
        s = str(val).strip()
        if s in ("-", "null", "None", "Tidak Diisi"):
            return ""
        # Collapse multiple spaces
        return re.sub(r"\s+", " ", s)

    def _flatten_entry(self, entry: Dict, fallback_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Flattens an individual JSON campus record (discovery + detail) into a 23-column dictionary.
        """
        disc = entry.get("discovery", {}) if isinstance(entry.get("discovery"), dict) else {}
        detail = entry.get("detail", {}) if isinstance(entry.get("detail"), dict) else {}

        # Resolve primary identifiers
        kode_pt = self._normalize_text(detail.get("kode_pt") or disc.get("kode_pt"))
        nama_pt = self._normalize_text(disc.get("nama_pt") or detail.get("nama_pt"))
        singkatan = self._normalize_text(disc.get("nama_singkat") or disc.get("singkatan") or detail.get("nm_singkat"))
        
        # Classification & Status
        jenis_pt = self._normalize_text(disc.get("jenis_pt") or detail.get("kelompok"))
        pembina = self._normalize_text(detail.get("pembina"))
        status_pt = self._normalize_text(disc.get("status_pt") or disc.get("status") or detail.get("status_pt"))
        akreditasi = self._normalize_text(disc.get("akreditasi") or detail.get("akreditasi_pt") or detail.get("status_akreditasi"))

        # Academic & Costs
        jumlah_prodi = disc.get("jumlah_prodi")
        if jumlah_prodi is None or str(jumlah_prodi).strip() in ("", "-", "None"):
            jumlah_prodi_str = ""
        else:
            jumlah_prodi_str = str(jumlah_prodi).strip()

        range_biaya = self._normalize_text(disc.get("range_biaya_kuliah"))

        # Legal & Establishment
        sk_pendirian = self._normalize_text(detail.get("sk_pendirian_sp") or detail.get("no_sk_pendirian"))
        tgl_sk_pendirian = self._clean_date(detail.get("tgl_sk_pendirian_sp") or detail.get("tanggal_sk_pendirian"))
        tgl_berdiri = self._clean_date(detail.get("tgl_berdiri_pt") or detail.get("tanggal_berdiri"))

        # Location & Address
        alamat = self._normalize_text(detail.get("alamat"))
        kecamatan = self._normalize_text(detail.get("kecamatan_pt"))
        kab_kota = self._normalize_text(disc.get("kab_kota_pt") or detail.get("kab_kota_pt"))
        provinsi = self._normalize_text(disc.get("provinsi_pt") or detail.get("provinsi_pt"))
        kode_pos = self._normalize_text(detail.get("kode_pos"))

        # Contact & Web
        telepon = self._normalize_text(detail.get("no_tel") or detail.get("telepon"))
        fax = self._normalize_text(detail.get("no_fax") or detail.get("fax"))
        email = self._normalize_text(detail.get("email"))
        website = self._normalize_text(detail.get("website"))

        # System Identifiers & Scrape Timestamp
        id_sp = self._normalize_text(disc.get("id_sp") or detail.get("id_sp") or disc.get("id"))
        scraped_at = entry.get("scraped_at") or fallback_timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            'kode_pt': kode_pt,
            'nama_pt': nama_pt,
            'singkatan': singkatan,
            'jenis_pt': jenis_pt,
            'pembina': pembina,
            'status_pt': status_pt,
            'akreditasi': akreditasi,
            'jumlah_prodi': jumlah_prodi_str,
            'range_biaya_kuliah': range_biaya,
            'sk_pendirian': sk_pendirian,
            'tgl_sk_pendirian': tgl_sk_pendirian,
            'tgl_berdiri': tgl_berdiri,
            'alamat': alamat,
            'kecamatan': kecamatan,
            'kab_kota': kab_kota,
            'provinsi': provinsi,
            'kode_pos': kode_pos,
            'telepon': telepon,
            'fax': fax,
            'email': email,
            'website': website,
            'id_sp': id_sp,
            'scraped_at': scraped_at
        }

    def save_all(self, campuses: List[Dict], timestamp: Optional[str] = None) -> str:
        """
        Saves a list of campus dictionary items into the consolidated CSV file.
        Uses UTF-8-SIG encoding for seamless Excel / Google Sheets compatibility.
        """
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.file_path, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for entry in campuses:
                row = self._flatten_entry(entry, fallback_timestamp=ts)
                writer.writerow(row)
        return str(self.file_path)

    def export_from_json(self, json_path: Path) -> str:
        """
        Reads existing JSON output file and converts all records into the consolidated CSV.
        """
        json_file = Path(json_path)
        if not json_file.exists():
            raise FileNotFoundError(f"JSON source file not found at: {json_file}")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        campuses = data.get("campuses", []) if isinstance(data, dict) else []
        return self.save_all(campuses)

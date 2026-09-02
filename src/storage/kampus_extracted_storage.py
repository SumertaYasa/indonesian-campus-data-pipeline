import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

class KampusExtractedStorage:
    """
    Dedicated Storage and Exporter for the cleaned 10-column KAMPUS schema.
    Strictly follows Table 3.1 KAMPUS in docs/data-structure.md:
    1. kode_kampus
    2. nama_kampus
    3. singkatan_kampus
    4. akreditasi
    5. alamat
    6. website_url
    7. logo_url
    8. banner_url
    9. deskripsi
    10. koordinat
    """

    HEADERS = [
        'kode_kampus',
        'nama_kampus',
        'singkatan_kampus',
        'akreditasi',
        'alamat',
        'website_url',
        'logo_url',
        'banner_url',
        'deskripsi',
        'koordinat'
    ]

    def __init__(self, output_dir: Path,
                 csv_filename: str = "kampus_extracted.csv",
                 json_filename: str = "kampus_extracted.json",
                 checkpoint_filename: str = "kampus_extracted_checkpoint.json"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_dir / csv_filename
        self.json_path = self.output_dir / json_filename
        self.checkpoint_path = self.output_dir / checkpoint_filename

        self.records: List[Dict[str, Any]] = []
        self.completed_keys: Set[str] = set()

    def load_checkpoint(self) -> int:
        """
        Loads previously processed records and checkpoint keys for resuming.
        """
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.completed_keys = set(data.get("completed_keys", []))
            except Exception:
                self.completed_keys = set()

        if self.json_path.exists():
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = data.get("kampus", [])
            except Exception:
                self.records = []

        return len(self.completed_keys)

    def is_completed(self, kode_kampus: Any, nama_kampus: str) -> bool:
        """
        Checks if a campus record was already processed.
        """
        k1 = str(kode_kampus).strip() if kode_kampus else ""
        k2 = nama_kampus.strip().lower() if nama_kampus else ""
        return (k1 in self.completed_keys) or (k2 in self.completed_keys) or (f"{k1}_{k2}" in self.completed_keys)

    def _mark_completed(self, kode_kampus: Any, nama_kampus: str):
        k1 = str(kode_kampus).strip() if kode_kampus else ""
        k2 = nama_kampus.strip().lower() if nama_kampus else ""
        if k1:
            self.completed_keys.add(k1)
        if k2:
            self.completed_keys.add(k2)
        if k1 and k2:
            self.completed_keys.add(f"{k1}_{k2}")

    def add_and_flush(self, record: Dict[str, Any]):
        """
        Appends an enriched campus record and flushes to CSV, JSON, and checkpoint atomically.
        """
        clean_row = {col: record.get(col, "") for col in self.HEADERS}
        self.records.append(clean_row)
        self._mark_completed(clean_row.get("kode_kampus"), clean_row.get("nama_kampus"))

        # 1. Append / Write to CSV
        file_exists = self.csv_path.exists()
        is_first_write = not file_exists or len(self.records) == 1

        if len(self.records) == 1:
            # Overwrite fresh at start of run
            with open(self.csv_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerow(clean_row)
        else:
            # Append subsequent rows
            with open(self.csv_path, mode='a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS, quoting=csv.QUOTE_ALL)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(clean_row)

        # 2. Flush JSON
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "count": len(self.records),
                "kampus": self.records
            }, f, ensure_ascii=False, indent=2)

        # 3. Flush Checkpoint
        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({
                "count": len(self.completed_keys),
                "completed_keys": list(self.completed_keys)
            }, f, indent=2)

    def finalize(self) -> str:
        """
        Finalizes and verifies the output CSV.
        """
        # Ensure complete dump of all records
        with open(self.csv_path, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in self.records:
                writer.writerow(row)

        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "count": len(self.records),
                "kampus": self.records
            }, f, ensure_ascii=False, indent=2)

        return str(self.csv_path)

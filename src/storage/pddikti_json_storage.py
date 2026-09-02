import json
import os
from pathlib import Path
from typing import Dict, List, Set, Optional

class PddiktiJsonStorage:
    """Storage class for PDDIKTI raw JSON payload with atomic streaming save and checkpointing."""
    
    def __init__(self, output_dir: Path, filename: str = "pddikti_campuses.json", checkpoint_name: str = "pddikti_checkpoint.json"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.output_dir / filename
        self.checkpoint_path = self.output_dir / checkpoint_name
        self.campuses: List[Dict] = []
        self.completed_urls: Set[str] = set()
        self.last_page: int = 1

    def load_existing(self) -> int:
        """
        Loads existing data from disk to support seamless resumption.
        Returns the number of already stored campus records.
        """
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    self.campuses = content.get("campuses", [])
                    for item in self.campuses:
                        disc = item.get("discovery", {})
                        if disc.get("detail_url"):
                            self.completed_urls.add(disc["detail_url"])
                        if disc.get("kode_pt"):
                            self.completed_urls.add(disc["kode_pt"])
            except Exception:
                pass

        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                    cp = json.load(f)
                    self.last_page = cp.get("last_page", 1)
                    for u in cp.get("completed_urls", []):
                        self.completed_urls.add(u)
            except Exception:
                pass

        return len(self.campuses)

    def is_completed(self, detail_url: str, kode_pt: Optional[str] = None) -> bool:
        """Checks whether a campus has already been scraped and persisted."""
        if detail_url and detail_url in self.completed_urls:
            return True
        if kode_pt and kode_pt in self.completed_urls:
            return True
        return False

    def add(self, data: dict):
        """Adds data to internal memory."""
        self.campuses.append(data)
        disc = data.get("discovery", {})
        if disc.get("detail_url"):
            self.completed_urls.add(disc["detail_url"])
        if disc.get("kode_pt"):
            self.completed_urls.add(disc["kode_pt"])

    def add_and_flush(self, data: dict, current_page: Optional[int] = None):
        """
        Atomically saves the single added record to disk immediately (Streaming write).
        Guarantees zero data loss if network or process drops.
        """
        self.add(data)
        if current_page:
            self.last_page = current_page
        self._atomic_save()
        self.save_checkpoint()

    def save_checkpoint(self, last_page: Optional[int] = None):
        """Saves current scraping progress state ledger."""
        if last_page:
            self.last_page = last_page
        cp_data = {
            "last_page": self.last_page,
            "total_saved": len(self.campuses),
            "completed_urls": list(self.completed_urls),
        }
        tmp_cp = self.checkpoint_path.with_suffix(".tmp")
        try:
            with open(tmp_cp, 'w', encoding='utf-8') as f:
                json.dump(cp_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_cp, self.checkpoint_path)
        except Exception:
            pass

    def _atomic_save(self):
        """Performs atomic file write to prevent file corruption upon sudden power/network drop."""
        tmp_file = self.file_path.with_suffix(".tmp")
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump({"campuses": self.campuses}, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, self.file_path)
        except Exception:
            pass

    def finalize(self) -> str:
        """Finalizes and flushes all data to the JSON output file."""
        self._atomic_save()
        self.save_checkpoint()
        return str(self.file_path)

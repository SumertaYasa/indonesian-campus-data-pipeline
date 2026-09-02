import csv
import re
from typing import Dict, Optional, Tuple

class AreaMatcher:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.area_data = [] # List of dicts with id, name
        self._load_data()

    def _extract_base_name(self, text: str) -> str:
        """Removes generic administrative prefixes to get the base area name."""
        # Remove 'kota administrasi', 'kabupaten administrasi', 'kota', 'kabupaten' from the start
        # Assumes text is already lowercased and whitespace-normalized
        pattern = r'^((kota|kabupaten)( administrasi)?\s+)'
        return re.sub(pattern, '', text).strip()

    def _load_data(self):
        try:
            with open(self.csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'regency_id' in row and 'regency_name' in row:
                        name_raw = row['regency_name'].strip()
                        name_norm = self._normalize(name_raw)
                        base_norm = self._extract_base_name(name_norm)
                        self.area_data.append({
                            'id': row['regency_id'].strip(),
                            'name': name_raw,
                            'name_norm': name_norm,
                            'base_norm': base_norm
                        })
        except Exception as e:
            print(f"Failed to load area data: {e}")

    def _normalize(self, text: str) -> str:
        """Lowercases, removes punctuation, and normalizes whitespace."""
        if not text:
            return ""
        text = text.lower()
        # Remove punctuation for exact comparison
        text = re.sub(r'[^\w\s]', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def find_wilayah(self, search_text: str) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """
        Attempts to find a matching wilayah code given a search string.
        search_text could be the full address or province string.
        Returns (wilayah_code, nama_wilayah, tingkat_wilayah, status_message)
        """
        if not search_text:
            return None, None, None, "UNMATCHED_WILAYAH"

        norm_search = self._normalize(search_text)
        
        # Helper to process candidates based on hierarchical rules
        def evaluate_candidates(candidates):
            if len(candidates) == 1:
                return candidates[0]['id'], candidates[0]['name'], "Kabupaten-Kota", "VALID"
            elif len(candidates) > 1:
                return None, None, None, "AMBIGUOUS_WILAYAH"
            return None, None, None, None # Signal to continue to next priority
            
        # Priority 1: Exact Match (either full name or base name)
        p1_candidates = []
        for area in self.area_data:
            if norm_search == area['name_norm'] or norm_search == area['base_norm']:
                p1_candidates.append(area)
                
        res = evaluate_candidates(p1_candidates)
        if res[3] is not None:
            return res
            
        # Priority 2: Phrase Match (name_norm)
        p2_candidates = []
        for area in self.area_data:
            # Check if name_norm appears as a distinct phrase using word boundaries
            pattern = r'\b' + re.escape(area['name_norm']) + r'\b'
            if re.search(pattern, norm_search):
                p2_candidates.append(area)
                
        res = evaluate_candidates(p2_candidates)
        if res[3] is not None:
            return res
            
        # Priority 3: Base Phrase Match (base_norm)
        p3_candidates = []
        for area in self.area_data:
            pattern = r'\b' + re.escape(area['base_norm']) + r'\b'
            if re.search(pattern, norm_search):
                p3_candidates.append(area)
                
        res = evaluate_candidates(p3_candidates)
        if res[3] is not None:
            return res
            
        return None, None, None, "UNMATCHED_WILAYAH"

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any

class DuplicateAuditor:
    """
    Audit and indicator tool for detecting duplicate campus names across datasets.
    Provides diagnostic metrics and reporting WITHOUT modifying, filtering, or cleaning the source data.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("DuplicateAuditor")

    def audit_csv(self, csv_path: Path, output_json_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Reads CSV file and scans for duplicate campus names.
        Saves diagnostic indicator JSON if output_json_path is provided.
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            self.logger.error(f"Duplicate audit failed: {csv_file} does not exist.")
            return {}

        records = []
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for r in reader:
                records.append(r)

        return self.audit_records(records, output_json_path)

    def audit_records(self, records: List[Dict[str, Any]], output_json_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Performs frequency analysis on campus records.
        """
        grouped = defaultdict(list)
        for r in records:
            # Support both raw pddikti (nama_pt) and extracted (nama_kampus)
            raw_name = (r.get("nama_pt") or r.get("nama_kampus") or "").strip()
            if not raw_name:
                continue
            key = raw_name.lower()
            grouped[key].append({
                "kode_pt": r.get("kode_pt") or r.get("kode_kampus") or "",
                "nama_pt": raw_name,
                "singkatan": r.get("singkatan") or r.get("singkatan_kampus") or "",
                "status_pt": r.get("status_pt") or "",
                "kab_kota": r.get("kab_kota") or "",
                "provinsi": r.get("provinsi") or "",
                "akreditasi": r.get("akreditasi") or ""
            })

        duplicates = []
        for norm_name, items in grouped.items():
            if len(items) > 1:
                duplicates.append({
                    "normalized_name": norm_name,
                    "display_name": items[0]["nama_pt"],
                    "occurrence_count": len(items),
                    "instances": items
                })

        # Sort duplicates by occurrence count descending
        duplicates.sort(key=lambda x: x["occurrence_count"], reverse=True)

        total_campuses = len(records)
        unique_names_count = len(grouped)
        duplicate_names_count = len(duplicates)
        total_duplicated_rows = sum(d["occurrence_count"] for d in duplicates)

        report = {
            "summary": {
                "total_records_scanned": total_campuses,
                "unique_campus_names": unique_names_count,
                "duplicate_names_count": duplicate_names_count,
                "total_duplicated_records": total_duplicated_rows,
                "duplicate_rate_percentage": round((total_duplicated_rows / total_campuses * 100), 2) if total_campuses else 0
            },
            "duplicates": duplicates
        }

        # Print summary indicators
        self.logger.info("=" * 60)
        self.logger.info("DUPLICATE CAMPUS NAME AUDIT REPORT (INDICATOR ONLY)")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Scanned    : {total_campuses} records")
        self.logger.info(f"Unique Names     : {unique_names_count}")
        self.logger.info(f"Duplicate Names  : {duplicate_names_count} names appear >1 time")
        self.logger.info(f"Affected Records : {total_duplicated_rows} records involved in duplicates")
        self.logger.info("=" * 60)

        if duplicates:
            self.logger.info("\nTop 5 Duplicate Name Samples:")
            for i, dup in enumerate(duplicates[:5], 1):
                self.logger.info(f"  {i}. '{dup['display_name']}' ({dup['occurrence_count']}x instances)")
                for inst in dup["instances"]:
                    kode = inst["kode_pt"] or "-"
                    status = inst["status_pt"] or "-"
                    loc = f"{inst['kab_kota']}, {inst['provinsi']}".strip(", -") or "-"
                    self.logger.info(f"     └─ [Kode: {kode:<8}] Status: {status:<12} Loc: {loc}")

        if output_json_path:
            out_file = Path(output_json_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.logger.info(f"\nDetailed Duplicate Indicator Report saved to: {out_file}\n")

        return report

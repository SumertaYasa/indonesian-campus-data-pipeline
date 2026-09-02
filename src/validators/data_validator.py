from typing import List, Tuple
from src.models.mapped_data import KampusMapped

class DataValidator:
    def validate(self, kampus: KampusMapped, mapper_warnings: List[str]) -> Tuple[str, List[str]]:
        """
        Validates the mapped kampus data.
        Returns a tuple of (Status, List of warnings/errors).
        Status can be VALID, WARNING, or ERROR.
        """
        issues = list(mapper_warnings)
        status = "VALID"
        
        # 1. Required fields checks (errors)
        if not kampus.nama:
            issues.append("ERROR: Missing required field 'nama'")
            status = "ERROR"
            
        if not kampus.slug:
            issues.append("ERROR: Missing required field 'slug'")
            status = "ERROR"
            
        # 2. Warning checks
        if len(kampus.alamat) == 0:
            issues.append("WARNING: Kampus has no addresses (location_type=UNKNOWN)")
            if status != "ERROR": status = "WARNING"

            
        if not kampus.jenis_kampus:
            issues.append("WARNING: Missing or unmapped 'jenis_kampus'")
            if status != "ERROR": status = "WARNING"
            
        if not kampus.akreditasi:
            issues.append("WARNING: Missing 'akreditasi' at kampus level")
            if status != "ERROR": status = "WARNING"
            

        if not kampus.fakultas:
            issues.append("WARNING: Kampus has no fakultas data")
            if status != "ERROR": status = "WARNING"
            
        return status, issues

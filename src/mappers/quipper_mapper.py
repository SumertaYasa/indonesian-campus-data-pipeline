import re
from typing import Dict, Any, List
from src.models.mapped_data import KampusMapped, FakultasMapped, ProdiMapped, LokasiMapped

class QuipperMapper:
    def __init__(self):
        self.warnings = []

    def map_school(self, raw_school: Dict[str, Any], base_slug: str, scraped_at: str) -> KampusMapped:
        self.warnings.clear()
        
        # 1. Alamat & Wilayah (Multi-Location)
        profile = raw_school.get('profile', {})
        candidates = []
        
        # Collect from campuses array (strictly from known address fields)
        raw_campuses = raw_school.get('campuses', [])
        if isinstance(raw_campuses, list):
            for camp in raw_campuses:
                addr = camp.get('address')
                if addr:
                    candidates.append(addr)
                    
        # Collect from profile.address
        prof_addr = profile.get('address')
        if prof_addr:
            candidates.append(prof_addr)
            
        # Deduplicate using exact normalization match
        unique_addresses = []
        seen_normalized = set()
        
        for addr in candidates:
            # Exact normalization for comparison: lowercase, regularize spaces, strip punctuation
            norm = re.sub(r'[^\w\s]', '', addr).lower()
            norm = re.sub(r'\s+', ' ', norm).strip()
            
            if norm not in seen_normalized:
                seen_normalized.add(norm)
                unique_addresses.append(addr)
                
        # Map each unique address to LokasiMapped
        alamat_list = []
        for addr in unique_addresses:
            lok = LokasiMapped(
                alamat=addr
            )
            alamat_list.append(lok)
            
        # Determine location_type
        if len(alamat_list) == 0:
            location_type = "UNKNOWN"
        elif len(alamat_list) == 1:
            location_type = "SINGLE_LOCATION"
        else:
            location_type = "MULTI_LOCATION"

        # 2. Jenis Kampus
        campus_sector = raw_school.get('campus_sector')
        jenis_kampus = None
        if campus_sector in ['public_university', 'public_institute', 'public_college']:
            jenis_kampus = 'Negeri'
        elif campus_sector in ['private_university', 'private_college', 'private_polytechnic']:
            jenis_kampus = 'Swasta'
        elif campus_sector == 'other':
            jenis_kampus = 'Lainnya'
        elif campus_sector:
            jenis_kampus = campus_sector
            self.warnings.append(f"UNMAPPED_CAMPUS_TYPE: {campus_sector}")
        
        # 3. Logo and Banner
        # For the current scraping phase, logo and banner are explicitly set to null.
        # Image enrichment will be handled in a future separate phase.
        logo_url = None
        banner_url = None
        
        # 4. Akreditasi
        # No semantic mapping for accreditation. Pass as-is (stripped).
        raw_akreditasi = profile.get('accreditation')
        akreditasi_mapped = raw_akreditasi.strip() if raw_akreditasi else raw_akreditasi

        kampus = KampusMapped(
            nama=raw_school.get('name', ''),
            slug=base_slug,
            scraped_at=scraped_at,
            jenis_kampus=jenis_kampus,
            akreditasi=akreditasi_mapped,
            location_type=location_type,
            alamat=alamat_list,
            website=profile.get('website'),
            logo_url=logo_url,
            banner_url=banner_url,
            deskripsi=profile.get('description'),
            fakultas=self._map_faculties(raw_school.get('faculties', []), scraped_at)
        )
        return kampus

    def _map_faculties(self, raw_faculties: List[Dict[str, Any]], scraped_at: str) -> List[FakultasMapped]:
        fakultas_list = []
        for raw_fac in raw_faculties:
            fak_name = raw_fac.get('name')
            if not fak_name:
                continue
                
            fak = FakultasMapped(
                nama=fak_name,
                scraped_at=scraped_at,
                keterangan=raw_fac.get('description'),
                prodi=self._map_majors(raw_fac.get('majors', {}), scraped_at)
            )
            fakultas_list.append(fak)
        return fakultas_list

    def _map_majors(self, raw_majors_dict: Dict[str, Any], scraped_at: str) -> List[ProdiMapped]:
        prodi_list = []
        
        # mapping source keys to jenjang
        jenjang_map = {
            's1': 'S1',
            's2': 'S2',
            's3': 'S3',
            'd3': 'D3',
            'd4': 'D4',
            'profession': 'Prof',
            'specialist': 'Sp'
        }
        
        for level_key, majors_list in raw_majors_dict.items():
            if not isinstance(majors_list, list):
                continue
                
            jenjang = jenjang_map.get(level_key, level_key.upper())
            
            for major in majors_list:
                raw_name = major.get('name', '')
                if not raw_name:
                    continue
                    
                # Extract akreditasi (e.g. "Ilmu Komputer (A)")
                akreditasi = None
                nama_prodi = raw_name
                
                match = re.search(r'\s*\(([A-C])\)$', raw_name)
                if match:
                    akreditasi = match.group(1)
                    nama_prodi = raw_name[:match.start()].strip()
                elif re.search(r'\s*\((.*?)\)$', raw_name):
                    # It might be unmapped accreditation or something else
                    self.warnings.append(f"Prodi Akreditasi Warning: Cannot recognize accreditation format for '{raw_name}'")
                
                # study_plans as keterangan
                keterangan = None
                study_plans = major.get('study_plans', [])
                if study_plans and isinstance(study_plans, list):
                    keterangan = ", ".join(study_plans)
                    
                prodi = ProdiMapped(
                    nama=nama_prodi,
                    jenjang=jenjang,
                    scraped_at=scraped_at,
                    akreditasi=akreditasi,
                    daya_tampung=None, # Not in source
                    keterangan=keterangan
                )
                prodi_list.append(prodi)
                
        return prodi_list

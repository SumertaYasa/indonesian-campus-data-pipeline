import unittest
import tempfile
import os
import csv
from src.utils.area_matcher import AreaMatcher

class TestAreaMatcher(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file with mock master data
        self.temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', encoding='utf-8')
        writer = csv.DictWriter(self.temp_csv, fieldnames=['regency_id', 'province_id', 'regency_name'])
        writer.writeheader()
        writer.writerows([
            {'regency_id': '3171', 'province_id': '31', 'regency_name': 'Kota Administrasi Jakarta Pusat'},
            {'regency_id': '3276', 'province_id': '32', 'regency_name': 'Kota Depok'},
            {'regency_id': '3273', 'province_id': '32', 'regency_name': 'Kota Bandung'},
            {'regency_id': '3204', 'province_id': '32', 'regency_name': 'Kabupaten Bandung'},
            {'regency_id': '1111', 'province_id': '11', 'regency_name': 'Kabupaten Xyz'},
            {'regency_id': '1112', 'province_id': '11', 'regency_name': 'Kota Xyz'}
        ])
        self.temp_csv.close()
        
        self.matcher = AreaMatcher(self.temp_csv.name)

    def tearDown(self):
        os.remove(self.temp_csv.name)

    def test_exact_match(self):
        # Should match priority 1 (name_norm)
        kode, nama, tingkat, status = self.matcher.find_wilayah("Kota Administrasi Jakarta Pusat")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Administrasi Jakarta Pusat")
        
        # Should match priority 1 (base_norm)
        kode, nama, tingkat, status = self.matcher.find_wilayah("Jakarta Pusat")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Administrasi Jakarta Pusat")

    def test_depok_cases(self):
        # "Depok" -> MATCH Kota Depok
        kode, nama, tingkat, status = self.matcher.find_wilayah("Depok")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Depok")

        # "Depokrejo" -> NOT MATCH Kota Depok (should be UNMATCHED)
        kode, nama, tingkat, status = self.matcher.find_wilayah("Depokrejo")
        self.assertEqual(status, "UNMATCHED_WILAYAH")

        # "Jl. Depok No. 10" -> MATCH Kota Depok
        kode, nama, tingkat, status = self.matcher.find_wilayah("Jl. Depok No. 10")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Depok")

    def test_phrase_match_address(self):
        # Match inside a longer address using Priority 2
        kode, nama, tingkat, status = self.matcher.find_wilayah("Jl. Salemba Raya No. 6, Kota Administrasi Jakarta Pusat, 10430")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Administrasi Jakarta Pusat")
        
        # Match inside a longer address using Priority 3 (base)
        kode, nama, tingkat, status = self.matcher.find_wilayah("Jl. Salemba Raya No. 6, Jakarta Pusat, 10430")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Administrasi Jakarta Pusat")

    def test_ambiguous_match(self):
        # "Bandung" should be ambiguous because there is Kota Bandung and Kabupaten Bandung
        kode, nama, tingkat, status = self.matcher.find_wilayah("Bandung")
        self.assertEqual(status, "AMBIGUOUS_WILAYAH")
        
        # "Kota Bandung" should NOT be ambiguous (matches exactly via Priority 2)
        kode, nama, tingkat, status = self.matcher.find_wilayah("Kota Bandung")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Bandung")
        
        # "Xyz" is ambiguous
        kode, nama, tingkat, status = self.matcher.find_wilayah("Xyz")
        self.assertEqual(status, "AMBIGUOUS_WILAYAH")

    def test_hierarchical_priority_preservation(self):
        # Address: "Kota Bandung"
        # Priority 2 will find "Kota Bandung" (1 candidate) -> returns VALID
        # Priority 3 would find both "Kota Bandung" and "Kabupaten Bandung" -> would be ambiguous
        # BUT because Priority 2 matched, it shouldn't reach Priority 3.
        kode, nama, tingkat, status = self.matcher.find_wilayah("Jl. ABC, Kota Bandung")
        self.assertEqual(status, "VALID")
        self.assertEqual(nama, "Kota Bandung")

    def test_unmatched(self):
        kode, nama, tingkat, status = self.matcher.find_wilayah("Wakanda")
        self.assertEqual(status, "UNMATCHED_WILAYAH")

if __name__ == '__main__':
    unittest.main()

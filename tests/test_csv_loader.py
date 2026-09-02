import unittest
import os
import tempfile
import csv
from src.loaders.csv_loader import load_campus_names

class TestCSVLoader(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file for testing
        self.test_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.test_dir.name, 'test_campus.csv')
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Ranking', 'Nama Kampus', 'Other Field'])
            writer.writerow(['1', 'Universitas Indonesia', 'Data'])
            writer.writerow(['2', 'Institut Teknologi Bandung', 'Data'])

    def tearDown(self):
        self.test_dir.cleanup()

    def test_load_campus_names(self):
        names = load_campus_names(self.csv_path)
        self.assertEqual(len(names), 2)
        self.assertEqual(names[0], "Universitas Indonesia")
        self.assertEqual(names[1], "Institut Teknologi Bandung")
        
    def test_file_not_found(self):
        # Should handle gracefully and return empty list
        names = load_campus_names("nonexistent_file.csv")
        self.assertEqual(names, [])

if __name__ == '__main__':
    unittest.main()

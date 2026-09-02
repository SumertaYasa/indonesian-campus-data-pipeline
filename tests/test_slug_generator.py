import unittest
from src.utils.slug_generator import generate_slug

class TestSlugGenerator(unittest.TestCase):
    def test_generate_slug_lowercase(self):
        self.assertEqual(generate_slug("UNIVERSITAS INDONESIA"), "universitas-indonesia")

    def test_generate_slug_replace_spaces(self):
        self.assertEqual(generate_slug("Institut Teknologi Bandung"), "institut-teknologi-bandung")

    def test_generate_slug_multiple_spaces(self):
        self.assertEqual(generate_slug("Universitas   Gadjah  Mada"), "universitas-gadjah-mada")
        
    def test_generate_slug_empty_string(self):
        self.assertEqual(generate_slug(""), "")

if __name__ == '__main__':
    unittest.main()

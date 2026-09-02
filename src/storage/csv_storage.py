import csv
import re
from pathlib import Path
from src.models.mapped_data import KampusMapped

class CsvStorage:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths for consolidated CSVs
        self.kampus_file = self.output_dir / "kampus.csv"
        self.fakultas_file = self.output_dir / "fakultas.csv"
        self.prodi_file = self.output_dir / "prodi.csv"
        
        self.kampus_headers = [
            'slug', 'nama', 'akreditasi', 'alamat', 'website', 
            'logo_url', 'banner_url', 'deskripsi', 'scraped_at'
        ]
        
        self.fakultas_headers = ['kampus_slug', 'nama', 'keterangan', 'scraped_at']
        
        self.prodi_headers = [
            'kampus_slug', 'fakultas_nama', 'nama', 'jenjang', 
            'akreditasi', 'daya_tampung', 'keterangan', 'scraped_at'
        ]

    def initialize(self) -> None:
        """
        Clears the consolidated CSV files and writes their headers.
        Must be called once before scraping a batch of campuses.
        """
        with open(self.kampus_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.kampus_headers, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
        with open(self.fakultas_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.fakultas_headers, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
        with open(self.prodi_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.prodi_headers, quoting=csv.QUOTE_ALL)
            writer.writeheader()

    def save(self, data: KampusMapped) -> None:
        """
        Saves the mapped data into 3 relational CSV files:
        1. {slug}-kampus.csv
        2. {slug}-fakultas.csv
        3. {slug}-prodi.csv
        """
        self._save_kampus(data)
        self._save_fakultas(data)
        self._save_prodi(data)


    def _normalize_text(self, text: str) -> str:
        """Normalizes multiple whitespaces and newlines into a single space."""
        if not text:
            return ''
        return re.sub(r'\s+', ' ', text).strip()

    def _save_kampus(self, data: KampusMapped):
        with open(self.kampus_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.kampus_headers, quoting=csv.QUOTE_ALL)
            
            # Base row properties
            base_row = {
                'slug': data.slug,
                'nama': data.nama,
                'akreditasi': data.akreditasi if data.akreditasi else '',
                'website': data.website if data.website else '',
                'logo_url': data.logo_url if data.logo_url else '',
                'banner_url': data.banner_url if data.banner_url else '',
                'deskripsi': self._normalize_text(data.deskripsi),
                'scraped_at': data.scraped_at
            }
            
            if len(data.alamat) == 0:
                row = dict(base_row)
                row.update({
                    'alamat': ''
                })
                writer.writerow(row)
            else:
                for loc in data.alamat:
                    row = dict(base_row)
                    row.update({
                        'alamat': loc.alamat if loc.alamat else ''
                    })
                    writer.writerow(row)

    def _save_fakultas(self, data: KampusMapped):
        with open(self.fakultas_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.fakultas_headers, quoting=csv.QUOTE_ALL)
            
            for fak in data.fakultas:
                writer.writerow({
                    'kampus_slug': data.slug,
                    'nama': fak.nama,
                    'keterangan': fak.keterangan if fak.keterangan else '',
                    'scraped_at': fak.scraped_at
                })

    def _save_prodi(self, data: KampusMapped):
        with open(self.prodi_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.prodi_headers, quoting=csv.QUOTE_ALL)
            
            for fak in data.fakultas:
                for prodi in fak.prodi:
                    writer.writerow({
                        'kampus_slug': data.slug,
                        'fakultas_nama': fak.nama,
                        'nama': prodi.nama,
                        'jenjang': prodi.jenjang,
                        'akreditasi': prodi.akreditasi if prodi.akreditasi else '',
                        'daya_tampung': prodi.daya_tampung if prodi.daya_tampung else '',
                        'keterangan': prodi.keterangan if prodi.keterangan else '',
                        'scraped_at': prodi.scraped_at
                    })

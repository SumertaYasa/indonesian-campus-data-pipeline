import csv
from typing import List

def load_campus_names(csv_path: str) -> List[str]:
    """
    Reads the master data CSV and extracts the list of campus names.
    Only uses the 'Nama Kampus' field.
    """
    campus_names = []
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'Nama Kampus' in row:
                    campus_names.append(row['Nama Kampus'].strip())
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_path}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        
    return campus_names

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
INPUT_DIR = DATA_DIR / 'input'
OUTPUT_DIR = DATA_DIR / 'output'

# Target URLs
BASE_URL = "https://campus.quipper.com/directory"

# Files
INPUT_CSV = INPUT_DIR / 'master_data_top_100_indonesian_campus.csv'

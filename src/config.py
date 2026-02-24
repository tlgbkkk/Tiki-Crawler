import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE = os.path.join(BASE_DIR, '../data_source/products-0-1500.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, '../processed_data')
CONCURRENCY_LIMIT = 30
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0'
}

os.makedirs(OUTPUT_DIR, exist_ok=True)
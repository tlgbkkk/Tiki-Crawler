import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE = os.path.join(BASE_DIR, '../data_source/products-0-200000.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, '../processed_data')
CONCURRENCY_LIMIT = 40
RATE_LIMIT = 60
RETRIES = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)
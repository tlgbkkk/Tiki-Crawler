import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE = os.path.join(BASE_DIR, '../data_source/products-0-200000.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, '../processed_data')
CONCURRENCY_LIMIT = 30
RATE_LIMIT = 50
RETRIES = 3

DATABASE = {
    "host": "localhost",
    "port": 5432,
    "database": "database",
    "user": "postgres",
    "password": "170723",
}

DATABASE_TABLE_NAME = "products"

os.makedirs(OUTPUT_DIR, exist_ok=True)
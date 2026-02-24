import csv
import asyncio
import time
from crawl import crawl
from config import SOURCE

async def main():
    all_ids = []
    with open(SOURCE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('id'):
                all_ids.append(row['id'].strip())

    print(f"Crawling {len(all_ids)} products...")

    start_time = time.perf_counter()
    await crawl(all_ids)
    end_time = time.perf_counter()
    duration = end_time - start_time

    print(f"Total time: {duration:.2f} secs (~{duration / 60:.2f} mins)")

if __name__ == "__main__":
    asyncio.run(main())
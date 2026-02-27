import csv
import glob
import asyncio
import os
import time
import orjson
from crawl import crawl, crawl_sequential
from config import SOURCE, OUTPUT_DIR


def load_processed_ids():
    ids = set()
    for path in glob.glob(f"{OUTPUT_DIR}/success_*.json"):
        with open(path, 'rb') as f:
            for r in orjson.loads(f.read()):
                if r.get("id"):
                    ids.add(str(r["id"]))
    return ids


def load_error_ids():
    ids = []
    for path in sorted(glob.glob(f"{OUTPUT_DIR}/error_*.json")):
        with open(path, 'rb') as f:
            for r in orjson.loads(f.read()):
                if r.get("id"):
                    ids.append(str(r["id"]))
    return ids


def load_remaining_ids():
    processed = load_processed_ids()
    error_ids = set(load_error_ids())
    ids = []
    with open(SOURCE, mode='r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            pid = row.get('id', '').strip()
            if pid and pid not in processed and pid not in error_ids:
                ids.append(pid)
    return ids


def delete_error_files():
    for path in glob.glob(f"{OUTPUT_DIR}/error_*.json"):
        os.remove(path)


async def main():
    start_time = time.perf_counter()

    error_ids = load_error_ids()
    remaining_ids = load_remaining_ids()

    seen = set()
    all_ids = []
    for pid in remaining_ids + error_ids:
        if pid not in seen:
            seen.add(pid)
            all_ids.append(pid)

    if not all_ids:
        print("Nothing to crawl.")
        return

    source_label = []
    if remaining_ids:
        source_label.append(f"{len(remaining_ids)} from source")
    if error_ids:
        source_label.append(f"{len(error_ids)} from errors")
    print(f"Crawling {len(all_ids)} IDs ({', '.join(source_label)})")

    delete_error_files()
    await crawl(all_ids)

    retry_ids = load_error_ids()
    if retry_ids:
        print(f"\nSequential retry | {len(retry_ids)} IDs | ~{len(retry_ids) * 2 / 60:.0f} mins estimated")
        delete_error_files()
        await crawl_sequential(retry_ids)

    final_errors = load_error_ids()
    elapsed = time.perf_counter() - start_time
    print(f"\nDone | Errors: {len(final_errors)} | Time: {elapsed:.2f}s (~{elapsed / 60:.2f} mins)")
    if final_errors:
        print("Run again later to retry remaining errors.")


if __name__ == "__main__":
    asyncio.run(main())
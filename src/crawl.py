import asyncio
import aiohttp
import orjson
import os
import logging
import glob
from aiolimiter import AsyncLimiter
from fake_useragent import UserAgent
from transform import normalize
from config import CONCURRENCY_LIMIT, RATE_LIMIT, OUTPUT_DIR, RETRIES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

ua = UserAgent()


def save_to_file(data, prefix, index):
    filename = os.path.join(OUTPUT_DIR, f"{prefix}_{index:03d}.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(orjson.dumps(data))


def load_last_file(prefix):
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, f"{prefix}_*.json")))
    if not files:
        return [], 1
    last_file = files[-1]
    idx = int(os.path.basename(last_file)[len(prefix)+1:len(prefix)+4])
    with open(last_file, 'rb') as f:
        data = orjson.loads(f.read())
    if len(data) < 1000:
        os.remove(last_file)
        return data, idx
    return [], idx + 1


async def fetch_product(session, product_id, semaphore, limiter):
    url = f"https://api.tiki.vn/product-detail/api/v1/products/{product_id}"
    async with semaphore:
        for attempt in range(RETRIES):
            sleep_after = 0
            async with limiter:
                try:
                    async with session.get(url, headers={"User-Agent": ua.random}, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            raw = await response.read()
                            data = orjson.loads(raw)
                            for field in ["description", "short_description"]:
                                if data.get(field): data[field] = normalize(data[field])
                            return True, data
                        elif response.status == 404:
                            if attempt < RETRIES - 1:
                                sleep_after = 1.0
                            else:
                                body = await response.text()
                                return False, {"id": product_id, "status": 404, "reason": "HTTP_404", "body": body}
                        elif response.status == 429:
                            sleep_after = 2 * (2 ** attempt)
                        else:
                            body = await response.text()
                            return False, {"id": product_id, "status": response.status, "reason": f"HTTP_{response.status}", "body": body}
                except Exception:
                    sleep_after = 0.5 * (2 ** attempt)

            if sleep_after:
                await asyncio.sleep(sleep_after)

    return False, {"id": product_id, "status": None, "reason": "Failed_After_Retries", "body": None}


async def crawl(all_product_ids):
    error_buffer = []
    success_buffer, s_idx = load_last_file("success")
    e_idx = 1

    connector = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT, keepalive_timeout=60)
    async with aiohttp.ClientSession(connector=connector) as session:
        logging.info(f"Crawling {len(all_product_ids)} IDs | Concurrency: {CONCURRENCY_LIMIT} | Rate: {RATE_LIMIT} req/s")
        sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
        limiter = AsyncLimiter(RATE_LIMIT, 1)

        try:
            for coro in asyncio.as_completed([fetch_product(session, pid, sem, limiter) for pid in all_product_ids]):
                is_success, result = await coro
                if is_success:
                    success_buffer.append(result)
                    if len(success_buffer) >= 1000:
                        save_to_file(success_buffer, "success", s_idx)
                        logging.info(f"[SUCCESS] Saved success_{s_idx:03d}.json")
                        success_buffer, s_idx = [], s_idx + 1
                else:
                    error_buffer.append(result)
                    if len(error_buffer) >= 1000:
                        save_to_file(error_buffer, "error", e_idx)
                        logging.info(f"[ERROR] Saved error_{e_idx:03d}.json")
                        error_buffer, e_idx = [], e_idx + 1

        except (asyncio.CancelledError, KeyboardInterrupt):
            logging.warning("Interrupted! Flushing buffers...")
            if success_buffer:
                save_to_file(success_buffer, "success", s_idx)
                logging.warning(f"[FLUSH] success_{s_idx:03d}.json ({len(success_buffer)} records)")
            if error_buffer:
                save_to_file(error_buffer, "error", e_idx)
                logging.warning(f"[FLUSH] error_{e_idx:03d}.json ({len(error_buffer)} records)")
            raise

    if success_buffer:
        save_to_file(success_buffer, "success", s_idx)
    if error_buffer:
        save_to_file(error_buffer, "error", e_idx)

    error_count = (e_idx - 1) * 1000 + len(error_buffer)
    logging.info(f"Done | Errors: {error_count}")
    return error_count


async def crawl_sequential(product_ids):
    success_buffer, s_idx = load_last_file("success")
    error_buffer = []
    e_idx = 1
    total = len(product_ids)

    connector = aiohttp.TCPConnector(limit=1, keepalive_timeout=60)
    async with aiohttp.ClientSession(connector=connector) as session:
        logging.info(f"Sequential retry | {total} IDs")
        sem = asyncio.Semaphore(1)
        limiter = AsyncLimiter(10, 1)

        try:
            for i, pid in enumerate(product_ids, 1):
                is_success, result = await fetch_product(session, pid, sem, limiter)

                if is_success:
                    success_buffer.append(result)
                    if len(success_buffer) >= 1000:
                        save_to_file(success_buffer, "success", s_idx)
                        logging.info(f"[SUCCESS] Saved success_{s_idx:03d}.json")
                        success_buffer, s_idx = [], s_idx + 1
                else:
                    error_buffer.append(result)
                    if len(error_buffer) >= 1000:
                        save_to_file(error_buffer, "error", e_idx)
                        logging.info(f"[ERROR] Saved error_{e_idx:03d}.json")
                        error_buffer, e_idx = [], e_idx + 1

                if i % 100 == 0:
                    logging.info(f"Progress: {i}/{total} | Errors so far: {(e_idx - 1) * 1000 + len(error_buffer)}")

        except (asyncio.CancelledError, KeyboardInterrupt):
            logging.warning("Interrupted! Flushing buffers...")
            if success_buffer:
                save_to_file(success_buffer, "success", s_idx)
                logging.warning(f"[FLUSH] success_{s_idx:03d}.json ({len(success_buffer)} records)")
            if error_buffer:
                save_to_file(error_buffer, "error", e_idx)
                logging.warning(f"[FLUSH] error_{e_idx:03d}.json ({len(error_buffer)} records)")
            raise

    if success_buffer:
        save_to_file(success_buffer, "success", s_idx)
    if error_buffer:
        save_to_file(error_buffer, "error", e_idx)

    error_count = (e_idx - 1) * 1000 + len(error_buffer)
    logging.info(f"Sequential done | Errors: {error_count}")
    return error_count
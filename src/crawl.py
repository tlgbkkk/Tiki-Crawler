import asyncio
import aiohttp
import orjson
import os
from transform import normalize
from config import HEADERS, CONCURRENCY_LIMIT, OUTPUT_DIR

async def fetch_product(session, product_id, semaphore):
    url = f"https://api.tiki.vn/product-detail/api/v1/products/{product_id}"
    retries = 3

    async with semaphore:
        for attempt in range(retries):
            try:
                async with session.get(url, headers=HEADERS, timeout=10) as response:
                    if response.status == 200:
                        raw = await response.read()
                        data = orjson.loads(raw)
                        if data.get("description"):
                            data["description"] = normalize(data["description"])
                        if data.get("short_description"):
                            data["short_description"] = normalize(data["short_description"])
                        return True, data

                    else:
                        if attempt == retries - 1:
                            return False, {"id": product_id, "reason": f"HTTP_{response.status}"}
                        await asyncio.sleep(0.1)

            except asyncio.TimeoutError:
                if attempt == retries - 1:
                    return False, {"id": product_id, "reason": "Timeout_Error"}
                await asyncio.sleep(0.1)

            except Exception as e:
                if attempt == retries - 1:
                    return False, {"id": product_id, "reason": type(e).__name__}
                await asyncio.sleep(0.1)

        return False, {"id": product_id, "reason": "Unknown_Error"}


def save_to_file(data, prefix, index):
    filename = os.path.join(OUTPUT_DIR, f"{prefix}_{index:03d}.json")
    with open(filename, 'wb') as f:
        f.write(orjson.dumps(data))


async def crawl(all_product_ids):
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    success_buffer = []
    error_buffer = []

    success_file_idx = 1
    error_file_idx = 1

    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY_LIMIT,
        keepalive_timeout=60,
        enable_cleanup_closed=True,
        ttl_dns_cache=300,
        limit_per_host=CONCURRENCY_LIMIT
    )

    async with aiohttp.ClientSession(
        connector = connector,
        json_serialize = lambda obj: orjson.dumps(obj).decode()
    ) as session:
            tasks = [fetch_product(session, pid, semaphore) for pid in all_product_ids]

            for coro in asyncio.as_completed(tasks):
                is_success, result = await coro

                if is_success:
                    success_buffer.append(result)
                    if len(success_buffer) >= 1000:
                        save_to_file(success_buffer[:1000], "success", success_file_idx)
                        msg = f"[SUC] Saved success_{success_file_idx:03d}.json (1000 ids)"
                        print(msg)

                        success_buffer = success_buffer[1000:]
                        success_file_idx += 1
                else:
                    error_buffer.append(result)
                    if len(error_buffer) >= 1000:
                        save_to_file(error_buffer[:1000], "error", error_file_idx)
                        msg = f"[ERR] Saved error_{error_file_idx:03d}.json (1000 error ids)"
                        print(msg)

                        error_buffer = error_buffer[1000:]
                        error_file_idx += 1

    if success_buffer:
        save_to_file(success_buffer, "success", success_file_idx)
        print(f"[SUC] Saved success_{success_file_idx:03d}.json ({len(success_buffer)} ids)")

    if error_buffer:
        save_to_file(error_buffer, "error", error_file_idx)
        print(f"[ERR] Saved error_{error_file_idx:03d}.json ({len(error_buffer)} error ids)")
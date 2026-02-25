# Tiki Product Crawler

Async crawler for fetching product data from the Tiki API, with data normalization and smart retry support.

## Project Structure

```
src/
├── main.py       # Entrypoint
├── crawl.py      # Core crawl logic
├── transform.py  # Normalize HTML descriptions
└── config.py     # Configuration

data_source/
└── products-0-200000.csv   # Source file containing product IDs

processed_data/ (gitignored, init on first run)
├── success_001.json        # Successful results (1000 records/file)
├── success_002.json
└── error_001.json          # Failed IDs to retry later
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SOURCE` | `products-0-200000.csv` | CSV file containing product IDs |
| `OUTPUT_DIR` | `../processed_data` | Output directory |
| `CONCURRENCY_LIMIT` | `40` | Max concurrent requests |
| `RATE_LIMIT` | `60` | Max requests per second |
| `RETRIES` | `3` | Retry attempts per request |

## Usage

```bash
python src/main.py
```

Each run automatically:
1. Skips IDs already present in `success_*.json`
2. Combines new IDs from source + failed IDs from `error_*.json`
3. Halves concurrency and rate when only retrying errors

## Resume Behavior

- Interrupted mid-run (Ctrl+C, network drop) → buffers are flushed to disk immediately
- Re-run → automatically resumes from where it left off, skipping already successful IDs

## Retry Strategy

Tiki's API uses server-side bot protection that may return **fake 404s** for valid products when it detects high request volume from a single IP. This means error files may contain IDs that are actually fetchable — they just need to be retried later with a cooled-down IP.

**Recommended retry schedule:**

1. Run once → check error count
2. Wait **15–30 minutes** → run again (IP sliding window resets)
3. Repeat until error count stops decreasing

When the error count no longer decreases between runs, the remaining errors are likely either truly deleted/unavailable products or persistent IP blocks requiring a proxy.

## Output Format

**success_*.json** — array of product objects from the Tiki API, with `description` and `short_description` normalized (HTML stripped)

**error_*.json** — array of failed records:
```json
[
  { "id": "123", "status": 404, "reason": "HTTP_404", "body": "..." },
  { "id": "456", "status": 429, "reason": "HTTP_429", "body": "..." },
  { "id": "789", "status": null, "reason": "Failed_After_Retries", "body": null }
]
```

| Reason | Description |
|--------|-------------|
| `HTTP_404` | Product not found — may be a fake 404 due to server-side rate limiting; retry later |
| `HTTP_429` | Too many requests — server explicitly throttling; wait longer before retrying |
| `Failed_After_Retries` | Request failed after all retry attempts (timeout, connection error, etc.) |

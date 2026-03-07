# 🛒 Tiki Product Crawler

Async crawler for fetching product data from the Tiki API, with data normalization and smart retry support.

## 📁 Project Structure

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

## ✅ Requirements

- **Python** 3.10+
- **PostgreSQL** 14+
- **Supervisor** 4+

Install system dependencies (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y python3 python3-pip postgresql supervisor
```

## ⚙️ Installation

```bash
pip install -r requirements.txt
```

## 🔧 Configuration

Edit `config.py`:

| Variable | Default                 | Description |
|----------|-------------------------|-------------|
| `SOURCE` | `products-0-200000.csv` | CSV file containing product IDs |
| `OUTPUT_DIR` | `../processed_data`     | Output directory |
| `CONCURRENCY_LIMIT` | `30`                    | Max concurrent requests |
| `RATE_LIMIT` | `50`                    | Max requests per second |
| `RETRIES` | `3`                     | Retry attempts per request |

## 🏃 Run

```bash
python src/main.py
```

Each run automatically:
1. Skips IDs already present in `success_*.json`
2. Combines new IDs from source + failed IDs from `error_*.json`
3. Halves concurrency and rate when only retrying errors

## ▶️ Resume Behavior

- Interrupted mid-run (Ctrl+C, network drop) → buffers are flushed to disk immediately
- Re-run → automatically resumes from where it left off, skipping already successful IDs

## 🔁 Retry Strategy

Tiki's API uses server-side bot protection that may return **fake 404s** for valid products when it detects high request volume from a single IP. This means error files may contain IDs that are actually fetchable — they just need to be retried later with a cooled-down IP.

**Recommended retry schedule:**

1. Run once → check error count
2. Wait **20 minutes** → run again

When the error count no longer decreases between runs, the remaining errors are likely either truly deleted/unavailable products or persistent IP blocks requiring a proxy.

## 🗄️ PostgreSQL Setup

The crawler loads data into PostgreSQL automatically at runtime. Before the first run, initialize the database schema once:

```bash
sudo -u postgres psql -c "CREATE DATABASE your_database_name;"
sudo -u postgres psql -d your_database_name -f sql/init.sql
```

Then configure the connection in `config.py` and run the crawler normally.
## 🔄 Restart with Supervisor

Use [Supervisor](http://supervisord.org/) to keep the crawler running as a managed process and auto-restart it on failure.

### 1. Install Supervisor

```bash
sudo apt install -y supervisor
sudo systemctl enable supervisor
sudo systemctl start supervisor
```

### 2. Create a virtual environment

```bash
cd /path/to/Tiki-Crawler
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create the Supervisor config

```bash
sudo nano /etc/supervisor/conf.d/tiki_crawler.conf
```

Paste the following, adjusting `command`, `directory`, and `user` to match your setup:

```ini
[program:tiki-crawler]
# Change with your directory
command=/home/bgs/Project/Tiki-Crawler/venv/bin/python /home/bgs/Project/Tiki-Crawler/src/main.py
directory=/home/bgs/Project/Tiki-Crawler
user=bgs
autostart=true
autorestart=true
startretries=3
stdout_logfile=/var/log/tiki_crawler.out.log
stderr_logfile=/var/log/tiki_crawler.err.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
stopsignal=TERM
stopwaitsecs=10
```

| Field | Description |
|-------|-------------|
| `command` | Full path to the venv Python binary + your `main.py` |
| `directory` | Project root — all relative paths in code resolve from here |
| `user` | OS user to run the process as |
| `autostart` | Start automatically when Supervisor starts |
| `autorestart` | Restart the process if it exits unexpectedly |
| `startretries` | Number of restart attempts before marking as `FATAL` |
| `stopsignal` | Signal sent on `supervisorctl stop` — `TERM` lets the crawler flush buffers gracefully |
| `stopwaitsecs` | Seconds to wait for clean shutdown before force-killing |
| `stdout/stderr_logfile` | Separate log files for stdout and stderr |
| `stdout_logfile_backups` | Number of rotated log files to keep |

### 4. Apply and start

```bash
sudo supervisorctl reread      # Pick up new config file
sudo supervisorctl update      # Apply changes
sudo supervisorctl start tiki-crawler
```

### 5. Common commands

```bash
sudo supervisorctl status tiki-crawler          # Check running status
sudo supervisorctl stop tiki-crawler            # Stop gracefully
sudo supervisorctl restart tiki-crawler         # Restart
sudo tail -f /var/log/tiki_crawler.out.log      # Live stdout log
sudo tail -f /var/log/tiki_crawler.err.log      # Live stderr log
```

### 6. Check logs if the process won't start

If status shows `FATAL` or `BACKOFF`, check the error log first:

```bash
sudo cat /var/log/tiki_crawler.err.log
```

Common causes: wrong path in `command`, incorrect `user` permissions, or missing Python packages in the venv.

Supervisor will automatically restart the crawler if it exits unexpectedly. Because the crawler skips already-processed IDs on startup, restarting is always safe with no duplicate work.

## 📦 Output Format

**success_*.json** — array of product objects from the Tiki API, with `description` and `short_description` normalized (HTML stripped)

**error_*.json** — array of failed records:
```json
[
  { "id": "123", "status": 404, "reason": "HTTP_404", "body": "..." },
  { "id": "456", "status": 429, "reason": "HTTP_429", "body": "..." },
  { "id": "789", "status": null, "reason": "Failed_After_Retries", "body": null }
]
```

| Status                 | Description |
|------------------------|-------------|
| `HTTP_404`             | Product not found — may be a fake 404 due to server-side rate limiting; retry later |
| `HTTP_429`             | Too many requests — server explicitly throttling; wait longer before retrying |
| `Failed_After_Retries` | Request failed after all retry attempts (timeout, connection error, etc.) |

## 📊 Performance Estimate (200,000 IDs)

Based on real runs with `CONCURRENCY_LIMIT=40`, `RATE_LIMIT=60`:

| Run | IDs     | Duration | Errors     |
|-----|---------|----------|------------|
| First run | 200,000 | ~62 min | ~6,750     |
| Retry #1 | ~6,750  | ~13 min | ~6,730     |
| Retry #2 | ~6,730  | ~13 min | ~6,729     |
| ... | ...     | ... | stabilizes |

The error count stabilizes around **6,729 IDs** — these are either truly unavailable products or persistent 404s due to IP-level throttling.
"""
notion_sync.py — Syncs scraped LinkedIn jobs → Notion database.

Setup:
  1. pip install notion-client
  2. Create a Notion integration: https://www.notion.so/my-integrations
     - Copy the "Internal Integration Token"
  3. Duplicate the job tracker template in Notion (see README)
     - Share the database with your integration
     - Copy the Database ID from the URL:
       notion.so/YOUR_WORKSPACE/<DATABASE_ID>?v=...
  4. Fill in NOTION_TOKEN and DATABASE_ID below
  5. Run: python notion_sync.py
     Or it runs automatically at the end of scraper.py (see integration below)
"""

import sqlite3
import logging
import os
from datetime import datetime
import requests


log = logging.getLogger(__name__)

# ── Config — fill these in ────────────────────────────────────────────────
NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "ntn_xxxxxxxxxxxx")
DATABASE_ID    = os.environ.get("NOTION_DB_ID", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
DB_PATH        = os.path.join(os.path.dirname(__file__), "jobs.db")
NOTION_VERSION = "2022-06-28"
# ─────────────────────────────────────────────────────────────────────────


def notion_headers():
    return {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VERSION,
    }
 
 
def get_existing_notion_ids() -> set:
    """Fetch all Job IDs already in Notion (handles pagination)."""
    existing = set()
    url      = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload  = {"page_size": 100}
 
    while True:
        resp = requests.post(url, headers=notion_headers(), json=payload, timeout=15)
        if resp.status_code != 200:
            log.error(f"Notion query failed {resp.status_code}: {resp.text[:300]}")
            return existing
        data = resp.json()
 
        for page in data.get("results", []):
            props   = page.get("properties", {})
            id_prop = props.get("Job ID", {})
            # Job ID is a number property now
            num = id_prop.get("number")
            if num is not None:
                existing.add(str(num))
 
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
 
    return existing
 
 
def job_to_notion_page(job: dict) -> dict:
    """Convert a DB row → Notion page payload."""
 
    def rich(text) -> list:
        return [{"type": "text", "text": {"content": str(text or "")[:2000]}}]
 
    status = "Applied" if job.get("is_applied") else \
             "Saved"   if job.get("is_saved")   else "New"
 
    # Job ID as number (LinkedIn IDs are numeric)
    try:
        job_id_value = {"number": int(job["job_id"])}
    except (ValueError, TypeError):
        job_id_value = {"number": None}
 
    props = {
        "Name":     {"title": rich(job["title"])},
        "Company":  {"rich_text": rich(job["company"])},
        "Location": {"multi_select": [{"name": (job["location"] or "Unknown")[:100]}]},
        "Status":   {"status": {"name": status}},
        "Job ID":   job_id_value,
        "Notes":    {"rich_text": rich(job.get("notes") or "")},
        "Favorite": {"checkbox": bool(job.get("is_favorite", 0))},
    }
 
    if job.get("job_url"):
        props["LinkedIn URL"] = {"url": job["job_url"]}
 
    if job.get("posted_date"):
        try:
            props["Posted Date"] = {"date": {"start": str(job["posted_date"])[:10]}}
        except Exception:
            pass
 
    if job.get("scraped_at"):
        try:
            props["Scraped At"] = {"date": {"start": str(job["scraped_at"])[:10]}}
        except Exception:
            pass
 
    return {
        "parent":     {"database_id": DATABASE_ID},
        "properties": props,
    }
 
 
def push_job(job: dict) -> bool:
    """Create a single page in Notion. Returns True on success."""
    url     = "https://api.notion.com/v1/pages"
    payload = job_to_notion_page(job)
    resp    = requests.post(url, headers=notion_headers(), json=payload, timeout=15)
    if resp.status_code != 200:
        log.error(f"  Notion API {resp.status_code}: {resp.text[:300]}")
        return False
    return True
 
 
def sync(dry_run: bool = False):
    """Push all new jobs from SQLite → Notion. Skips already-synced jobs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    jobs = [dict(r) for r in conn.execute(
        "SELECT * FROM jobs ORDER BY scraped_at DESC"
    ).fetchall()]
    conn.close()
 
    if not jobs:
        log.info("[Notion] No jobs in DB yet.")
        return
 
    log.info("[Notion] Checking existing pages in Notion...")
    existing_ids = get_existing_notion_ids()
    log.info(f"[Notion] {len(existing_ids)} already synced | {len(jobs)} total in DB")
 
    new_jobs = [j for j in jobs if j["job_id"] not in existing_ids]
    log.info(f"[Notion] {len(new_jobs)} new jobs to push")
 
    pushed = 0
    errors = 0
 
    for job in new_jobs:
        if dry_run:
            log.info(f"  [DRY RUN] Would push: {job['title']} @ {job['company']}")
            continue
        if push_job(job):
            pushed += 1
            log.info(f"  ✓ {job['title']} @ {job['company']}")
        else:
            errors += 1
 
    log.info(f"[Notion] Done — pushed {pushed}, errors {errors}")
 
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
 
    token_ok = NOTION_TOKEN.startswith("ntn_") or NOTION_TOKEN.startswith("secret_")
    db_ok    = not DATABASE_ID.startswith("xxx") and len(DATABASE_ID) >= 32
 
    if not token_ok or not db_ok:
        print("""
  ┌─────────────────────────────────────────────────────┐
  │  Fill in NOTION_TOKEN and DATABASE_ID first!        │
  │                                                     │
  │  In notion_sync.py:                                 │
  │    NOTION_TOKEN = "ntn_..."                         │
  │    DATABASE_ID  = "abc123..."  (32 chars from URL)  │
  │                                                     │
  │  Or via environment:                                │
  │    export NOTION_TOKEN=ntn_...                      │
  │    export NOTION_DB_ID=abc123...                    │
  └─────────────────────────────────────────────────────┘
""")
    else:
        sync()
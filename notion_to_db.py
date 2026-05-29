"""
notion_to_db.py — Reverse sync: prune the local DB to match Notion.

Workflow:
  1. In Notion, delete the job rows that don't fit you.
  2. Run:  python notion_to_db.py
  3. Any job still in jobs.db but no longer in Notion is deleted from jobs.db AND
     remembered in an `ignored_jobs` blocklist, so the scraper never re-adds it.

Safety:
  • If the Notion query fails, NOTHING is deleted (we never guess).
  • Run with --dry-run first to preview what would be removed.
  • Run this AFTER a normal scrape/sync, when the DB and Notion are in sync —
    otherwise brand-new jobs not yet pushed to Notion would look "deleted".
"""

import sqlite3
import logging
import argparse
from datetime import datetime

import requests

# Reuse the Notion config + helpers already set up for the forward sync.
from notion_sync import notion_headers, DATABASE_ID, DB_PATH, NOTION_TOKEN

log = logging.getLogger(__name__)


def fetch_notion_job_ids() -> set:
    """Set of Job IDs currently in Notion. Raises RuntimeError if the query fails."""
    ids     = set()
    url     = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {"page_size": 100}

    while True:
        resp = requests.post(url, headers=notion_headers(), json=payload, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Notion query failed {resp.status_code}: {resp.text[:300]}")
        data = resp.json()

        for page in data.get("results", []):
            num = page.get("properties", {}).get("Job ID", {}).get("number")
            if num is not None:
                ids.add(str(num))

        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    return ids


def run(dry_run: bool = False):
    notion_ids = fetch_notion_job_ids()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Blocklist of rejected jobs so the scraper never re-adds them.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ignored_jobs (
            job_id     TEXT PRIMARY KEY,
            title      TEXT,
            company    TEXT,
            ignored_at TEXT
        )
    """)
    rows = conn.execute("SELECT job_id, title, company FROM jobs").fetchall()

    to_delete = [r for r in rows if str(r["job_id"]) not in notion_ids]
    log.info(f"[ReverseSync] Notion: {len(notion_ids)} jobs | DB: {len(rows)} jobs "
             f"| {len(to_delete)} to delete from DB")

    if not to_delete:
        log.info("[ReverseSync] DB already matches Notion. Nothing to do.")
        conn.close()
        return

    for r in to_delete:
        if dry_run:
            log.info(f"  [DRY RUN] would delete + blocklist: {r['title']} @ {r['company']}")
            continue
        conn.execute("DELETE FROM jobs WHERE job_id=?", (r["job_id"],))
        conn.execute(
            "INSERT OR IGNORE INTO ignored_jobs (job_id, title, company, ignored_at) "
            "VALUES (?,?,?,?)",
            (r["job_id"], r["title"], r["company"], datetime.now().isoformat()),
        )
        log.info(f"  deleted + blocklisted: {r['title']} @ {r['company']}")

    if not dry_run:
        conn.commit()
    conn.close()

    deleted = 0 if dry_run else len(to_delete)
    log.info(f"[ReverseSync] Done — deleted {deleted}"
             f"{' (dry run, nothing written)' if dry_run else ''}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    p = argparse.ArgumentParser(description="Delete DB jobs that were removed from Notion")
    p.add_argument("--dry-run", action="store_true", help="preview deletions, write nothing")
    args = p.parse_args()

    if NOTION_TOKEN.startswith("ntn_xxx") or NOTION_TOKEN.startswith("secret_xxx"):
        print("\n  Set NOTION_TOKEN in .env first (see .env.example).\n")
    else:
        try:
            run(dry_run=args.dry_run)
        except Exception as e:
            log.error(f"[ReverseSync] aborted — nothing deleted: {e}")

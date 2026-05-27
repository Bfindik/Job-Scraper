"""
jobs_cli.py — Query and manage your scraped LinkedIn jobs.

Usage:
  python jobs_cli.py list                        # Show all jobs
  python jobs_cli.py list --keyword "python"     # Filter by keyword
  python jobs_cli.py list --company "Google"     # Filter by company
  python jobs_cli.py list --location "remote"    # Filter by location
  python jobs_cli.py list --new                  # Only today's jobs
  python jobs_cli.py apply <job_id>              # Mark as applied
  python jobs_cli.py note <job_id> "note text"   # Add a note
  python jobs_cli.py export                      # Export to CSV
  python jobs_cli.py stats                       # Show statistics
"""

import sqlite3
import argparse
from datetime import datetime

DB_PATH = "jobs.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def reset_db(path="jobs.db"):
    import os
    if not os.path.exists(path):
        print(f"No database found at '{path}' — nothing to delete.")
        return
    confirm = input(f"⚠️  This will DELETE all scraped jobs in '{path}'. Type 'yes' to confirm: ")
    if confirm.strip().lower() == "yes":
        os.remove(path)
        print(f"✓ Database '{path}' deleted. It will be recreated fresh on next scrape run.")
    else:
        print("Cancelled — nothing was deleted.")


def list_jobs(keyword=None, company=None, location=None, new_only=False, not_applied=False):
    conn = get_conn()
    query = "SELECT job_id, title, company, location, posted_date, salary, is_applied, scraped_at FROM jobs WHERE 1=1"
    params = []

    if keyword:
        query += " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ?)"
        params += [f"%{keyword.lower()}%", f"%{keyword.lower()}%"]
    if company:
        query += " AND LOWER(company) LIKE ?"
        params.append(f"%{company.lower()}%")
    if location:
        query += " AND LOWER(location) LIKE ?"
        params.append(f"%{location.lower()}%")
    if new_only:
        query += " AND DATE(scraped_at) = DATE('now')"
    if not_applied:
        query += " AND is_applied = 0"

    query += " ORDER BY scraped_at DESC"

    cur = conn.execute(query, params)
    rows = cur.fetchall()

    if not rows:
        print("No jobs found.")
        return

    print(f"\n{'─'*100}")
    print(f"{'ID':<12} {'TITLE':<35} {'COMPANY':<25} {'LOCATION':<20} {'POSTED':<12} {'SALARY':<15} {'APPLIED'}")
    print(f"{'─'*100}")

    for r in rows:
        job_id, title, company, location, posted, salary, applied, scraped = r
        applied_str = "✓ Applied" if applied else ""
        today       = "🆕 " if scraped[:10] == datetime.now().strftime("%Y-%m-%d") else ""
        print(f"{job_id:<12} {today}{title[:32]:<35} {company[:23]:<25} {location[:18]:<20} {posted[:10]:<12} {(salary or '')[:13]:<15} {applied_str}")

    print(f"{'─'*100}")
    print(f"Total: {len(rows)} jobs\n")
    conn.close()


def mark_applied(job_id: str):
    conn = get_conn()
    conn.execute("UPDATE jobs SET is_applied=1 WHERE job_id=?", (job_id,))
    conn.commit()
    print(f"✓ Marked job {job_id} as applied.")
    conn.close()


def add_note(job_id: str, note: str):
    conn = get_conn()
    conn.execute("UPDATE jobs SET notes=? WHERE job_id=?", (note, job_id))
    conn.commit()
    print(f"✓ Note saved for job {job_id}.")
    conn.close()


def show_job(job_id: str):
    conn = get_conn()
    cur  = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
    row  = cur.fetchone()
    if not row:
        print(f"Job {job_id} not found.")
        return
    cols = [d[0] for d in cur.description]
    print(f"\n{'─'*60}")
    for col, val in zip(cols, row):
        print(f"  {col:<15} {val}")
    print(f"{'─'*60}\n")
    conn.close()


def export_csv(path="jobs_export.csv"):
    import csv
    conn = get_conn()
    cur  = conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    print(f"✓ Exported {len(rows)} jobs → {path}")
    conn.close()


def show_stats():
    conn = get_conn()
    total   = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    today   = conn.execute("SELECT COUNT(*) FROM jobs WHERE DATE(scraped_at)=DATE('now')").fetchone()[0]
    applied = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_applied=1").fetchone()[0]
    top_cos = conn.execute(
        "SELECT company, COUNT(*) c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 5"
    ).fetchall()
    runs    = conn.execute(
        "SELECT run_at, jobs_found, jobs_new, method FROM scrape_runs ORDER BY id DESC LIMIT 5"
    ).fetchall()

    print(f"\n{'═'*50}")
    print(f"  LINKEDIN JOB SCRAPER — STATS")
    print(f"{'═'*50}")
    print(f"  Total jobs in DB : {total}")
    print(f"  Found today      : {today}")
    print(f"  Applied          : {applied}")
    print(f"\n  Top companies:")
    for co, cnt in top_cos:
        print(f"    {co}: {cnt} listings")
    print(f"\n  Last 5 scrape runs:")
    for run in runs:
        print(f"    {run[0][:16]}  found={run[1]}  new={run[2]}  via={run[3]}")
    print(f"{'═'*50}\n")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Job Scraper CLI")
    sub = parser.add_subparsers(dest="cmd")

    # list
    p_list = sub.add_parser("list", help="List jobs")
    p_list.add_argument("--keyword",  help="Filter by title keyword")
    p_list.add_argument("--company",  help="Filter by company name")
    p_list.add_argument("--location", help="Filter by location")
    p_list.add_argument("--new",      action="store_true", help="Only today's jobs")
    p_list.add_argument("--pending",  action="store_true", help="Exclude already applied")

    # show
    p_show = sub.add_parser("show", help="Show full job details")
    p_show.add_argument("job_id")

    # apply
    p_apply = sub.add_parser("apply", help="Mark job as applied")
    p_apply.add_argument("job_id")

    # note
    p_note = sub.add_parser("note", help="Add note to a job")
    p_note.add_argument("job_id")
    p_note.add_argument("text")

    # export / stats / reset
    sub.add_parser("export", help="Export all jobs to CSV")
    sub.add_parser("stats",  help="Show scrape statistics")
    sub.add_parser("reset",  help="Delete the database and start fresh")

    args = parser.parse_args()

    if args.cmd == "list":
        list_jobs(
            keyword=args.keyword,
            company=args.company,
            location=args.location,
            new_only=args.new,
            not_applied=args.pending,
        )
    elif args.cmd == "show":
        show_job(args.job_id)
    elif args.cmd == "apply":
        mark_applied(args.job_id)
    elif args.cmd == "note":
        add_note(args.job_id, args.text)
    elif args.cmd == "export":
        export_csv()
    elif args.cmd == "stats":
        show_stats()
    elif args.cmd == "reset":
        reset_db()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""
score.py — AI match scoring for scraped jobs (Google Gemini, free tier).

For every job that has a description, sends your resume (cv.pdf) + the job
description to Gemini and asks it to rate three dimensions 0-100:
  • experience  — how well the seniority level fits a new grad
  • tech_stack  — overlap between the job's tech and your resume
  • company     — company scale / sector (banking is penalised)

The final `match_score` written back to the DB is the weighted average of
those three (weights live in config.py → "match_scoring"). notion_sync.py
then orders by match_score, so your best-fit jobs surface first in Notion.

Why Gemini: the free tier needs no credit card and allows ~250 requests/day
on gemini-2.5-flash — far more than enough at this volume.

Setup:
  1. pip install google-genai
  2. Put your resume at cv.pdf (next to this file)
  3. Get a free key at https://aistudio.google.com/apikey
  4. Put it in .env as  GEMINI_API_KEY=...   (see .env.example)
  5. Run: python score.py            (scores new jobs)
          python score.py --all      (re-scores everything)
          python score.py --dry-run  (prints, writes nothing)
"""

import os
import time
import sqlite3
import logging
import argparse

from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

from google import genai
from google.genai import types

from config import CONFIG

log = logging.getLogger(__name__)

HERE    = os.path.dirname(__file__)
DB_PATH = os.path.join(HERE, "jobs.db")
MS      = CONFIG.get("match_scoring", {})


# ── Structured output the model must return ───────────────────────────────
class MatchResult(BaseModel):
    experience: int   # 0-100
    tech_stack: int   # 0-100
    company:    int   # 0-100
    reason:     str   # one short sentence


def build_system_prompt() -> str:
    """Assemble the scoring rubric from config — this is your editable prompt."""
    c = MS["criteria"]
    return (
        "You score how well a job posting fits a job seeker, given their "
        "resume (attached as a PDF) and a job description.\n"
        "Return an integer 0-100 for each of three dimensions, plus one short "
        "sentence of reasoning. 0 = terrible fit, 100 = ideal fit.\n\n"
        f"experience: {c['experience']}\n\n"
        f"tech_stack: {c['tech_stack']}\n\n"
        f"company: {c['company']}\n\n"
        "Judge only from the resume and the job description. If something is "
        "unclear, score it conservatively (middle of the range)."
    )


def load_resume_bytes() -> bytes:
    path = os.path.join(HERE, MS.get("resume_path", "cv.pdf"))
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Resume not found at {path}. Put your CV there or set "
            f'match_scoring["resume_path"] in config.py.'
        )
    with open(path, "rb") as f:
        return f.read()


def ensure_columns(conn: sqlite3.Connection):
    """Add match_score / match_reason columns if they don't exist yet."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "match_score" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN match_score REAL")
    if "match_reason" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN match_reason TEXT")
    conn.commit()


def job_text(job: dict) -> str:
    desc = (job.get("description") or "")[: MS.get("max_desc_chars", 6000)]
    return (
        f"Title: {job.get('title','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n\n"
        f"Job description:\n{desc}"
    )


def is_retryable(err: Exception) -> bool:
    """Transient errors worth waiting out: rate limits (429) and overload (503/500)."""
    msg = str(err).lower()
    return any(s in msg for s in (
        "429", "resource_exhausted", "quota", "rate",      # rate limits
        "503", "unavailable", "overloaded", "high demand",  # temporary overload
        "500", "internal",                                  # transient server errors
    ))


def score_job(client, system: str, resume_pdf: bytes, job: dict) -> MatchResult:
    """One scored job, with simple backoff on free-tier rate limits."""
    resume_part = types.Part.from_bytes(data=resume_pdf, mime_type="application/pdf")
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=MatchResult,
        temperature=0,
    )

    attempts = 3
    for attempt in range(attempts):
        try:
            resp = client.models.generate_content(
                model=MS.get("model", "gemini-2.5-flash"),
                contents=[resume_part, job_text(job)],
                config=config,
            )
            if resp.parsed is not None:
                return resp.parsed
            # Fallback: parse the raw JSON text ourselves.
            return MatchResult.model_validate_json(resp.text)
        except Exception as e:
            if is_retryable(e) and attempt < attempts - 1:
                log.warning(f"    temporary error ({str(e)[:60]}…) — "
                            f"waiting 25s and retrying ({attempt+1}/{attempts-1})…")
                time.sleep(25)
                continue
            raise


def weighted(result: MatchResult) -> float:
    w = MS["weights"]
    total = (
        result.experience * w["experience"]
        + result.tech_stack * w["tech_stack"]
        + result.company    * w["company"]
    )
    return round(total, 1)


def run(rescore_all: bool = False, dry_run: bool = False, limit: int = 0):
    if not MS.get("enabled", True):
        log.info("[Score] match_scoring disabled in config.py")
        return

    weights = MS["weights"]
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        log.warning(f"[Score] weights sum to {sum(weights.values())}, not 1.0 — "
                    "scores will be off-scale.")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        log.info("[Score] GEMINI_API_KEY not set — skipping AI scoring")
        return
    client = genai.Client(api_key=api_key)
    system = build_system_prompt()
    resume_pdf = load_resume_bytes()
    delay = MS.get("request_delay_seconds", 7)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_columns(conn)

    where = "description IS NOT NULL AND TRIM(description) != ''"
    if not rescore_all:
        where += " AND match_score IS NULL"
    sql = f"SELECT * FROM jobs WHERE {where} ORDER BY scraped_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    jobs = [dict(r) for r in conn.execute(sql).fetchall()]
    log.info(f"[Score] {len(jobs)} job(s) to score "
             f"({'all' if rescore_all else 'new only'})")

    scored = errors = 0
    for i, job in enumerate(jobs):
        try:
            result = score_job(client, system, resume_pdf, job)
            final = weighted(result)
            if dry_run:
                log.info(f"  [DRY] {final:5.1f}  {job['title']} @ {job['company']} "
                         f"(exp {result.experience}/tech {result.tech_stack}/"
                         f"co {result.company}) — {result.reason}")
            else:
                conn.execute(
                    "UPDATE jobs SET match_score=?, match_reason=? WHERE job_id=?",
                    (final, result.reason, job["job_id"]),
                )
                conn.commit()
                log.info(f"  scored {final:5.1f}  {job['title']} @ {job['company']}")
            scored += 1
        except Exception as e:
            errors += 1
            log.error(f"  ERROR {job.get('title','?')} @ {job.get('company','?')}: {e}")

        # Throttle to stay under the free-tier per-minute limit.
        if delay and i < len(jobs) - 1:
            time.sleep(delay)

    conn.close()
    log.info(f"[Score] Done — scored {scored}, errors {errors}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    p = argparse.ArgumentParser(description="AI match scoring for scraped jobs")
    p.add_argument("--all",     action="store_true", help="re-score every job, not just new ones")
    p.add_argument("--dry-run", action="store_true", help="print scores without writing to the DB")
    p.add_argument("--limit",   type=int, default=0, help="only score the N most recent jobs")
    args = p.parse_args()

    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("\n  Set GEMINI_API_KEY in .env first (see .env.example).")
        print("  Get a free key at https://aistudio.google.com/apikey\n")
    else:
        run(rescore_all=args.all, dry_run=args.dry_run, limit=args.limit)

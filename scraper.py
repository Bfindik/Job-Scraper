"""
LinkedIn Job Scraper — Long-lasting, resilient solution
- Primary: Guest API (fast, no browser)
- Fallback: Playwright (if API breaks)
- Storage: SQLite (deduplication across runs)
- Scheduling: runs daily automatically
"""

import sqlite3
import requests
import time
import random
import json
import csv
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional
from config import CONFIG

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Data model ───────────────────────────────────────────────────────────
@dataclass
class Job:
    job_id: str
    title: str
    company: str
    location: str
    posted_date: str
    job_url: str
    salary: str = ""
    description: str = ""
    scraped_at: str = ""

    def __post_init__(self):
        self.scraped_at = datetime.now().isoformat()

# ── User-Agent pool ──────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.linkedin.com/",
    }

def random_delay():
    """Human-like delay between requests."""
    time.sleep(random.uniform(CONFIG["min_delay"], CONFIG["max_delay"]))

# ── Database ─────────────────────────────────────────────────────────────
class Database:
    def __init__(self, path="jobs.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                posted_date TEXT,
                job_url     TEXT,
                salary      TEXT,
                description TEXT,
                scraped_at  TEXT,
                is_applied  INTEGER DEFAULT 0,
                notes       TEXT DEFAULT ''
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at      TEXT,
                jobs_found  INTEGER,
                jobs_new    INTEGER,
                method      TEXT
            )
        """)
        # Jobs you deleted in Notion — never scrape/re-add these again.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ignored_jobs (
                job_id     TEXT PRIMARY KEY,
                title      TEXT,
                company    TEXT,
                ignored_at TEXT
            )
        """)
        self.conn.commit()

    def job_exists(self, job_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM jobs WHERE job_id=?", (job_id,))
        return cur.fetchone() is not None

    def is_ignored(self, job_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM ignored_jobs WHERE job_id=?", (job_id,))
        return cur.fetchone() is not None

    def insert_job(self, job: Job) -> bool:
        """Returns True if inserted (new), False if already existed."""
        if self.job_exists(job.job_id):
            return False
        self.conn.execute(
            """INSERT INTO jobs
               (job_id, title, company, location, posted_date, job_url, salary, description, scraped_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (job.job_id, job.title, job.company, job.location,
             job.posted_date, job.job_url, job.salary, job.description, job.scraped_at),
        )
        self.conn.commit()
        return True

    def log_run(self, jobs_found: int, jobs_new: int, method: str):
        self.conn.execute(
            "INSERT INTO scrape_runs (run_at, jobs_found, jobs_new, method) VALUES (?,?,?,?)",
            (datetime.now().isoformat(), jobs_found, jobs_new, method),
        )
        self.conn.commit()

    def export_csv(self, filepath="jobs_export.csv"):
        cur = self.conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
        log.info(f"Exported {len(rows)} jobs -> {filepath}")
        return filepath

    def get_stats(self):
        total   = self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        today   = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE DATE(scraped_at)=DATE('now')"
        ).fetchone()[0]
        applied = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE is_applied=1").fetchone()[0]
        return {"total": total, "today": today, "applied": applied}

# ── Guest API Scraper (Primary) ──────────────────────────────────────────
class GuestAPIScraper:
    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def scrape(self, keyword: str, location: str, max_jobs: int = 100) -> list[Job]:
        jobs = []
        start = 0
        session = requests.Session()

        log.info(f"[GuestAPI] '{keyword}' in '{location}' — target {max_jobs} jobs")

        while len(jobs) < max_jobs:
            params = {
                "keywords": keyword,
                "location": location,
                "start": start,
                "f_TPR": "r604800",  # past week
            }
            try:
                resp = session.get(
                    self.BASE_URL,
                    params=params,
                    headers=get_headers(),
                    timeout=15,
                )
                if resp.status_code == 429:
                    log.warning("Rate limited — sleeping 60s")
                    time.sleep(60)
                    continue
                if resp.status_code != 200:
                    log.error(f"HTTP {resp.status_code} — stopping")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.find_all("div", class_="base-card")

                if not cards:
                    log.info(f"No more results at start={start}")
                    break

                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)

                log.info(f"  Fetched {len(cards)} cards (total so far: {len(jobs)})")
                start += 10
                random_delay()

            except requests.RequestException as e:
                log.error(f"Request error: {e}")
                break

        return jobs[:max_jobs]

    def _parse_card(self, card) -> Optional[Job]:
        try:
            # Job ID
            job_id = card.get("data-entity-urn", "").split(":")[-1]
            if not job_id:
                anchor = card.find("a", class_="base-card__full-link")
                job_id = anchor["href"].split("/")[-1].split("?")[0] if anchor else ""

            title_el  = card.find("h3", class_="base-search-card__title")
            comp_el   = card.find("h4", class_="base-search-card__subtitle")
            loc_el    = card.find("span", class_="job-search-card__location")
            time_el   = card.find("time")
            link_el   = card.find("a", class_="base-card__full-link")
            salary_el = card.find("span", class_="job-search-card__salary-info")

            return Job(
                job_id      = job_id,
                title       = title_el.get_text(strip=True) if title_el else "N/A",
                company     = comp_el.get_text(strip=True)  if comp_el  else "N/A",
                location    = loc_el.get_text(strip=True)   if loc_el   else "N/A",
                posted_date = time_el.get("datetime", "")   if time_el  else "",
                job_url     = link_el["href"].split("?")[0]  if link_el  else "",
                salary      = salary_el.get_text(strip=True) if salary_el else "",
            )
        except Exception as e:
            log.debug(f"Card parse error: {e}")
            return None

    def fetch_description(self, job_id: str) -> str:
        """Fetch the full job description by hitting the per-job endpoint."""
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            desc_el = soup.find("div", class_="show-more-less-html__markup") \
                   or soup.find("div", class_="description__text")
            return desc_el.get_text(" ", strip=True) if desc_el else ""
        except requests.RequestException as e:
            log.debug(f"Description fetch error for {job_id}: {e}")
            return ""

# ── Playwright Fallback Scraper ──────────────────────────────────────────
class PlaywrightScraper:
    def scrape(self, keyword: str, location: str, max_jobs: int = 50) -> list[Job]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        jobs = []
        log.info(f"[Playwright] '{keyword}' in '{location}'")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=random.choice(USER_AGENTS))
            page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })

            url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={keyword.replace(' ', '%20')}"
                f"&location={location.replace(' ', '%20')}"
                f"&f_TPR=r604800"
            )
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            # Scroll to load more jobs
            for _ in range(max_jobs // 25):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                try:
                    btn = page.query_selector("button.infinite-scroller__show-more-button")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2000)
                except:
                    pass

            cards = page.query_selector_all(".base-card")
            log.info(f"  Found {len(cards)} cards via Playwright")

            for card in cards[:max_jobs]:
                try:
                    title   = card.query_selector(".base-search-card__title")
                    company = card.query_selector(".base-search-card__subtitle")
                    loc     = card.query_selector(".job-search-card__location")
                    link    = card.query_selector("a.base-card__full-link")
                    t       = card.query_selector("time")

                    job_url = link.get_attribute("href").split("?")[0] if link else ""
                    job_id  = job_url.split("/")[-1] if job_url else ""

                    jobs.append(Job(
                        job_id      = job_id,
                        title       = title.inner_text().strip()                if title   else "N/A",
                        company     = company.inner_text().strip()              if company else "N/A",
                        location    = loc.inner_text().strip()                  if loc     else "N/A",
                        posted_date = t.get_attribute("datetime")               if t       else "",
                        job_url     = job_url,
                    ))
                except Exception as e:
                    log.debug(f"Playwright card error: {e}")

            browser.close()

        return jobs

# ── Experience-level filter ──────────────────────────────────────────────
def is_senior_by_title(job: Job) -> bool:
    """Cheap check using only the title (no extra request)."""
    title = job.title.lower().strip()
    for prefix in CONFIG.get("blocked_title_prefixes", []):
        if title.__contains__(prefix.lower()):
            log.debug(f"  FILTERED (senior title): {job.title}")
            return True
    return False


def is_senior_by_description(desc: str) -> Optional[str]:
    """Returns the matched phrase if description contains a blocked phrase, else None."""
    desc_lower = (desc or "").lower()
    for phrase in CONFIG.get("blocked_description_phrases", []):
        if phrase.lower() in desc_lower:
            return phrase
    return None


# ── Orchestrator ─────────────────────────────────────────────────────────
class LinkedInJobScraper:
    def __init__(self):
        self.db  = Database()
        self.api = GuestAPIScraper()
        self.pw  = PlaywrightScraper()

    def run(self):
        log.info("=" * 60)
        log.info(f"Starting scrape run — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        total_found = 0
        total_new   = 0
        method_used = "guest_api"

        for search in CONFIG["searches"]:
            keyword  = search["keyword"]
            location = search["location"]
            max_jobs = search.get("max_jobs", CONFIG["default_max_jobs"])

            # Try Guest API first
            jobs = self.api.scrape(keyword, location, max_jobs)

            # If API returns nothing, fall back to Playwright
            if not jobs:
                log.warning("Guest API returned 0 jobs — switching to Playwright fallback")
                jobs = self.pw.scrape(keyword, location, max_jobs)
                method_used = "playwright"

            new_count       = 0
            filtered_title  = 0
            filtered_desc   = 0
            filter_enabled  = CONFIG.get("filter_senior_jobs", True)

            for job in jobs:
                # Stage 0: skip jobs you already rejected in Notion (no extra request)
                if self.db.is_ignored(job.job_id):
                    continue

                # Stage 1: cheap title check (no extra request)
                if filter_enabled and is_senior_by_title(job):
                    filtered_title += 1
                    continue

                # Stage 2: fetch description and check phrases (extra request)
                if filter_enabled and CONFIG.get("blocked_description_phrases"):
                    job.description = self.api.fetch_description(job.job_id)
                    random_delay()  # be polite — extra request

                    matched = is_senior_by_description(job.description)
                    if matched:
                        log.debug(f"  FILTERED (exp phrase '{matched}'): {job.title}")
                        filtered_desc += 1
                        continue

                if self.db.insert_job(job):
                    new_count += 1
                    log.info(f"  NEW: {job.title} @ {job.company} ({job.location})")

            log.info(
                f"  '{keyword}' / '{location}': {len(jobs)} found | "
                f"{filtered_title} senior-title | {filtered_desc} senior-desc | "
                f"{new_count} new saved"
            )
            total_found += len(jobs)
            total_new   += new_count

            random_delay()

        self.db.log_run(total_found, total_new, method_used)

        stats = self.db.get_stats()
        log.info(f"\nRun complete — Found: {total_found} | New: {total_new}")
        log.info(f"Database: {stats['total']} total jobs | {stats['applied']} applied")

        # Auto-export CSV after each run
        self.db.export_csv("jobs_export.csv")

        def notion_sync():
            """Push new jobs + update scores. Isolated so a failure never
            stops the rest of the run."""
            try:
                from notion_sync import sync, NOTION_TOKEN
                if NOTION_TOKEN.startswith("secret_xxx") or NOTION_TOKEN.startswith("ntn_xxx"):
                    log.info("Notion sync skipped — token not configured (set NOTION_TOKEN in .env)")
                    return
                sync()
            except Exception as e:
                log.warning(f"Notion sync failed: {e}")

        # 1) Push new jobs to Notion FIRST, so they appear even if the (slower,
        #    rate-limited) AI scoring step is interrupted or fails.
        log.info("Syncing new jobs to Notion...")
        notion_sync()

        # 2) Score the newly scraped jobs with AI (Gemini).
        try:
            import score
            log.info("Scoring new jobs with AI...")
            score.run()  # new jobs only; no-ops if GEMINI_API_KEY isn't set
        except Exception as e:
            log.warning(f"AI scoring failed: {e}")

        # 3) Sync again to write the fresh match scores onto the Notion pages.
        log.info("Updating Notion with match scores...")
        notion_sync()

if __name__ == "__main__":
    LinkedInJobScraper().run()
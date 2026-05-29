<div align="left">

# 📋 JobTracker

### Free LinkedIn job scraper for new grads — filters out senior roles, AI-scores your fit, syncs to Notion

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Notion](https://img.shields.io/badge/Notion-000000?style=flat&logo=notion&logoColor=white)](https://developers.notion.com/)
[![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=flat&logo=googlegemini&logoColor=white)](https://aistudio.google.com/)

*Scrape LinkedIn → Filter senior roles → AI-score your fit → Track in SQLite → Sync to Notion → Apply.*

</div>

---

## ✨ Why JobTracker?

I built JobTracker during my own job search as a new grad — it scrapes LinkedIn, filters out senior roles, scores how well each job fits *me* with AI, and syncs new listings to Notion so I can focus on roles that actually match my level.

- 🔍 **Two-stage filtering** — title prefix check (`Senior`, `Lead`...) + description scan (`3+ years`...)
- 🤖 **AI match scoring** — Gemini reads your resume (`cv.pdf`) + each job and rates fit, so best matches surface first
- 💾 **SQLite storage** — zero duplicates, persistent state, applied/favorite tracking
- 📋 **Notion two-way sync** — pushes new jobs in; jobs you delete in Notion get pruned from the DB (and never come back)
- 🛡️ **Resilient** — Guest API primary + Playwright fallback, rotating user-agents, randomized delays
- ⚡ **Zero cost** — no API keys to scrape; Notion and Gemini both run on free tiers
- 🗂️ **CLI included** — search, filter, mark applied, add notes, export to CSV

---

## 🎬 Quick Start

```bash
git clone https://github.com/<your-username>/job-tracker.git
cd job-tracker
pip install -r requirements.txt

cp .env.example .env   # optional: add NOTION_TOKEN, NOTION_DB_ID, GEMINI_API_KEY
# edit config.py with your job searches, then:
python scraper.py
```

`scraper.py` scrapes → pushes new jobs to Notion → AI-scores them → updates Notion with the scores. Results land in `jobs.db` and (optionally) your Notion database.

---

## ⚙️ Configuration

All search settings live in `config.py`:

```python
CONFIG = {
    "searches": [
        {"keyword": "Backend Engineer", "location": "Remote",   "max_jobs": 100},
        {"keyword": "Python Developer", "location": "Istanbul", "max_jobs": 50},
    ],
    "filter_senior_jobs": True,
    "blocked_title_prefixes": ["senior", "lead", "principal", "staff", "manager", "architect"],
    "blocked_description_phrases": ["3+ years", "5+ years", "at least 5 years"],
    "schedule_time": "09:00",   # daily run time
    "min_delay": 2, "max_delay": 5,
    "match_scoring": {          # AI scoring — weights must sum to 1.0
        "model": "gemini-2.5-flash",
        "weights": {"experience": 0.5, "tech_stack": 0.3, "company": 0.2},
    },
}
```

Secrets (Notion token + DB ID, Gemini key) go in `.env` — see `.env.example`.

---

## 🤖 AI Match Scoring

`score.py` sends your resume (`cv.pdf`) + each job description to **Google Gemini**, which rates three dimensions 0–100 — **experience** (seniority fit), **tech_stack** (overlap with your resume), **company** (scale/sector). The weighted average becomes each job's `match_score`, and Notion orders by it so best-fit jobs surface first.

```bash
python score.py            # score new jobs only
python score.py --all      # re-score everything
python score.py --dry-run  # print scores, write nothing
```

> Free Gemini tier needs no credit card (~250 req/day on `gemini-2.5-flash`). Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey), add it to `.env` as `GEMINI_API_KEY`. The scoring rubric in `config.py` is *your* prompt — edit freely.

---

## 🗂️ Project Structure

```
scraper.py       # Main scraper (Guest API + Playwright fallback) → Notion → AI score
config.py        # Search settings, filter rules & scoring weights
score.py         # AI match scoring (Google Gemini)
notion_sync.py   # Push new jobs → Notion (ordered by match score)
notion_to_db.py  # Reverse sync: prune DB to match Notion + blocklist
jobs_cli.py      # CLI to query/manage scraped jobs
cv.pdf           # Your resume for AI scoring (gitignored)
jobs.db          # Auto-generated SQLite DB (gitignored)
```

---

## 🛠️ CLI Commands

```bash
python jobs_cli.py list                  # all jobs  (--new, --pending, --keyword python)
python jobs_cli.py show <job_id>         # full details for one job
python jobs_cli.py apply <job_id>        # mark as applied
python jobs_cli.py note <job_id> "text"  # attach a note
python jobs_cli.py export                # export to CSV
python jobs_cli.py stats                 # summary stats
python jobs_cli.py reset                 # wipe database (with confirmation)
```

---

## 🔗 Notion Integration

<details>
<summary><strong>Setup (3 minutes)</strong></summary>

1. Create an integration at [notion.so/my-integrations](https://www.notion.so/my-integrations) → copy the **Internal Integration Token** (`ntn_` / `secret_`).
2. Create a database with columns: `Status`, `LinkedIn URL` (URL), `Posted Date` / `Scraped At` (Date), `Favorite` (Checkbox), `Job ID` (Number), `Location` (Multi-select), `Match Score` (Number). Then `···` → **Connections** → add `job-tracker`.
3. `cp .env.example .env`, fill in `NOTION_TOKEN` + `NOTION_DB_ID`, run `python notion_sync.py`. After that, `scraper.py` auto-syncs every run.

</details>

**Reverse sync:** delete jobs that don't fit you in Notion, then run `python notion_to_db.py` (`--dry-run` to preview). They're removed from `jobs.db` *and* blocklisted so the scraper never re-adds them. If the Notion query fails, nothing is deleted.

---

## 🧪 How the Filtering Works

Cheap checks first, expensive checks only when needed:

1. **Notion blocklist** *(no request)* — skip any job you already rejected in Notion.
2. **Title check** *(no extra request)* — skip titles starting with `senior`, `lead`, `principal`...
3. **Description check** *(1 request per job that passed)* — skip if it hits `3+ years`, `minimum 5 years`...

This minimizes requests so you don't hit LinkedIn's rate limits while still catching senior roles hidden in the description.

---

## 🚧 Tips & Gotchas

- **Getting blocked?** Raise `min_delay` / `max_delay` to 5/10.
- **Fewer requests?** Set `blocked_description_phrases: []` — only the title filter runs.
- **AI hitting limits?** Free Gemini is ~10 req/min — bump `request_delay_seconds` or use `gemini-2.5-flash-lite` (~1000/day).
- **Cron it:** runs daily at `schedule_time`, or add `python scraper.py` to cron / Task Scheduler.
- **Schema changes?** Delete `jobs.db` (or `python jobs_cli.py reset`) and re-run.

---

<div align="center">

**Built with frustration during a job hunt — may yours be short.**

⭐ Star this repo if it helped you!

</div>

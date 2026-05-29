<div align="left">

# 📋 JobTracker

### Free LinkedIn job scraper for new grads — filters out senior roles, syncs to Notion

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Notion](https://img.shields.io/badge/Notion-000000?style=flat&logo=notion&logoColor=white)](https://developers.notion.com/)

*Scrape LinkedIn → Filter senior roles → Track in SQLite → Sync to Notion → Apply.*

</div>

---

## ✨ Why JobTracker?

I built JobTracker during my own job search as a new grad — it scrapes LinkedIn, filters out senior roles, and syncs new listings to Notion so I can focus on roles that actually match my level.

- 🔍 **Two-stage filtering** — title prefix check (`Senior`, `Lead`...) + description scan (`3+ years`, `5 years experience`...)
- 💾 **SQLite storage** — zero duplicates across runs, persistent state, applied/favorite tracking
- 📋 **Notion integration** — auto-syncs new jobs into a clean Notion database after every scrape
- 🛡️ **Resilient by design** — Guest API primary + Playwright fallback, rotating user-agents, randomized delays
- ⚡ **Zero cost** — no paid services, no API keys for scraping (only Notion if you want sync)
- 🗂️ **CLI included** — search, filter, mark applied, add notes, export to CSV

---

## 🎬 Quick Start

```bash
# 1. Clone and install
git clone https://github.com/<your-username>/job-tracker.git
cd job-tracker
pip install -r requirements.txt

# 2. (Optional) Set up Notion sync
cp .env.example .env
# Edit .env with your Notion token + database ID

# 3. Edit config.py with your job searches

# 4. Run!
python scraper.py
```

That's it. New jobs land in `jobs.db` (SQLite) and optionally in your Notion database.

---

## ⚙️ Configuration

All search settings live in `config.py`:

```python
CONFIG = {
    "searches": [
        {"keyword": "Backend Engineer", "location": "Remote",   "max_jobs": 100},
        {"keyword": "Python Developer", "location": "Istanbul", "max_jobs": 50},
    ],

    # Skip senior roles automatically
    "filter_senior_jobs": True,

    "blocked_title_prefixes": [
        "senior", "sr.", "lead", "principal", "staff",
        "director", "vp", "manager", "architect",
    ],

    "blocked_description_phrases": [
        "3+ years", "5+ years", "minimum 3 years",
        "at least 5 years", "10+ years of experience",
    ],

    "min_delay": 2,
    "max_delay": 5,
}
```

Secrets (Notion token, database ID) go in `.env` — see `.env.example`.

---

## 🗂️ Project Structure

```
jobs-tracker/
├── scraper.py                  # Main scraper (Guest API + Playwright fallback)
├── config.py                   # Search settings & filter rules
├── notion_sync.py              # Auto-push new jobs → Notion
├── jobs_cli.py                 # CLI to query/manage scraped jobs
├── notion_jobs_template.csv    # Notion database template
├── requirements.txt
├── .env.example                # Template for your secrets
├── .gitignore
└── jobs.db                     # Auto-generated SQLite DB (gitignored)
```

---

## 🛠️ CLI Commands

The `jobs_cli.py` script gives you a quick interface to your scraped jobs:

| Command | Description |
|---|---|
| `python jobs_cli.py list` | Show all jobs |
| `python jobs_cli.py list --new` | Only today's results |
| `python jobs_cli.py list --pending` | Jobs you haven't applied to |
| `python jobs_cli.py list --keyword python` | Filter by keyword |
| `python jobs_cli.py show <job_id>` | Full details for one job |
| `python jobs_cli.py apply <job_id>` | Mark as applied |
| `python jobs_cli.py note <job_id> "text"` | Attach a note |
| `python jobs_cli.py export` | Export all jobs to CSV |
| `python jobs_cli.py stats` | Show summary stats |
| `python jobs_cli.py reset` | Wipe database (with confirmation) |

---

## 🔗 Notion Integration

Auto-sync every scraped job into a Notion database for visual tracking.

<details>
<summary><strong>Setup (3 minutes)</strong></summary>

### 1. Create a Notion integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. **New integration** → name it `job-tracker`
3. Copy the **Internal Integration Token** (starts with `ntn_` or `secret_`)

### 2. Import the CSV template

1. In Notion, create a new page → **Import** → **CSV** → upload `notion_jobs_template.csv`
2. Set column types:
   - `Status` → **Status** (`New`, `Saved`, `Applied`)
   - `LinkedIn URL` → **URL**
   - `Posted Date` / `Scraped At` → **Date**
   - `Favorite` → **Checkbox**
   - `Job ID` → **Number**
   - `Location` → **Multi-select**

### 3. Connect integration to the database

1. Open the database, click `···` (top-right) → **Connections**
2. Add `job-tracker`

### 4. Configure & run

```bash
# Create .env from template and fill in your values
cp .env.example .env

# Then run sync
python notion_sync.py
```

From now on, `scraper.py` auto-syncs to Notion after every run.

</details>

---

## 🏗️ Architecture

```
                  ┌────────────────────────┐
                  │      LinkedIn          │
                  │      Guest API         │  ← primary (fast)
                  └──────────┬─────────────┘
                             │
              fallback if blocked or empty
                             ↓
                  ┌────────────────────────┐
                  │   Playwright + Chrome  │
                  └──────────┬─────────────┘
                             │
                             ↓
              ┌──────────────────────────────┐
              │     Filter Pipeline          │
              │  • Title prefix check        │
              │  • Description phrase scan   │
              └──────────┬───────────────────┘
                         │
                         ↓
              ┌──────────────────────┐
              │   SQLite (jobs.db)   │  ← single source of truth
              └────┬─────────────────┘
                   │
        ┌──────────┼──────────┬──────────────┐
        ↓          ↓          ↓              ↓
       CLI       CSV       Notion        (your future
                          (auto-sync)     dashboard)
```

---

## 🧪 How the Filtering Works

Two-stage approach — cheap check first, expensive check only when needed:

**Stage 1 — Title check (no extra request):**
```python
if title.__contains__(("senior", "lead", "principal", ...)):
    skip()
```

**Stage 2 — Description check (1 extra request per job that passed Stage 1):**
```python
desc = fetch_description(job_id)
if "3+ years" in desc or "minimum 5 years" in desc:
    skip()
```

This minimizes requests so you don't hit LinkedIn's rate limits while still catching senior roles hidden in the description.

---

## 🚧 Tips & Gotchas

- **Getting blocked?** Increase `min_delay` / `max_delay` in `config.py` to 5/10.
- **Want fewer requests?** Set `blocked_description_phrases: []` — only title filter runs (no per-job fetches).
- **Cron it:** Add `python scraper.py` to your daily cron / Task Scheduler / launchd.
- **DB schema changes?** Delete `jobs.db` (or `python jobs_cli.py reset`) and re-run.

---


<div align="center">

**Built with frustration during a job hunt — may yours be short.**

⭐ Star this repo if it helped you!

</div>

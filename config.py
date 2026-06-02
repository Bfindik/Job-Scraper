"""
config.py — Edit this file to customize your job search.
No other file needs to be touched.
"""


def _experience_phrases(min_years: int = 3, max_years: int = 10) -> list:
    """Generate the 'too senior' description phrases for every year in the
    range so we don't have to hand-list each one. Matching is a plain
    case-insensitive substring check (see scraper.is_senior_by_description)."""
    phrases = []
    for n in range(min_years, max_years + 1):
        phrases += [
            f"{n}+ years",
            f"{n} or more years",
            f"minimum {n} years",
            f"minimum of {n}",
            f"at least {n} years",
            f"{n} years of experience",
            f"{n} yıl",          # Turkish: "N years"
            f"{n}+ yıl",
        ]
    # Ranges like "3-5 years", "4-6 years", ...
    for n in range(min_years, max_years):
        phrases.append(f"{n}-{n + 2} years")
    return phrases


CONFIG = {
    # ── Your job searches ──────────────────────────────────────────────
    # Add as many (keyword + location) pairs as you want.
    "searches": [
        {"keyword": "Java Developer",    "location": "Turkey",         "max_jobs": 20},
        {"keyword": "Backend Engineer",    "location": "Turkey",       "max_jobs": 20},
        {"keyword": "Software Engineer",       "location": "Turkey",         "max_jobs": 20},
        {"keyword": "Junior Developer",    "location": "Turkey",         "max_jobs": 20},
        {"keyword": "Yazılım Mühendisi",    "location": "Turkey",         "max_jobs": 20},

        # Add more:
        # {"keyword": "DevOps Engineer",  "location": "Berlin",         "max_jobs": 50},
    ],

    # ── Experience filter ─────────────────────────────────────────────
    # Set to True to skip jobs that look too senior / require too much experience.
    # Useful for new grads!
    "filter_senior_jobs": True,

    # Job TITLES that start with these words are skipped (case-insensitive).
    "blocked_title_prefixes": [
        "senior", "sr.", "sr ", "lead", "principal", "staff", "head of",
        "director", "vp ", "vice president", "manager", "architect","principal","kıdemli","part-time","internship","stajyer",
        "intern","part time","working student","mid-level","mid level"
    ],

    # If ANY of these phrases appear in the description, the job is skipped.
    # Catches things like "3+ years", "5 years experience", etc.
    # Auto-generated for 3–10 years (English + Turkish). Edit the range in
    # _experience_phrases() above, or append extra one-off phrases here:
    "blocked_description_phrases": _experience_phrases(3, 10) + [
        # add any custom phrases below
    ],

    # ── Scheduler ─────────────────────────────────────────────────────
    # Time (24h format) to run the scraper daily
    "schedule_time": "09:00",

    # ── Rate limiting (seconds) ───────────────────────────────────────
    # Increase these if you get blocked
    "min_delay": 2,
    "max_delay": 5,

    # ── Defaults ──────────────────────────────────────────────────────
    "default_max_jobs": 50,

    # ── Retention ─────────────────────────────────────────────────────
    # At the start of each run, delete jobs scraped more than this many days
    # ago so the database stays current. Applied jobs (is_applied=1) are kept.
    # Set to 0 to disable cleanup.
    "retention_days": 30,

    # ── AI match scoring (score.py) ───────────────────────────────────
    # Each job's description is sent to Google Gemini together with your
    # resume (cv.pdf). The model scores 3 dimensions 0-100; the final
    # match_score is their weighted average. Edit freely — this is "your
    # prompt". The resume is read by the model directly, so criteria can
    # refer to "the candidate's resume" instead of hard-coding your stack.
    "match_scoring": {
        "enabled":     True,
        # Google Gemini — free tier, no credit card. Get a key at
        # https://aistudio.google.com/apikey and put it in .env as GEMINI_API_KEY.
        # gemini-2.5-flash: 250 requests/day free. (gemini-2.5-flash-lite
        # allows ~1000/day if you ever need more headroom.)
        "model":       "gemini-2.5-flash",
        "resume_path": "cv.pdf",             # gitignored; sits next to this file
        "max_desc_chars": 6000,              # cap JD length sent
        # Free tier is ~10 requests/min — wait this long between jobs to avoid 429s.
        "request_delay_seconds": 7,

        # Weights MUST sum to 1.0. Experience matters most for a new grad.
        "weights": {
            "experience": 0.5,
            "tech_stack": 0.3,
            "company":    0.2,
        },

        # How the model should score each dimension (0 = bad fit, 100 = ideal).
        "criteria": {
            "experience":
                "The candidate is a NEW GRADUATE with little/no professional "
                "experience. Score 90-100 for entry-level / junior / "
                "new-grad roles. Score 0-20 for senior / lead / principal / "
                "staff / architect roles or anything requiring 3+ years. "
                "Mid-level (1-2 yrs) is 40-60.",
            "tech_stack":
                "Compare the technologies the job requires against the "
                "candidate's resume. Higher score = more overlap with skills "
                "the candidate already has.",
            "company":
                "Prefer established mid-to-large companies (more headcount = "
                "higher score). The BANKING / finance sector is undesirable: "
                "score it low even if everything else fits.",
        },
    },
}

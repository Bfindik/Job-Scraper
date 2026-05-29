"""
config.py — Edit this file to customize your job search.
No other file needs to be touched.
"""

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
    "blocked_description_phrases": [
        "3+ years", "3 or more years", "3-5 years", "4+ years", "5+ years",
        "6+ years", "7+ years", "8+ years", "10+ years",
        "minimum 3 years", "minimum of 3", "at least 3 years",
        "at least 4 years", "at least 5 years",
        "3 years of experience", "4 years of experience", "5 years of experience",
        "3 yıl", "4 yıl", "5 yıl", "6 yıl","7 yıl", "10 yıl"

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

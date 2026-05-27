"""
config.py — Edit this file to customize your job search.
No other file needs to be touched.
"""

CONFIG = {
    # ── Your job searches ──────────────────────────────────────────────
    # Add as many (keyword + location) pairs as you want.
    "searches": [
        {"keyword": "Java Developer",    "location": "Istanbul",         "max_jobs": 20},
        {"keyword": "Backend Engineer",    "location": "Istanbul",       "max_jobs": 20},
        {"keyword": "Software Engineer",       "location": "Istanbul",         "max_jobs": 20},
        {"keyword": "Junior Developer",    "location": "Istanbul",         "max_jobs": 10},
        {"keyword": "Yazılım Mühendisi",    "location": "Istanbul",         "max_jobs": 10},

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
        "director", "vp ", "vice president", "manager", "architect","principal","kıdemli","part-time","internship","stajyer"
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
}

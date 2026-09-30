"""
Central configuration — loads environment variables and exposes
typed constants used across all modules.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── API Keys ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]

REDDIT_CLIENT_ID: str = os.environ["REDDIT_CLIENT_ID"]
REDDIT_CLIENT_SECRET: str = os.environ["REDDIT_CLIENT_SECRET"]
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "40kDigest/1.0")

YOUTUBE_API_KEY: str = os.environ["YOUTUBE_API_KEY"]

# ── Email ─────────────────────────────────────────────────────────
GMAIL_ADDRESS: str = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD: str = os.environ["GMAIL_APP_PASSWORD"]
DIGEST_RECIPIENT: str = os.getenv("DIGEST_RECIPIENT", GMAIL_ADDRESS)

# ── Scoring ───────────────────────────────────────────────────────
ALERT_THRESHOLD: int = int(os.getenv("ALERT_THRESHOLD", "8"))

# ── Niche subreddits ──────────────────────────────────────────────
SUBREDDITS = [
    "Warhammer40k",
    "Warhammer",
    "minipainting",
    "ttrpg",
    "ageofsigmar",
    "killteam",
    "AdeptusMechanicus",
    "40kLore",
]

# ── YouTube search terms ──────────────────────────────────────────
YOUTUBE_QUERIES = [
    "Warhammer 40K 2026",
    "miniature painting 2026",
    "Kill Team 2026",
    "Warhammer lore 2026",
    "tabletop RPG 2026",
    "Age of Sigmar 2026",
]

# ── Aggregator URLs ───────────────────────────────────────────────
AGGREGATOR_URLS = [
    "https://later.com/blog/instagram-reels-trends/",
    "https://www.socialpilot.co/blog/instagram-reels-trends",
    "https://www.heyorca.com/blog/trending-audio-for-reels-tiktok",
    "https://www.scottsocialmarketing.com/blog/trending-reels-audio-this-week-on-instagram",
    "https://buffer.com/resources/trending-audio-instagram/",
]

# ── Community site URLs ───────────────────────────────────────────
COMMUNITY_URLS = [
    "https://www.warhammer-community.com/",
    "https://www.dakkadakka.com/",
]

# ── TikTok Creative Center ────────────────────────────────────────
TIKTOK_TREND_URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/music/pc/en"

# ── Claude model ─────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

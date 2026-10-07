"""
Central configuration — loads environment variables and exposes
typed constants used across all modules.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── API Keys ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]

REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID","")
REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET","")
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "40kDigest/1.0")

YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY","")

APIFY_API_KEY: str = os.getenv("APIFY_API_KEY", "")

# ── Email ─────────────────────────────────────────────────────────
GMAIL_ADDRESS: str = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD: str = os.environ["GMAIL_APP_PASSWORD"]
DIGEST_RECIPIENT: str = os.getenv("DIGEST_RECIPIENT", GMAIL_ADDRESS)

# ── Scoring ───────────────────────────────────────────────────────
ALERT_THRESHOLD: int = int(os.getenv("ALERT_THRESHOLD") or "8")

# Audio below this potency score is never recommended (email, alerts, Trend Scout examples)
MIN_RECOMMEND_SCORE: int = 6

# Week-over-week memory (built from saved digests in docs/data/)
HISTORY_WEEKS: int = 8
# After this many weekly recommendations a sound is held back from the email unless it's climbing
MAX_REPEAT_RECOMMENDATIONS: int = 2

# Hard cap on audio items sent to the scorer per run (keeps cost + output bounded)
MAX_AUDIO_ITEMS: int = 80
# Items per Claude call — small enough that the JSON reply never hits max_tokens
AUDIO_BATCH_SIZE: int = 15

# Content-format taxonomy the scorer classifies each audio item into
FORMAT_TYPES = [
    "POV + reaction",
    "Hobby + trending audio",
    "Green screen template",
    "Show/movie clip",
    "Audio/voiceline",
]

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
# Core niche — searched for both Shorts and 4–20 min videos
YOUTUBE_QUERIES = [
    "Warhammer 40K",
    "Warhammer 40k lore",
    "Kill Team",
    "Horus Heresy",
    "Age of Sigmar",
    "miniature painting",
    "miniature painting techniques",
    "warhammer hobby",
]

# Broader nerd / internet culture that crosses into the niche
YOUTUBE_CROSSOVER_QUERIES = [
    "Space Marine 2",
    "tabletop RPG",
    "dungeons and dragons",
    "green screen tutorial 40k",
    "warhammer meme",
    "nerd culture",
    "cosplay build",
    "3d printed miniatures",
]

YOUTUBE_WINDOW_DAYS: int = 14     # weekly run → look back two weeks
YOUTUBE_MAX_PER_GROUP: int = 30   # fastest-moving videos kept per query group

# ── Aggregator URLs ───────────────────────────────────────────────
AGGREGATOR_URLS = [
    "https://later.com/blog/instagram-reels-trends/",
    "https://www.socialpilot.co/blog/instagram-reels-trends",
    "https://www.heyorca.com/blog/trending-audio-for-reels-tiktok",
    "https://www.scottsocialmarketing.com/blog/trending-reels-audio-this-week-on-instagram",
    "https://buffer.com/resources/trending-audio-instagram/",
]

AGG_MAX_PER_SITE: int = 20      # newest linked sounds kept per trend blog

# ── Community site URLs ───────────────────────────────────────────
COMMUNITY_URLS = [
    "https://www.warhammer-community.com/",
]

# ── Apify (TikTok + Instagram) ────────────────────────────────────
# Apify Free = $5/month credit. Stay under this, leaving headroom for manual runs.
APIFY_MONTHLY_BUDGET_USD: float = 4.50
APIFY_RUN_BUDGET_USD: float = 0.75        # worst case for one run (both actors capped)

TIKTOK_REGION = "US"
TIKTOK_SONG_LIMIT: int = 60               # ~$0.06/run at $0.001 per song

# Reels under these hashtags show which sounds the niche itself is using
IG_HASHTAGS = [
    "warhammer40k",
    "minipainting",
    "warhammer",
    "miniaturepainting",
    "killteam",
    "paintingwarhammer",
]
IG_REELS_PER_HASHTAG: int = 35            # 210 reels ≈ $0.55/run on the Free plan rate

# ── RSS feeds (community news) ───────────────────────────────────
RSS_FEEDS = {
    "spikey_bits": "https://spikeybits.com/feed/",
    "tabletop_battles": "https://www.tabletopbattles.com/feed",   # goonhammer.com/feed redirects here
}
RSS_WINDOW_DAYS: int = 7
RSS_MAX_PER_FEED: int = 20

# ── Claude model ─────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-5-5"

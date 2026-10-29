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
# Worst case for one run: IG hashtags (0.65) + own-account comments (0.15).
# If you turn TikTok back on, add its 0.15 here too.
APIFY_RUN_BUDGET_USD: float = 0.85

# Off: as of Oct 2026 the Creative Center actor returns 0 songs for US/7d but still
# bills ~$0.05–0.23 per run. Flip to True to retry (e.g. with period "30").
TIKTOK_ENABLED: bool = False
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

# ── Own account (Comment Picks) ──────────────────────────────────
# Comments on your own recent posts, scraped through Apify (no Meta developer setup needed)
IG_ACCOUNT: str = os.getenv("IG_ACCOUNT", "itzzhobbytime")
COMMENTS_ENABLED: bool = True
COMMENT_WINDOW_DAYS: int = 7
OWN_POSTS_LIMIT: int = 10                 # newest posts checked for comments
COMMENTS_PER_POST: int = 30
COMMENT_PICKS: int = 3                    # max picks per email (fewer on slow weeks)

# ── RSS feeds (community news) ───────────────────────────────────
RSS_FEEDS = {
    "spikey_bits": "https://spikeybits.com/feed/",
    "tabletop_battles": "https://www.tabletopbattles.com/feed",   # goonhammer.com/feed redirects here
}
RSS_WINDOW_DAYS: int = 7
RSS_MAX_PER_FEED: int = 20

# ── Claude model ─────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-5-5"


# ── Content engines ──────────────────────────────────────────────
# Mirror of the "00 Content Engines" note in the ItzzHobbyTime Obsidian vault.
# Keep these in sync when an engine changes status there.
ENGINES = {
    "Road to Palm Springs": (
        "Core. The 99-day countdown following 2,000 pts of Astra Militarum to the Palm Springs "
        "tournament: list changes, practice games, painting progress, nerves. Includes the "
        "Recruit Diaries segment (one lesson or mistake of the week from a newer player) and "
        "the rivalry with @moss.and.monsters as storyline stakes."
    ),
    "Hobby FX Lab": (
        "Core. Outside-the-box crafting: film-set practical effects, LEDs/electronics and "
        "props-department tricks applied to minis and terrain (flicker fire, smoke, squib dust "
        "hits, rain rigs, forced perspective, UV reveals, servos, foley). Shape: reveal, 'film "
        "sets do this', how, reveal again. Always say the film-set angle."
    ),
    "Cinematic Recreations": (
        "Core. Pre-staged moments, or great moments from past games, reshot like a war film "
        "with VO, sound design, slider moves and FX (last Guardsman on the objective, tank "
        "that wouldn't die, danger-close artillery)."
    ),
    "Store Crawl": (
        "Core. Local game stores (Kingslayer Games, Brookhurst Hobbies, Lost Planet Games, "
        "Guildhouse): hidden-gem tours, best table shot cinematically, player street "
        "interviews, 'owner picks my next unit', event coverage."
    ),
    "Comment Replies": "Support. Instagram comment-reply Reels answering a viewer's comment (20-40s).",
    "Hobby on the Clock": (
        "Support. Realistic hobby time for someone with school and multiple jobs: 20 minutes "
        "between shifts, timer on screen, timelapse. Busy-week fallback."
    ),
    "Memes": (
        "Support. Trending audio/meme formats. Best used as a WRAPPER for the other engines "
        "(hobby content inside a proven meme format), not as a separate track."
    ),
    "Lore Through a Lens": (
        "Developing. A filmmaker learning 40k lore and pitching it like a movie ('how I'd shoot "
        "this', genre swaps, lore begging for a movie). Director reacting, not lore expert."
    ),
    "Digest Drop": (
        "Developing. 'New player tries to understand this week's 40k news' - honest beginner "
        "take; corrections in the comments are welcome engagement."
    ),
}
ENGINE_NAMES = list(ENGINES)

# Parked or dropped in the vault — the scorer must never suggest these
RETIRED_ENGINES = {
    "Shot Breakdown": "parked until more painting time and new gear",
    "Guardsman POV": "dropped as too formulaic",
}

# ── 99-day challenge + weekly rotation ───────────────────────────
import datetime as _dt
CHALLENGE_START = _dt.date(2026, 10, 8)
CHALLENGE_DAYS: int = 99      # day 99 is treated as tournament time
FINAL_PUSH_DAYS: int = 21     # last ~3 weeks: nearly all Road to Palm Springs

# Weekly baseline from the vault: Slot A story, Slot B craft (rotates), Slot C optional flex
ROTATION = [
    {"A": "Road to Palm Springs", "B": "Hobby FX Lab",          "C": "Memes"},
    {"A": "Road to Palm Springs", "B": "Store Crawl",           "C": "Comment Replies"},
    {"A": "Road to Palm Springs", "B": "Cinematic Recreations", "C": "Hobby on the Clock"},
    {"A": "Road to Palm Springs", "B": "Store Crawl",           "C": "Memes"},
]

# Shared account brief used by every Claude prompt
ACCOUNT_CONTEXT = """
ACCOUNT: @itzzhobbytime — a Warhammer 40K / minis / hobby Instagram (YouTube launching later).
Positioning: Warhammer 40K shot like a movie. Models that light up, smoke and explode, made by a
working film gaffer/DP with practical-effects experience. The film-set background is the
differentiator and may be referenced (especially in Hobby FX Lab).
Persona: a relatively NEW player (Warhammer since late 2023) learning competitive Astra Militarum
on the road to the Palm Springs tournament. Never position him as an expert, news authority or
lore master; frame ideas as him learning, trying, reacting.
Capacity: 1-3 posts a week around school and multiple jobs, so ideas must be batchable and
low-friction. Gear: camera, lights, slider.

WHAT PERFORMS: memes vastly outperform everything else. Non-meme posts only win when they
lead with the payoff (e.g. the LED Grey Knights reels). Every idea must follow these rules:
  1. Payoff first: reveal, explosion or finished shot in the first 1-2 seconds; the "how" after.
     Never open on build steps or a progress update.
  2. One clear reason to share: funny, impressive or useful.
  3. Joke on screen, story in the caption ("Guard players when they realize they need 60 more
     of these", not "Day 34: painted 20 Guardsmen").
  4. Use trending meme formats as the wrapper for hobby content.
"""

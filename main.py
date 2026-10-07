"""
main.py — orchestrates the full weekly digest pipeline.

Run locally:   python main.py
Run in CI:     triggered by GitHub Actions on schedule
"""

import sys
import json
import datetime
from pathlib import Path

# ── Scrapers ──────────────────────────────────────────────────────
from src.scrapers.aggregators import scrape_aggregators
from src.scrapers.reddit_scraper import scrape_reddit
from src.scrapers.youtube_scraper import scrape_youtube
from src.scrapers.apify_scraper import scrape_apify
from src.scrapers.rss_scraper import scrape_rss
from src.scrapers.community_scraper import scrape_community

# ── Processors ───────────────────────────────────────────────────
from src.processors.claude_scorer import score_audio, score_topics
from src.processors.personal_taste import get_taste_profile
from src.processors.email_sender import send_digest, send_alert
from src.processors.dashboard_updater import update_dashboard
from src.processors.trend_scout import build_trend_scout
from src.processors.audio_merge import merge_audio
from src.processors.history import annotate_history, is_stale_repeat
from src.processors.feedback import collect_feedback, excluded_keys, is_excluded, verdicts_prompt


def main() -> None:
    today = datetime.date.today().isoformat()
    print(f"\n🎙️  40K Content Intel — {today}\n{'─'*50}")

    # ── 1. Load personal taste profile (if available) ────────────
    print("Loading personal taste profile…")
    taste_profile = get_taste_profile()

    print("Collecting your votes on past recommendations…")
    feedback = collect_feedback()

    # ── 2. Scrape all audio sources ───────────────────────────────
    print("Scraping aggregator sites…")
    aggregator_audio = scrape_aggregators()

    print("Scraping TikTok + Instagram via Apify…")
    apify_audio = scrape_apify()

    # Niche-reel sounds first so their signals win when the same track appears twice
    raw_audio = merge_audio(
        [a for a in apify_audio if "instagram_niche_reels" in a.get("sources", [])],
        aggregator_audio,
        [a for a in apify_audio if "tiktok_creative_center" in a.get("sources", [])],
    )

    # Never re-recommend sounds you marked 👎 or ✅ used
    blocked = excluded_keys(feedback)
    before = len(raw_audio)
    raw_audio = [a for a in raw_audio if not is_excluded(a, blocked)]
    if before != len(raw_audio):
        print(f"  → dropped {before - len(raw_audio)} sound(s) you already voted 👎 or used")

    # Week-over-week memory: new / week N / climbing / cooling
    raw_audio = annotate_history(raw_audio)

    print(f"  → {len(raw_audio)} unique audio items collected")

    # ── 3. Scrape community sources for topics ────────────────────
    print("Scraping Reddit…")
    reddit_data = scrape_reddit()

    print("Scraping YouTube…")
    youtube_data = scrape_youtube()

    print("Scraping community sites…")
    community_data = scrape_community()

    print("Reading hobby news RSS feeds…")
    rss_data = scrape_rss()

    raw_topics = reddit_data + youtube_data + community_data + rss_data
    print(f"  → {len(raw_topics)} raw topic signals collected")

    # ── 4. Score audio through Claude ────────────────────────────
    print("Scoring audio with Claude…")
    guidance = "\n\n".join(p for p in (taste_profile, verdicts_prompt(feedback)) if p)
    scored_audio = score_audio(raw_audio, guidance)

    # ── 5. Score topics through Claude ───────────────────────────
    print("Scoring topics with Claude…")
    scored_topics = score_topics(raw_topics)

    # ── 5b. Trend Scout: format mix vs last week ─────────────────
    print("Building Trend Scout…")
    trend_scout = build_trend_scout(scored_audio)

    # ── 6. Fire individual alerts for high-potency audio ─────────
    from src.config import ALERT_THRESHOLD, MIN_RECOMMEND_SCORE
    # Capped so a strong day can't flood the inbox — the rest are in the digest
    alert_bar = max(ALERT_THRESHOLD, MIN_RECOMMEND_SCORE)
    alerts = [a for a in scored_audio
              if a.get("potency_score", 0) >= alert_bar and not is_stale_repeat(a)][:3]
    if alerts:
        print(f"  ⚡ Sending {len(alerts)} individual alert(s)…")
        for item in alerts:
            send_alert(item)

    # ── 7. Send weekly digest email ───────────────────────────────
    print("Sending digest email…")
    send_digest(scored_audio, scored_topics, trend_scout)

    # ── 8. Update dashboard ───────────────────────────────────────
    print("Updating dashboard…")
    update_dashboard(scored_audio, scored_topics, trend_scout)   # also saves JSON + date index

    print(f"\n✅ Digest complete — {today}")
    print(f"   Audio scored: {len(scored_audio)}")
    print(f"   Topics scored: {len(scored_topics)}")
    print(f"   Alerts sent: {len(alerts)}")


if __name__ == "__main__":
    main()

"""
main.py — orchestrates the full daily digest pipeline.

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
from src.scrapers.tiktok_scraper import scrape_tiktok
from src.scrapers.community_scraper import scrape_community

# ── Processors ───────────────────────────────────────────────────
from src.processors.claude_scorer import score_audio, score_topics
from src.processors.personal_taste import get_taste_profile
from src.processors.email_sender import send_digest, send_alert
from src.processors.dashboard_updater import update_dashboard


def main() -> None:
    today = datetime.date.today().isoformat()
    print(f"\n🎙️  40K Content Intel — {today}\n{'─'*50}")

    # ── 1. Load personal taste profile (if available) ────────────
    print("Loading personal taste profile…")
    taste_profile = get_taste_profile()

    # ── 2. Scrape all audio sources ───────────────────────────────
    print("Scraping aggregator sites…")
    aggregator_audio = scrape_aggregators()

    print("Scraping TikTok Creative Center…")
    tiktok_audio = scrape_tiktok()

    # Combine and deduplicate audio by name (case-insensitive)
    seen_audio: set[str] = set()
    raw_audio: list[dict] = []
    for item in aggregator_audio + tiktok_audio:
        key = item.get("name", "").lower().strip()
        if key and key not in seen_audio:
            seen_audio.add(key)
            raw_audio.append(item)

    print(f"  → {len(raw_audio)} unique audio items collected")

    # ── 3. Scrape community sources for topics ────────────────────
    print("Scraping Reddit…")
    reddit_data = scrape_reddit()

    print("Scraping YouTube…")
    youtube_data = scrape_youtube()

    print("Scraping community sites…")
    community_data = scrape_community()

    raw_topics = reddit_data + youtube_data + community_data
    print(f"  → {len(raw_topics)} raw topic signals collected")

    # ── 4. Score audio through Claude ────────────────────────────
    print("Scoring audio with Claude…")
    scored_audio = score_audio(raw_audio, taste_profile)

    # ── 5. Score topics through Claude ───────────────────────────
    print("Scoring topics with Claude…")
    scored_topics = score_topics(raw_topics)

    # ── 6. Fire individual alerts for high-potency audio ─────────
    from src.config import ALERT_THRESHOLD
    # Capped so a strong day can't flood the inbox — the rest are in the digest
    alerts = [a for a in scored_audio if a.get("potency_score", 0) >= ALERT_THRESHOLD][:3]
    if alerts:
        print(f"  ⚡ Sending {len(alerts)} individual alert(s)…")
        for item in alerts:
            send_alert(item)

    # ── 7. Send daily digest email ───────────────────────────────
    print("Sending digest email…")
    send_digest(scored_audio, scored_topics)

    # ── 8. Update dashboard ───────────────────────────────────────
    print("Updating dashboard…")
    update_dashboard(scored_audio, scored_topics)   # also saves JSON + date index

    print(f"\n✅ Digest complete — {today}")
    print(f"   Audio scored: {len(scored_audio)}")
    print(f"   Topics scored: {len(scored_topics)}")
    print(f"   Alerts sent: {len(alerts)}")


if __name__ == "__main__":
    main()

"""
Reads hobby-news RSS feeds — the sanctioned way to pull headlines from a
site automatically. Replaces the DakkaDakka scraper.

Returns topic signals in the same shape as the other community scrapers,
limited to items published within RSS_WINDOW_DAYS.
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

from src.config import RSS_FEEDS, RSS_WINDOW_DAYS, RSS_MAX_PER_FEED

HEADERS = {"User-Agent": "40kDigest/1.0 (weekly RSS reader)"}


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _read_feed(name: str, url: str, cutoff: datetime) -> list[dict]:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "xml")

    items = []
    for it in soup.find_all(["item", "entry"]):
        title = _text(it.find("title"))
        if not title:
            continue
        link_el = it.find("link")
        link = (link_el.get("href") or _text(link_el)) if link_el else ""
        date_txt = _text(it.find("pubDate")) or _text(it.find("published")) or _text(it.find("updated"))
        try:
            published = parsedate_to_datetime(date_txt) if "," in date_txt else datetime.fromisoformat(date_txt.replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published = None
        if published and published < cutoff:
            continue

        summary = BeautifulSoup(_text(it.find("description")) or _text(it.find("summary")), "lxml").get_text(" ", strip=True)
        categories = [_text(c) for c in it.find_all("category")][:5]
        items.append({
            "source": name,
            "title": title,
            "summary": summary[:200],
            "categories": categories,
            "published": published.date().isoformat() if published else "",
            "url": link,
            "type": "topic",
            "is_question": title.strip().endswith("?"),
            "is_audio_mention": False,
        })
        if len(items) >= RSS_MAX_PER_FEED:
            break
    return items


def scrape_rss() -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RSS_WINDOW_DAYS)
    results: list[dict] = []
    for name, url in RSS_FEEDS.items():
        try:
            items = _read_feed(name, url, cutoff)
            print(f"    [rss] {name} → {len(items)} items")
            results.extend(items)
        except Exception as e:
            print(f"    [rss] {name} error: {e}")
    return results

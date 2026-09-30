"""
Scrapes trend aggregator websites for audio names, use counts,
trend stages, and source links. Returns a list of raw audio dicts.
"""

import re
import requests
from bs4 import BeautifulSoup
from src.config import AGGREGATOR_URLS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Regex helpers
USE_COUNT_RE = re.compile(r"([\d,.]+[KkMm]?)\s*(uses?|reels?|videos?|posts?)", re.I)
STAGE_RE = re.compile(r"\b(early|rising|peak|fading|growing)\b", re.I)


def _parse_use_count(text: str) -> str:
    m = USE_COUNT_RE.search(text)
    return m.group(0).strip() if m else ""


def _parse_stage(text: str) -> str:
    m = STAGE_RE.search(text)
    return m.group(1).capitalize() if m else "Unknown"


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"    [aggregators] Could not fetch {url}: {e}")
        return None


# Phrases that indicate this is a page header/nav element, not a track name
HEADER_NOISE = [
    "trending", "instagram", "tiktok", "reels", "audio", "week", "month",
    "subscribe", "follow", "more", "read", "learn", "view", "best", "top",
    "how to", "tips", "guide", "what", "why", "when", "here", "these",
    "your", "our", "all", "new", "this", "that", "for", "with", "about",
    "update", "latest", "popular", "playlist", "songs", "tracks", "music",
    "2024", "2025", "2026", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december",
]


def _looks_like_track(text: str) -> bool:
    """Rough heuristic: does this string look like a song/audio title?"""
    t = text.lower()
    
    # Must be reasonable length (3–80 chars, 1–7 words)
    word_count = len(text.split())
    if word_count < 1 or word_count > 7:
        return False
    if len(text) < 3 or len(text) > 80:
        return False
    
    # If it contains a separator, it's probably "Song - Artist" format — good
    for sep in [" — ", " - ", " by ", " · ", " | "]:
        if sep in text:
            return True
    
    # Reject if it contains header/nav noise words
    if any(noise in t for noise in HEADER_NOISE):
        return False
    
    # Reject if it's a full sentence (has a verb ending or question mark)
    if text.endswith("?") or text.endswith("!") or text.endswith(":"):
        return False
    
    # Reject if it's all caps (likely a section heading)
    if text.isupper() and len(text) > 5:
        return False
    
    return True


def _extract_audio_blocks(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """
    Generic extractor: looks for heading/strong tags that look like audio
    names followed by paragraphs with artist info and use counts.
    """
    results = []
    seen_names: set[str] = set()
    
    candidates = soup.find_all(["h2", "h3", "h4", "strong", "b"])

    for el in candidates:
        text = el.get_text(strip=True)
        
        # Apply track heuristic before anything else
        if not _looks_like_track(text):
            continue

        # Deduplicate
        key = text.lower()[:40]
        if key in seen_names:
            continue
        seen_names.add(key)

        # Look for artist in sibling text
        parent_text = ""
        if el.parent:
            parent_text = el.parent.get_text(" ", strip=True)

        # Try to extract artist — pattern: "Song Name — Artist" or "Song Name by Artist"
        name = text
        artist = ""
        for sep in [" — ", " - ", " by ", " · "]:
            if sep in text:
                parts = text.split(sep, 1)
                name = parts[0].strip()
                artist = parts[1].strip()
                break

        use_count = _parse_use_count(parent_text)
        stage = _parse_stage(parent_text)

        results.append({
            "name": name,
            "artist": artist,
            "audio_type": "music",
            "use_count": use_count,
            "trend_stage": stage,
            "source_url": source_url,
            "ig_link": "",
            "tiktok_link": "",
        })

    return results


def scrape_aggregators() -> list[dict]:
    all_audio: list[dict] = []
    for url in AGGREGATOR_URLS:
        soup = _fetch(url)
        if not soup:
            continue
        items = _extract_audio_blocks(soup, url)
        print(f"    [aggregators] {url.split('/')[2]} → {len(items)} items")
        all_audio.extend(items)

    return all_audio

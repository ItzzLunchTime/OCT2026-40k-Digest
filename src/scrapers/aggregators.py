"""
Scrapes trend aggregator blogs for trending audio.

Every aggregator we track links each track straight to the platform:
    https://www.instagram.com/reels/audio/<id>/
    https://www.tiktok.com/music/<slug>-<id>
Those links are the signal. Instead of guessing which headings "look like"
song titles (which let hundreds of nav/footer strings through), we only keep
anchors that point at an audio page, then read the title, artist and a short
context blurb from around the link.

The same track often appears on several aggregators. Items are de-duplicated
by platform audio ID, and `mention_count` records how many sites listed it —
a useful cross-source trend signal for the scorer.
"""

import re
import requests
from bs4 import BeautifulSoup, Tag
from src.config import AGGREGATOR_URLS, MAX_AUDIO_ITEMS, AGG_MAX_PER_SITE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

IG_AUDIO_RE = re.compile(r"instagram\.com/reels?/audio/(\d+)", re.I)
TT_MUSIC_RE = re.compile(r"tiktok\.com/music/([^/?#]*?)-?(\d{6,})", re.I)

USE_COUNT_RE = re.compile(r"([\d,.]+\s?[KkMm]?)\s*(uses?|reels?|videos?|posts?)\b", re.I)
STAGE_RE = re.compile(r"\b(early|rising|peak|peaking|fading|growing|emerging)\b", re.I)
AKA_RE = re.compile(r"\baka\b\s+(?:the\s+)?[\"“'‘]?(.+?)[\"”'’]?\s*(?:trend)?$", re.I)

# Anchor texts that say nothing about the track ("Use this sound", "Listen here")
GENERIC_WORDS_RE = re.compile(
    r"\b(sound|audio|here|listen|link|click|tap|use|save|view|instagram|tiktok)\b", re.I
)


def _is_generic(label: str) -> bool:
    if len(label) < 2:
        return True
    if label.lower().startswith("original"):     # "Original audio" is a real IG title
        return False
    return len(label.split()) <= 4 and bool(GENERIC_WORDS_RE.search(label))


# Separators between title and artist, most specific first
SEPARATORS = [" • ", " — ", " – ", " · ", " | ", " - "]

# Page chrome that never contains the track list
CHROME_TAGS = ["nav", "header", "footer", "aside", "form", "script", "style", "noscript"]

STAGE_MAP = {"emerging": "Early", "growing": "Rising", "peaking": "Peak"}


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"    [aggregators] Could not fetch {url}: {e}")
        return None


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"^\s*(\d+[.)]\s*)", "", text)                       # "1. Song"
    text = re.sub(r"^(reels? )?audio( link)?\s*:\s*", "", text, flags=re.I)
    text = re.sub(r"\s*trending (audio|sound)\s*$", "", text, flags=re.I)
    return text.strip(" \"“”'‘’*:")


def _split_title_artist(text: str) -> tuple[str, str]:
    for sep in SEPARATORS:
        if sep in text:
            title, artist = text.split(sep, 1)
            return title.strip(" \"“”'‘’"), artist.strip(" \"“”'‘’")
    m = re.match(r"^(.+?)\s+by\s+(.+)$", text, re.I)
    if m and len(m.group(2).split()) <= 5:
        return m.group(1).strip(" \"“”'‘’"), m.group(2).strip(" \"“”'‘’")
    return text, ""


def _heading_before(a: Tag) -> str:
    """Nearest preceding heading / bold line — used when the anchor text is generic."""
    for prev in a.find_all_previous(["h2", "h3", "h4", "strong", "b"], limit=6):
        txt = _clean(prev.get_text(" ", strip=True))
        if txt and not _is_generic(txt) and len(txt) <= 120:
            return txt
    return ""


def _context_for(a: Tag) -> tuple[str, str]:
    """
    Returns (own_block, blurb). own_block is the link's own paragraph/list item —
    the only text trusted for use counts and stage. blurb adds the following
    paragraph when the own block is too short to describe the trend.
    """
    block = a.find_parent(["p", "li", "td", "div"])
    own = re.sub(r"\s+", " ", block.get_text(" ", strip=True)) if block else ""
    blurb = own
    if len(own) < 60:
        nxt = a.find_next(["p", "li"])
        if nxt:
            blurb = f"{own} {nxt.get_text(' ', strip=True)}".strip()
    return own[:300], re.sub(r"\s+", " ", blurb)[:300]


def _parse_link(href: str) -> tuple[str, str] | None:
    """Return (platform, audio_id) for an audio link, else None."""
    m = IG_AUDIO_RE.search(href)
    if m:
        return "instagram", m.group(1)
    m = TT_MUSIC_RE.search(href)
    if m:
        return "tiktok", m.group(2)
    return None


def _extract_audio_links(soup: BeautifulSoup, source_url: str) -> list[dict]:
    for tag in soup.find_all(CHROME_TAGS):
        tag.decompose()

    results: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        parsed = _parse_link(a["href"])
        if not parsed:
            continue
        platform, audio_id = parsed
        key = f"{platform}:{audio_id}"
        if key in results:
            continue

        label = _clean(a.get_text(" ", strip=True))
        if not label or _is_generic(label):
            label = _heading_before(a)
        if not label:
            continue

        # "Original audio aka the 'Trip started…' trend" → keep the trend name
        trend_note = ""
        aka = AKA_RE.search(label)
        if aka:
            trend_note = aka.group(1).strip(" \"“”'‘’")
            label = label[: aka.start()].strip()

        name, artist = _split_title_artist(label)
        own, context = _context_for(a)
        stage_m = STAGE_RE.search(own)
        stage = stage_m.group(1).lower() if stage_m else ""
        use_m = USE_COUNT_RE.search(own)

        results[key] = {
            "name": name,
            "artist": artist,
            "audio_type": "",                       # left for the scorer to classify
            "use_count": use_m.group(0).strip() if use_m else "",
            "trend_stage": STAGE_MAP.get(stage, stage.capitalize()) or "Unknown",
            "trend_note": trend_note,
            "context": context,
            "source_url": source_url,
            "sources": [source_url],
            "mention_count": 1,
            "ig_link": a["href"].split("?")[0] if platform == "instagram" else "",
            "tiktok_link": a["href"].split("?")[0] if platform == "tiktok" else "",
            "_key": key,
        }
    return list(results.values())


def _name_key(item: dict) -> str:
    return re.sub(r"[^a-z0-9]", "", item["name"].lower())[:40]


def scrape_aggregators() -> list[dict]:
    merged: dict[str, dict] = {}       # audio-ID key → item
    by_name: dict[str, str] = {}       # name key → audio-ID key (catches IG vs TikTok of same track)

    for url in AGGREGATOR_URLS:
        soup = _fetch(url)
        if not soup:
            continue
        # Blogs list newest picks first and keep older weeks further down the page
        items = _extract_audio_links(soup, url)[:AGG_MAX_PER_SITE]
        print(f"    [aggregators] {url.split('/')[2]} → {len(items)} linked audio items")

        for item in items:
            nkey = _name_key(item)
            generic = nkey.startswith("original") and not item["trend_note"]
            existing_key = item["_key"] if item["_key"] in merged else (
                None if generic else by_name.get(nkey)
            )
            if existing_key:
                cur = merged[existing_key]
                if url not in cur["sources"]:
                    cur["sources"].append(url)
                    cur["mention_count"] += 1
                for f in ("artist", "use_count", "trend_note", "ig_link", "tiktok_link"):
                    if not cur[f] and item[f]:
                        cur[f] = item[f]
                if cur["trend_stage"] == "Unknown":
                    cur["trend_stage"] = item["trend_stage"]
            else:
                merged[item["_key"]] = item
                if not generic:
                    by_name.setdefault(nkey, item["_key"])

    audio = sorted(merged.values(), key=lambda x: x["mention_count"], reverse=True)
    for item in audio:
        item.pop("_key", None)
    if len(audio) > MAX_AUDIO_ITEMS:
        print(f"    [aggregators] capping {len(audio)} → {MAX_AUDIO_ITEMS} items")
        audio = audio[:MAX_AUDIO_ITEMS]
    return audio

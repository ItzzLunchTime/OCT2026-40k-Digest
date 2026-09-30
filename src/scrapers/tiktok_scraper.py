"""
Scrapes the TikTok Creative Center public trending music page.
No auth required — the page is publicly accessible.

Also checks CapCut's public trending templates page for
non-music audio formats.
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIKTOK_CC_URL = (
    "https://ads.tiktok.com/business/creativecenter/"
    "inspiration/popular/music/pc/en"
)

CAPCUT_URL = "https://www.capcut.com/template"

USE_COUNT_RE = re.compile(r"([\d,.]+[KkMm]?)\s*(uses?|videos?|posts?|clips?)", re.I)


def _parse_use_count(text: str) -> str:
    m = USE_COUNT_RE.search(text)
    return m.group(0).strip() if m else ""


def _scrape_tiktok_cc() -> list[dict]:
    """
    TikTok Creative Center renders much of its content via JS,
    so we scrape what's available in the initial HTML and look
    for JSON-LD / data attributes that contain track names.
    """
    results = []
    try:
        resp = requests.get(TIKTOK_CC_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Look for track data in script tags (often embedded as JSON)
        import json
        for script in soup.find_all("script"):
            text = script.string or ""
            if '"musicName"' in text or '"title"' in text:
                # Try to extract track names via regex
                names = re.findall(r'"musicName"\s*:\s*"([^"]+)"', text)
                artists = re.findall(r'"authorName"\s*:\s*"([^"]+)"', text)
                for i, name in enumerate(names[:20]):
                    results.append({
                        "name": name,
                        "artist": artists[i] if i < len(artists) else "",
                        "audio_type": "music",
                        "use_count": "",
                        "trend_stage": "Rising",
                        "source_url": TIKTOK_CC_URL,
                        "ig_link": "",
                        "tiktok_link": f"https://www.tiktok.com/music/{name.replace(' ', '-')}",
                    })

        # Fallback: look for visible text blocks
        if not results:
            for el in soup.find_all(class_=re.compile(r"music|track|song|title", re.I)):
                text = el.get_text(strip=True)
                if 3 < len(text) < 100:
                    results.append({
                        "name": text,
                        "artist": "",
                        "audio_type": "music",
                        "use_count": _parse_use_count(
                            el.parent.get_text() if el.parent else ""
                        ),
                        "trend_stage": "Rising",
                        "source_url": TIKTOK_CC_URL,
                        "ig_link": "",
                        "tiktok_link": "",
                    })

    except Exception as e:
        print(f"    [tiktok] TikTok CC fetch error: {e}")

    return results


def _scrape_capcut() -> list[dict]:
    """
    Scrapes CapCut's public template page for trending template
    names — these often carry specific audio sounds that cross
    to Reels.
    """
    results = []
    try:
        resp = requests.get(CAPCUT_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for el in soup.find_all(class_=re.compile(r"template.name|title|card", re.I)):
            text = el.get_text(strip=True)
            if 3 < len(text) < 80:
                results.append({
                    "name": text,
                    "artist": "CapCut Template",
                    "audio_type": "template",
                    "use_count": "",
                    "trend_stage": "Rising",
                    "source_url": CAPCUT_URL,
                    "ig_link": "",
                    "tiktok_link": "",
                })

    except Exception as e:
        print(f"    [tiktok] CapCut fetch error: {e}")

    return results[:15]   # cap at 15 templates


def scrape_tiktok() -> list[dict]:
    cc = _scrape_tiktok_cc()
    cap = _scrape_capcut()
    total = cc + cap
    print(f"    [tiktok] {len(cc)} TikTok CC + {len(cap)} CapCut = {len(total)} items")
    return total

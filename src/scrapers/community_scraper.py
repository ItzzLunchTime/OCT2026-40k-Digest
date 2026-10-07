"""
Scrapes the Warhammer Community site for
trending topics, new releases, and community discussions.
"""

import requests
from bs4 import BeautifulSoup
from src.config import COMMUNITY_URLS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SKIP_TERMS = [
    "cookie", "privacy", "terms", "login", "sign in",
    "subscribe", "newsletter", "advertisement"
]


def _is_skippable(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in SKIP_TERMS)


def _scrape_warhammer_community() -> list[dict]:
    url = "https://www.warhammer-community.com/"
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Article headlines
        for el in soup.find_all(["h1", "h2", "h3", "article"]):
            title = el.get_text(strip=True)
            if len(title) < 10 or len(title) > 200:
                continue
            if _is_skippable(title):
                continue

            link = ""
            a_tag = el.find("a") or (el if el.name == "a" else None)
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                link = href if href.startswith("http") else f"https://www.warhammer-community.com{href}"

            results.append({
                "source": "warhammer_community",
                "title": title,
                "url": link,
                "type": "topic",
                "is_question": False,
                "is_audio_mention": False,
            })

    except Exception as e:
        print(f"    [community] Warhammer Community error: {e}")

    return results[:20]


# DakkaDakka was removed (Oct 2026): every forum page now sits behind a
# "prove you're human" check added specifically to stop scraping bots, and its
# robots.txt disallows AI crawlers. We respect that rather than work around it.


def scrape_community() -> list[dict]:
    wc = _scrape_warhammer_community()
    print(f"    [community] {len(wc)} Warhammer Community items")
    return wc

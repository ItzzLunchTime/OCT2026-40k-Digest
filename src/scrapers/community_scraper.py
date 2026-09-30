"""
Scrapes Warhammer Community site and Dakka Dakka forum for
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


def _scrape_dakkadakka() -> list[dict]:
    url = "https://www.dakkadakka.com/dakkaforum/forums/show/1.page"
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for el in soup.find_all(["h3", "h4", "td", "a"], class_=re.compile(r"topic|thread|subject", re.I) if False else True):
            title = el.get_text(strip=True)
            if len(title) < 10 or len(title) > 200:
                continue
            if _is_skippable(title):
                continue

            results.append({
                "source": "dakkadakka",
                "title": title,
                "url": url,
                "type": "topic",
                "is_question": title.strip().endswith("?"),
                "is_audio_mention": any(
                    kw in title.lower()
                    for kw in ["music", "song", "audio", "sound", "track"]
                ),
            })

    except Exception as e:
        print(f"    [community] Dakka Dakka error: {e}")

    return results[:20]


def scrape_community() -> list[dict]:
    import re   # needed inside _scrape_dakkadakka but imported here to keep module clean
    wc = _scrape_warhammer_community()
    dd = _scrape_dakkadakka()
    total = wc + dd
    print(f"    [community] {len(wc)} WarCom + {len(dd)} DakkaDakka = {len(total)} items")
    return total

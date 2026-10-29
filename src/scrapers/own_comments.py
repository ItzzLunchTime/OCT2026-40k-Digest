"""
Your own recent posts: their comments (fuel for Comment Picks / the Comment Replies
engine) and their public numbers (views, likes, comments, length) for the weekly
performance check.

Uses Apify, so no Meta developer app / Graph API token is needed:
  1. apify/instagram-scraper          → your newest posts (with their latest comments)
  2. apify/instagram-comment-scraper  → full comment list, only for posts where the
                                        post scrape didn't already return every comment

Free-tier guard rails: both calls carry a hard max_total_charge_usd, and the whole
step is skipped if this month's Apify budget is nearly spent (checked by the caller).
"""

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.config import (
    APIFY_API_KEY,
    IG_ACCOUNT,
    COMMENTS_ENABLED,
    COMMENT_WINDOW_DAYS,
    OWN_POSTS_LIMIT,
    COMMENTS_PER_POST,
)

POSTS_ACTOR = "apify/instagram-scraper"
COMMENTS_ACTOR = "apify/instagram-comment-scraper"

POSTS_MAX_CHARGE = Decimal("0.05")
COMMENTS_MAX_CHARGE = Decimal("0.10")
MAX_COMMENTS_TOTAL = 150


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _parse_time(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _is_substantive(text: str) -> bool:
    """Skip emoji-only / single-word comments — nothing to build a video on."""
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    return len(words) >= 3


def _normalise(c: dict, post: dict) -> dict:
    return {
        "text": str(_first(c, "text", "comment", default="")).strip(),
        "username": str(_first(c, "ownerUsername", "username", default="")).strip(),
        "likes": int(_first(c, "likesCount", "likes", default=0) or 0),
        "replies": int(_first(c, "repliesCount", default=0) or 0),
        "timestamp": str(_first(c, "timestamp", default="")),
        "post_url": post.get("url", ""),
        "post_caption": re.sub(r"\s+", " ", post.get("caption") or "")[:160],
    }


def _post_metrics(p: dict) -> dict:
    views = int(_first(p, "videoPlayCount", "igPlayCount", "videoViewCount", default=0) or 0)
    return {
        "url": p.get("url", ""),
        "short_code": p.get("shortCode", ""),
        "timestamp": str(p.get("timestamp", "")),
        "type": p.get("productType") or p.get("type") or "",
        "caption": re.sub(r"\s+", " ", p.get("caption") or "")[:220],
        "views": max(views, 0),
        "likes": max(int(p.get("likesCount") or 0), 0),
        "comments": max(int(p.get("commentsCount") or 0), 0),
        "duration_s": round(float(p.get("videoDuration") or 0), 1),
    }


def scrape_own_account(client) -> dict:
    """{"posts": [public metrics per recent post], "comments": [last week's comments]}"""
    if not COMMENTS_ENABLED or not IG_ACCOUNT:
        return {"posts": [], "comments": []}
    from src.scrapers.apify_scraper import _run_actor

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=COMMENT_WINDOW_DAYS)

    # 1. Newest posts. Comments keep arriving on older posts, so look back a bit further.
    try:
        posts = _run_actor(
            client,
            POSTS_ACTOR,
            {
                "directUrls": [f"https://www.instagram.com/{IG_ACCOUNT}/"],
                "resultsType": "posts",
                "resultsLimit": OWN_POSTS_LIMIT,
                "addParentData": False,
            },
            max_items=OWN_POSTS_LIMIT,
            max_charge=POSTS_MAX_CHARGE,
        )
    except Exception as e:
        print(f"    [comments] Post scrape error: {e}")
        return {"posts": [], "comments": []}
    if posts:
        print(f"    [comments] Post fields: {sorted(posts[0].keys())[:25]}")

    comments: list[dict] = []
    need_full: list[dict] = []
    for post in posts:
        latest = post.get("latestComments") or []
        comments.extend(_normalise(c, post) for c in latest)
        total = int(post.get("commentsCount") or 0)
        if total > len(latest):
            need_full.append(post)

    # 2. Full comment lists only where the post scrape came back short
    if need_full:
        by_url = {p.get("url", ""): p for p in need_full}
        try:
            extra = _run_actor(
                client,
                COMMENTS_ACTOR,
                {"directUrls": list(by_url), "resultsLimit": COMMENTS_PER_POST},
                max_items=min(MAX_COMMENTS_TOTAL, COMMENTS_PER_POST * len(by_url)),
                max_charge=COMMENTS_MAX_CHARGE,
            )
            if extra:
                print(f"    [comments] Comment fields: {sorted(extra[0].keys())[:25]}")
            for c in extra:
                url = _first(c, "postUrl", "inputUrl", "url", default="")
                post = by_url.get(url) or next(
                    (p for u, p in by_url.items() if u and url and (u in url or url in u)), {"url": url}
                )
                comments.append(_normalise(c, post))
        except Exception as e:
            print(f"    [comments] Comment scrape error (using post previews only): {e}")

    # Dedupe, drop your own replies, keep last week's substantive comments
    seen: set[tuple] = set()
    kept: list[dict] = []
    for c in comments:
        key = (c["username"], c["text"][:80])
        if key in seen:
            continue
        seen.add(key)
        if c["username"].lower() == IG_ACCOUNT.lower() or not _is_substantive(c["text"]):
            continue
        ts = _parse_time(c["timestamp"])
        if ts and ts < cutoff:
            continue
        kept.append(c)

    print(f"    [comments] {len(posts)} posts · {len(comments)} comments → {len(kept)} from the last "
          f"{COMMENT_WINDOW_DAYS} days worth scoring")
    return {"posts": [_post_metrics(p) for p in posts if p.get("url")], "comments": kept}


def scrape_own_comments(client) -> list[dict]:
    return scrape_own_account(client)["comments"]

"""
Weekly check on your own posts, so the digest learns from what you actually posted.

Every run stores the public numbers for your recent posts in docs/data/own_posts.json
(views, likes, comments, length; one snapshot per run), then:
  - works out the account's median Reel views (live once enough posts are tracked,
    otherwise the audit baseline in config)
  - tiers each post from the last 2 weeks: Breakout >3x median · Above >1.5x ·
    Baseline · Under <0.5x  (posts under 3 days old are marked "too early")
  - picks the best Under-tier post as a repost / recut candidate (the "second roll")

Shares, saves, follows and skip rate are only in Instagram Insights, so they can't be
tracked here — the audit numbers in the ACCOUNT_PROFILE cover those.
"""

import json
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import ACCOUNT_BASELINE_MEDIAN

HISTORY_PATH = Path("docs/data/own_posts.json")
RECENT_DAYS = 14
MIN_AGE_DAYS = 3           # younger posts are still collecting views
LIVE_MEDIAN_MIN_POSTS = 10


def _load() -> dict:
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _age_days(ts: str, now: datetime) -> float | None:
    try:
        posted = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return max((now - posted).total_seconds() / 86400, 0.0)


def _median(posts: list[dict]) -> tuple[int, str]:
    settled = sorted(p["views"] for p in posts if p.get("views") and (p.get("age_days") or 0) >= 7)
    if len(settled) >= LIVE_MEDIAN_MIN_POSTS:
        m = statistics.median(settled)
        # Drop one-off viral outliers (the cat Reel was 233x) so they don't skew the bar
        trimmed = [v for v in settled if v <= 20 * m] or settled
        return int(statistics.median(trimmed)), f"live median of {len(trimmed)} tracked posts"
    return ACCOUNT_BASELINE_MEDIAN, "audit baseline (Oct 2026)"


def _tier(ratio: float) -> str:
    if ratio > 3:
        return "Breakout"
    if ratio > 1.5:
        return "Above"
    if ratio < 0.5:
        return "Under"
    return "Baseline"


def build_performance(posts: list[dict], today: date | None = None) -> dict | None:
    """Update the history file and return this week's read-out (None if no data)."""
    if not posts:
        print("    [performance] No post data this run — skipping")
        return None
    today = today or date.today()
    now = datetime.now(timezone.utc)
    history = _load()

    for p in posts:
        rec = history.setdefault(p["url"], {"snapshots": []})
        rec.update({k: p[k] for k in ("url", "short_code", "timestamp", "type", "caption", "duration_s")})
        rec.update(views=p["views"], likes=p["likes"], comments=p["comments"])
        snaps = [s for s in rec["snapshots"] if s.get("date") != today.isoformat()]
        snaps.append({"date": today.isoformat(), "views": p["views"], "likes": p["likes"], "comments": p["comments"]})
        rec["snapshots"] = snaps[-12:]

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    tracked = []
    for rec in history.values():
        age = _age_days(rec.get("timestamp", ""), now)
        tracked.append(dict(rec, age_days=age))
    median, median_source = _median(tracked)

    recent = []
    for rec in sorted(tracked, key=lambda r: r.get("timestamp", ""), reverse=True):
        age = rec.get("age_days")
        if age is None or age > RECENT_DAYS:
            continue
        ratio = rec["views"] / median if median else 0
        recent.append({
            "url": rec["url"],
            "caption": rec.get("caption", ""),
            "posted": rec.get("timestamp", "")[:10],
            "age_days": round(age, 1),
            "duration_s": rec.get("duration_s", 0),
            "views": rec["views"],
            "likes": rec["likes"],
            "comments": rec["comments"],
            "x_median": round(ratio, 1),
            "tier": "Too early" if age < MIN_AGE_DAYS else _tier(ratio),
        })

    # Second roll: the most-liked-per-view Under post (the idea had fans, the roll was bad)
    unders = [r for r in recent if r["tier"] == "Under"]
    second_roll = max(unders, key=lambda r: (r["likes"] + 3 * r["comments"]) / max(r["views"], 1), default=None)

    result = {
        "median": median,
        "median_source": median_source,
        "recent": recent,
        "second_roll": second_roll,
        "tracked_posts": len(history),
    }
    tiers = ", ".join(f"{r['tier']}" for r in recent) or "none in the last 2 weeks"
    print(f"    [performance] Median {median} views ({median_source}) · recent: {tiers}")
    return result

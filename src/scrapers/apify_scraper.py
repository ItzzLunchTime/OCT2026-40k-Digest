"""
Apify-backed scrapers for platforms with no usable public API.

  1. TikTok Creative Center trending songs  (actor: datapeak/tiktok-creative-center)
     — the platform-wide "what sounds are trending" chart, with rank + rank change.
  2. Instagram niche reels by hashtag        (actor: apify/instagram-hashtag-scraper)
     — recent reels under #warhammer40k, #minipainting, etc. Each reel carries the
       song it uses, so we can see which sounds the niche itself is posting with.

Both return audio dicts in the same shape as the aggregator scraper so the
scorer, email and dashboard treat them identically.

Free-tier guard rails (Apify Free = $5/month credit, blocked when spent):
  - Before running anything we read this month's usage from the Apify API and
    skip Apify entirely if it's within one run's budget of APIFY_MONTHLY_BUDGET_USD.
  - Every actor call carries a hard max_total_charge_usd and max_items cap.
"""

import re
from decimal import Decimal
from datetime import datetime, timedelta, timezone

import requests

from src.config import (
    APIFY_API_KEY,
    APIFY_MONTHLY_BUDGET_USD,
    APIFY_RUN_BUDGET_USD,
    TIKTOK_ENABLED,
    TIKTOK_REGION,
    TIKTOK_SONG_LIMIT,
    IG_HASHTAGS,
    IG_REELS_PER_HASHTAG,
)

TIKTOK_ACTOR = "datapeak/tiktok-creative-center"
IG_ACTOR = "apify/instagram-hashtag-scraper"

# Per-actor spend ceilings (USD). Sum stays under APIFY_RUN_BUDGET_USD.
TIKTOK_MAX_CHARGE = Decimal("0.15")
IG_MAX_CHARGE = Decimal("0.65")

MIN_PLAYS_FOR_ENGAGEMENT = 2000

RESIDENTIAL_PROXY = {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _first(d: dict, *keys, default=""):
    """First non-empty value among several possible field names."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _month_usage_ok() -> bool:
    """True if this month's Apify spend leaves room for one more run."""
    try:
        resp = requests.get(
            "https://api.apify.com/v2/users/me/limits",
            headers={"Authorization": f"Bearer {APIFY_API_KEY}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        used = float(data.get("current", {}).get("monthlyUsageUsd", 0) or 0)
        cap = float(data.get("limits", {}).get("maxMonthlyUsageUsd", 0) or 0)
        budget = min(APIFY_MONTHLY_BUDGET_USD, cap) if cap else APIFY_MONTHLY_BUDGET_USD
        print(f"    [apify] Month-to-date usage ${used:.2f} of ${budget:.2f} budget")
        if used + APIFY_RUN_BUDGET_USD > budget:
            print("    [apify] Not enough budget left this month — skipping Apify")
            return False
        return True
    except Exception as e:
        print(f"    [apify] Couldn't read usage ({e}) — skipping Apify to be safe")
        return False


def _run_actor(client, actor: str, run_input: dict, max_items: int, max_charge: Decimal) -> list[dict]:
    run = client.actor(actor).call(
        run_input=run_input,
        max_items=max_items,
        max_total_charge_usd=max_charge,
        run_timeout=timedelta(minutes=8),
        logger=None,
    )
    if run is None:
        raise RuntimeError("run did not return")
    status = getattr(run, "status", None) or (run.get("status") if isinstance(run, dict) else None)
    dataset_id = getattr(run, "default_dataset_id", None) or (
        run.get("defaultDatasetId") if isinstance(run, dict) else None
    )
    cost = getattr(run, "usage_total_usd", None)
    print(f"    [apify] {actor}: {status}" + (f" · ${float(cost):.3f}" if cost is not None else ""))
    if not dataset_id:
        return []
    return list(client.dataset(dataset_id).iterate_items(limit=max_items))


# ─────────────────────────────────────────────────────────────────
# 1. TikTok Creative Center — trending songs
# ─────────────────────────────────────────────────────────────────

def _parse_tiktok_song(item: dict) -> dict | None:
    name = _first(item, "title", "songName", "song_name", "name", "musicName")
    if not name:
        return None
    artist = _first(item, "author", "artist", "authorName", "singer", "artistName")
    link = _first(item, "link", "url", "musicUrl", "music_url", "tiktokUrl", "audioLink")
    rank = _first(item, "rank", "position", default=None)
    change = _first(item, "rankDiff", "rank_diff", "rankChange", "rank_change", default=None)
    is_new = bool(_first(item, "markedAsNew", "isNew", "is_new", default=False))

    note_bits = [f"TikTok Creative Center #{rank}" if rank else "TikTok Creative Center chart",
                 f"({TIKTOK_REGION}, 7 days)"]
    if is_new:
        note_bits.append("· new entry")
    elif isinstance(change, (int, float)) and change:
        note_bits.append(f"· {'▲' if change > 0 else '▼'}{abs(int(change))}")

    stage = "Early" if is_new else ("Rising" if isinstance(change, (int, float)) and change > 0 else "Unknown")
    return {
        "name": str(name).strip(),
        "artist": str(artist).strip(),
        "audio_type": "",
        "use_count": "",
        "trend_stage": stage,
        "trend_note": " ".join(note_bits),
        "context": "",
        "source_url": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/music/pc/en",
        "sources": ["tiktok_creative_center"],
        "mention_count": 1,
        "ig_link": "",
        "tiktok_link": str(link) if link else "",
        "tiktok_rank": rank,
    }


def scrape_tiktok_trending(client) -> list[dict]:
    try:
        items = _run_actor(
            client,
            TIKTOK_ACTOR,
            {
                "mode": "songs",
                "region": TIKTOK_REGION,
                "period": "7",
                "maxItems": TIKTOK_SONG_LIMIT,
                "proxyConfiguration": RESIDENTIAL_PROXY,
            },
            max_items=TIKTOK_SONG_LIMIT,
            max_charge=TIKTOK_MAX_CHARGE,
        )
    except Exception as e:
        print(f"    [apify] TikTok Creative Center error: {e}")
        return []

    if items:
        # Field names aren't documented by the actor — log them once for maintenance
        print(f"    [apify] TikTok item fields: {sorted(items[0].keys())[:20]}")
    songs = [s for s in (_parse_tiktok_song(i) for i in items) if s]
    print(f"    [apify] TikTok Creative Center → {len(songs)} trending songs")
    return songs


# ─────────────────────────────────────────────────────────────────
# 2. Instagram — sounds used in niche hashtag reels
# ─────────────────────────────────────────────────────────────────

def _reel_metrics(reel: dict, now: datetime) -> dict:
    plays = int(_first(reel, "videoPlayCount", "igPlayCount", "videoViewCount", default=0) or 0)
    likes = max(int(reel.get("likesCount") or 0), 0)          # -1 when likes are hidden
    comments = max(int(reel.get("commentsCount") or 0), 0)
    try:
        posted = datetime.fromisoformat(str(reel.get("timestamp", "")).replace("Z", "+00:00"))
        age_days = max((now - posted).total_seconds() / 86400, 0.5)
    except ValueError:
        age_days = 7.0
    return {
        "plays": max(plays, 0),
        "plays_per_day": max(plays, 0) / age_days,
        "engagement": (likes + comments) / plays if plays > 0 else 0.0,
        "age_days": age_days,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    return vals[min(len(vals) - 1, int(pct * len(vals)))]


def scrape_instagram_niche_audio(client) -> list[dict]:
    """
    The actor only returns *recent* reels, so we pull a wide pool and judge
    success ourselves: a reel is a "hit" if its views-per-day is in the top
    half of this week's niche pool, or its engagement rate is in the top
    quarter. Only hit reels count toward a sound's signal.
    """
    limit = IG_REELS_PER_HASHTAG * len(IG_HASHTAGS)
    try:
        reels = _run_actor(
            client,
            IG_ACTOR,
            {
                "hashtags": IG_HASHTAGS,
                "resultsType": "reels",
                "resultsLimit": IG_REELS_PER_HASHTAG,
            },
            max_items=limit,
            max_charge=IG_MAX_CHARGE,
        )
    except Exception as e:
        print(f"    [apify] Instagram hashtag error: {e}")
        return []

    now = datetime.now(timezone.utc)
    for r in reels:
        r["_m"] = _reel_metrics(r, now)
    ppd_bar = _percentile([r["_m"]["plays_per_day"] for r in reels], 0.5)
    eng_bar = _percentile([r["_m"]["engagement"] for r in reels if r["_m"]["plays"] > 0], 0.75)
    # Engagement only counts once a reel has real reach (tiny reels have noisy ratios)
    hits = [r for r in reels
            if r["_m"]["plays_per_day"] >= ppd_bar
            or (r["_m"]["engagement"] >= eng_bar and r["_m"]["plays"] >= MIN_PLAYS_FOR_ENGAGEMENT)]

    sounds: dict[str, dict] = {}
    for reel in hits:
        mi = reel.get("musicInfo") or {}
        audio_id = str(mi.get("audio_id") or "").strip()
        song = (mi.get("song_name") or "").strip()
        artist = (mi.get("artist_name") or "").strip()
        if not audio_id or not song:
            continue
        m = reel["_m"]
        owner = reel.get("ownerUsername") or ""
        tags = {t.lower() for t in (reel.get("hashtags") or [])}

        s = sounds.setdefault(audio_id, {
            "name": song, "artist": artist, "original": bool(mi.get("uses_original_audio")),
            "reels": 0, "owners": set(), "plays": 0, "tags": set(), "captions": [],
            "best": None,
        })
        s["reels"] += 1
        s["plays"] += m["plays"]
        if owner:
            s["owners"].add(owner)
        s["tags"] |= tags & {h.lower() for h in IG_HASHTAGS}
        if s["best"] is None or m["plays_per_day"] > s["best"]["ppd"]:
            s["best"] = {"ppd": m["plays_per_day"], "plays": m["plays"], "days": m["age_days"],
                         "url": reel.get("url", "")}
        cap = re.sub(r"\s+", " ", reel.get("caption") or "")[:120]
        if cap and len(s["captions"]) < 2:
            s["captions"].append(cap)

    results = []
    for audio_id, s in sounds.items():
        creators = len(s["owners"]) or s["reels"]
        # A creator's own voiceover only counts as a trend once other creators reuse it
        if s["original"] and creators < 2:
            continue
        tag_txt = ", ".join(f"#{t}" for t in sorted(s["tags"])[:3]) or "niche hashtags"
        best = s["best"]
        results.append({
            "name": s["name"],
            "artist": s["artist"],
            "audio_type": "",
            "use_count": f"{s['reels']} hit niche reel{'s' if s['reels'] != 1 else ''}",
            "trend_stage": "Unknown",
            "trend_note": (f"In {s['reels']} high-performing {tag_txt} reel{'s' if s['reels'] != 1 else ''} "
                           f"by {creators} creator{'s' if creators != 1 else ''} — best: "
                           f"{_fmt_count(best['plays'])} plays in {max(1, round(best['days']))} days"),
            "context": " | ".join(s["captions"]),
            "source_url": best["url"] or f"https://www.instagram.com/explore/tags/{IG_HASHTAGS[0]}/",
            "sources": ["instagram_niche_reels"],
            "mention_count": 1,
            "ig_link": f"https://www.instagram.com/reels/audio/{audio_id}/",
            "tiktok_link": "",
            "niche_reel_count": s["reels"],
            "niche_creators": creators,
            "niche_plays": s["plays"],
            "niche_best_plays_per_day": int(best["ppd"]),
        })

    results.sort(key=lambda r: (r["niche_creators"], r["niche_best_plays_per_day"]), reverse=True)
    print(f"    [apify] Instagram: {len(reels)} niche reels, {len(hits)} hits "
          f"(≥{_fmt_count(int(ppd_bar))} views/day or top-quarter engagement) → {len(results)} sounds")
    return results


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def scrape_apify() -> list[dict]:
    if not APIFY_API_KEY:
        print("    [apify] No APIFY_API_KEY set — skipping")
        return []
    if not _month_usage_ok():
        return []
    try:
        from apify_client import ApifyClient
    except ImportError:
        print("    [apify] apify-client not installed — skipping")
        return []

    client = ApifyClient(APIFY_API_KEY)
    tiktok = scrape_tiktok_trending(client) if TIKTOK_ENABLED else []
    return scrape_instagram_niche_audio(client) + tiktok

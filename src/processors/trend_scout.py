"""
Trend Scout — the weekly "which post formats are working" read-out.

Takes this week's scored audio, groups it by `format_type`, and compares the
mix against the previous week's digest in docs/data/. Produces:

  - per-format stats (count, strong sounds, avg score, niche fit, share)
  - week-over-week change in each format's share of trending audio
  - the top 3 formats, each with its best example sounds
  - a one-sentence insight written by Claude (falls back to a template)

The result is shown at the top of the weekly email and saved into the
digest JSON so the dashboard can show it too.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from src.config import FORMAT_TYPES, CLAUDE_MODEL, MIN_RECOMMEND_SCORE

DATA_DIR = Path("docs/data")

STRONG_SCORE = MIN_RECOMMEND_SCORE   # potency at or above this counts as a "strong" sound
RISING_DELTA = 5.0      # share change (percentage points) that counts as rising/falling
EXAMPLES_PER_FORMAT = 2


def _format_stats(audio: list[dict]) -> dict[str, dict]:
    total = len(audio) or 1
    stats = {}
    for fmt in FORMAT_TYPES:
        items = [a for a in audio if a.get("format_type") == fmt]
        scores = [a.get("potency_score", 0) or 0 for a in items]
        fits = [a.get("niche_relevance", 0) or 0 for a in items]
        best = sorted(
            items,
            key=lambda a: (a.get("potency_score", 0), a.get("niche_relevance", 0)),
            reverse=True,
        )
        stats[fmt] = {
            "count": len(items),
            "strong": sum(1 for s in scores if s >= STRONG_SCORE),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "avg_fit": round(sum(fits) / len(fits), 2) if fits else 0.0,
            "share": round(100 * len(items) / total, 1),
            "examples": [
                {
                    "name": a.get("name", ""),
                    "artist": a.get("artist", ""),
                    "potency_score": a.get("potency_score", 0),
                    "ig_link": a.get("ig_link", ""),
                    "tiktok_link": a.get("tiktok_link", ""),
                    "cinematic_angle": a.get("cinematic_angle", ""),
                }
                for a in best
                if (a.get("potency_score") or 0) >= MIN_RECOMMEND_SCORE
            ][:EXAMPLES_PER_FORMAT],
        }
    return stats


def _load_baseline(today: date) -> tuple[str, list[dict]] | tuple[None, None]:
    """
    Last week's audio: the newest earlier digest that has format data,
    preferring one at least 5 days old so an extra manual run mid-week
    doesn't become the comparison point.
    """
    candidates = []
    for p in DATA_DIR.glob("digest_*.json"):
        d = p.stem.replace("digest_", "")
        try:
            day = date.fromisoformat(d)
        except ValueError:
            continue
        if day >= today:
            continue
        try:
            audio = json.loads(p.read_text(encoding="utf-8")).get("audio", [])
        except Exception:
            continue
        if any(a.get("format_type") for a in audio):
            candidates.append((day, audio))
    if not candidates:
        return None, None
    candidates.sort(key=lambda c: c[0], reverse=True)
    older = [c for c in candidates if c[0] <= today - timedelta(days=5)]
    day, audio = (older or candidates)[0]
    return day.isoformat(), audio


def _insight(top: list[dict], rising: list[str], falling: list[str]) -> str:
    """One-sentence takeaway from Claude; template fallback if the call fails."""
    lead = top[0]["format"] if top else None
    fallback = (
        f"{lead} leads this week's trending audio"
        + (f", with {', '.join(rising)} gaining ground." if rising else ".")
        if lead else "Not enough scored audio this week to call a format trend."
    )
    if not top:
        return fallback
    try:
        from src.processors.claude_scorer import client
        payload = {"top_formats": top, "rising": rising, "falling": falling}
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=(
                "You write the one-sentence takeaway for a weekly trend report for an "
                "Instagram creator in Warhammer 40K, miniature painting, hobby crafts and "
                "nerd culture. The stats describe sounds trending across Instagram/TikTok "
                "this week, grouped by post format and scored for fit with that niche — "
                "they are NOT the creator's own engagement or performance, so never say "
                "'your engagement' or 'your posts'. 'share' is the format's percentage of "
                "this week's trending sounds; avg_score is out of 10. Write ONE concrete, "
                "actionable sentence (max 35 words) on which format to lean into this week, "
                "naming a specific example sound and a niche-specific idea. "
                "No preamble, no quotes, no emoji."
            ),
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content
                       if getattr(b, "type", "") == "text").strip().strip('"')
        return text.split("\n")[0] or fallback
    except Exception as e:
        print(f"    [trend_scout] Insight call failed, using template: {e}")
        return fallback


def build_trend_scout(scored_audio: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    this_week = _format_stats(scored_audio)

    baseline_date, last_audio = _load_baseline(today)
    last_week = _format_stats(last_audio) if last_audio else None

    formats = []
    for fmt in FORMAT_TYPES:
        cur = this_week[fmt]
        entry = {"format": fmt, **cur, "share_delta": None, "trend": "new baseline"}
        if last_week is not None:
            prev = last_week[fmt]
            delta = round(cur["share"] - prev["share"], 1)
            entry["share_delta"] = delta
            entry["last_count"] = prev["count"]
            if prev["count"] == 0 and cur["count"] > 0:
                entry["trend"] = "new"
            elif delta >= RISING_DELTA:
                entry["trend"] = "rising"
            elif delta <= -RISING_DELTA:
                entry["trend"] = "falling"
            else:
                entry["trend"] = "steady"
        formats.append(entry)

    ranked = sorted(
        [f for f in formats if f["count"]],
        key=lambda f: (f["strong"], f["avg_score"], f["avg_fit"]),
        reverse=True,
    )
    # Only formats with at least one strong sound make the top list
    top = [f for f in ranked if f["strong"]][:3] or ranked[:1]
    rising = [f["format"] for f in formats if f["trend"] in ("rising", "new")]
    falling = [f["format"] for f in formats if f["trend"] == "falling"]

    summary_for_insight = [
        {k: f[k] for k in ("format", "count", "strong", "avg_score", "avg_fit", "share", "share_delta")}
        | {"example": f["examples"][0]["name"] if f["examples"] else ""}
        for f in top
    ]
    result = {
        "week_of": today.isoformat(),
        "compared_to": baseline_date,
        "formats": formats,
        "top": [f["format"] for f in top],
        "rising": rising,
        "falling": falling,
        "insight": _insight(summary_for_insight, rising, falling),
    }
    print(f"    [trend_scout] Top formats: {', '.join(result['top']) or '—'}"
          f" · baseline: {baseline_date or 'none (first week)'}")
    return result

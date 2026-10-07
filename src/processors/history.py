"""
Week-over-week memory, built from the digests already saved in docs/data/.

No database: every past digest JSON is the record. For each sound this week
we look up previous weeks (matching on platform audio ID or title) and add:

  weeks_seen        how many weeks (incl. this one) it has shown up
  times_recommended how many past weeks it scored at/above the recommend bar
  prev_score        last week's potency score, if any
  history_label     "New this week" | "Week N" | "Climbing · week N" | "Cooling · week N"

Repeat recommendations that aren't climbing are held back from the email
(they stay on the dashboard), so each Monday leads with what's new.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from src.config import MIN_RECOMMEND_SCORE, HISTORY_WEEKS, MAX_REPEAT_RECOMMENDATIONS
from src.processors.audio_merge import sound_keys

DATA_DIR = Path("docs/data")


def _signal(item: dict) -> float:
    """Comparable momentum number across weeks."""
    return 3.0 * (item.get("niche_creators") or 0) + 2.0 * (item.get("mention_count") or 1)


def _load_past_weeks(today: date) -> list[tuple[str, list[dict]]]:
    """Latest digest per ISO week, newest first, excluding the current week."""
    this_week = today.isocalendar()[:2]
    by_week: dict[tuple, tuple[date, list]] = {}
    for p in DATA_DIR.glob("digest_*.json"):
        try:
            d = date.fromisoformat(p.stem.replace("digest_", ""))
        except ValueError:
            continue
        wk = d.isocalendar()[:2]
        if wk == this_week or d < today - timedelta(weeks=HISTORY_WEEKS):
            continue
        if wk in by_week and by_week[wk][0] >= d:
            continue
        try:
            audio = json.loads(p.read_text(encoding="utf-8")).get("audio", [])
        except Exception:
            continue
        by_week[wk] = (d, audio)
    return [(d.isoformat(), audio) for d, audio in sorted(by_week.values(), key=lambda x: x[0], reverse=True)]


def annotate_history(audio: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    past = _load_past_weeks(today)

    # key → list of (week_date, item) newest first
    index: dict[str, list[tuple[str, dict]]] = {}
    for week_date, items in past:
        for it in items:
            for k in sound_keys(it):
                index.setdefault(k, []).append((week_date, it))

    for item in audio:
        seen: dict[str, dict] = {}
        for k in sound_keys(item):
            for week_date, it in index.get(k, []):
                seen.setdefault(week_date, it)
        weeks = sorted(seen, reverse=True)
        item["weeks_seen"] = len(weeks) + 1
        item["times_recommended"] = sum(
            1 for w in weeks if (seen[w].get("potency_score") or 0) >= MIN_RECOMMEND_SCORE
        )
        if not weeks:
            item["history_label"] = "New this week"
            item["prev_score"] = None
            continue
        prev = seen[weeks[0]]
        item["prev_score"] = prev.get("potency_score")
        now_sig, prev_sig = _signal(item), _signal(prev)
        n = item["weeks_seen"]
        if now_sig > prev_sig:
            item["history_label"] = f"Climbing · week {n}"
        elif now_sig < prev_sig:
            item["history_label"] = f"Cooling · week {n}"
        else:
            item["history_label"] = f"Week {n}"

    new = sum(1 for a in audio if a["history_label"] == "New this week")
    print(f"    [history] {len(past)} past week(s) loaded · {new}/{len(audio)} sounds new this week")
    return audio


def is_stale_repeat(item: dict) -> bool:
    """Already recommended enough times and not gaining momentum."""
    return (item.get("times_recommended") or 0) >= MAX_REPEAT_RECOMMENDATIONS and not str(
        item.get("history_label", "")
    ).startswith("Climbing")

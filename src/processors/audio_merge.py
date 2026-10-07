"""
Merges audio from every source (trend blogs, TikTok chart, Instagram niche
reels) into one de-duplicated list, then keeps the most promising items up
to MAX_AUDIO_ITEMS before scoring.

Two items are the same sound if they share a platform audio link, or (for
anything other than generic "Original audio") the same normalised title.
When merged, sources and signals are combined so the scorer sees, e.g.,
"on 2 trend sites + TikTok #14 + used by 5 niche creators".
"""

import hashlib
import re
from src.config import MAX_AUDIO_ITEMS

SIGNAL_FIELDS = ("tiktok_rank", "niche_reel_count", "niche_creators", "niche_plays", "niche_best_plays_per_day")


def _name_key(item: dict) -> str:
    return re.sub(r"[^a-z0-9]", "", (item.get("name") or "").lower())[:40]


def _link_keys(item: dict) -> list[str]:
    keys = []
    for f in ("ig_link", "tiktok_link"):
        m = re.search(r"(\d{6,})", item.get(f) or "")
        if m:
            keys.append(f"{f}:{m.group(1)}")
    return keys


def sound_keys(item: dict) -> list[str]:
    """Every key that identifies this sound: platform audio IDs, plus title unless generic."""
    nkey = _name_key(item)
    return _link_keys(item) + ([] if not nkey or nkey.startswith("original") else [f"name:{nkey}"])


def make_sound_id(item: dict) -> str:
    keys = sound_keys(item) or [f"name:{_name_key(item)}"]
    return hashlib.sha1(keys[0].encode()).hexdigest()[:10]


def _priority(item: dict) -> float:
    score = 3.0 * (item.get("niche_creators") or 0)       # proven niche use
    score += 2.0 * (item.get("mention_count") or 1)       # cross-source momentum
    rank = item.get("tiktok_rank")
    if isinstance(rank, (int, float)) and rank > 0:
        score += max(0.0, 3.0 - rank / 20)                # top of the TikTok chart
    return score


def merge_audio(*sources: list[dict]) -> list[dict]:
    merged: list[dict] = []
    index: dict[str, dict] = {}

    for source in sources:
        for item in source:
            if not _name_key(item):
                continue
            keys = sound_keys(item)
            existing = next((index[k] for k in keys if k in index), None)

            if existing is None:
                item = dict(item)
                item["sources"] = list(item.get("sources") or [item.get("source_url", "")])
                merged.append(item)
                existing = item
            else:
                for src in item.get("sources") or []:
                    if src not in existing["sources"]:
                        existing["sources"].append(src)
                existing["mention_count"] = len(existing["sources"])
                for f in ("artist", "use_count", "ig_link", "tiktok_link", "context"):
                    if not existing.get(f) and item.get(f):
                        existing[f] = item[f]
                if item.get("trend_note") and item["trend_note"] not in (existing.get("trend_note") or ""):
                    existing["trend_note"] = "; ".join(
                        x for x in (existing.get("trend_note"), item["trend_note"]) if x
                    )
                if existing.get("trend_stage", "Unknown") == "Unknown":
                    existing["trend_stage"] = item.get("trend_stage", "Unknown")
                for f in SIGNAL_FIELDS:
                    if item.get(f) is not None and existing.get(f) is None:
                        existing[f] = item[f]
            for k in keys:
                index.setdefault(k, existing)

    for item in merged:
        item["sound_id"] = make_sound_id(item)

    merged.sort(key=_priority, reverse=True)
    if len(merged) > MAX_AUDIO_ITEMS:
        print(f"  → capping {len(merged)} sounds to the {MAX_AUDIO_ITEMS} strongest signals")
        merged = merged[:MAX_AUDIO_ITEMS]
    return merged

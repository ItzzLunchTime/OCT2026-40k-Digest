"""
Sends raw scraped audio and topic data to Claude for:
  - Niche categorisation
  - Cinematic scoring (sync, register, counterpoint)
  - Content angle generation
  - Topic gap detection

Returns enriched lists ready for email and dashboard.
"""

import json
import re
import anthropic
from src.config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, ALERT_THRESHOLD, AUDIO_BATCH_SIZE, FORMAT_TYPES,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _reply_text(response) -> str:
    """Join the text blocks of a reply (newer models may put a thinking block first)."""
    return "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")


def _parse_json_array(raw_text: str) -> list:
    """Pull the JSON array out of a model reply, tolerating code fences or stray prose."""
    text = raw_text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in reply")
    return json.loads(text[start : end + 1])


# ─────────────────────────────────────────────────────────────────
# AUDIO SCORING
# ─────────────────────────────────────────────────────────────────

FORMAT_LIST = "\n".join(f"  - {f}" for f in FORMAT_TYPES)

AUDIO_SYSTEM_PROMPT = f"""
You are a content intelligence system for a Warhammer 40K / hobby / tabletop RPG
Instagram account run by a filmmaker with a strong cinematic sensibility.

Your job is to evaluate trending audio (music, dialogue clips, soundbites, meme audio,
CapCut template sounds) and determine how useful each is for this account.

The account's aesthetic is grimdark, cinematic, and craft-focused. The creator
approaches edits like a film director — thinking about sync points, emotional register,
and counterpoint, not just "does this sound cool." The filmmaker background is never
referenced directly in content; it is simply the lens through which editorial decisions
are made.

Each input item has an "id", plus scraped fields. Use "context" (the blurb around the
link on the source site) and "trend_note" to understand HOW the sound is being used.
"mention_count" is how many independent trend sites listed it — higher means broader
momentum. Items from "instagram_niche_reels" are sounds already being used in recent
#warhammer40k / #minipainting reels ("niche_creators" = how many different creators):
that is direct proof of niche fit, so weight niche_relevance up accordingly.
"tiktok_rank" is the sound's position on TikTok's platform-wide trending chart.

Classify every item into exactly one content format (use the label verbatim):
{FORMAT_LIST}
Format guide:
  - POV + reaction: first-person voiceover or caption reacting to a statement/situation
  - Hobby + trending audio: craft/painting/build process riding the sound
  - Green screen template: speaker in front of a reference image or clip
  - Show/movie clip: audio lifted from a known film/show/game used as backdrop
  - Audio/voiceline: a standalone sound bite or voiceline that drives the joke/format

For each audio item, return a JSON object with these exact fields:
{{
  "id": <the input id, unchanged>,
  "name": "track or audio name",
  "artist": "artist or source",
  "audio_type": "music | dialogue | soundbite | template | meme",
  "trend_stage": "Early | Rising | Peak | Fading | Unknown",
  "format_type": "one of the five format labels above",
  "niche_relevance": <float 0-1: how applicable to 40K / minis / crafts / nerd culture>,
  "categories": ["list of applicable: Warhammer 40K, Dark Fantasy, Gaming/Hobby, General Trending"],
  "potency_score": <integer 1-10>,
  "sync_note": "brief note on sync potential — beat drops, swells, silence breaks",
  "register_note": "emotional register this creates — dread, awe, tension, intimacy, etc.",
  "counterpoint_potential": true or false,
  "counterpoint_note": "if true: how it creates productive tension against typical 40K visuals",
  "cinematic_angle": "a specific, filmmaker-informed post idea for this account — never mention filmmaking directly"
}}

Scoring guidance:
- 9-10: Strong early-stage sound with clear cinematic application for 40K content
- 7-8: Good fit, usable with creative framing
- 5-6: Possible with significant creative work
- 1-4: Poor fit for this account
If an item is clearly not an audio track (a website heading, a product name), give it
potency_score 1 and niche_relevance 0.

Consider personal taste profile if provided — weight scores toward demonstrated preferences.
Return ONLY a JSON array with one object per input item. No commentary outside the JSON.
"""

# Scraped fields we trust over anything the model echoes back
PASSTHROUGH_FIELDS = [
    "use_count", "trend_note", "context", "source_url", "sources",
    "mention_count", "ig_link", "tiktok_link",
    "tiktok_rank", "niche_reel_count", "niche_creators", "niche_plays",
]


def _score_batch(batch: list[dict], taste_note: str) -> list[dict]:
    user_content = (
        f"Score the following {len(batch)} audio items.\n"
        f"{taste_note}\n"
        f"AUDIO ITEMS:\n{json.dumps(batch, indent=2, ensure_ascii=False)}"
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=AUDIO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    if response.stop_reason == "max_tokens":
        raise ValueError("reply truncated at max_tokens")
    return _parse_json_array(_reply_text(response))


def score_audio(raw_audio: list[dict], taste_profile: str = "") -> list[dict]:
    if not raw_audio:
        return []

    taste_note = ""
    if taste_profile:
        taste_note = f"\n\nPERSONAL TASTE PROFILE (use to weight scores):\n{taste_profile}\n"

    items = [dict(item, id=i) for i, item in enumerate(raw_audio)]
    scored: list[dict] = []
    failed = 0

    for start in range(0, len(items), AUDIO_BATCH_SIZE):
        batch = items[start : start + AUDIO_BATCH_SIZE]
        result = None
        for attempt in (1, 2):
            try:
                result = _score_batch(batch, taste_note)
                break
            except Exception as e:
                print(f"    [scorer] Audio batch {start // AUDIO_BATCH_SIZE + 1} "
                      f"attempt {attempt} failed: {e}")
        if result is None:
            failed += len(batch)
            continue

        by_id = {it["id"]: it for it in batch}
        for obj in result:
            src = by_id.get(obj.get("id"))
            if src is None:
                continue
            for f in PASSTHROUGH_FIELDS:
                if f in src:
                    obj[f] = src[f]
            if obj.get("format_type") not in FORMAT_TYPES:
                obj["format_type"] = "Audio/voiceline"
            try:
                obj["niche_relevance"] = max(0.0, min(1.0, float(obj.get("niche_relevance", 0))))
            except (TypeError, ValueError):
                obj["niche_relevance"] = 0.0
            obj.pop("id", None)
            scored.append(obj)

    if failed:
        print(f"    [scorer] {failed} audio item(s) could not be scored and were dropped")
    print(f"    [scorer] Scored {len(scored)}/{len(raw_audio)} audio items")

    scored.sort(
        key=lambda x: (x.get("potency_score", 0), x.get("niche_relevance", 0)),
        reverse=True,
    )
    return scored


# ─────────────────────────────────────────────────────────────────
# TOPIC SCORING
# ─────────────────────────────────────────────────────────────────

TOPIC_SYSTEM_PROMPT = """
You are a content intelligence system for a Warhammer 40K / hobby / tabletop RPG
Instagram account. Your job is to identify the most valuable trending topics from
raw community signals (Reddit posts, YouTube video titles, forum threads, official
news) and structure them as actionable content opportunities.

Categories:
- Lore/Narrative: new releases, faction spotlights, story beats, codex drops
- Hobby Craft: painting techniques, new products, army showcases, modelling
- Tabletop/Gameplay: rule changes, meta shifts, tournament results, FAQs
- Community Questions: recurring questions being asked, content gaps (topics
  with lots of discussion but little quality video content)

For each item, return a JSON object:
{
  "title": "clear, concise topic headline",
  "category": "Lore/Narrative | Hobby Craft | Tabletop/Gameplay | Community Questions",
  "what_is_driving_it": "one sentence on what's causing the discussion",
  "relevance_note": "why this is worth covering now",
  "is_content_gap": true or false,
  "gap_note": "if true: why this is undercovered and what kind of content could own this space",
  "is_question": true or false,
  "source": "reddit | youtube | warhammer_community | spikey_bits | tabletop_battles | other",
  "url": "link if available"
}

YouTube signals include "views_per_day" (momentum — weight this over raw views),
"length" (short = YouTube Shorts, the closest proxy for Reels/TikTok formats) and
"group": "core" is the 40K/minis/hobby niche itself; "crossover" is broader nerd
culture. Only pick a crossover topic if it clearly connects to 40K, miniatures,
hobby crafting or tabletop gaming — say how in relevance_note.

Select only the 5-10 highest-value topics. Prioritise:
1. Content gaps (high discussion, low quality video coverage)
2. Recurring questions (the account can answer cinematically)
3. High-velocity discussions (lots of engagement right now)

Return ONLY a JSON array. No commentary outside the JSON.
"""


def score_topics(raw_topics: list[dict]) -> list[dict]:
    if not raw_topics:
        return []

    # Deduplicate by title similarity before sending
    seen: set[str] = set()
    unique: list[dict] = []
    for t in raw_topics:
        key = t.get("title", "")[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(t)

    user_content = (
        f"Analyse the following {len(unique)} community signals and return the "
        f"5-10 most valuable content topics.\n\n"
        f"SIGNALS:\n{json.dumps(unique, indent=2)}"
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8000,
            system=TOPIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        return _parse_json_array(_reply_text(response))

    except Exception as e:
        print(f"    [scorer] Topic scoring error: {e}")
        return []

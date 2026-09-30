"""
Sends raw scraped audio and topic data to Claude for:
  - Niche categorisation
  - Cinematic scoring (sync, register, counterpoint)
  - Content angle generation
  - Topic gap detection

Returns enriched lists ready for email and dashboard.
"""

import json
import anthropic
from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, ALERT_THRESHOLD

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────────────────────────
# AUDIO SCORING
# ─────────────────────────────────────────────────────────────────

AUDIO_SYSTEM_PROMPT = """
You are a content intelligence system for a Warhammer 40K / hobby / tabletop RPG
Instagram account run by a filmmaker with a strong cinematic sensibility.

Your job is to evaluate trending audio (music, dialogue clips, soundbites, meme audio,
CapCut template sounds) and determine how useful each is for this account.

The account's aesthetic is grimdark, cinematic, and craft-focused. The creator
approaches edits like a film director — thinking about sync points, emotional register,
and counterpoint, not just "does this sound cool." The filmmaker background is never
referenced directly in content; it is simply the lens through which editorial decisions
are made.

For each audio item, return a JSON object with these exact fields:
{
  "name": "track or audio name",
  "artist": "artist or source",
  "audio_type": "music | dialogue | soundbite | template | meme",
  "use_count": "as provided or empty string",
  "trend_stage": "Early | Rising | Peak | Fading | Unknown",
  "categories": ["list of applicable: Warhammer 40K, Dark Fantasy, Gaming/Hobby, General Trending"],
  "potency_score": <integer 1-10>,
  "sync_note": "brief note on sync potential — beat drops, swells, silence breaks",
  "register_note": "emotional register this creates — dread, awe, tension, intimacy, etc.",
  "counterpoint_potential": true or false,
  "counterpoint_note": "if true: how it creates productive tension against typical 40K visuals",
  "cinematic_angle": "a specific, filmmaker-informed post idea for this account — never mention filmmaking directly",
  "ig_link": "as provided or empty string",
  "tiktok_link": "as provided or empty string",
  "source_url": "as provided"
}

Scoring guidance:
- 9-10: Strong early-stage sound with clear cinematic application for 40K content
- 7-8: Good fit, usable with creative framing
- 5-6: Possible with significant creative work
- 1-4: Poor fit for this account

Consider personal taste profile if provided — weight scores toward demonstrated preferences.
Return ONLY a JSON array of objects. No commentary outside the JSON.
"""


def score_audio(raw_audio: list[dict], taste_profile: str = "") -> list[dict]:
    if not raw_audio:
        return []

    # Build the user message
    taste_note = ""
    if taste_profile:
        taste_note = f"\n\nPERSONAL TASTE PROFILE (use to weight scores):\n{taste_profile}\n"

    user_content = (
        f"Score the following {len(raw_audio)} audio items.\n"
        f"{taste_note}\n"
        f"AUDIO ITEMS:\n{json.dumps(raw_audio, indent=2)}"
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8000,
            system=AUDIO_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        scored = json.loads(raw_text)

        # Sort by potency descending
        scored.sort(key=lambda x: x.get("potency_score", 0), reverse=True)
        return scored

    except Exception as e:
        print(f"    [scorer] Audio scoring error: {e}")
        return raw_audio   # return unscored as fallback


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
  "source": "reddit | youtube | warhammer_community | dakkadakka | other",
  "url": "link if available"
}

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
            max_tokens=4000,
            system=TOPIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw_text = response.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        return json.loads(raw_text)

    except Exception as e:
        print(f"    [scorer] Topic scoring error: {e}")
        return []

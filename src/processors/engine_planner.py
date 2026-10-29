"""
Engine planner — turns this week's signals into a posting plan built around the
content engines in the "00 Content Engines" vault note.

  - pick_comments():  up to COMMENT_PICKS comments from your own posts worth a reply
                      video (only 6+/10; fewer on slow weeks, never padded)
  - digest_drop():    up to 3 news topics framed as "new player reads the news"
  - build_slate():    this week's Slot A / B / C posts, following the vault rotation
                      and the 99-day countdown (final 3 weeks lean on Road to Palm Springs)
"""

import json
from datetime import date

from src.config import (
    CLAUDE_MODEL,
    ACCOUNT_CONTEXT,
    MIN_RECOMMEND_SCORE,
    COMMENT_PICKS,
    CHALLENGE_START,
    CHALLENGE_DAYS,
    FINAL_PUSH_DAYS,
    ROTATION,
)
from src.processors.claude_scorer import (
    client, _reply_text, _parse_json_array, _clean_engine, ENGINE_BRIEF,
)

REPLY_FORMATS = ["tutorial", "answer", "reaction", "skit", "challenge accepted"]


def _ask(system: str, payload, max_tokens: int = 4000) -> str:
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    return _reply_text(resp)


# ─────────────────────────────────────────────────────────────────
# Challenge clock + rotation
# ─────────────────────────────────────────────────────────────────

def challenge_status(today: date | None = None) -> dict:
    today = today or date.today()
    day = (today - CHALLENGE_START).days + 1
    days_left = CHALLENGE_DAYS - day
    week_index = max(0, (day - 1) // 7)
    slots = dict(ROTATION[week_index % len(ROTATION)])
    phase = "countdown"
    if day < 1:
        phase = "pre-challenge"
    elif days_left < 0:
        phase = "post-tournament"
        slots = {"A": "Road to Palm Springs", "B": "Cinematic Recreations", "C": "Comment Replies"}
    elif days_left <= FINAL_PUSH_DAYS:
        phase = "final push"
        slots = {"A": "Road to Palm Springs", "B": "Road to Palm Springs", "C": slots["C"]}
    return {
        "day": day,
        "days_left": max(days_left, 0),
        "week": week_index + 1,
        "rotation_week": week_index % len(ROTATION) + 1,
        "phase": phase,
        "slots": slots,
    }


# ─────────────────────────────────────────────────────────────────
# Comment Picks
# ─────────────────────────────────────────────────────────────────

COMMENT_SYSTEM = f"""
You pick which viewer comments on this creator's own Instagram posts are worth turning
into a comment-reply Reel this week.
{ACCOUNT_CONTEXT}
{ENGINE_BRIEF}
Look for: genuine questions (especially "how did you do that?"), friendly disagreement or
corrections, funny lines, challenges or requests. Skip spam, self-promotion, generic praise
and anything mean-spirited about a person.

Score each candidate 1-10 for content potential and return ONLY a JSON array (best first)
of at most {COMMENT_PICKS} objects with score >= {MIN_RECOMMEND_SCORE}. Return [] if none qualify —
never pad. Each object:
{{
  "index": <input index>,
  "score": <integer 1-10>,
  "why": "one sentence: what makes it good material",
  "reply_format": "one of: {', '.join(REPLY_FORMATS)}",
  "engine": "the content engine the reply belongs to (usually Comment Replies, or the engine the answer shows off)",
  "idea": "the reply video in one sentence",
  "hook": "first 1-2 seconds — the payoff"
}}
"""


def pick_comments(comments: list[dict]) -> list[dict]:
    if not comments:
        return []
    # Most-liked first so the model sees the strongest candidates if we have to trim
    pool = sorted(comments, key=lambda c: (c.get("likes", 0), c.get("replies", 0)), reverse=True)[:60]
    payload = [
        {"index": i, "comment": c["text"][:400], "likes": c.get("likes", 0),
         "on_post": c.get("post_caption", "")}
        for i, c in enumerate(pool)
    ]
    try:
        picks = _parse_json_array(_ask(COMMENT_SYSTEM, payload))
    except Exception as e:
        print(f"    [planner] Comment picks failed: {e}")
        return []

    out = []
    for p in picks:
        try:
            src = pool[int(p.get("index"))]
            score = int(p.get("score") or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if score < MIN_RECOMMEND_SCORE:
            continue
        out.append({
            "comment": src["text"],
            "username": src.get("username", ""),
            "likes": src.get("likes", 0),
            "post_url": src.get("post_url", ""),
            "score": score,
            "why": p.get("why", ""),
            "reply_format": p.get("reply_format", ""),
            "engine": _clean_engine(p.get("engine")) or "Comment Replies",
            "idea": p.get("idea", ""),
            "hook": p.get("hook", ""),
        })
        if len(out) >= COMMENT_PICKS:
            break
    print(f"    [planner] Comment picks: {len(out)} of {len(comments)} comments")
    return out


# ─────────────────────────────────────────────────────────────────
# Digest Drop
# ─────────────────────────────────────────────────────────────────

def digest_drop(topics: list[dict], limit: int = 3) -> list[dict]:
    """News topics with a beginner take; Guard-relevant items first."""
    news = [t for t in topics if t.get("is_news") and t.get("beginner_take")]
    news.sort(key=lambda t: (bool(t.get("guard_relevant")), t.get("engine") == "Digest Drop"), reverse=True)
    return [
        {
            "title": t.get("title", ""),
            "summary": t.get("what_is_driving_it", ""),
            "url": t.get("url", ""),
            "source": t.get("source", ""),
            "guard_relevant": bool(t.get("guard_relevant")),
            "beginner_take": t.get("beginner_take", ""),
        }
        for t in news[:limit]
    ]


# ─────────────────────────────────────────────────────────────────
# Weekly slate
# ─────────────────────────────────────────────────────────────────

SLATE_SYSTEM = f"""
You plan this week's posts for a solo Instagram creator.
{ACCOUNT_CONTEXT}
{ENGINE_BRIEF}
You get: the 99-day challenge status, the engine assigned to each slot by the rotation,
and this week's scored trending sounds, community topics and viewer comments.

Write one concrete post per slot. Slot A = story, Slot B = craft, Slot C = optional flex
for a good week. Stick to the assigned engine for each slot. Pull real material from the
inputs: pair a hobby idea with a specific trending sound (meme as wrapper), use a topic,
or answer a comment. Name the sound/topic/comment you used.

Return ONLY a JSON object:
{{
  "headline": "one sentence: the week's angle",
  "slots": [
    {{
      "slot": "A | B | C",
      "engine": "engine name verbatim",
      "title": "working title",
      "hook": "first 1-2 seconds — the payoff",
      "on_screen_text": "the on-screen line",
      "caption_angle": "what the caption carries (the story/progress)",
      "uses": "the sound / topic / comment this draws on, or 'original'",
      "effort": "low | medium | high",
      "batch_tip": "how to shoot it alongside the other slots, or ''"
    }}
  ]
}}
"""


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1].removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def build_slate(scored_audio: list[dict], topics: list[dict], comment_picks: list[dict],
                today: date | None = None) -> dict:
    status = challenge_status(today)
    slots = status["slots"]
    sounds = [
        {k: a.get(k) for k in ("name", "artist", "format_type", "engine", "hook",
                               "on_screen_text", "cinematic_angle", "potency_score", "trend_stage")}
        for a in scored_audio if (a.get("potency_score") or 0) >= MIN_RECOMMEND_SCORE
    ][:10]
    payload = {
        "challenge": status,
        "sounds": sounds,
        "topics": [{k: t.get(k) for k in ("title", "engine", "episode_idea", "hook", "category")}
                   for t in topics][:10],
        "comments": [{k: c.get(k) for k in ("comment", "idea", "reply_format")} for c in comment_picks],
    }
    fallback = {
        "headline": f"Day {status['day']} of {CHALLENGE_DAYS}: rotation week {status['rotation_week']}.",
        "slots": [{"slot": k, "engine": v, "title": "", "hook": "", "on_screen_text": "",
                   "caption_angle": "", "uses": "", "effort": "", "batch_tip": ""}
                  for k, v in slots.items()],
    }
    try:
        plan = _parse_json_object(_ask(SLATE_SYSTEM, payload, max_tokens=3000))
        plan_slots = []
        for s in plan.get("slots", []):
            key = str(s.get("slot", "")).strip().upper()[:1]
            if key not in slots:
                continue
            s["slot"] = key
            s["engine"] = _clean_engine(s.get("engine")) or slots[key]
            plan_slots.append(s)
        if not plan_slots:
            raise ValueError("no usable slots")
        plan["slots"] = sorted(plan_slots, key=lambda s: s["slot"])
    except Exception as e:
        print(f"    [planner] Slate call failed, using rotation only: {e}")
        plan = fallback
    plan["challenge"] = status
    print(f"    [planner] Slate: day {status['day']}/{CHALLENGE_DAYS} ({status['phase']}) · "
          + ", ".join(f"{s['slot']}={s['engine']}" for s in plan["slots"]))
    return plan

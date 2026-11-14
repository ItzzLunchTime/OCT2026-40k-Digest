"""
Weekly account audit — runs before anything is scored or planned, so the rest of the
digest (sound scoring, topic scoring, the slate and the weekly goals) can react to it.

What it measures, all from data the digest already collects:
  - Cadence      posts in the last 7 / 28 days against the 1-3 a week target, gaps
  - Reach        recent median views against the account median, tier spread, best/worst
  - Length       how long posts run and whether long ones are costing views
  - Engagement   likes + comments per view, recent vs earlier
  - Content mix  reach posts vs product-facing posts against the partnership plan's split
  - Brand proof  whether product-facing posts tag a brand and use original audio
  - Growth       follower count, weekly change, pace toward the 10k goal
  - Follow-through  what was posted against last week's slate

How it works:
  1. Numbers are computed here in Python from docs/data/own_posts.json (the per-post
     history the performance check keeps) and docs/data/account_history.json (follower
     count per run). No model is involved in the arithmetic.
  2. One small Claude call labels each recent post (meme / product / story / craft) from
     its caption, tags and length. The label is cached on the post so it is done once.
  3. One Claude call turns the scorecard into findings, up to four goals for the week and
     a short note for the planner and scorers. If that call fails, the findings and goals
     fall back to the scorecard's own rules, so the section never disappears.

Limits worth knowing: saves, shares, follows per post and skip rate are only in Instagram
Insights, so they are not audited here; post labels come from captions, not the video.
"""

import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.config import ACCOUNT_CONTEXT, IG_ACCOUNT
from src.processors.claude_scorer import _parse_json_array
from src.processors.engine_planner import _ask, _parse_json_object
from src.processors.weekly_goals import PLAN_WEEKS, plan_week

DATA_DIR = Path("docs/data")
POSTS_PATH = DATA_DIR / "own_posts.json"
ACCOUNT_PATH = DATA_DIR / "account_history.json"

WINDOW_DAYS = 28            # the audit looks at the last four weeks
SETTLE_DAYS = 3             # younger posts are still collecting views
POSTS_PER_WEEK = (1, 3)     # stated capacity
FOLLOWER_GOAL = 10_000
LONG_POST_S = 45            # the profile's ceiling for a post that opens on a meme
PRODUCT_SHARE_TARGET = 0.5  # partnership plan: about half reach, half product-facing
MAX_AUDIT_GOALS = 4

KINDS = ["meme", "product", "story", "craft", "other"]
STATUS_ORDER = {"fix": 0, "watch": 1, "good": 2, "info": 3}


# ─────────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────────

def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _posts(now: datetime) -> list[dict]:
    """Every tracked post with its age, newest first."""
    out = []
    for rec in _load(POSTS_PATH).values():
        try:
            posted = datetime.fromisoformat(str(rec.get("timestamp", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append(dict(rec, posted=posted, age_days=max((now - posted).total_seconds() / 86400, 0.0)))
    return sorted(out, key=lambda p: p["posted"], reverse=True)


def _median(values) -> float:
    values = [v for v in values if v is not None]
    return float(statistics.median(values)) if values else 0.0


def _short(caption: str, n: int = 70) -> str:
    caption = (caption or "(no caption)").strip()
    return caption if len(caption) <= n else caption[: n - 1].rstrip() + "…"


def _row(area: str, value: str, status: str, action: str = "") -> dict:
    return {"area": area, "value": value, "status": status, "action": action}


# ─────────────────────────────────────────────────────────────────
# Scorecard sections (pure arithmetic)
# ─────────────────────────────────────────────────────────────────

def _cadence(posts: list[dict]) -> tuple[dict, dict]:
    recent = [p for p in posts if p["age_days"] <= WINDOW_DAYS]
    last7 = sum(1 for p in posts if p["age_days"] <= 7)
    per_week = len(recent) / (WINDOW_DAYS / 7)
    since_last = posts[0]["age_days"] if posts else None
    ages = sorted(p["age_days"] for p in recent)
    longest_gap = max((b - a for a, b in zip(ages, ages[1:])), default=0.0)
    stats = {
        "posts_last_7_days": last7,
        "posts_last_28_days": len(recent),
        "avg_per_week_28d": round(per_week, 1),
        "target_per_week": f"{POSTS_PER_WEEK[0]}-{POSTS_PER_WEEK[1]}",
        "days_since_last_post": None if since_last is None else round(since_last, 1),
        "longest_gap_days_28d": round(longest_gap, 1),
    }
    if since_last is None:
        return stats, _row("Cadence", "No tracked posts yet", "info")
    value = (f"{last7} post{'s' if last7 != 1 else ''} in the last 7 days · "
             f"{per_week:.1f} a week over 4 weeks (target {stats['target_per_week']})")
    if last7 == 0 or per_week < POSTS_PER_WEEK[0]:
        return stats, _row("Cadence", value, "fix",
                           f"Post at least once by midweek: the last post was {since_last:.0f} days ago")
    if longest_gap > 9:
        return stats, _row("Cadence", value + f" · longest gap {longest_gap:.0f} days", "watch",
                           "Bank one finished post so a busy week doesn't leave a gap")
    return stats, _row("Cadence", value, "good")


def _reach(posts: list[dict], median: float) -> tuple[dict, dict]:
    settled = [p for p in posts if p["age_days"] >= SETTLE_DAYS and p.get("views")]
    recent = [p for p in settled if p["age_days"] <= WINDOW_DAYS]
    earlier = [p for p in settled if WINDOW_DAYS < p["age_days"] <= 2 * WINDOW_DAYS]
    recent_med, earlier_med = _median(p["views"] for p in recent), _median(p["views"] for p in earlier)
    tiers = {"breakout": 0, "above": 0, "baseline": 0, "under": 0}
    for p in recent:
        r = p["views"] / median if median else 0
        tiers["breakout" if r > 3 else "above" if r > 1.5 else "under" if r < 0.5 else "baseline"] += 1
    best = max(recent, key=lambda p: p["views"], default=None)
    worst = min(recent, key=lambda p: p["views"], default=None)
    stats = {
        "account_median_views": int(median),
        "median_views_last_28d": int(recent_med),
        "median_views_previous_28d": int(earlier_med) if earlier else None,
        "settled_posts_last_28d": len(recent),
        "tiers_last_28d": tiers,
        "best_post": best and {"caption": _short(best.get("caption")), "views": best["views"],
                               "x_median": round(best["views"] / median, 1) if median else None},
        "worst_post": worst and {"caption": _short(worst.get("caption")), "views": worst["views"],
                                 "x_median": round(worst["views"] / median, 1) if median else None},
    }
    if len(recent) < 3 or not median:
        return stats, _row("Reach", f"Only {len(recent)} settled post{'s' if len(recent) != 1 else ''} "
                                    f"in 4 weeks — too few to judge", "info")
    ratio = recent_med / median
    value = (f"4-week median {int(recent_med):,} views = {ratio:.1f}x the account median · "
             f"{tiers['breakout']} breakout, {tiers['above']} above, {tiers['under']} under")
    if ratio < 0.5:
        return stats, _row("Reach", value, "fix",
                           "Open the next post on the payoff in second 1-2, and wrap it in a meme or reaction")
    if ratio < 0.8 or tiers["under"] > len(recent) / 2:
        return stats, _row("Reach", value, "watch", "Recut the best under-performer with the payoff moved to second 1")
    return stats, _row("Reach", value, "good")


def _length(posts: list[dict]) -> tuple[dict, dict]:
    recent = [p for p in posts if p["age_days"] <= WINDOW_DAYS and (p.get("duration_s") or 0) > 0]
    settled = [p for p in recent if p["age_days"] >= SETTLE_DAYS]
    buckets = {"up_to_30s": [], "30_to_45s": [], "over_45s": []}
    for p in settled:
        d = p["duration_s"]
        buckets["up_to_30s" if d <= 30 else "30_to_45s" if d <= LONG_POST_S else "over_45s"].append(p["views"])
    long_count = sum(1 for p in recent if p["duration_s"] > LONG_POST_S)
    stats = {
        "videos_last_28d": len(recent),
        "over_45s": long_count,
        "median_length_s": round(_median(p["duration_s"] for p in recent), 1),
        "median_views_by_length": {k: int(_median(v)) if v else None for k, v in buckets.items()},
    }
    if not recent:
        return stats, _row("Length", "No videos in the last 4 weeks", "info")
    short_med, long_med = _median(buckets["up_to_30s"]), _median(buckets["over_45s"])
    value = f"Median {stats['median_length_s']:.0f}s · {long_count} of {len(recent)} over {LONG_POST_S}s"
    if buckets["up_to_30s"] and buckets["over_45s"]:
        value += f" · ≤30s median {int(short_med):,} views vs {int(long_med):,} over {LONG_POST_S}s"
        if long_count >= len(recent) / 2 and long_med < short_med:
            return stats, _row("Length", value, "fix", f"Cut this week's posts to 30s or less, strongest shot first")
        if long_med < 0.5 * short_med:
            return stats, _row("Length", value, "watch", f"Keep anything over {LONG_POST_S}s for posts that open on a meme")
    elif long_count >= len(recent) / 2:
        return stats, _row("Length", value, "watch", f"Try one post at 30s or less this week to compare")
    return stats, _row("Length", value, "good")


def _engagement(posts: list[dict]) -> tuple[dict, dict]:
    def rate(group):
        return _median((p["likes"] + p["comments"]) / p["views"] for p in group if p.get("views"))
    settled = [p for p in posts if p["age_days"] >= SETTLE_DAYS]
    recent = [p for p in settled if p["age_days"] <= WINDOW_DAYS]
    earlier = [p for p in settled if WINDOW_DAYS < p["age_days"] <= 2 * WINDOW_DAYS]
    r, e = rate(recent), rate(earlier)
    stats = {
        "engagement_per_view_last_28d": round(r, 4),
        "engagement_per_view_previous_28d": round(e, 4) if earlier else None,
        "median_comments_last_28d": int(_median(p["comments"] for p in recent)),
    }
    if len(recent) < 3:
        return stats, _row("Engagement", "Too few settled posts to judge", "info")
    value = f"{r * 100:.1f}% likes + comments per view · median {stats['median_comments_last_28d']} comments a post"
    if earlier and e:
        value += f" (previous 4 weeks {e * 100:.1f}%)"
        if r < 0.7 * e:
            return stats, _row("Engagement", value, "watch", "End this week's captions on a question the comments can answer")
    return stats, _row("Engagement", value, "good")


def _mix(posts: list[dict]) -> tuple[dict, list[dict]]:
    recent = [p for p in posts if p["age_days"] <= WINDOW_DAYS]
    counts = {k: sum(1 for p in recent if p.get("kind") == k) for k in KINDS}
    labelled = sum(counts.values())
    product = [p for p in recent if p.get("kind") == "product"]
    tagged = [p for p in product if p.get("mentions")]
    audio_known = [p for p in product if p.get("original_audio") is not None]
    original = [p for p in audio_known if p.get("original_audio")]
    stats = {
        "labelled_posts_last_28d": labelled,
        "kinds": counts,
        "product_share": round(counts["product"] / labelled, 2) if labelled else None,
        "product_share_target": PRODUCT_SHARE_TARGET,
        "product_posts_tagging_a_brand_or_store": f"{len(tagged)} of {len(product)}",
        "product_posts_with_original_audio": f"{len(original)} of {len(audio_known)}" if audio_known else "not measured",
        "accounts_tagged_last_28d": sorted({m for p in recent for m in (p.get("mentions") or [])})[:12],
    }
    if not labelled:
        return stats, [_row("Content mix", "Posts couldn't be labelled this week", "info")]
    share = counts["product"] / labelled
    mix_value = (f"{counts['meme']} meme · {counts['product']} product-facing · {counts['story']} story · "
                 f"{counts['craft']} craft of {labelled} posts ({share * 100:.0f}% product-facing, target about "
                 f"{PRODUCT_SHARE_TARGET * 100:.0f}%)")
    if share < 0.2:
        rows = [_row("Content mix", mix_value, "fix",
                     "Make this week's second post product-facing: one tool or paint, named, used and judged")]
    elif share < 0.35:
        rows = [_row("Content mix", mix_value, "watch", "Keep one product-facing post in every week's slate")]
    elif counts["meme"] == 0:
        rows = [_row("Content mix", mix_value, "watch", "Add a meme this week so reach doesn't stall")]
    else:
        rows = [_row("Content mix", mix_value, "good")]

    if not product:
        rows.append(_row("Brand proof", "No product-facing posts in 4 weeks, so nothing a brand could judge", "fix",
                         "Tag every brand whose product is on screen in the next product-facing post"))
    else:
        value = f"{len(tagged)} of {len(product)} product-facing posts tag a brand or store"
        if audio_known:
            value += f" · {len(original)} of {len(audio_known)} use original audio"
        if len(tagged) < len(product):
            rows.append(_row("Brand proof", value, "fix" if not tagged else "watch",
                             "Tag every brand whose product appears, in the caption and on the video"))
        elif audio_known and len(original) < len(audio_known):
            rows.append(_row("Brand proof", value, "watch",
                             "Use voiceover or original audio on product-facing posts so brands can reuse them"))
        else:
            rows.append(_row("Brand proof", value, "good"))
    return stats, rows


def _growth(profile: dict | None, today: date) -> tuple[dict, dict]:
    """Store this run's follower count and read the trend back out."""
    history = _load(ACCOUNT_PATH) or {}
    snaps = [s for s in history.get("snapshots", []) if s.get("date") != today.isoformat()]
    followers = (profile or {}).get("followers")
    if followers:
        snaps.append({"date": today.isoformat(), "followers": int(followers),
                      "posts": (profile or {}).get("posts")})
        snaps = snaps[-104:]
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ACCOUNT_PATH.write_text(json.dumps({"snapshots": snaps}, indent=2), encoding="utf-8")
    if not followers:
        return {"followers": None}, _row("Growth", "Follower count not available this run", "info")

    def at_or_before(days: int):
        cutoff = (today - timedelta(days=days)).isoformat()
        older = [s for s in snaps if s["date"] <= cutoff]
        return older[-1] if older else None

    week_ago, month_ago = at_or_before(6), at_or_before(27)
    delta_week = followers - week_ago["followers"] if week_ago else None
    pace = None
    if month_ago:
        weeks = max((today - date.fromisoformat(month_ago["date"])).days / 7, 1)
        pace = (followers - month_ago["followers"]) / weeks
    to_goal = max(FOLLOWER_GOAL - followers, 0)
    stats = {
        "followers": int(followers),
        "change_last_week": delta_week,
        "avg_weekly_change_4wk": round(pace, 1) if pace is not None else None,
        "to_goal": to_goal,
        "goal": FOLLOWER_GOAL,
        "weeks_to_goal_at_4wk_pace": round(to_goal / pace) if pace and pace > 0 else None,
    }
    value = f"{int(followers):,} followers · {to_goal:,} to {FOLLOWER_GOAL:,}"
    if delta_week is None:
        return stats, _row("Growth", value + " · first week tracked", "info")
    value += f" · {delta_week:+,} this week"
    if stats["weeks_to_goal_at_4wk_pace"]:
        value += f" · about {stats['weeks_to_goal_at_4wk_pace']} weeks to goal at the 4-week pace"
    if delta_week < 0:
        return stats, _row("Growth", value, "fix", "Put a face-to-camera story beat in this week's Slot A")
    if delta_week == 0 or (pace is not None and delta_week < 0.5 * pace):
        return stats, _row("Growth", value, "watch", "Make this week's meme about your own minis or Guard army, not a generic joke")
    return stats, _row("Growth", value, "good")


def _last_digest(today: date) -> dict:
    """Slate and goals from the most recent earlier digest, for the follow-through check."""
    files = sorted(p for p in DATA_DIR.glob("digest_*.json") if p.stem[7:] < today.isoformat())
    if not files:
        return {}
    data = _load(files[-1])
    slots = [{"slot": s.get("slot"), "engine": s.get("engine"), "title": s.get("title"), "hook": s.get("hook")}
             for s in ((data.get("slate") or {}).get("slots") or [])]
    goals = [i for g in ((data.get("weekly_goals") or {}).get("groups") or []) for i in g.get("items", [])
             if g.get("title") != "Every post"]
    return {"date": files[-1].stem[7:], "slate": slots, "goals": goals}


# ─────────────────────────────────────────────────────────────────
# Claude: label posts, then write the findings
# ─────────────────────────────────────────────────────────────────

LABEL_SYSTEM = f"""
You label Instagram posts from one hobby account so a weekly audit can count the content mix.
{ACCOUNT_CONTEXT}
You only see each post's caption, the accounts it tags, its type and its length — not the video.
Pick the one label that fits best:
  "meme"     a joke, reaction, trending-sound or POV post made mainly for reach
  "product"  a named tool, paint, kit, piece of gear or a store is shown being used or judged
             (tool tests, reviews, hauls, store visits, "what I use", gift guides)
  "story"    a to-camera or progress update about him, his army or the tournament
  "craft"    a build, paint, lighting or effects post with no named product
  "other"    anything else (throwbacks, announcements, thank-you posts)
Return ONLY a JSON array of {{"index": <input index>, "kind": "<label>"}}, one per input post.
"""

PLAN_TARGETS = f"""
TARGETS THE AUDIT JUDGES AGAINST:
  - Capacity: {POSTS_PER_WEEK[0]}-{POSTS_PER_WEEK[1]} posts a week, no more.
  - Growth goal: {FOLLOWER_GOAL:,} followers.
  - 90-Day Brand Partnership Plan: about half of posts for reach (memes), about half product-facing
    (brand proof and pitch assets). Product-facing posts name the product, tag the brand, and use
    original audio or voiceover so a brand could reuse them. Never fewer than one meme a week.
  - The account-performance rules in the account brief above (payoff in second 1-2, 6-30s by
    default, meme opener + craft payoff, face-to-camera converts follows).
"""

AUDIT_SYSTEM = f"""
You are auditing one creator's Instagram account for his weekly planning email.
{ACCOUNT_CONTEXT}
{PLAN_TARGETS}
You get a JSON object:
  "scorecard"   the audit's measured rows, each with a status already assigned by fixed rules
  "stats"       the numbers behind those rows
  "recent_posts" his posts from the last four weeks (caption, label, views, length, tags)
  "last_week"   last week's planned slate and goals, and "posted_since" what he posted after it
  "already_planned" this week's partnership-plan milestones and posts (do not repeat these as goals)

Rules:
  - Use ONLY numbers that appear in the input. Never estimate saves, shares, follows per post or
    anything else that is not given. If something isn't measured, leave it out.
  - Keep each scorecard row's status unless the stats clearly contradict it.
  - Follow-through: compare "posted_since" with last week's slate. Say plainly which planned
    posts appear to have gone out and which did not. If you can't tell from captions, say so.
  - Goals must be things he can finish this week inside his capacity, each tied to a finding,
    each checkable (a count, a named post, a deadline). No more than {MAX_AUDIT_GOALS}. Return fewer
    when little needs fixing; an all-good week can return none.
  - Plain, direct language to a busy student. No praise padding.

Return ONLY a JSON object:
{{
  "headline": "one sentence: the single most important thing the audit found",
  "findings": [
    {{"area": "Cadence | Reach | Length | Engagement | Content mix | Brand proof | Growth | Follow-through",
      "status": "good | watch | fix",
      "evidence": "the numbers, in one sentence",
      "action": "what to do this week, or '' when status is good"}}
  ],
  "goals": ["goal 1", "goal 2"],
  "guidance": "two or three sentences for the planner and scorers: what to favour and avoid this week"
}}
"""


def _label_posts(posts: list[dict]) -> int:
    """Label unlabelled recent posts and cache the label in own_posts.json. Returns how many were labelled."""
    todo = [p for p in posts if p["age_days"] <= WINDOW_DAYS and p.get("kind") not in KINDS]
    if not todo:
        return 0
    payload = [{"index": i, "caption": p.get("caption", ""), "tags": p.get("mentions") or [],
                "type": p.get("type", ""), "length_s": p.get("duration_s", 0)} for i, p in enumerate(todo)]
    try:
        labels = _parse_json_array(_ask(LABEL_SYSTEM, payload, max_tokens=2000))
    except Exception as e:
        print(f"    [audit] Post labelling failed: {e}")
        return 0
    history = _load(POSTS_PATH)
    done = 0
    for item in labels:
        try:
            post, kind = todo[int(item.get("index"))], str(item.get("kind", "")).strip().lower()
        except (TypeError, ValueError, IndexError, AttributeError):
            continue
        if kind in KINDS and post.get("url") in history:
            history[post["url"]]["kind"] = kind
            post["kind"] = kind
            done += 1
    if done:
        POSTS_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return done


def _fallback(scorecard: list[dict]) -> dict:
    needs = sorted((r for r in scorecard if r["status"] in ("fix", "watch")),
                   key=lambda r: STATUS_ORDER[r["status"]])
    fixes = [r for r in needs if r["status"] == "fix"]
    if fixes:
        headline = f"{len(fixes)} area{'s' if len(fixes) != 1 else ''} need fixing this week: " \
                   + ", ".join(r["area"].lower() for r in fixes) + "."
    elif needs:
        headline = "Nothing is broken; " + ", ".join(r["area"].lower() for r in needs) + " to watch."
    else:
        headline = "Everything measured is on target this week."
    return {
        "headline": headline,
        "findings": [{"area": r["area"], "status": r["status"], "evidence": r["value"], "action": r["action"]}
                     for r in scorecard if r["status"] != "info"],
        "goals": [r["action"] for r in needs if r["action"]][:MAX_AUDIT_GOALS],
        "guidance": " ".join(r["action"] + "." for r in needs if r["action"])[:600],
    }


def _clean(result: dict, scorecard: list[dict]) -> dict:
    findings = []
    for f in result.get("findings") or []:
        status = str(f.get("status", "")).strip().lower()
        if status not in ("good", "watch", "fix") or not f.get("area"):
            continue
        findings.append({"area": str(f["area"]).strip(), "status": status,
                         "evidence": str(f.get("evidence", "")).strip(),
                         "action": "" if status == "good" else str(f.get("action", "")).strip()})
    if not findings:
        raise ValueError("no usable findings")
    findings.sort(key=lambda f: STATUS_ORDER[f["status"]])
    goals = [str(g).strip() for g in (result.get("goals") or []) if str(g).strip()][:MAX_AUDIT_GOALS]
    return {
        "headline": str(result.get("headline", "")).strip() or _fallback(scorecard)["headline"],
        "findings": findings,
        "goals": goals,
        "guidance": str(result.get("guidance", "")).strip(),
    }


# ─────────────────────────────────────────────────────────────────
# Entry points
# ─────────────────────────────────────────────────────────────────

def build_audit(performance: dict | None, profile: dict | None = None, today: date | None = None) -> dict | None:
    """
    Run after build_performance() (which refreshes own_posts.json).
    Returns {"headline", "scorecard", "findings", "goals", "guidance", "stats", "window_days"}
    or None when there is no post history to audit.
    """
    today = today or date.today()
    now = datetime.now(timezone.utc)
    posts = _posts(now)
    if not posts:
        print("    [audit] No tracked posts yet — skipping the audit")
        return None

    labelled = _label_posts(posts)
    median = float((performance or {}).get("median") or 0) or _median(
        p["views"] for p in posts if p.get("views") and p["age_days"] >= 7)

    cadence, cadence_row = _cadence(posts)
    reach, reach_row = _reach(posts, median)
    length, length_row = _length(posts)
    engagement, engagement_row = _engagement(posts)
    mix, mix_rows = _mix(posts)
    growth, growth_row = _growth(profile, today)
    scorecard = [cadence_row, reach_row, length_row, engagement_row, *mix_rows, growth_row]
    stats = {"cadence": cadence, "reach": reach, "length": length, "engagement": engagement,
             "content_mix": mix, "growth": growth}

    last = _last_digest(today)
    since = last.get("date", "")
    week = plan_week(today)
    entry = PLAN_WEEKS[min(max(week, 1), len(PLAN_WEEKS)) - 1] if week <= len(PLAN_WEEKS) else {}
    payload = {
        "scorecard": scorecard,
        "stats": stats,
        "recent_posts": [
            {"posted": p["posted"].date().isoformat(), "caption": p.get("caption", ""), "label": p.get("kind", ""),
             "views": p.get("views", 0), "likes": p.get("likes", 0), "comments": p.get("comments", 0),
             "length_s": p.get("duration_s", 0), "tags": p.get("mentions") or [],
             "x_median": round(p["views"] / median, 1) if median and p.get("views") else None,
             "still_collecting_views": p["age_days"] < SETTLE_DAYS}
            for p in posts if p["age_days"] <= WINDOW_DAYS
        ],
        "last_week": {
            "digest_date": since or None,
            "slate": last.get("slate", []),
            "goals": last.get("goals", []),
            "posted_since": [{"posted": p["posted"].date().isoformat(), "caption": p.get("caption", ""),
                              "label": p.get("kind", "")}
                             for p in posts if since and p["posted"].date().isoformat() >= since],
        },
        "already_planned": {"milestones": entry.get("milestones", []),
                            "reach_post": entry.get("reach", ""), "product_post": entry.get("product", "")},
    }

    result, source = None, "claude"
    for attempt in (1, 2):
        try:
            result = _clean(_parse_json_object(_ask(AUDIT_SYSTEM, payload, max_tokens=6000)), scorecard)
            break
        except Exception as e:
            print(f"    [audit] Findings attempt {attempt} failed: {e}")
    if result is None:
        result, source = _fallback(scorecard), "scorecard rules"

    audit = dict(result, scorecard=scorecard, stats=stats, window_days=WINDOW_DAYS,
                 posts_audited=len(payload["recent_posts"]), account=IG_ACCOUNT, source=source)
    marks = ", ".join(f"{r['area']}={r['status']}" for r in scorecard)
    print(f"    [audit] {audit['posts_audited']} posts over {WINDOW_DAYS} days · {labelled} newly labelled · "
          f"{marks} · {len(audit['goals'])} goal(s) · findings from {source}")
    return audit


def audit_guidance(audit: dict | None) -> str:
    """The audit boiled down for other prompts (sound scoring, topic scoring)."""
    if not audit:
        return ""
    lines = [f"THIS WEEK'S ACCOUNT AUDIT (measured on his own last {audit.get('window_days', WINDOW_DAYS)} days "
             f"of posts — let it shape what you recommend):", audit.get("headline", "")]
    for f in audit.get("findings", []):
        if f["status"] in ("fix", "watch") and f.get("action"):
            lines.append(f"- {f['area']} ({f['status']}): {f['evidence']} → {f['action']}")
    if audit.get("guidance"):
        lines.append(audit["guidance"])
    return "\n".join(line for line in lines if line)


def audit_brief(audit: dict | None) -> dict | None:
    """The slice of the audit the slate planner needs."""
    if not audit:
        return None
    return {
        "headline": audit.get("headline", ""),
        "needs_attention": [f for f in audit.get("findings", []) if f["status"] in ("fix", "watch")],
        "goals": audit.get("goals", []),
        "guidance": audit.get("guidance", ""),
    }

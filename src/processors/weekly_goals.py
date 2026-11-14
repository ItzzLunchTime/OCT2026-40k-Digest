"""
Weekly goals — the checklist at the top of the Monday digest.

Combines four sources into one list of things to hit this week:
  - posting goals from this week's slate and comment picks
  - the goals set by this week's account audit (src/processors/account_audit.py),
    which also marks the plan's product-facing post as a priority when the audit
    finds the content mix or brand proof short
  - the dated milestones and content calendar from the 90-Day Brand Partnership
    Plan (vault note "04 Brand Partnership Plan")
  - the standing habits from that plan that apply to every post

No Claude call: the plan is a fixed 13-week schedule, so the goals are looked up
by date. Edit PLAN_WEEKS below when the plan changes.
"""

from datetime import date, timedelta

from src.config import CHALLENGE_DAYS

PLAN_NAME = "90-Day Brand Partnership Plan"
PLAN_START = date(2026, 11, 16)   # Monday of plan week 1

# One entry per plan week: milestones from the roadmap, then that week's reach post
# and product-facing post from the 12-week content calendar (week 13 is review only).
PLAN_WEEKS = [
    {"milestones": ["Reply to Stedi with the three-option message (product / affiliate / paid UGC)",
                    "Add a business email to the Instagram bio",
                    "Get the link hub live",
                    "Pull 90-day Insights (reach, average non-meme Reel views, audience age and countries)"],
     "reach": "Meme from the bank",
     "product": '"What\'s actually on my hobby desk" voiceover tour, every brand tagged',
     "purpose": "proof"},
    {"milestones": ["Apply to four affiliate programs (Green Stuff World, Miniature Market, Golden Maple, Elegoo)",
                    "Post the first tool-test Reel",
                    "Open the TikTok account"],
     "reach": "Meme from the bank",
     "product": "Clippers test: clean cut vs my old pair, macro, original audio",
     "purpose": "proof and pitch"},
    {"milestones": ["Finish media kit v1 (one page)",
                    "Film the first Brookhurst Hobbies collab"],
     "reach": "Hybrid meme filmed at the hobby desk",
     "product": "Brookhurst crawl: three things a beginner should buy",
     "purpose": "proof"},
    {"milestones": ["Run the first batch-filming day: two proof posts and one spec ad banked"],
     "reach": "Meme from the bank",
     "product": "LED cook-off explosion build, part 1",
     "purpose": "proof"},
    {"milestones": ["Finish spec ads 1 and 2",
                    "Start the portfolio page"],
     "reach": "Meme from the bank",
     "product": "Spec ad: wet palette 24-hour test",
     "purpose": "pitch asset"},
    {"milestones": ["Publish the gift-guide post with affiliate links",
                    "Ask Kingslayer Games and Lost Planet Games about filming"],
     "reach": "Holiday meme",
     "product": "Carousel: beginner gifts under $30, with links",
     "purpose": "proof (clicks)"},
    {"milestones": ["Send pitch wave 1: five small brands, product or affiliate ask"],
     "reach": "Meme from the bank",
     "product": "Packing 2,000 points for travel",
     "purpose": "proof"},
    {"milestones": ["Run the second batch-filming day",
                    "Write the rate card"],
     "reach": "Meme from the bank",
     "product": "Spec ad: Guard squad with one paint range, beginner voiceover",
     "purpose": "pitch asset"},
    {"milestones": ["Make the tournament prep content",
                    "Follow up on pitch wave 1"],
     "reach": "Tournament-nerves meme",
     "product": "Behind the shot: how I light and film a mini",
     "purpose": "proof"},
    {"milestones": ['Post the tournament recap and the "what I\'d buy again" post'],
     "reach": "Event recap Reel",
     "product": '"Buy again / skip" after my first big tournament',
     "purpose": "proof"},
    {"milestones": ["Finish spec ads 3 to 6",
                    "Make the portfolio page public"],
     "reach": "Meme from the bank",
     "product": "Spec ad: bare base to finished in three textures",
     "purpose": "pitch asset"},
    {"milestones": ["Send pitch wave 2: eight brands, paid UGC ask with the portfolio link"],
     "reach": "Meme from the bank",
     "product": '"90 days of testing hobby gear: top five"',
     "purpose": "pitch asset"},
    {"milestones": ["Review the 90 days: views on proof posts, link clicks, brand replies, deals",
                    "Update the media kit with the new numbers"],
     "reach": "",
     "product": "",
     "purpose": ""},
]

# Habits from the plan that apply to every post, every week
STANDING = [
    "Tag every brand whose product appears on screen",
    "Original audio or voiceover on anything you might send to a brand",
    "Disclose gifted product and affiliate links in the video or the first caption line",
    "Update the outreach tracker and send any follow-ups that are due",
]


def plan_week(today: date | None = None) -> int:
    """1-based week of the partnership plan; 0 before it starts, 14+ once it is over."""
    today = today or date.today()
    days = (today - PLAN_START).days
    return 0 if days < 0 else days // 7 + 1


def build_weekly_goals(plan: dict | None = None, today: date | None = None) -> dict:
    """
    plan: the digest's plan dict (slate, comment_picks, audit) so posting goals can name
    this week's slots and the audit's goals are included. Returns {"week_of", "sub", "groups": [{"title", "items"}]}.
    """
    plan = plan or {}
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    week = plan_week(today)
    entry = PLAN_WEEKS[min(max(week, 1), len(PLAN_WEEKS)) - 1] if week <= len(PLAN_WEEKS) else None

    # ── Posting goals ────────────────────────────────────────────
    posting = []
    slots = (plan.get("slate") or {}).get("slots") or []
    required = [s for s in slots if s.get("slot") in ("A", "B")]
    if required:
        for s in required:
            name = s.get("title") or s.get("engine") or ""
            posting.append(f"Post Slot {s.get('slot')}: {name}".rstrip(": "))
        if any(s.get("slot") == "C" for s in slots):
            posting.append("Slot C if it's a good week (optional)")
    else:
        posting.append("Post at least twice: one reach post and one product-facing post")
    if entry and entry["reach"]:
        posting.append(f"Reach post this week: {entry['reach']}")
    audit = plan.get("audit") or {}
    short_on_proof = any(f.get("status") == "fix" and f.get("area", "").lower().startswith(("content mix", "brand proof"))
                         for f in audit.get("findings", []))
    if entry and entry["product"]:
        lead = "Priority, per the audit — product-facing post" if short_on_proof else "Product-facing post this week"
        posting.append(f"{lead} ({entry['purpose']}): {entry['product']}")
    picks = plan.get("comment_picks") or []
    if picks:
        posting.append("Make a reply video for the comment pick" if len(picks) == 1
                       else f"Make a reply video for at least one of the {len(picks)} comment picks")

    groups = [{"title": "Posting", "items": posting}]

    # ── Goals from this week's audit ─────────────────────────────
    audit_goals = [g for g in (audit.get("goals") or []) if g]
    if audit_goals:
        groups.append({"title": "From this week's audit", "items": audit_goals})

    # ── Partnership plan milestones ──────────────────────────────
    if entry:
        label = f"Brand partnership plan · week {max(week, 1)} of {len(PLAN_WEEKS)}"
        if week == 0:
            label += f" (starts {PLAN_START.strftime('%b %d').replace(' 0', ' ')})"
        groups.append({"title": label, "items": list(entry["milestones"])})
    else:
        groups.append({"title": "Brand partnership plan · complete",
                       "items": ["Plan the next 90 days from the week-13 review",
                                 "Follow up on any brand conversation still open"]})

    # Last week's milestones can't be checked from public data, so they are carried forward
    if 2 <= week <= len(PLAN_WEEKS) + 1:
        groups.append({"title": f"Carry over if not done · plan week {week - 1}",
                       "items": list(PLAN_WEEKS[week - 2]["milestones"])})

    groups.append({"title": "Every post", "items": list(STANDING)})

    # ── Sub-line: countdown context ──────────────────────────────
    ch = (plan.get("slate") or {}).get("challenge") or {}
    sub = []
    if ch.get("phase") in ("countdown", "final push"):
        sub.append(f"Day {ch.get('day')} of {CHALLENGE_DAYS} · {ch.get('days_left')} days to Palm Springs")
    sub.append(f"Milestones and post ideas from the {PLAN_NAME}"
               + (" · adjusted by this week's audit" if audit_goals or short_on_proof else ""))

    total = sum(len(g["items"]) for g in groups)
    print(f"    [goals] {total} goals · plan week {week}")
    return {
        "week_of": monday.isoformat(),
        "plan_week": week,
        "plan_weeks": len(PLAN_WEEKS),
        "sub": " · ".join(sub),
        "groups": groups,
    }

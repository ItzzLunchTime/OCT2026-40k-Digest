"""
Your verdicts on recommendations — collected by email, remembered forever.

Each recommended sound in the email/dashboard has three links:
    👍 More like this   👎 Not for me   ✅ Used it
Each opens a pre-filled email (subject "40K vote: up <sound_id>") addressed
to the digest's Gmail inbox. You just hit send.

At the start of every run we read those emails over IMAP (same Gmail app
password the digest already uses), store the latest vote per sound in
docs/data/feedback.json, and then:
  - never recommend a sound you marked 👎 or ✅ again
  - give the scorer your 👍/✅ and 👎 picks as calibration examples
"""

import email
import email.header
import imaplib
import json
import re
from datetime import date, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

from src.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, DIGEST_RECIPIENT

FEEDBACK_PATH = Path("docs/data/feedback.json")
DATA_DIR = Path("docs/data")
SUBJECT_TAG = "40K vote"
VOTE_RE = re.compile(r"40K vote:\s*(up|down|used)\s+([0-9a-f]{10})", re.I)
LOOKBACK_DAYS = 45

VOTE_LABELS = {"up": "👍 More like this", "down": "👎 Not for me", "used": "✅ Used it"}


# ─────────────────────────────────────────────────────────────────
# Links (used by the email + dashboard)
# ─────────────────────────────────────────────────────────────────

def vote_link(vote: str, item: dict) -> str:
    sid = item.get("sound_id", "")
    name = item.get("name", "")
    artist = item.get("artist", "")
    subject = f"{SUBJECT_TAG}: {vote} {sid} — {name}"[:150]
    body = (f"{VOTE_LABELS[vote]}\n{name}" + (f" — {artist}" if artist else "")
            + "\n\nJust hit send. (The digest reads this next Monday.)")
    return f"mailto:{GMAIL_ADDRESS}?subject={quote(subject)}&body={quote(body)}"


# ─────────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────────

def load_feedback() -> dict:
    try:
        return json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"votes": {}, "processed": []}


def _save(fb: dict) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fb["processed"] = fb["processed"][-500:]
    FEEDBACK_PATH.write_text(json.dumps(fb, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_sound(sound_id: str) -> dict:
    """Look up the sound's details in saved digests (newest first)."""
    for p in sorted(DATA_DIR.glob("digest_*.json"), reverse=True):
        try:
            for a in json.loads(p.read_text(encoding="utf-8")).get("audio", []):
                if a.get("sound_id") == sound_id:
                    return a
        except Exception:
            continue
    return {}


# ─────────────────────────────────────────────────────────────────
# Collect votes from Gmail
# ─────────────────────────────────────────────────────────────────

def _fetch_vote_emails() -> list[tuple[str, str, str, str]]:
    """Returns (message_id, iso_date, vote, sound_id) for every vote email found."""
    allowed = {a.lower() for a in (GMAIL_ADDRESS, DIGEST_RECIPIENT) if a}
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    found = []
    with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
        imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        status, _ = imap.select('"[Gmail]/All Mail"', readonly=True)
        if status != "OK":
            imap.select("INBOX", readonly=True)
        status, data = imap.search(None, "SINCE", since, "SUBJECT", f'"{SUBJECT_TAG}"')
        if status != "OK" or not data or not data[0]:
            return []
        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
            sender = parseaddr(msg.get("From", ""))[1].lower()
            m = VOTE_RE.search(subject)
            if not m or sender not in allowed:
                continue
            try:
                when = parsedate_to_datetime(msg.get("Date")).isoformat()
            except Exception:
                when = date.today().isoformat()
            found.append((msg.get("Message-ID", f"{num}-{subject}"), when, m.group(1).lower(), m.group(2).lower()))
    return found


def collect_feedback() -> dict:
    fb = load_feedback()
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return fb
    try:
        emails = _fetch_vote_emails()
    except Exception as e:
        print(f"    [feedback] Couldn't read vote emails: {e}")
        return fb

    processed = set(fb["processed"])
    new = 0
    for msg_id, when, vote, sid in sorted(emails, key=lambda e: e[1]):
        if msg_id in processed:
            continue
        processed.add(msg_id)
        fb["processed"].append(msg_id)
        cur = fb["votes"].get(sid)
        if cur and cur.get("date", "") > when:
            continue
        info = _find_sound(sid) or cur or {}
        fb["votes"][sid] = {
            "vote": vote,
            "date": when,
            "name": info.get("name", ""),
            "artist": info.get("artist", ""),
            "format_type": info.get("format_type", ""),
            "register_note": info.get("register_note", ""),
            "score_given": info.get("potency_score"),
            "ig_link": info.get("ig_link", ""),
            "tiktok_link": info.get("tiktok_link", ""),
        }
        new += 1

    _save(fb)
    counts = {v: sum(1 for x in fb["votes"].values() if x["vote"] == v) for v in VOTE_LABELS}
    print(f"    [feedback] {new} new vote(s) · totals 👍{counts['up']} 👎{counts['down']} ✅{counts['used']}")
    return fb


# ─────────────────────────────────────────────────────────────────
# Apply
# ─────────────────────────────────────────────────────────────────

def excluded_keys(fb: dict) -> set[str]:
    """Sound IDs and platform links never to recommend again (👎 or already used)."""
    out = set()
    for sid, v in fb.get("votes", {}).items():
        if v["vote"] in ("down", "used"):
            out.add(sid)
            for link in (v.get("ig_link"), v.get("tiktok_link")):
                if link:
                    out.add(link.rstrip("/"))
    return out


def is_excluded(item: dict, keys: set[str]) -> bool:
    if item.get("sound_id") in keys:
        return True
    return any((item.get(f) or "").rstrip("/") in keys for f in ("ig_link", "tiktok_link") if item.get(f))


def verdicts_prompt(fb: dict, limit: int = 25) -> str:
    """Calibration examples for the scorer from your past votes."""
    votes = sorted(fb.get("votes", {}).values(), key=lambda v: v.get("date", ""), reverse=True)
    liked = [v for v in votes if v["vote"] in ("up", "used")][:limit]
    disliked = [v for v in votes if v["vote"] == "down"][:limit]
    if not liked and not disliked:
        return ""

    def line(v):
        bits = [f'"{v["name"]}"' + (f' — {v["artist"]}' if v.get("artist") else "")]
        if v.get("format_type"):
            bits.append(v["format_type"])
        if v.get("register_note"):
            bits.append(v["register_note"][:80])
        if v.get("score_given") is not None:
            bits.append(f"you scored it {v['score_given']}/10")
        return "  - " + " · ".join(bits)

    parts = ["CREATOR'S PAST VERDICTS ON YOUR RECOMMENDATIONS (calibrate scores to these):"]
    if liked:
        parts.append("Liked or actually used:\n" + "\n".join(line(v) for v in liked))
    if disliked:
        parts.append("Rejected ('not for me'):\n" + "\n".join(line(v) for v in disliked))
    parts.append("Score sounds similar to the liked ones higher and similar to the rejected ones lower. "
                 "Where your earlier score disagreed with the verdict, correct in that direction.")
    return "\n".join(parts)

"""
Formats and sends the daily digest email and individual alert emails
via Gmail SMTP using an App Password.

Two email types:
  - digest: full daily report (audio + topics)
  - alert: fired immediately when a potency score >= ALERT_THRESHOLD
"""

import smtplib
import html as html_module
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from src.config import (
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    DIGEST_RECIPIENT,
    ALERT_THRESHOLD,
    FORMAT_TYPES,
)

# Max audio cards shown per format section in the digest
PER_FORMAT_LIMIT = 4

TODAY = date.today().strftime("%B %-d, %Y")   # e.g. "September 30, 2026"
TODAY_SHORT = date.today().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────────
# SHARED EMAIL UTILITIES
# ─────────────────────────────────────────────────────────────────

def _send(subject: str, html_body: str, recipient: str = DIGEST_RECIPIENT) -> bool:
    """Send a single HTML email via Gmail SMTP. Returns True on success."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("    [email] Gmail credentials not configured — skipping send")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())
        print(f"    [email] Sent: {subject}")
        return True
    except Exception as e:
        print(f"    [email] Send error: {e}")
        return False


def _e(text) -> str:
    """HTML-escape a value safely."""
    return html_module.escape(str(text or ""))


def _score_badge(score: int) -> str:
    """Return a coloured badge span for a potency score."""
    if score >= 9:
        colour = "#c0392b"   # red — high potency
    elif score >= 7:
        colour = "#e67e22"   # orange
    elif score >= 5:
        colour = "#27ae60"   # green
    else:
        colour = "#7f8c8d"   # grey
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
        f'background:{colour};color:#fff;font-size:12px;font-weight:700;">'
        f'{score}/10</span>'
    )


# ─────────────────────────────────────────────────────────────────
# ALERT EMAIL
# ─────────────────────────────────────────────────────────────────

ALERT_CSS = """
  body { font-family: 'Helvetica Neue', Arial, sans-serif; background:#0d0d0d; color:#e8e8e8; margin:0; padding:0; }
  .wrap { max-width:600px; margin:0 auto; padding:24px 16px; }
  .header { border-left:4px solid #c0392b; padding:8px 16px; margin-bottom:24px; }
  .header h1 { margin:0; font-size:20px; color:#c0392b; letter-spacing:1px; }
  .header p { margin:4px 0 0; font-size:13px; color:#aaa; }
  .card { background:#1a1a1a; border:1px solid #333; border-radius:6px; padding:20px; margin-bottom:16px; }
  .card h2 { margin:0 0 4px; font-size:18px; color:#fff; }
  .card .meta { font-size:12px; color:#888; margin-bottom:12px; }
  .card .field { margin:8px 0; font-size:14px; line-height:1.5; }
  .card .label { color:#aaa; font-size:11px; text-transform:uppercase; letter-spacing:.5px; }
  .card .value { color:#e8e8e8; }
  .card .angle { background:#111; border-left:3px solid #c0392b; padding:10px 14px; margin-top:12px; font-style:italic; font-size:14px; color:#ccc; }
  a { color:#e67e22; text-decoration:none; }
  a:hover { text-decoration:underline; }
"""

def send_alert(audio: dict) -> bool:
    """
    Fire an immediate alert email for a high-potency audio item.
    Called as soon as scoring detects score >= ALERT_THRESHOLD.
    """
    score = audio.get("potency_score", 0)
    name = _e(audio.get("name", "Unknown"))
    artist = _e(audio.get("artist", ""))
    audio_type = _e(audio.get("audio_type", ""))
    trend_stage = _e(audio.get("trend_stage", ""))
    use_count = _e(audio.get("use_count", ""))
    categories = ", ".join(_e(c) for c in audio.get("categories", []))
    sync_note = _e(audio.get("sync_note", ""))
    register_note = _e(audio.get("register_note", ""))
    cp = audio.get("counterpoint_potential", False)
    cp_note = _e(audio.get("counterpoint_note", "")) if cp else ""
    angle = _e(audio.get("cinematic_angle", ""))
    ig_link = audio.get("ig_link", "")
    tiktok_link = audio.get("tiktok_link", "")
    source_url = audio.get("source_url", "")

    link_html = ""
    if ig_link:
        link_html += f'<a href="{_e(ig_link)}">Instagram</a>  '
    if tiktok_link:
        link_html += f'<a href="{_e(tiktok_link)}">TikTok</a>  '
    if source_url:
        link_html += f'<a href="{_e(source_url)}">Source</a>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{ALERT_CSS}</style></head>
<body><div class="wrap">
  <div class="header">
    <h1>⚡ HIGH-POTENCY AUDIO ALERT</h1>
    <p>{TODAY} · Score: {_score_badge(score)}</p>
  </div>
  <div class="card">
    <h2>{name}</h2>
    <div class="meta">{artist} · {audio_type} · {trend_stage}{' · ' + use_count if use_count else ''}</div>

    <div class="field"><span class="label">Categories</span><br>
      <span class="value">{categories or '—'}</span></div>

    <div class="field"><span class="label">Sync potential</span><br>
      <span class="value">{sync_note or '—'}</span></div>

    <div class="field"><span class="label">Emotional register</span><br>
      <span class="value">{register_note or '—'}</span></div>

    {'<div class="field"><span class="label">Counterpoint potential</span><br><span class="value">' + cp_note + '</span></div>' if cp_note else ''}

    {'<div class="angle">' + angle + '</div>' if angle else ''}

    {'<div class="field" style="margin-top:16px;">' + link_html + '</div>' if link_html.strip() else ''}
  </div>
  <p style="font-size:11px;color:#555;text-align:center;">40K Content Digest · Automated alert · potency ≥ {ALERT_THRESHOLD}</p>
</div></body></html>"""

    subject = f"⚡ Audio Alert [{score}/10]: {audio.get('name', 'Unknown')} — {TODAY_SHORT}"
    return _send(subject, html)


# ─────────────────────────────────────────────────────────────────
# DIGEST EMAIL
# ─────────────────────────────────────────────────────────────────

DIGEST_CSS = """
  body { font-family: 'Helvetica Neue', Arial, sans-serif; background:#0d0d0d; color:#e8e8e8; margin:0; padding:0; }
  .wrap { max-width:680px; margin:0 auto; padding:24px 16px; }
  h1 { font-size:22px; color:#fff; margin:0 0 4px; }
  .subtitle { font-size:13px; color:#888; margin-bottom:32px; }
  h2 { font-size:16px; color:#c0392b; text-transform:uppercase; letter-spacing:1px; border-bottom:1px solid #333; padding-bottom:6px; margin:32px 0 16px; }
  h3 { font-size:17px; color:#fff; margin:0 0 4px; }
  .card { background:#1a1a1a; border:1px solid #2a2a2a; border-radius:6px; padding:16px 20px; margin-bottom:12px; }
  .meta { font-size:12px; color:#777; margin-bottom:10px; }
  .field { margin:6px 0; font-size:13px; line-height:1.55; }
  .label { color:#888; font-size:11px; text-transform:uppercase; letter-spacing:.5px; display:block; margin-bottom:2px; }
  .angle { background:#111; border-left:3px solid #c0392b; padding:10px 14px; margin-top:12px; font-style:italic; font-size:13px; color:#bbb; }
  .badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700; margin-right:4px; }
  .gap-badge { background:#1a4a2e; color:#2ecc71; }
  .q-badge { background:#1a2a4a; color:#5dade2; }
  .topic-card { background:#1a1a1a; border:1px solid #2a2a2a; border-radius:6px; padding:14px 18px; margin-bottom:10px; }
  .topic-title { font-size:15px; color:#fff; font-weight:600; margin:0 0 4px; }
  .topic-meta { font-size:12px; color:#777; margin-bottom:8px; }
  .topic-field { font-size:13px; color:#ccc; line-height:1.5; margin:4px 0; }
  a { color:#e67e22; text-decoration:none; }
  a:hover { text-decoration:underline; }
  .footer { font-size:11px; color:#444; text-align:center; margin-top:40px; padding-top:16px; border-top:1px solid #222; }
  .summary-bar { background:#111; border:1px solid #222; border-radius:6px; padding:12px 16px; margin-bottom:28px; font-size:13px; color:#aaa; }
  .summary-bar strong { color:#fff; }
"""


def _audio_card(audio: dict, rank: int) -> str:
    score = audio.get("potency_score", 0)
    name = _e(audio.get("name", "Unknown"))
    artist = _e(audio.get("artist", ""))
    audio_type = _e(audio.get("audio_type", ""))
    trend_stage = _e(audio.get("trend_stage", ""))
    use_count = _e(audio.get("use_count", ""))
    categories = ", ".join(_e(c) for c in audio.get("categories", []))
    sync_note = _e(audio.get("sync_note", ""))
    register_note = _e(audio.get("register_note", ""))
    cp = audio.get("counterpoint_potential", False)
    cp_note = _e(audio.get("counterpoint_note", "")) if cp else ""
    angle = _e(audio.get("cinematic_angle", ""))
    ig_link = audio.get("ig_link", "")
    tiktok_link = audio.get("tiktok_link", "")
    source_url = audio.get("source_url", "")
    trend_note = _e(audio.get("trend_note", ""))
    mentions = audio.get("mention_count", 1) or 1
    relevance = audio.get("niche_relevance")

    links = []
    if ig_link:
        links.append(f'<a href="{_e(ig_link)}">Instagram ↗</a>')
    if tiktok_link:
        links.append(f'<a href="{_e(tiktok_link)}">TikTok ↗</a>')
    if source_url:
        links.append(f'<a href="{_e(source_url)}">Source ↗</a>')
    link_html = "  ".join(links)

    meta_parts = [p for p in [artist, audio_type, trend_stage, use_count] if p]
    if mentions > 1:
        meta_parts.append(f"on {mentions} trend sites")
    if isinstance(relevance, (int, float)):
        meta_parts.append(f"niche fit {round(relevance * 100)}%")
    meta = " · ".join(meta_parts)

    return f"""<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">
    <h3>#{rank} {name}</h3>
    {_score_badge(score)}
  </div>
  <div class="meta">{meta}</div>
  {'<div class="field"><span class="label">Trend</span>' + trend_note + '</div>' if trend_note else ''}
  {'<div class="field"><span class="label">Categories</span>' + categories + '</div>' if categories else ''}
  <div class="field"><span class="label">Sync potential</span>{sync_note or '—'}</div>
  <div class="field"><span class="label">Emotional register</span>{register_note or '—'}</div>
  {'<div class="field"><span class="label">Counterpoint</span>' + cp_note + '</div>' if cp_note else ''}
  {'<div class="angle">' + angle + '</div>' if angle else ''}
  {'<div class="field" style="margin-top:12px;font-size:12px;">' + link_html + '</div>' if link_html else ''}
</div>"""


def _topic_card(topic: dict) -> str:
    title = _e(topic.get("title", "Unknown topic"))
    category = _e(topic.get("category", ""))
    what = _e(topic.get("what_is_driving_it", ""))
    relevance = _e(topic.get("relevance_note", ""))
    is_gap = topic.get("is_content_gap", False)
    gap_note = _e(topic.get("gap_note", "")) if is_gap else ""
    is_q = topic.get("is_question", False)
    source = _e(topic.get("source", ""))
    url = topic.get("url", "")

    badges = ""
    if is_gap:
        badges += '<span class="badge gap-badge">Content Gap</span>'
    if is_q:
        badges += '<span class="badge q-badge">Question</span>'

    driving_html = f'<div class="topic-field"><em>What\'s driving it:</em> {what}</div>' if what else ""
    relevance_html = f'<div class="topic-field"><em>Why cover now:</em> {relevance}</div>' if relevance else ""
    gap_html = f'<div class="topic-field" style="color:#2ecc71;"><em>Gap opportunity:</em> {gap_note}</div>' if gap_note else ""
    url_html = f'<div class="topic-field" style="margin-top:8px;font-size:12px;"><a href="{_e(url)}">View source &#8599;</a></div>' if url else ""

    return (
        '<div class="topic-card">'
        f'<div class="topic-title">{title}</div>'
        f'<div class="topic-meta">{category}'
        + (" · " + source if source else "")
        + ("  " + badges if badges else "")
        + "</div>"
        + driving_html
        + relevance_html
        + gap_html
        + url_html
        + "</div>"
    )


def send_digest(scored_audio: list[dict], scored_topics: list[dict]) -> bool:
    """
    Build and send the full daily digest email.
    scored_audio: sorted by potency_score descending (from claude_scorer)
    scored_topics: list of topic dicts (from claude_scorer)
    """
    audio_count = len(scored_audio)
    topic_count = len(scored_topics)
    alert_count = sum(1 for a in scored_audio if a.get("potency_score", 0) >= ALERT_THRESHOLD)

    # Summary bar
    summary_html = f"""<div class="summary-bar">
  <strong>{audio_count}</strong> audio items scored &nbsp;·&nbsp;
  <strong>{topic_count}</strong> topics identified &nbsp;·&nbsp;
  <strong style="color:#c0392b;">{alert_count}</strong> high-potency alerts (≥{ALERT_THRESHOLD})
</div>"""

    # Audio section — grouped by content format, best few per format
    sections = []
    for fmt in FORMAT_TYPES:
        group = [a for a in scored_audio if a.get("format_type") == fmt]
        if not group:
            continue
        cards = "".join(_audio_card(a, i + 1) for i, a in enumerate(group[:PER_FORMAT_LIMIT]))
        more = (f'<p style="font-size:12px;color:#666;">+{len(group) - PER_FORMAT_LIMIT} more '
                f'on the dashboard</p>' if len(group) > PER_FORMAT_LIMIT else "")
        sections.append(
            f'<h3 style="color:#e67e22;font-size:14px;margin:24px 0 10px;">'
            f'{_e(fmt)} <span style="color:#666;font-weight:400;">({len(group)})</span></h3>'
            + cards + more
        )
    # Anything without a format (e.g. older-style data) goes last
    unformatted = [a for a in scored_audio if a.get("format_type") not in FORMAT_TYPES]
    if unformatted:
        sections.append("".join(_audio_card(a, i + 1) for i, a in enumerate(unformatted[:PER_FORMAT_LIMIT])))
    audio_cards = "".join(sections)

    # Topic section
    topic_cards = "".join(_topic_card(t) for t in scored_topics)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{DIGEST_CSS}</style></head>
<body><div class="wrap">
  <h1>🎖 40K Content Intelligence Digest</h1>
  <p class="subtitle">{TODAY} · Daily automated report</p>

  {summary_html}

  <h2>🔊 Trending Audio — by Format</h2>
  {audio_cards if audio_cards else '<p style="color:#666;">No audio items scored today.</p>'}

  <h2>📡 Community Topics — Content Opportunities</h2>
  {topic_cards if topic_cards else '<p style="color:#666;">No topics identified today.</p>'}

  <div class="footer">
    40K Content Intelligence Digest · {TODAY} ·
    Powered by Claude API · <a href="https://itzzlunchtime.github.io/OCT2026-40k-Digest/">View Dashboard</a>
  </div>
</div></body></html>"""

    subject = f"🎖 40K Digest {TODAY_SHORT} — {audio_count} audio, {topic_count} topics"
    return _send(subject, html)

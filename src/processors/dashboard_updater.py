"""
Writes the JSON data file for today's digest and regenerates
the docs/index.html dashboard, which is served via GitHub Pages.

The dashboard is a single self-contained HTML page that loads all
digest JSON files from docs/data/ and presents them as a searchable,
filterable table.
"""

import json
import os
from pathlib import Path
from datetime import date

DOCS_DIR = Path("docs")
DATA_DIR = DOCS_DIR / "data"
INDEX_PATH = DOCS_DIR / "index.html"

TODAY = date.today().isoformat()   # e.g. "2026-09-30"


def save_digest_json(scored_audio: list[dict], scored_topics: list[dict], trend_scout: dict | None = None,
                     plan: dict | None = None) -> Path:
    """Write today's digest as a JSON file to docs/data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "date": TODAY,
        "audio": scored_audio,
        "topics": scored_topics,
    }
    if trend_scout:
        out["trend_scout"] = trend_scout
    if plan:
        out.update(plan)   # slate, comment_picks, digest_drop
    path = DATA_DIR / f"digest_{TODAY}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"    [dashboard] Saved digest JSON → {path}")
    return path


def _collect_digest_dates() -> list[str]:
    """Return list of digest dates available in docs/data/, newest first."""
    if not DATA_DIR.exists():
        return []
    dates = []
    for p in DATA_DIR.glob("digest_*.json"):
        stem = p.stem  # e.g. "digest_2026-09-30"
        d = stem.replace("digest_", "")
        dates.append(d)
    return sorted(dates, reverse=True)


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>40K Content Intelligence Dashboard</title>
<style>
  :root {
    --bg: #0d0d0d;
    --surface: #1a1a1a;
    --border: #2a2a2a;
    --accent: #c0392b;
    --accent2: #e67e22;
    --text: #e8e8e8;
    --muted: #888;
    --green: #2ecc71;
    --blue: #5dade2;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  header { background: #111; border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; color: #fff; letter-spacing: .5px; }
  header .sub { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .controls { padding: 16px 24px; display: flex; flex-wrap: wrap; gap: 10px; border-bottom: 1px solid var(--border); background: #0f0f0f; }
  input[type=text], select { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 4px; font-size: 13px; outline: none; }
  input[type=text]:focus, select:focus { border-color: var(--accent); }
  #search { width: 260px; }
  .tabs { display: flex; gap: 0; padding: 0 24px; border-bottom: 1px solid var(--border); background: #0f0f0f; }
  .tab { padding: 10px 20px; cursor: pointer; font-size: 13px; color: var(--muted); border-bottom: 2px solid transparent; transition: color .15s, border-color .15s; }
  .tab.active { color: #fff; border-bottom-color: var(--accent); }
  .main { padding: 20px 24px; }
  .date-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .8px; margin-bottom: 16px; }

  /* Audio grid */
  .audio-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
  .audio-card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 16px; }
  .audio-card:hover { border-color: #444; }
  .audio-card .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
  .audio-card h3 { font-size: 15px; color: #fff; line-height: 1.3; }
  .score { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .score-hi { background: var(--accent); color: #fff; }
  .score-md { background: #7d3c00; color: #f39c12; }
  .score-ok { background: #0d3320; color: var(--green); }
  .score-lo { background: #1a1a1a; color: var(--muted); border: 1px solid var(--border); }
  .audio-meta { font-size: 11px; color: var(--muted); margin-bottom: 10px; }
  .field { font-size: 12px; line-height: 1.55; margin: 5px 0; }
  .field-label { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .5px; display: block; }
  .angle { background: #111; border-left: 3px solid var(--accent); padding: 8px 12px; margin-top: 10px; font-style: italic; font-size: 12px; color: #bbb; }
  .links { margin-top: 10px; font-size: 11px; display: flex; gap: 10px; flex-wrap: wrap; }
  a { color: var(--accent2); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .cat-tag { display: inline-block; background: #1c1c1c; border: 1px solid #333; border-radius: 10px; padding: 1px 7px; font-size: 10px; color: #aaa; margin: 1px 2px 1px 0; }

  /* Topic list */
  .topic-list { display: flex; flex-direction: column; gap: 10px; max-width: 800px; }
  .topic-card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px 18px; }
  .topic-card .title { font-size: 15px; color: #fff; font-weight: 600; margin-bottom: 4px; }
  .topic-card .meta { font-size: 11px; color: var(--muted); margin-bottom: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .badge { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 10px; font-weight: 700; }
  .badge-gap { background: #0d2e1a; color: var(--green); }
  .badge-q { background: #0d1a2e; color: var(--blue); }
  .topic-field { font-size: 13px; color: #ccc; line-height: 1.5; margin: 4px 0; }
  .gap-note { color: var(--green); margin-top: 6px; font-size: 12px; }

  /* Empty state */
  .empty { color: var(--muted); font-size: 14px; padding: 40px 0; text-align: center; }
  .stats { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 10px 16px; font-size: 13px; }
  .stat .n { font-size: 22px; font-weight: 700; color: #fff; }
  .stat .l { color: var(--muted); font-size: 11px; }
  .engine-tag { display:inline-block; padding:1px 8px; border-radius:10px; font-size:10px; font-weight:700; background:#2a1a0a; color:var(--accent2); border:1px solid #5a3510; }
  .hook { font-size:12px; color:#fff; margin:6px 0; }
  .slot { display:inline-block; width:20px; height:20px; line-height:20px; text-align:center; border-radius:10px; background:var(--accent); color:#fff; font-size:11px; font-weight:700; margin-right:6px; }
  .section-title { font-size:13px; color:var(--accent2); text-transform:uppercase; letter-spacing:1px; margin:0 0 8px; }
  footer { text-align: center; padding: 24px; font-size: 11px; color: #444; border-top: 1px solid var(--border); margin-top: 40px; }
</style>
</head>
<body>
<header>
  <div>
    <h1>🎖 40K Content Intelligence</h1>
    <div class="sub">Weekly trending audio &amp; topic digest</div>
  </div>
</header>

<div class="controls">
  <input type="text" id="search" placeholder="Search audio, topics…" oninput="applyFilters()">
  <select id="dateSelect" onchange="loadDate(this.value)"></select>
  <select id="formatFilter" onchange="applyFilters()">
    <option value="">All formats</option>
    <option value="POV + reaction">POV + reaction</option>
    <option value="Hobby + trending audio">Hobby + trending audio</option>
    <option value="Green screen template">Green screen template</option>
    <option value="Show/movie clip">Show/movie clip</option>
    <option value="Audio/voiceline">Audio/voiceline</option>
  </select>
  <select id="engineFilter" onchange="applyFilters()">
    <option value="">All engines</option>
    <option>Road to Palm Springs</option>
    <option>Hobby FX Lab</option>
    <option>Cinematic Recreations</option>
    <option>Store Crawl</option>
    <option>Comment Replies</option>
    <option>Hobby on the Clock</option>
    <option>Memes</option>
    <option>Lore Through a Lens</option>
    <option>Digest Drop</option>
  </select>
  <select id="typeFilter" onchange="applyFilters()">
    <option value="">All audio types</option>
    <option value="music">Music</option>
    <option value="dialogue">Dialogue</option>
    <option value="soundbite">Soundbite</option>
    <option value="template">Template</option>
    <option value="meme">Meme</option>
  </select>
  <select id="stageFilter" onchange="applyFilters()">
    <option value="">All trend stages</option>
    <option value="Early">Early</option>
    <option value="Rising">Rising</option>
    <option value="Peak">Peak</option>
    <option value="Fading">Fading</option>
  </select>
  <select id="minScore" onchange="applyFilters()">
    <option value="6">6+ (Recommended)</option>
    <option value="7">7+ (Good)</option>
    <option value="8">8+ (High)</option>
    <option value="9">9+ (Top)</option>
  </select>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('audio', this)">🔊 Audio</div>
  <div class="tab" onclick="switchTab('topics', this)">📡 Topics</div>
</div>

<div class="main">
  <div class="stats" id="stats"></div>
  <div class="date-label" id="dateLabel"></div>
  <div id="planPanel"></div>
  <div id="scoutPanel"></div>
  <div id="audioPanel"></div>
  <div id="topicsPanel" style="display:none;"></div>
</div>

<footer>40K Content Intelligence · Automated weekly digest via GitHub Actions</footer>

<script>
let allDates = [];
let currentData = { audio: [], topics: [] };
let currentTab = 'audio';
const MIN_SCORE = 6;   // sounds below this are never recommended

// ── Score badge ──────────────────────────────────────────────────
function scoreBadge(s) {
  const cls = s >= 9 ? 'score-hi' : s >= 7 ? 'score-md' : s >= 5 ? 'score-ok' : 'score-lo';
  return `<span class="score ${cls}">${s}/10</span>`;
}

// ── Audio card ───────────────────────────────────────────────────
function audioCard(a, rank) {
  const cats = (a.categories || []).map(c => `<span class="cat-tag">${esc(c)}</span>`).join('');
  const links = [
    a.ig_link ? `<a href="${esc(a.ig_link)}" target="_blank">Instagram ↗</a>` : '',
    a.tiktok_link ? `<a href="${esc(a.tiktok_link)}" target="_blank">TikTok ↗</a>` : '',
    a.source_url ? `<a href="${esc(a.source_url)}" target="_blank">Source ↗</a>` : '',
  ].filter(Boolean).join('');

  const extra = [
    (a.mention_count||1) > 1 ? `${a.mention_count} sources` : '',
    typeof a.niche_relevance === 'number' ? `niche fit ${Math.round(a.niche_relevance*100)}%` : '',
  ];
  const meta = [a.artist, a.audio_type, a.trend_stage, a.use_count, ...extra].filter(Boolean).join(' · ');
  const fmt = a.format_type ? `<span class="cat-tag" style="border-color:#e67e22;color:#e67e22;">${esc(a.format_type)}</span>` : '';

  return `<div class="audio-card" data-score="${a.potency_score||0}" data-type="${esc(a.audio_type||'')}" data-stage="${esc(a.trend_stage||'')}">
    <div class="top"><h3>#${rank} ${esc(a.name||'Unknown')}</h3>${scoreBadge(a.potency_score||0)}</div>
    ${a.history_label ? `<div style="font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;margin-bottom:4px;color:${/^(New|Climbing)/.test(a.history_label) ? '#2ecc71' : /^Cooling/.test(a.history_label) ? '#c0392b' : 'var(--muted)'}">${esc(a.history_label)}</div>` : ''}
    <div class="audio-meta">${esc(meta)}</div>
    ${(fmt || cats) ? `<div style="margin-bottom:8px;">${fmt}${cats}</div>` : ''}
    ${a.trend_note ? `<div class="field"><span class="field-label">Trend</span>${esc(a.trend_note)}</div>` : ''}
    ${a.sync_note ? `<div class="field"><span class="field-label">Sync potential</span>${esc(a.sync_note)}</div>` : ''}
    ${a.register_note ? `<div class="field"><span class="field-label">Emotional register</span>${esc(a.register_note)}</div>` : ''}
    ${a.counterpoint_potential && a.counterpoint_note ? `<div class="field"><span class="field-label">Counterpoint</span>${esc(a.counterpoint_note)}</div>` : ''}
    ${a.cinematic_angle ? `<div class="angle">${esc(a.cinematic_angle)}</div>` : ''}
    ${a.engine ? `<div style="margin-top:8px;">${engineTag(a.engine)}</div>` : ''}
    ${hookHtml(a.hook, a.on_screen_text)}
    ${(a.target_runtime_s || 'non_player_readable' in a) ? `<div class="audio-meta" style="margin:6px 0 0;">${[a.target_runtime_s ? '~' + esc(a.target_runtime_s) + 's' : '', 'non_player_readable' in a ? (a.non_player_readable ? 'reads for non-players' : 'insider-only') : ''].filter(Boolean).join(' · ')}</div>` : ''}
    ${a.follow_reason && String(a.follow_reason).toLowerCase() !== 'none' ? `<div class="field"><span class="field-label">Why they'd follow</span>${esc(a.follow_reason)}</div>` : ''}
    ${links ? `<div class="links">${links}</div>` : ''}
  </div>`;
}

// ── Topic card ───────────────────────────────────────────────────
function topicCard(t) {
  const badges = [
    t.is_content_gap ? `<span class="badge badge-gap">Content Gap</span>` : '',
    t.is_question ? `<span class="badge badge-q">Question</span>` : '',
  ].filter(Boolean).join('');

  return `<div class="topic-card">
    <div class="title">${esc(t.title||'')}</div>
    <div class="meta">
      <span>${esc(t.category||'')}</span>
      ${t.source ? `<span>· ${esc(t.source)}</span>` : ''}
      ${badges}
    </div>
    ${t.what_is_driving_it ? `<div class="topic-field"><em>What's driving it:</em> ${esc(t.what_is_driving_it)}</div>` : ''}
    ${t.relevance_note ? `<div class="topic-field"><em>Why cover now:</em> ${esc(t.relevance_note)}</div>` : ''}
    ${t.is_content_gap && t.gap_note ? `<div class="topic-field gap-note"><em>Gap opportunity:</em> ${esc(t.gap_note)}</div>` : ''}
    ${(t.engine || t.episode_idea) ? `<div class="topic-field" style="margin-top:8px;">${engineTag(t.engine)} <strong style="color:#fff;">${esc(t.episode_idea||'')}</strong></div>` : ''}
    ${hookHtml(t.hook)}
    ${t.url ? `<div style="margin-top:8px;font-size:11px;"><a href="${esc(t.url)}" target="_blank">View source ↗</a></div>` : ''}
  </div>`;
}

// ── Engines: tags, hooks, weekly plan ────────────────────────────
function engineTag(e) { return e ? `<span class="engine-tag">⚙ ${esc(e)}</span>` : ''; }
function hookHtml(h, txt) {
  return (h ? `<div class="hook"><span class="field-label">First 2 seconds</span>${esc(h)}</div>` : '')
       + (txt ? `<div class="field"><span class="field-label">On-screen text</span>“${esc(txt)}”</div>` : '');
}

function renderPlan() {
  const el = document.getElementById('planPanel');
  const sl = currentData.slate, picks = currentData.comment_picks, drop = currentData.digest_drop;
  const perf = currentData.performance;
  let html = '';
  if (perf) {
    const col = {Breakout:'#c0392b', Above:'#e67e22', Baseline:'#7f8c8d', Under:'#34495e'};
    html += `<div style="margin:0 0 20px;"><div class="section-title">📈 How your last posts did</div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:8px;">Bar: ${(perf.median||0).toLocaleString()} views (${esc(perf.median_source)}) · Breakout &gt;3x · Above &gt;1.5x · Under &lt;0.5x</div>
      ${(perf.recent||[]).length ? `<div class="topic-list">${perf.recent.map(r => `<div class="topic-card" style="display:flex;justify-content:space-between;gap:12px;">
        <div><a href="${esc(r.url)}" target="_blank">${esc((r.caption||'(no caption)').slice(0,90))}</a>
          <div class="meta" style="margin:4px 0 0;">${esc(r.posted)} · ${Math.round(r.age_days)}d old · ${r.duration_s||'?'}s</div></div>
        <div style="text-align:right;white-space:nowrap;font-size:13px;">${(r.views||0).toLocaleString()} views<br>
          <span class="badge" style="background:${col[r.tier]||'#555'};color:#fff;">${esc(r.tier)}</span> <span style="font-size:11px;color:var(--muted);">${r.x_median}x</span></div>
      </div>`).join('')}</div>` : '<div style="font-size:12px;color:var(--muted);">No posts in the last 2 weeks.</div>'}</div>`;
  }
  if (sl && (sl.slots||[]).length) {
    const ch = sl.challenge || {};
    const sub = ch.day ? `Day ${ch.day} of 99 · ${ch.days_left} days to Palm Springs · rotation week ${ch.rotation_week}${ch.phase === 'final push' ? ' · FINAL PUSH' : ''}` : '';
    html += `<div style="margin:0 0 20px;"><div class="section-title">📋 This week's slate</div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:6px;">${esc(sub)}</div>
      ${sl.headline ? `<div class="angle" style="font-style:normal;margin:0 0 12px;">${esc(sl.headline)}</div>` : ''}
      <div class="audio-grid">${sl.slots.map(s => `<div class="audio-card" style="border-left:3px solid var(--accent);">
        <div class="top"><h3><span class="slot">${esc(s.slot)}</span>${esc(s.title || s.engine)}${s.slot === 'C' ? ' <span style="color:var(--muted);font-size:11px;">(optional)</span>' : ''}</h3></div>
        <div style="margin-bottom:6px;">${engineTag(s.engine)}</div>
        ${hookHtml(s.hook, s.on_screen_text)}
        ${s.caption_angle ? `<div class="field"><span class="field-label">Caption carries</span>${esc(s.caption_angle)}</div>` : ''}
        ${s.uses ? `<div class="field"><span class="field-label">Uses</span>${esc(s.uses)}</div>` : ''}
        ${s.why_it_should_work ? `<div class="field"><span class="field-label">Why it should work</span>${esc(s.why_it_should_work)}</div>` : ''}
        ${s.batch_tip ? `<div class="field"><span class="field-label">Batch tip</span>${esc(s.batch_tip)}</div>` : ''}
        ${(s.effort || s.runtime_s) ? `<div class="audio-meta" style="margin-top:6px;">${[s.effort ? 'Effort: ' + esc(s.effort) : '', s.runtime_s ? '~' + esc(s.runtime_s) + 's' : ''].filter(Boolean).join(' · ')}</div>` : ''}
      </div>`).join('')}
      ${sl.second_roll && sl.second_roll.post ? `<div class="audio-card" style="border-left:3px solid var(--blue);"><h3>🎲 Second roll: ${esc(sl.second_roll.post)}</h3><div class="field">${esc(sl.second_roll.change)}</div></div>` : ''}
      </div></div>`;
  }
  if (Array.isArray(picks)) {
    html += `<div style="margin:0 0 20px;"><div class="section-title">💬 Comment picks</div>` +
      (picks.length ? `<div class="audio-grid">${picks.map(p => `<div class="audio-card">
        <div class="top"><h3>“${esc(p.comment)}”</h3>${scoreBadge(p.score||0)}</div>
        <div class="audio-meta">@${esc(p.username)} · ${p.likes||0} likes · reply as: ${esc(p.reply_format)}</div>
        <div class="field"><span class="field-label">Why it's good</span>${esc(p.why)}</div>
        <div class="angle">${esc(p.idea)}</div>
        <div style="margin-top:8px;">${engineTag(p.engine)}</div>
        ${hookHtml(p.hook)}
        ${p.post_url ? `<div class="links"><a href="${esc(p.post_url)}" target="_blank">Open post ↗</a></div>` : ''}
      </div>`).join('')}</div>` : `<div style="font-size:12px;color:var(--muted);">No comments strong enough for a reply video this week.</div>`) + `</div>`;
  }
  if ((drop||[]).length) {
    html += `<div style="margin:0 0 20px;"><div class="section-title">🗞 Digest Drop — new player reads the news</div>
      <div class="topic-list">${drop.map(d => `<div class="topic-card">
        <div class="title">${esc(d.title)} ${d.guard_relevant ? '<span class="badge" style="background:#3a2a0a;color:#f1c40f;">Affects Guard</span>' : ''}</div>
        <div class="topic-field">${esc(d.summary)} ${d.url ? `<a href="${esc(d.url)}" target="_blank" style="font-size:11px;">Source ↗</a>` : ''}</div>
        <div class="topic-field" style="color:var(--accent2);"><em>New-player take:</em> ${esc(d.beginner_take)}</div>
      </div>`).join('')}</div></div>`;
  }
  el.innerHTML = html;
}

// ── Filters ──────────────────────────────────────────────────────
function applyFilters() {
  const q = document.getElementById('search').value.toLowerCase();
  const type = document.getElementById('typeFilter').value.toLowerCase();
  const fmtSel = document.getElementById('formatFilter').value;
  const stage = document.getElementById('stageFilter').value;
  const eng = document.getElementById('engineFilter').value;
  const minS = Math.max(MIN_SCORE, parseInt(document.getElementById('minScore').value) || 0);

  if (currentTab === 'audio') {
    const filtered = currentData.audio.filter(a => {
      if (fmtSel && a.format_type !== fmtSel) return false;
      if (eng && a.engine !== eng) return false;
      if (type && (a.audio_type||'').toLowerCase() !== type) return false;
      if (stage && a.trend_stage !== stage) return false;
      if ((a.potency_score||0) < minS) return false;
      if (q) {
        const blob = [a.name, a.artist, a.format_type, a.trend_note, a.sync_note, a.register_note, a.cinematic_angle, a.engine, a.hook, (a.categories||[]).join(' ')].join(' ').toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
    renderAudio(filtered);
  } else {
    const filtered = currentData.topics.filter(t => {
      if (eng && t.engine !== eng) return false;
      if (!q) return true;
      const blob = [t.title, t.what_is_driving_it, t.relevance_note, t.gap_note, t.category, t.engine, t.episode_idea].join(' ').toLowerCase();
      return blob.includes(q);
    });
    renderTopics(filtered);
  }
}

function renderAudio(items) {
  const panel = document.getElementById('audioPanel');
  if (!items.length) { panel.innerHTML = '<div class="empty">No audio items match your filters.</div>'; return; }
  panel.innerHTML = `<div class="audio-grid">${items.map((a,i) => audioCard(a, i+1)).join('')}</div>`;
}

function renderTopics(items) {
  const panel = document.getElementById('topicsPanel');
  if (!items.length) { panel.innerHTML = '<div class="empty">No topics match your filters.</div>'; return; }
  panel.innerHTML = `<div class="topic-list">${items.map(t => topicCard(t)).join('')}</div>`;
}

function renderScout() {
  const ts = currentData.trend_scout;
  const el = document.getElementById('scoutPanel');
  if (!ts || !(ts.top||[]).length) { el.innerHTML = ''; return; }
  const by = Object.fromEntries(ts.formats.map(f => [f.format, f]));
  const tag = f => ({rising:'▲ Rising', new:'★ New', falling:'▼ Falling', steady:'● Steady'})[f.trend] || '';
  const col = f => ({rising:'#2ecc71', new:'#2ecc71', falling:'#c0392b'})[f.trend] || 'var(--muted)';
  const card = (name, i) => { const f = by[name]; const d = f.share_delta;
    return `<div class="audio-card" style="border-left:3px solid #e67e22;">
      <div class="top"><h3>#${i+1} ${esc(name)}</h3><span style="font-size:11px;font-weight:700;color:${col(f)}">${tag(f)}${d ? ` (${d>0?'+':''}${d} pts)` : ''}</span></div>
      <div class="audio-meta">${f.count} sounds · ${f.strong} strong · avg ${f.avg_score}/10 · niche fit ${Math.round(f.avg_fit*100)}% · ${f.share}% share</div>
      ${(f.examples||[]).map(e => `<div class="field">♪ ${esc(e.name)}${e.artist ? ' — '+esc(e.artist) : ''} <span style="color:var(--muted)">· ${e.potency_score}/10</span></div>`).join('')}
    </div>`; };
  el.innerHTML = `<div style="margin:0 0 20px;">
    <div style="font-size:13px;color:#e67e22;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">🧭 Trend Scout — week of ${esc(ts.week_of)}</div>
    <div class="angle" style="font-style:normal;margin:0 0 12px;">${esc(ts.insight||'')}</div>
    <div class="audio-grid">${ts.top.map(card).join('')}</div>
    <div style="font-size:11px;color:var(--muted);margin-top:8px;">${ts.compared_to ? 'Compared with ' + esc(ts.compared_to) : 'First week with format data — comparisons start next run'}</div>
  </div>`;
}

function renderStats() {
  renderPlan();
  renderScout();
  const audio = currentData.audio.filter(a => (a.potency_score||0) >= MIN_SCORE);
  const topics = currentData.topics;
  const highPotency = audio.filter(a => (a.potency_score||0) >= 8).length;
  const gaps = topics.filter(t => t.is_content_gap).length;
  document.getElementById('stats').innerHTML = `
    <div class="stat"><div class="n">${audio.length}</div><div class="l">Recommended (6+)</div></div>
    <div class="stat"><div class="n" style="color:#c0392b;">${highPotency}</div><div class="l">High potency (8+)</div></div>
    <div class="stat"><div class="n">${topics.length}</div><div class="l">Topics</div></div>
    <div class="stat"><div class="n" style="color:#2ecc71;">${gaps}</div><div class="l">Content gaps</div></div>
  `;
}

// ── Tab switching ────────────────────────────────────────────────
function switchTab(name, el) {
  currentTab = name;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('audioPanel').style.display = name === 'audio' ? '' : 'none';
  document.getElementById('topicsPanel').style.display = name === 'topics' ? '' : 'none';
  // Reset type/stage/score filters (only relevant to audio)
  const audioFilters = ['formatFilter','typeFilter','stageFilter','minScore'];
  audioFilters.forEach(id => { document.getElementById(id).style.display = name === 'audio' ? '' : 'none'; });
  applyFilters();
}

// ── Load a date's digest ─────────────────────────────────────────
async function loadDate(d) {
  if (!d) return;
  document.getElementById('dateLabel').textContent = `Digest for ${d}`;
  try {
    const res = await fetch(`data/digest_${d}.json?t=${Date.now()}`);
    if (!res.ok) throw new Error(res.status);
    currentData = await res.json();
  } catch(e) {
    currentData = { audio: [], topics: [] };
    console.error('Could not load digest:', e);
  }
  renderStats();
  applyFilters();
}

// ── Initialise ───────────────────────────────────────────────────
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function init() {
  // Load the index of available dates
  try {
    const res = await fetch(`data/index.json?t=${Date.now()}`);
    if (res.ok) {
      allDates = await res.json();
    }
  } catch(e) { /* index may not exist yet */ }

  const sel = document.getElementById('dateSelect');
  if (allDates.length === 0) {
    sel.innerHTML = '<option>No digests yet</option>';
    document.getElementById('audioPanel').innerHTML = '<div class="empty">No digest data available. Run the pipeline to generate your first digest.</div>';
    return;
  }

  sel.innerHTML = allDates.map(d => `<option value="${d}">${d}</option>`).join('');
  await loadDate(allDates[0]);
}

init();
</script>
</body>
</html>"""


def _write_date_index(dates: list[str]) -> None:
    """Write docs/data/index.json listing all available digest dates."""
    index_path = DATA_DIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(dates, f)


def update_dashboard(scored_audio: list[dict], scored_topics: list[dict], trend_scout: dict | None = None,
                     plan: dict | None = None) -> None:
    """
    1. Save today's digest JSON.
    2. Regenerate the date index.
    3. Write/refresh docs/index.html.
    """
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save digest JSON
    save_digest_json(scored_audio, scored_topics, trend_scout, plan)

    # Refresh date index
    dates = _collect_digest_dates()
    _write_date_index(dates)
    print(f"    [dashboard] Date index updated: {len(dates)} digest(s) available")

    # Write dashboard HTML
    INDEX_PATH.write_text(DASHBOARD_HTML, encoding="utf-8")
    print(f"    [dashboard] Dashboard written → {INDEX_PATH}")

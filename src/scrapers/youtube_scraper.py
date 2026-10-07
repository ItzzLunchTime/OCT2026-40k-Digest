"""
Uses the YouTube Data API v3 to find what's taking off in the
Warhammer / miniatures / hobby space and the wider nerd-culture
crossover around it.

For every query in YOUTUBE_QUERIES (core niche) and YOUTUBE_CROSSOVER_QUERIES
(broader nerd/internet culture) it searches both Shorts (< 4 min) and
regular videos (4–20 min) published in the last YOUTUBE_WINDOW_DAYS, then
pulls view/like/comment counts so videos can be ranked by views per day —
a better "is this hot right now" signal than raw views.

Quota: search.list = 100 units per call, videos.list = 1 unit per 50 IDs.
With ~14 queries × 2 lengths that's ~2,800 units a run, well inside the
10,000/day free quota for a weekly job.
"""

import datetime
from googleapiclient.discovery import build
from src.config import (
    YOUTUBE_API_KEY,
    YOUTUBE_QUERIES,
    YOUTUBE_CROSSOVER_QUERIES,
    YOUTUBE_WINDOW_DAYS,
    YOUTUBE_MAX_PER_GROUP,
)

AUDIO_KEYWORDS = [
    "music", "song", "track", "audio", "ost", "soundtrack",
    "beat", "sound design", "composed by", "featuring", "remix", "sound",
]

# videoDuration values to search — Shorts carry most format/audio trends
DURATIONS = {"short": "short", "medium": "long"}


def _mentions_audio(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in AUDIO_KEYWORDS)


def _search(yt, query: str, duration: str, published_after: str) -> list[dict]:
    resp = (
        yt.search()
        .list(
            q=query,
            part="snippet",
            type="video",
            order="viewCount",
            publishedAfter=published_after,
            maxResults=10,
            relevanceLanguage="en",
            videoDuration=duration,
            safeSearch="moderate",
        )
        .execute()
    )
    return resp.get("items", [])


def _fetch_stats(yt, video_ids: list[str]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        try:
            resp = yt.videos().list(part="statistics", id=",".join(chunk)).execute()
            for item in resp.get("items", []):
                stats[item["id"]] = item.get("statistics", {})
        except Exception as e:
            print(f"    [youtube] Stats lookup error: {e}")
    return stats


def scrape_youtube() -> list[dict]:
    if not YOUTUBE_API_KEY:
        print("    [youtube] No API key set — skipping")
        return []

    try:
        yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False)
    except Exception as e:
        print(f"    [youtube] Build error: {e}")
        return []

    now = datetime.datetime.now(datetime.timezone.utc)
    published_after = (now - datetime.timedelta(days=YOUTUBE_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    videos: dict[str, dict] = {}
    groups = [("core", YOUTUBE_QUERIES), ("crossover", YOUTUBE_CROSSOVER_QUERIES)]

    for group, queries in groups:
        for query in queries:
            for duration, length_label in DURATIONS.items():
                try:
                    items = _search(yt, query, duration, published_after)
                except Exception as e:
                    print(f"    [youtube] '{query}' ({duration}) error: {e}")
                    continue
                for item in items:
                    vid = item["id"]["videoId"]
                    if vid in videos:
                        continue
                    sn = item["snippet"]
                    text = f"{sn.get('title', '')} {sn.get('description', '')}"
                    videos[vid] = {
                        "source": "youtube",
                        "group": group,
                        "query": query,
                        "length": "short" if length_label == "short" else "long-form",
                        "title": sn.get("title", ""),
                        "channel": sn.get("channelTitle", ""),
                        "description": sn.get("description", "")[:200],
                        "published": sn.get("publishedAt", ""),
                        "url": (f"https://www.youtube.com/shorts/{vid}" if length_label == "short"
                                else f"https://www.youtube.com/watch?v={vid}"),
                        "is_audio_mention": _mentions_audio(text),
                        "type": "audio_mention" if _mentions_audio(text) else "topic",
                    }

    stats = _fetch_stats(yt, list(videos))
    for vid, v in videos.items():
        st = stats.get(vid, {})
        views = int(st.get("viewCount", 0) or 0)
        try:
            pub = datetime.datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
            age_days = max((now - pub).total_seconds() / 86400, 1.0)
        except ValueError:
            age_days = float(YOUTUBE_WINDOW_DAYS)
        v["views"] = views
        v["likes"] = int(st.get("likeCount", 0) or 0)
        v["comments"] = int(st.get("commentCount", 0) or 0)
        v["views_per_day"] = int(views / age_days)

    # Keep the fastest-moving videos from each group so crossover isn't drowned out
    results: list[dict] = []
    for group, _ in groups:
        ranked = sorted(
            (v for v in videos.values() if v["group"] == group),
            key=lambda v: v["views_per_day"],
            reverse=True,
        )
        results.extend(ranked[:YOUTUBE_MAX_PER_GROUP])

    shorts = sum(1 for v in results if v["length"] == "short")
    print(f"    [youtube] {len(videos)} unique videos found → kept {len(results)} "
          f"({shorts} Shorts) by views/day")
    return results

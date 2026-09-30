"""
Uses the YouTube Data API v3 to find recently-trending videos
in the Warhammer / miniature / TTRPG space.

Returns topic signals (video titles + descriptions) and
any audio/music references found in descriptions or titles.
"""

import datetime
from googleapiclient.discovery import build
from src.config import YOUTUBE_API_KEY, YOUTUBE_QUERIES

AUDIO_KEYWORDS = [
    "music", "song", "track", "audio", "ost", "soundtrack",
    "beat", "sound design", "composed by", "featuring"
]


def _mentions_audio(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in AUDIO_KEYWORDS)


def scrape_youtube() -> list[dict]:
    if not YOUTUBE_API_KEY:
        print("    [youtube] No API key set — skipping")
        return []

    try:
        yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        print(f"    [youtube] Build error: {e}")
        return []

    results: list[dict] = []

    for query in YOUTUBE_QUERIES:
        try:
            response = (
                yt.search()
                .list(
                    q=query,
                    part="snippet",
                    type="video",
                    order="viewCount",          # trending by views
                    publishedAfter=(datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    maxResults=10,
                    relevanceLanguage="en",
                    videoDuration="medium",     # 4–20 min = real content
                )
                .execute()
            )

            for item in response.get("items", []):
                snippet = item["snippet"]
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                channel = snippet.get("channelTitle", "")
                video_id = item["id"]["videoId"]
                url = f"https://www.youtube.com/watch?v={video_id}"

                full_text = f"{title} {description}"

                results.append({
                    "source": "youtube",
                    "query": query,
                    "title": title,
                    "channel": channel,
                    "url": url,
                    "is_audio_mention": _mentions_audio(full_text),
                    "type": "audio_mention" if _mentions_audio(full_text) else "topic",
                })

        except Exception as e:
            print(f"    [youtube] Query '{query}' error: {e}")
            continue

    print(f"    [youtube] {len(results)} videos collected")
    return results

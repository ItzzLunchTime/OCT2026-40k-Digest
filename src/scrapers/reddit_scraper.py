"""
Scrapes configured subreddits via PRAW for:
  - Hot/rising posts (trending topics)
  - Recurring questions (post titles ending in ?)
  - Audio mentions in post titles / top-level comments
"""

import praw
from src.config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    SUBREDDITS,
)

AUDIO_KEYWORDS = [
    "song", "music", "audio", "track", "sound", "beat",
    "ost", "soundtrack", "listening", "playing"
]

QUESTION_WORDS = ["how", "what", "which", "why", "where", "anyone", "help", "advice"]


def _is_audio_mention(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in AUDIO_KEYWORDS)


def _is_question(title: str) -> bool:
    t = title.lower()
    return title.strip().endswith("?") or any(t.startswith(w) for w in QUESTION_WORDS)


def scrape_reddit() -> list[dict]:
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            read_only=True,
        )
    except Exception as e:
        print(f"    [reddit] Auth failed: {e}")
        return []

    topics: list[dict] = []

    for sub_name in SUBREDDITS:
        try:
            sub = reddit.subreddit(sub_name)
            posts = list(sub.hot(limit=25)) + list(sub.rising(limit=15))

            for post in posts:
                title = post.title
                score = post.score
                num_comments = post.num_comments
                url = f"https://reddit.com{post.permalink}"

                # High-velocity signal threshold
                if score < 50 and num_comments < 10:
                    continue

                entry: dict = {
                    "source": "reddit",
                    "subreddit": sub_name,
                    "title": title,
                    "score": score,
                    "comments": num_comments,
                    "url": url,
                    "is_question": _is_question(title),
                    "is_audio_mention": _is_audio_mention(title),
                    "type": "topic",
                }

                # If it looks like an audio mention, tag it for audio pipeline too
                if entry["is_audio_mention"]:
                    entry["type"] = "audio_mention"

                topics.append(entry)

        except Exception as e:
            print(f"    [reddit] r/{sub_name} error: {e}")
            continue

    print(f"    [reddit] {len(topics)} posts collected across {len(SUBREDDITS)} subreddits")
    return topics

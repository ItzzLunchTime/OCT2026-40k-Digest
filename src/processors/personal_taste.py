"""
Parses an Instagram data export (JSON) from instagram_data/
to build a personal taste profile string.

The profile is passed to claude_scorer.py to weight audio scores
toward the creator's demonstrated preferences.

Instagram data is never uploaded anywhere — it's read locally only.
"""

import json
import os
from pathlib import Path

INSTAGRAM_DATA_DIR = Path("instagram_data")

# Fields we care about from Instagram's export structure
LIKED_CONTENT_FILES = [
    "likes/liked_posts.json",
    "likes/liked_comments.json",
]
SAVED_CONTENT_FILES = [
    "saved/saved_posts.json",
]
OWN_POSTS_FILES = [
    "content/posts_1.json",
    "content/posts_2.json",
    "content/reels.json",
    "content/igtv_videos.json",
]


def _load_json_file(rel_path: str) -> list | dict | None:
    """Load a JSON file from the instagram_data directory, return None if missing."""
    full_path = INSTAGRAM_DATA_DIR / rel_path
    if not full_path.exists():
        return None
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"    [taste] Could not read {rel_path}: {e}")
        return None


def _extract_captions(posts: list | dict) -> list[str]:
    """
    Extract caption text from Instagram post export structures.
    Instagram exports vary slightly by export version; we try several paths.
    """
    captions = []
    items = posts if isinstance(posts, list) else [posts]

    for item in items:
        # Instagram export: each post has a list of "media" items
        media_list = item.get("media", [item])
        for media in media_list:
            title = media.get("title", "")
            caption = media.get("caption", "")
            text = title or caption
            if text and len(text) > 5:
                captions.append(text[:300])  # cap length

    return captions


def _extract_audio_mentions(captions: list[str]) -> list[str]:
    """
    Look for hashtags, audio mentions, or music references in captions.
    """
    audio_keywords = [
        "#music", "#audio", "#song", "#soundtrack", "#ost", "#darkambient",
        "#grimdark", "#synthwave", "#metal", "#orchestral", "#cinematic",
        "🎵", "🎶", "🎸", "🥁", "using audio", "audio by", "music by",
        "sound by", "track by", "ft.", "feat.", "produced by"
    ]
    mentions = []
    for cap in captions:
        lower = cap.lower()
        if any(kw.lower() in lower for kw in audio_keywords):
            # Return the caption snippet for context
            mentions.append(cap[:150])
    return mentions


def _extract_hashtags(captions: list[str]) -> dict[str, int]:
    """Count hashtag frequency across captions to identify niche clusters."""
    import re
    counts: dict[str, int] = {}
    for cap in captions:
        tags = re.findall(r"#\w+", cap.lower())
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def build_taste_profile() -> str:
    """
    Reads available Instagram export files and returns a plaintext
    taste profile string for use in audio scoring prompts.

    Returns an empty string if no Instagram data is found.
    """
    if not INSTAGRAM_DATA_DIR.exists():
        print("    [taste] No instagram_data/ directory found — skipping taste profile")
        return ""

    own_captions: list[str] = []
    liked_captions: list[str] = []
    saved_captions: list[str] = []

    # Own posts
    for f in OWN_POSTS_FILES:
        data = _load_json_file(f)
        if data:
            own_captions.extend(_extract_captions(data))

    # Liked posts
    for f in LIKED_CONTENT_FILES:
        data = _load_json_file(f)
        if data:
            liked_captions.extend(_extract_captions(data if isinstance(data, list) else [data]))

    # Saved posts
    for f in SAVED_CONTENT_FILES:
        data = _load_json_file(f)
        if data:
            saved_captions.extend(_extract_captions(data if isinstance(data, list) else [data]))

    if not any([own_captions, liked_captions, saved_captions]):
        print("    [taste] Instagram data found but no captions extracted")
        return ""

    # Build the profile text
    sections = []

    # Top hashtags from own posts
    if own_captions:
        tag_counts = _extract_hashtags(own_captions)
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        if top_tags:
            sections.append(
                "Creator's own hashtag clusters (most used → least used):\n"
                + ", ".join(f"{tag}({count})" for tag, count in top_tags)
            )

    # Audio mentions in own posts
    own_audio = _extract_audio_mentions(own_captions)
    if own_audio:
        sections.append(
            f"Audio/music references in creator's own posts ({len(own_audio)} found):\n"
            + "\n".join(f"  - {m}" for m in own_audio[:10])
        )

    # Audio mentions in liked content
    liked_audio = _extract_audio_mentions(liked_captions)
    if liked_audio:
        sections.append(
            f"Audio/music references in liked content ({len(liked_audio)} found):\n"
            + "\n".join(f"  - {m}" for m in liked_audio[:10])
        )

    # Sample of own post captions (for general aesthetic/tone reference)
    if own_captions:
        sample = own_captions[:5]
        sections.append(
            "Sample captions from creator's own posts (for tone/aesthetic reference):\n"
            + "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(sample))
        )

    if not sections:
        return ""

    profile = (
        "PERSONAL TASTE PROFILE — derived from Instagram export data.\n"
        "Use this to weight scores toward demonstrated preferences.\n\n"
        + "\n\n".join(sections)
    )

    print(f"    [taste] Profile built: {len(sections)} signal sections from Instagram data")
    return profile


def load_taste_profile_from_cache(cache_path: str = "instagram_data/taste_profile.txt") -> str:
    """
    Load a pre-generated taste profile from a plain text file.
    This is useful when the full Instagram export is not present
    but a manually curated profile has been saved.
    """
    p = Path(cache_path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception as e:
        print(f"    [taste] Could not load cached profile: {e}")
        return ""


def get_taste_profile() -> str:
    """
    Main entry point. Returns the best available taste profile:
    0. TASTE_PROFILE environment variable (GitHub secret — used in CI)
    1. Cached plaintext profile
    2. Generated from a local Instagram export
    3. Empty string (scoring proceeds without weighting)
    """
    # 0. Private GitHub secret (the repo is public, so the profile lives here in CI)
    secret = os.getenv("TASTE_PROFILE", "").strip()
    if secret:
        print(f"    [taste] Using TASTE_PROFILE secret ({len(secret)} chars)")
        return secret

    # Try cached first — it may have been manually curated
    cached = load_taste_profile_from_cache()
    if cached:
        print("    [taste] Using cached taste profile")
        return cached

    # Try building from export
    generated = build_taste_profile()
    if generated:
        # Cache it for future runs
        try:
            cache_path = INSTAGRAM_DATA_DIR / "taste_profile.txt"
            cache_path.write_text(generated, encoding="utf-8")
            print("    [taste] Taste profile cached to instagram_data/taste_profile.txt")
        except Exception:
            pass
        return generated

    return ""

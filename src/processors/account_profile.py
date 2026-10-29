"""
Private, evidence-based profile of what performs on the account (real Insights numbers,
top/bottom posts, ready ideas, hook bank). The repo is public, so the profile lives in the
ACCOUNT_PROFILE GitHub secret; locally it's read from instagram_data/account_profile.md
(gitignored). Either way it is passed to every Claude prompt as extra context.
"""

import os
from pathlib import Path

LOCAL_PATH = Path("instagram_data/account_profile.md")
_cache: str | None = None


def get_account_profile() -> str:
    global _cache
    if _cache is not None:
        return _cache
    text = os.getenv("ACCOUNT_PROFILE", "").strip()
    source = "ACCOUNT_PROFILE secret"
    if not text and LOCAL_PATH.exists():
        text = LOCAL_PATH.read_text(encoding="utf-8").strip()
        source = str(LOCAL_PATH)
    _cache = text
    print(f"    [profile] {'Using ' + source + f' ({len(text)} chars)' if text else 'No account profile found — scoring on general rules only'}")
    return text


def profile_block() -> str:
    """The profile wrapped for a prompt, or '' if there isn't one."""
    p = get_account_profile()
    return f"\n\n{p}\n" if p else ""

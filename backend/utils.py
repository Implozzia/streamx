import re
from urllib.parse import urlparse


def extract_nickname_from_url(url: str) -> str:
    """Extract a streamer nickname from a profile URL.

    Supported patterns:
      tiktok.com/@name        → "name"
      instagram.com/name      → "name"
      t.me/name               → "name"
      youtube.com/@channel    → "channel"
      youtube.com/c/channel   → "channel"
      youtube.com/channel/ID  → "ID"
      youtube.com/user/name   → "name"
      fallback                → last non-empty path segment (stripped of leading @)

    Tolerates: www prefix, http/https, trailing slash, surrounding whitespace.
    Returns "" if a nickname cannot be extracted.
    """
    if not url:
        return ""

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        host = re.sub(r"^www\.", "", host)

        path = parsed.path.rstrip("/")
        segments = [s for s in path.split("/") if s]

        if not segments:
            return ""

        # TikTok
        if "tiktok.com" in host:
            return segments[0].lstrip("@")

        # YouTube
        if "youtube.com" in host:
            first = segments[0]
            if first.startswith("@"):
                return first.lstrip("@")
            if first in ("c", "channel", "user") and len(segments) > 1:
                return segments[1]
            return first

        # Telegram
        if host in ("t.me", "telegram.me", "telegram.dog"):
            return segments[0]

        # Instagram
        if "instagram.com" in host:
            return segments[0].lstrip("@")

        # Fallback: last path segment, strip leading @
        return segments[-1].lstrip("@")

    except Exception:
        return ""

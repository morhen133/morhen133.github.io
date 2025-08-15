import feedparser
import hashlib
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
from typing import List, Dict, Optional, Tuple


UX_FEEDS: List[Tuple[str, str]] = [
    ("Nielsen Norman Group", "https://www.nngroup.com/feed/rss/"),
    ("Smashing Magazine – UX", "https://www.smashingmagazine.com/category/ux-design/feed/"),
    ("Smashing Magazine – Design", "https://www.smashingmagazine.com/category/design/feed/"),
    ("UX Collective", "https://uxdesign.cc/feed"),
    ("UX Planet", "https://uxplanet.org/feed"),
    ("UX Booth", "https://www.uxbooth.com/feed/"),
    ("Sidebar.io", "https://sidebar.io/feed"),
    ("Muzli by InVision", "https://medium.muz.li/feed"),
    ("Interaction Design Foundation", "https://www.interaction-design.org/literature/rss"),
    ("Codrops", "https://tympanus.net/codrops/feed/"),
    ("A List Apart – UX", "https://alistapart.com/topics/ux/feed/"),
]


def _parse_entry_datetime(entry: dict) -> Optional[datetime]:
    for key in ("published", "updated", "created", "pubDate"):
        value = entry.get(key)
        if value:
            try:
                dt = date_parser.parse(value)
                # Normalize to UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            except Exception:
                continue
    # Some feeds provide structured time
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                dt = datetime(*value[:6], tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
    return None


def _normalize_item(source: str, entry: dict) -> Optional[Dict]:
    link = entry.get("link") or entry.get("id")
    title = (entry.get("title") or "").strip()
    if not link or not title:
        return None

    published_at = _parse_entry_datetime(entry)

    # Use a stable id to deduplicate across feeds
    stable_id_base = f"{source}|{title}|{link}"
    stable_id = hashlib.sha1(stable_id_base.encode("utf-8")).hexdigest()

    return {
        "id": stable_id,
        "source": source,
        "title": title,
        "link": link,
        "published_at": published_at,
    }


def fetch_ux_news(since_utc: Optional[datetime] = None, limit: int = 5) -> List[Dict]:
    """
    Fetch recent UX design articles from curated RSS feeds.

    - since_utc: only include items published on/after this UTC datetime. Defaults to 7 days ago.
    - limit: number of items to return after ranking.
    """
    if since_utc is None:
        since_utc = datetime.now(timezone.utc) - timedelta(days=7)

    items: List[Dict] = []
    seen_ids = set()

    for source, url in UX_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.get("entries", []):
            normalized = _normalize_item(source, entry)
            if not normalized:
                continue

            published_at = normalized.get("published_at")
            if published_at is not None and published_at < since_utc:
                continue

            if normalized["id"] in seen_ids:
                continue

            seen_ids.add(normalized["id"])
            items.append(normalized)

    # Simple ranking heuristic: newer first; tie-breaker by source preference
    source_priority = {name: idx for idx, (name, _) in enumerate(UX_FEEDS)}

    def sort_key(item: Dict):
        published_at = item.get("published_at") or datetime(1970, 1, 1, tzinfo=timezone.utc)
        source_rank = source_priority.get(item.get("source"), 999)
        return (published_at, -source_rank)

    items.sort(key=sort_key, reverse=True)

    return items[:limit]


def format_news_digest(items: List[Dict]) -> str:
    """Format the shortlist message using HTML for Telegram."""
    if not items:
        return "No fresh UX design highlights found for the last week."

    lines = ["<b>Top UX and UI design highlights from the last 7 days</b>"]
    for idx, item in enumerate(items, start=1):
        title = item.get("title", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        link = item.get("link", "#")
        source = item.get("source", "")
        lines.append(f"{idx}. <a href=\"{link}\">{title}</a>  —  <i>{source}</i>")
    return "\n".join(lines)
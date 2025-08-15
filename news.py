import feedparser
import hashlib
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
from typing import List, Dict, Optional, Tuple, Any


UX_FEEDS: List[Tuple[str, str, str]] = [
	("Nielsen Norman Group", "https://www.nngroup.com/feed/rss/", "en"),
	("Smashing Magazine – UX", "https://www.smashingmagazine.com/category/ux-design/feed/", "en"),
	("Smashing Magazine – Design", "https://www.smashingmagazine.com/category/design/feed/", "en"),
	("UX Collective", "https://uxdesign.cc/feed", "en"),
	("UX Planet", "https://uxplanet.org/feed", "en"),
	("UX Booth", "https://www.uxbooth.com/feed/", "en"),
	("Sidebar.io", "https://sidebar.io/feed", "en"),
	("Muzli by InVision", "https://medium.muz.li/feed", "en"),
	("Interaction Design Foundation", "https://www.interaction-design.org/literature/rss", "en"),
	("Codrops", "https://tympanus.net/codrops/feed/", "en"),
	("A List Apart – UX", "https://alistapart.com/topics/ux/feed/", "en"),
	("Baymard Institute", "https://baymard.com/blog/feed", "en"),
	# Russian sources
	("UPROCK", "https://uprock.pro/feed", "ru"),
	("VC.ru – Design", "https://vc.ru/design/rss", "ru"),
	("Habr – UX", "https://habr.com/ru/hub/ux/rss/", "ru"),
	("Habr – Design", "https://habr.com/ru/hub/design/rss/", "ru"),
	("UX Journal (RU)", "https://ux-journal.ru/feed/", "ru"),
]


def _parse_entry_datetime(entry: dict) -> Optional[datetime]:
    for key in ("published", "updated", "created", "pubDate"):
        value = entry.get(key)
        if value:
            try:
                dt = date_parser.parse(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            except Exception:
                continue
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                dt = datetime(*value[:6], tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
    return None


def _try_parse_int(value: Any) -> Optional[int]:
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = ''.join(ch for ch in value if ch.isdigit())
            if digits:
                return int(digits)
        if isinstance(value, dict):
            for k, v in value.items():
                parsed = _try_parse_int(v)
                if parsed is not None:
                    return parsed
    except Exception:
        return None
    return None


def _extract_engagement(entry: dict) -> Dict[str, Optional[int]]:
    """Best-effort extraction of views/reads/comments from heterogeneous feeds."""
    views_keys = (
        "views", "view_count", "views_count", "read_count", "reads", "viewcount",
        "metrics_views", "stats_views", "statistics", "media_statistics",
    )
    comments_keys = ("comments", "comments_count", "slash_comments", "thr_total")

    views: Optional[int] = None
    comments: Optional[int] = None

    for key in entry.keys():
        lower = key.lower()
        try:
            value = entry.get(key)
        except Exception:
            value = None
        if views is None and any(k in lower for k in views_keys):
            parsed = _try_parse_int(value)
            if parsed is not None:
                views = parsed
        if comments is None and any(k in lower for k in comments_keys):
            parsed = _try_parse_int(value)
            if parsed is not None:
                comments = parsed

    # Some feeds put counts into extensions
    for ext in ("media_statistics", "yt_statistics", "storm_views"):
        if views is None and ext in entry:
            parsed = _try_parse_int(entry.get(ext))
            if parsed is not None:
                views = parsed

    return {"views": views, "comments": comments}


def _normalize_item(source: str, entry: dict, lang: str) -> Optional[Dict]:
	link = entry.get("link") or entry.get("id")
	title = (entry.get("title") or "").strip()
	if not link or not title:
		return None

	published_at = _parse_entry_datetime(entry)
	engagement = _extract_engagement(entry)

	stable_id_base = f"{source}|{title}|{link}"
	stable_id = hashlib.sha1(stable_id_base.encode("utf-8")).hexdigest()

	return {
		"id": stable_id,
		"source": source,
		"title": title,
		"link": link,
		"published_at": published_at,
		"views": engagement.get("views"),
		"comments": engagement.get("comments"),
		"lang": lang,
	}


def fetch_ux_news(since_utc: Optional[datetime] = None, limit: int = 10) -> List[Dict]:
	"""
	Fetch recent UX/UI design articles from curated RSS feeds.

	- since_utc: only include items published on/after this UTC datetime. Defaults to 7 days ago.
	- limit: number of items to return after ranking.
	"""
	if since_utc is None:
		since_utc = datetime.now(timezone.utc) - timedelta(days=7)

	items: List[Dict] = []
	seen_ids = set()

	for source, url, lang in UX_FEEDS:
		try:
			feed = feedparser.parse(url)
		except Exception:
			continue

		for entry in feed.get("entries", []):
			normalized = _normalize_item(source, entry, lang)
			if not normalized:
				continue

			published_at = normalized.get("published_at")
			if published_at is not None and published_at < since_utc:
				continue

			if normalized["id"] in seen_ids:
				continue

			seen_ids.add(normalized["id"])
			items.append(normalized)

	source_priority = {name: idx for idx, (name, _, __) in enumerate(UX_FEEDS)}

	def sort_key(item: Dict):
		published_at = item.get("published_at") or datetime(1970, 1, 1, tzinfo=timezone.utc)
		source_rank = source_priority.get(item.get("source"), 999)
		views_rank = item.get("views") or 0
		return (views_rank, published_at, -source_rank)

	# Split by language and sort independently
	en_items = [i for i in items if i.get("lang") == "en"]
	ru_items = [i for i in items if i.get("lang") == "ru"]
	en_sorted = sorted(en_items, key=sort_key, reverse=True)
	ru_sorted = sorted(ru_items, key=sort_key, reverse=True)

	quota = max(1, limit // 2)
	selected_en = en_sorted[:quota]
	selected_ru = ru_sorted[:quota]
	combined = selected_en + selected_ru

	if len(combined) < limit:
		remaining_pool = en_sorted[quota:] + ru_sorted[quota:]
		remaining_sorted = sorted(remaining_pool, key=sort_key, reverse=True)
		combined.extend(remaining_sorted[: max(0, limit - len(combined))])

	return combined[:limit]


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_news_digest(items: List[Dict]) -> str:
	"""Format the shortlist as a clean list with links; show views if available and tag language."""
	if not items:
		return "No fresh UX/UI design highlights found for the last week."

	lines = [
		"<b>Top UX and UI design highlights from the last 7 days</b>",
		"<i>5 English + 5 Russian</i>",
	]
	for idx, item in enumerate(items, start=1):
		title = _html_escape(_truncate(item.get("title", ""), 180))
		link = item.get("link", "#")
		source = _html_escape(item.get("source", ""))
		lang = item.get("lang")
		views = item.get("views")

		meta_parts = []
		if isinstance(views, int):
			meta_parts.append(f"{views} views")
		if lang in ("en", "ru"):
			meta_parts.append(lang.upper())
		meta = f" ({' · '.join(meta_parts)})" if meta_parts else ""

		lines.append(f"{idx}. <a href=\"{link}\">{title}</a> — <i>{source}</i>{meta}")

	return "\n".join(lines)
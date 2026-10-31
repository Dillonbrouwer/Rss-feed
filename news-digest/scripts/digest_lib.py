"""Pure helpers for the news digest. No network or file I/O lives here."""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

TRACKING_PARAM = re.compile(r"^(utm_[a-z0-9_]+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src)$", re.I)
UTC = timezone.utc


def normalize_url(url: str) -> str:
    """Canonical form used as the article ID: lowercase host, no www, no tracking params, no trailing slash."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not TRACKING_PARAM.match(k)]
    return urlunsplit((parts.scheme.lower() or "https", host, path, urlencode(query), ""))


def normalize_title(title: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(html.unescape(text).split())


def make_excerpt(text: str, limit: int = 300) -> str:
    text = strip_html(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def struct_to_utc(t) -> datetime | None:
    if not t:
        return None
    return datetime(*t[:6], tzinfo=UTC)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def parse_feed_bytes(content: bytes, outlet: str, fetched_at: datetime) -> list[dict]:
    """Turn raw RSS/Atom bytes into article dicts. Missing dates fall back to fetch time."""
    parsed = feedparser.parse(content)
    items = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = strip_html(entry.get("title", ""))
        if not link or not title:
            continue
        published = struct_to_utc(entry.get("published_parsed") or entry.get("updated_parsed"))
        raw_summary = entry.get("summary", "") or entry.get("description", "")
        items.append({
            "id": normalize_url(link),
            "title": title,
            "link": link.strip(),
            "outlet": outlet,
            "author": strip_html(entry.get("author", "")) or None,
            "published": iso(published or fetched_at),
            "first_seen": iso(fetched_at),
            "excerpt": make_excerpt(raw_summary),
            "tags": [],
            "also_reported_by": [],
        })
    return items


def compile_topics(topics: dict[str, list[str]]) -> dict[str, re.Pattern]:
    compiled = {}
    for name, keywords in (topics or {}).items():
        kws = [k for k in keywords if k and k.strip()]
        if not kws:
            continue
        alt = "|".join(re.escape(k.strip()) for k in kws)
        compiled[name] = re.compile(rf"\b(?:{alt})\b", re.I)
    return compiled


def tag_article(article: dict, compiled: dict[str, re.Pattern]) -> list[str]:
    haystack = f"{article.get('title', '')} {article.get('excerpt', '')}"
    return sorted(name for name, pat in compiled.items() if pat.search(haystack))


def _title_day_key(article: dict) -> tuple[str, str] | None:
    pub = parse_iso(article.get("published"))
    if not pub:
        return None
    return normalize_title(article["title"]), pub.astimezone(UTC).date().isoformat()


def merge_articles(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Add incoming items to the archive. Earliest-seen record wins; duplicates
    are recorded in also_reported_by instead of being stored twice."""
    by_id: dict[str, dict] = {}
    by_title_day: dict[tuple, str] = {}

    for art in existing:
        art.setdefault("also_reported_by", [])
        by_id.setdefault(art["id"], art)
        key = _title_day_key(art)
        if key:
            by_title_day.setdefault(key, art["id"])

    for item in incoming:
        if item["id"] in by_id:
            continue
        key = _title_day_key(item)
        if key and key in by_title_day:
            kept = by_id[by_title_day[key]]
            outlet = item["outlet"]
            if outlet != kept["outlet"] and outlet not in kept["also_reported_by"]:
                kept["also_reported_by"].append(outlet)
            continue
        by_id[item["id"]] = item
        if key:
            by_title_day[key] = item["id"]

    return list(by_id.values())


def prune(articles: list[dict], now: datetime, days: int) -> list[dict]:
    cutoff = now - timedelta(days=days)
    kept = []
    for a in articles:
        seen = parse_iso(a.get("first_seen"))
        if seen and seen >= cutoff:
            kept.append(a)
    return kept


def sort_newest_first(articles: list[dict]) -> list[dict]:
    return sorted(articles, key=lambda a: a.get("published") or "", reverse=True)

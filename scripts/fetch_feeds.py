"""Fetch all enabled feeds, dedupe, tag, merge into the archive, and write data/.

Usage:
  python scripts/fetch_feeds.py           # normal run (used by the workflow)
  python scripts/fetch_feeds.py --check   # print per-feed status without writing data
"""
import argparse
import logging
import sys
from datetime import datetime, timezone

import requests

from common import DATA, load_json, load_yaml, save_json
from digest_lib import (compile_topics, merge_articles, parse_feed_bytes,
                        iso, prune, sort_newest_first, tag_article)

log = logging.getLogger("fetch")


def fetch_one(feed: dict, settings: dict, now: datetime) -> tuple[list[dict], str | None]:
    headers = {"User-Agent": settings["user_agent"]}
    try:
        resp = requests.get(feed["url"], headers=headers,
                            timeout=settings.get("request_timeout_seconds", 20))
        resp.raise_for_status()
        items = parse_feed_bytes(resp.content, feed["name"], now)
        if not items:
            return [], "feed returned no usable items"
        return items, None
    except Exception as exc:  # one bad feed must not stop the run
        return [], f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report feed health only")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = load_yaml("settings.yaml")
    feeds = [f for f in load_yaml("feeds.yaml").get("feeds", []) if f.get("enabled")]
    topics = load_yaml("topics.yaml").get("topics", {})
    compiled = compile_topics(topics)
    now = datetime.now(timezone.utc)

    status = load_json(DATA / "feed_status.json", {})
    incoming, failures = [], 0

    for feed in feeds:
        items, error = fetch_one(feed, settings, now)
        entry = status.get(feed["name"], {})
        if error:
            failures += 1
            log.warning("%s failed: %s", feed["name"], error)
            entry.update({"last_error": error, "last_error_at": iso(now)})
        else:
            log.info("%s: %d items", feed["name"], len(items))
            incoming.extend(items)
            entry.update({"last_success": iso(now), "last_item_count": len(items),
                          "last_error": None})
        status[feed["name"]] = entry

    if args.check:
        for name, entry in status.items():
            print(name, entry)
        return 0

    archive = load_json(DATA / "articles.json", [])
    for art in archive:
        art["tags"] = tag_article(art, compiled)  # re-tag so keyword edits apply to history
    for item in incoming:
        item["tags"] = tag_article(item, compiled)

    merged = merge_articles(archive, incoming)
    merged = sort_newest_first(prune(merged, now, settings.get("archive_days", 90)))

    counts = {name: 0 for name in compiled}
    for art in merged:
        for t in art["tags"]:
            counts[t] += 1
    log.info("tag hit counts: %s", counts or "(no topics configured)")

    save_json(DATA / "articles.json", merged)
    save_json(DATA / "feed_status.json", status)
    log.info("archive now holds %d articles", len(merged))

    if feeds and failures == len(feeds):
        log.error("every enabled feed failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

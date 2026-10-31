"""Post a daily digest to a Microsoft Teams channel via a Workflows webhook.

The workflow runs twice a day (12:00 and 13:00 UTC) so 7:00 AM Central is hit
in both daylight and standard time. This script exits early unless the local
hour matches digest_local_hour, so only one post happens per day.

Usage:
  python scripts/send_teams_digest.py              # posts only at the digest hour
  python scripts/send_teams_digest.py --force      # post now (manual runs)
  python scripts/send_teams_digest.py --dry-run    # print the card, do not post
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

from common import DATA, load_json, load_yaml, local_tz
from digest_lib import parse_iso


def build_card(groups: dict[str, list[dict]], now_local: datetime, tz, per_topic: int) -> dict:
    body = [{"type": "TextBlock", "text": f"Daily digest · {now_local.strftime('%A, %B %d')}",
             "weight": "Bolder", "size": "Large", "wrap": True}]
    for topic, items in groups.items():
        body.append({"type": "TextBlock", "text": topic, "weight": "Bolder", "separator": True,
                     "spacing": "Medium", "wrap": True})
        for art in items[:per_topic]:
            pub = parse_iso(art.get("published"))
            when = pub.astimezone(tz).strftime("%I:%M %p") if pub else ""
            line = f"[{art['title']}]({art['link']})  \n{art['outlet']}{' · ' + when if when else ''}"
            body.append({"type": "TextBlock", "text": line, "wrap": True, "spacing": "Small"})
        extra = len(items) - per_topic
        if extra > 0:
            body.append({"type": "TextBlock", "text": f"+{extra} more in the archive",
                         "isSubtle": True, "wrap": True})
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }


def wrap_for_workflow(card: dict) -> dict:
    return {"type": "message", "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": card,
    }]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    settings = load_yaml("settings.yaml")
    tz = local_tz(settings)
    now_local = datetime.now(tz)

    if not args.force and now_local.hour != settings.get("digest_local_hour", 7):
        print(f"local time {now_local:%H:%M %Z}; not digest hour, skipping")
        return 0

    topics = list((load_yaml("topics.yaml").get("topics") or {}).keys())
    articles = load_json(DATA / "articles.json", [])
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    fresh = [a for a in articles
             if (parse_iso(a.get("first_seen")) or since) >= since]

    groups = {}
    if not topics and fresh:
        groups["All"] = fresh
    for topic in topics:
        matched = [a for a in fresh if topic in a.get("tags", [])]
        if matched:
            groups[topic] = matched

    if not groups:
        if not settings.get("post_on_quiet_days", False) and not args.force:
            print("no new items for any topic; quiet day, not posting")
            return 0
        card = {"type": "AdaptiveCard", "version": "1.4", "body": [
            {"type": "TextBlock", "wrap": True,
             "text": f"Daily digest · {now_local:%A, %B %d}: no new items matched any topic today."}]}
    else:
        card = build_card(groups, now_local, tz, settings.get("digest_items_per_topic", 5))

    payload = wrap_for_workflow(card)
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    url = os.environ.get("TEAMS_WEBHOOK_URL", "").strip()
    if not url:
        print("TEAMS_WEBHOOK_URL is not set", file=sys.stderr)
        return 1

    # One attempt only, so a flaky response can't produce duplicate posts.
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"posted digest ({len(groups)} topics, HTTP {resp.status_code})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

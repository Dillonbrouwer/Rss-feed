from datetime import datetime, timezone
from pathlib import Path

from digest_lib import (compile_topics, make_excerpt, merge_articles, normalize_title,
                        normalize_url, parse_feed_bytes, prune, tag_article)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def test_normalize_url_strips_tracking_and_trailing_slash():
    a = normalize_url("https://WWW.Example.com/news/x/?utm_source=a&id=7&fbclid=zz")
    assert a == "https://example.com/news/x?id=7"


def test_normalize_title_collapses_punctuation():
    assert normalize_title("Senate Passes “Tariff” Bill!") == "senate passes tariff bill"


def test_excerpt_strips_html_and_truncates_on_word():
    text = "<p>" + "word " * 100 + "</p>"
    out = make_excerpt(text, limit=50)
    assert "<" not in out and out.endswith("…") and len(out) <= 52


def test_parse_feed_skips_items_without_link_and_strips_html():
    items = parse_feed_bytes(FIXTURE.read_bytes(), "Sample Outlet", NOW)
    assert len(items) == 2
    first = items[0]
    assert first["id"] == "https://example.com/news/tariff-bill"
    assert first["author"] == "Jane Reporter"
    assert "<b>" not in first["excerpt"]
    assert first["published"].startswith("2026-10-27T14:00:00")


def test_tagging_uses_word_boundaries():
    compiled = compile_topics({"AI": ["AI"], "Trade": ["tariff", "export controls"]})
    items = parse_feed_bytes(FIXTURE.read_bytes(), "Sample Outlet", NOW)
    assert tag_article(items[0], compiled) == ["Trade"]
    # "Ai model" matches, but "said" must not match "AI"
    assert tag_article(items[1], compiled) == ["AI"]
    assert tag_article({"title": "They said nothing", "excerpt": ""}, compiled) == []


def test_compile_topics_ignores_empty_keyword_lists():
    assert compile_topics({"Empty": []}) == {}
    assert compile_topics({}) == {}


def test_merge_dedupes_by_link_and_keeps_earliest():
    base = {"id": "https://a.com/x", "title": "Same", "link": "https://a.com/x", "outlet": "A",
            "published": "2026-10-27T10:00:00+00:00", "first_seen": "2026-10-27T11:00:00+00:00",
            "excerpt": "", "tags": [], "also_reported_by": []}
    dup = dict(base, id="https://b.com/x", outlet="B", first_seen="2026-10-27T12:00:00+00:00")
    merged = merge_articles([base], [dup])
    assert len(merged) == 1 and merged[0]["outlet"] == "A"


def test_merge_dedupes_syndicated_copy_by_title_and_day():
    first = {"id": "https://a.com/story", "title": "Big News Today", "link": "https://a.com/story",
             "outlet": "A", "published": "2026-10-27T10:00:00+00:00",
             "first_seen": "2026-10-27T11:00:00+00:00", "excerpt": "", "tags": [],
             "also_reported_by": []}
    syndicated = dict(first, id="https://b.com/copy", link="https://b.com/copy", outlet="B")
    merged = merge_articles([first], [syndicated])
    assert len(merged) == 1
    assert merged[0]["also_reported_by"] == ["B"]


def test_prune_drops_entries_older_than_window():
    old = {"id": "1", "first_seen": "2026-06-01T00:00:00+00:00"}
    recent = {"id": "2", "first_seen": "2026-10-20T00:00:00+00:00"}
    kept = prune([old, recent], NOW, days=90)
    assert [a["id"] for a in kept] == ["2"]

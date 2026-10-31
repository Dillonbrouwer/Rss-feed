import json
from datetime import datetime, timezone

import pytest

import fetch_feeds
import render_page
import send_teams_digest

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    for module in (fetch_feeds, render_page, send_teams_digest):
        monkeypatch.setattr(module, "datetime", Clock)


def article(**changes):
    return {
        "id": "https://example.com/story", "link": "https://example.com/story",
        "title": "A headline", "outlet": "Example", "author": None,
        "published": NOW.isoformat(), "first_seen": NOW.isoformat(),
        "excerpt": "An excerpt", "tags": [], "also_reported_by": [], **changes,
    }


@pytest.mark.parametrize("check", [False, True])
def test_total_fetch_failure_reports_failure_and_preserves_archive(monkeypatch, tmp_path, check):
    archive = [article()]
    (tmp_path / "articles.json").write_text(json.dumps(archive), encoding="utf-8")
    config = {
        "settings.yaml": {}, "topics.yaml": {"topics": {}},
        "feeds.yaml": {"feeds": [{"name": "Example", "enabled": True}]},
    }
    monkeypatch.setattr(fetch_feeds, "DATA", tmp_path)
    monkeypatch.setattr(fetch_feeds, "load_yaml", config.__getitem__)
    monkeypatch.setattr(fetch_feeds, "fetch_one", lambda *args: ([], "DNS failure"))
    monkeypatch.setattr("sys.argv", ["fetch_feeds.py"] + (["--check"] if check else []))

    assert fetch_feeds.main() == 1
    assert json.loads((tmp_path / "articles.json").read_text(encoding="utf-8")) == archive
    if check:
        assert not (tmp_path / "feed_status.json").exists()
    else:
        status = json.loads((tmp_path / "feed_status.json").read_text(encoding="utf-8"))
        assert status["Example"]["last_error"] == "DNS failure"


def test_no_enabled_feeds_is_an_error(monkeypatch):
    monkeypatch.setattr(fetch_feeds, "load_yaml", lambda name: {})
    monkeypatch.setattr("sys.argv", ["fetch_feeds.py", "--check"])
    assert fetch_feeds.main() == 1


def test_partial_fetch_success_keeps_articles_and_only_enabled_status(monkeypatch, tmp_path):
    (tmp_path / "feed_status.json").write_text('{"Disabled": {}}', encoding="utf-8")
    config = {
        "settings.yaml": {}, "topics.yaml": {"topics": {}},
        "feeds.yaml": {"feeds": [
            {"name": "Example", "enabled": True},
            {"name": "Broken", "enabled": True},
            {"name": "Disabled", "enabled": False},
        ]},
    }
    monkeypatch.setattr(fetch_feeds, "DATA", tmp_path)
    monkeypatch.setattr(fetch_feeds, "load_yaml", config.__getitem__)
    monkeypatch.setattr(fetch_feeds, "fetch_one", lambda feed, *args:
                        ([article()], None) if feed["name"] == "Example" else ([], "HTTP 403"))
    monkeypatch.setattr("sys.argv", ["fetch_feeds.py"])

    assert fetch_feeds.main() == 0
    assert len(json.loads((tmp_path / "articles.json").read_text(encoding="utf-8"))) == 1
    status = json.loads((tmp_path / "feed_status.json").read_text(encoding="utf-8"))
    assert set(status) == {"Example", "Broken"}
    assert status["Example"]["last_item_count"] == 1
    assert status["Broken"]["last_error"] == "HTTP 403"


def test_render_escapes_feed_text_and_reports_only_enabled_stale_feeds(monkeypatch, tmp_path):
    config = {
        "settings.yaml": {"stale_feed_hours": 72},
        "topics.yaml": {"topics": {}},
        "feeds.yaml": {"feeds": [
            {"name": "Missing feed", "enabled": True},
            {"name": "Disabled feed", "enabled": False},
        ]},
    }
    monkeypatch.setattr(render_page, "DOCS", tmp_path)
    monkeypatch.setattr(render_page, "load_yaml", config.__getitem__)
    monkeypatch.setattr(render_page, "load_json", lambda path, default:
                        [article(title='<img src=x onerror="alert(1)">',
                                 excerpt="<script>alert(1)</script>")]
                        if path.name == "articles.json" else {"Disabled feed": {}})

    render_page.main()
    output = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<img src=x' not in output
    assert '<script>alert(1)</script>' not in output
    assert '&lt;img' in output and '&lt;script&gt;' in output
    assert "last 72 hours" in output and "Missing feed (last: never)" in output
    assert "Disabled feed" not in output


def test_digest_without_topics_includes_new_articles(monkeypatch, capsys):
    config = {
        "settings.yaml": {"timezone": "UTC", "digest_local_hour": NOW.hour},
        "topics.yaml": {"topics": {}},
    }
    monkeypatch.setattr(send_teams_digest, "load_yaml", config.__getitem__)
    monkeypatch.setattr(send_teams_digest, "load_json", lambda *args: [article()])
    monkeypatch.setattr("sys.argv", ["send_teams_digest.py", "--dry-run"])

    assert send_teams_digest.main() == 0
    payload = json.loads(capsys.readouterr().out)
    body = payload["attachments"][0]["content"]["body"]
    assert body[1]["text"] == "All"
    assert "A headline" in body[2]["text"]

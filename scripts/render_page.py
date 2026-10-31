"""Render data/ into docs/index.html for GitHub Pages."""
from datetime import datetime, timedelta, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import DATA, DOCS, ROOT, load_json, load_yaml, local_tz
from digest_lib import parse_iso


def fmt_local(dt: datetime, tz) -> str:
    return dt.astimezone(tz).strftime("%b %d, %Y %I:%M %p %Z")


def build_citation(art: dict, pub_local: str, accessed: str) -> str:
    who = art.get("author") or art["outlet"]
    return f'{who}. "{art["title"]}." {pub_local}. {art["link"]}. Accessed {accessed}.'


def main() -> None:
    settings = load_yaml("settings.yaml")
    topics = list((load_yaml("topics.yaml").get("topics") or {}).keys())
    articles = load_json(DATA / "articles.json", [])
    status = load_json(DATA / "feed_status.json", {})
    tz = local_tz(settings)
    now = datetime.now(timezone.utc)
    accessed = now.astimezone(tz).strftime("%B %d, %Y")

    rows = []
    for art in articles:
        pub = parse_iso(art.get("published"))
        pub_local = fmt_local(pub, tz) if pub else "Date unknown"
        rows.append({
            **art,
            "pub_local": pub_local,
            "pub_date": pub.astimezone(tz).strftime("%Y-%m-%d") if pub else "",
            "citation": build_citation(art, pub_local, accessed),
            "search_text": f'{art["title"]} {art["outlet"]} {art.get("excerpt", "")}'.lower(),
        })

    stale_cutoff = now - timedelta(hours=settings.get("stale_feed_hours", 48))
    stale = []
    enabled_names = {f["name"] for f in load_yaml("feeds.yaml").get("feeds", [])
                     if f.get("enabled")}
    for name in sorted(enabled_names):
        entry = status.get(name, {})
        last = parse_iso(entry.get("last_success"))
        if not last or last < stale_cutoff:
            stale.append({"name": name, "last": fmt_local(last, tz) if last else "never"})

    env = Environment(loader=FileSystemLoader(ROOT / "scripts" / "templates"),
                      autoescape=select_autoescape(["html", "html.j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    html = env.get_template("index.html.j2").render(
        site_title=settings.get("site_title", "News Digest"),
        generated=fmt_local(now, tz),
        topics=topics,
        outlets=sorted({a["outlet"] for a in articles}),
        articles=rows,
        stale=stale,
        stale_feed_hours=settings.get("stale_feed_hours", 48),
        archive_days=settings.get("archive_days", 90),
    )

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").touch()
    print(f"rendered {len(rows)} articles to docs/index.html")


if __name__ == "__main__":
    main()

# News Digest

A static news page built from RSS feeds. A Python script runs hourly on GitHub Actions,
dedupes and tags articles, and publishes `docs/index.html` on GitHub Pages. A daily summary
is posted to a Microsoft Teams channel at 7:00 AM Central.

## Setup

1. **Replace `OWNER`** in `config/settings.yaml` (`user_agent`) with your GitHub username.
2. **Verify feeds.** Run `python scripts/fetch_feeds.py --check` locally. Set `enabled` and
   `verified` in `config/feeds.yaml`. Drop or fix any feed that fails.
3. **Set topics.** Fill in `config/topics.yaml`. Until then every article appears only under "All".
4. **Enable Pages.** Settings → Pages → Deploy from branch `main`, folder `/docs`.
5. **Create the Teams webhook.** In Teams, add a Workflow "Post to a channel when a webhook
   request is received" to the target channel and copy its URL. If your tenant has blocked
   Workflows, ask an admin to allow it.
6. **Add the secret.** Settings → Secrets and variables → Actions → `TEAMS_WEBHOOK_URL`.
7. **Run once.** Actions → "Update feeds and page" → Run workflow. Then Actions → "Teams daily
   digest" → Run workflow with `force` checked to test the Teams post.

## Local development

```
pip install -r requirements.txt
python -m pytest -q
python scripts/fetch_feeds.py
python scripts/render_page.py
python scripts/send_teams_digest.py --dry-run --force
```

## Files

- `config/` – feeds, topics, and settings. Edit these, not the code, when topics change.
- `scripts/digest_lib.py` – normalization, dedupe, tagging, pruning (pure, tested).
- `scripts/fetch_feeds.py` – fetches feeds and writes `data/articles.json` and `data/feed_status.json`.
- `scripts/render_page.py` – writes `docs/index.html`.
- `scripts/send_teams_digest.py` – posts the Teams Adaptive Card.
- `.github/workflows/` – hourly update, twice-daily digest check, monthly keepalive.

## Notes

- The archive keeps 90 days (`archive_days`). Only titles, links, dates, and short excerpts are stored.
- The repo is public, so never commit the webhook URL. It lives only in the repo secret.
- If every enabled feed fails, the update workflow fails. Partial failures show on the page.
- Respect each publisher's terms. This project links to articles and shows short excerpts only.

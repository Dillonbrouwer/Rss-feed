# News Digest

A static news page built from RSS feeds. A Python script runs hourly on GitHub Actions,
dedupes and tags articles, and publishes `docs/index.html` on GitHub Pages. A daily summary
is posted to a Microsoft Teams channel at 7:00 AM Central.

## Setup

1. **Check settings.** Set the title, timezone, and user agent in `config/settings.yaml`.
2. **Verify feeds.** Run `python scripts/fetch_feeds.py --check` locally. Set `enabled` and
   `status` in `config/feeds.yaml`. Investigate feeds that fail; other feeds keep updating.
3. **Set topics (optional).** Fill in `config/topics.yaml`. With no topics, the page and
   Teams digest show all articles under "All".
4. **Enable Pages.** Settings → Pages → Build and deployment → Source → **GitHub Actions**.
   If this repo currently publishes from `main` / `/docs`, switch it to GitHub Actions.
   The update workflow deploys `docs/` directly; a bot commit alone does not trigger a
   branch-based Pages build.
5. **Allow archive updates.** Settings → Actions → General → Workflow permissions →
   **Read and write permissions**. The update workflow pushes the archive to `main`;
   branch protection must allow those bot pushes before scheduling updates.
6. **Run once.** Actions → "Update feeds and page" → Run workflow on `main`.
   Check that Fetch feeds and Deploy page complete, then open the Pages URL.

### Optional Teams delivery

1. **Create the Teams webhook.** In Teams, add a Workflow "Post to a channel when a webhook
   request is received" to the target channel and copy its URL. If your tenant has blocked
   Workflows, ask an admin to allow it.
2. **Add the secret.** Settings → Secrets and variables → Actions → `TEAMS_WEBHOOK_URL`.
3. **Test delivery.** Actions → "Teams daily digest" → Run workflow with `force` checked.
   Without the secret, this optional workflow skips delivery and logs a warning.

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
- `.github/workflows/` – hourly update and Pages deployment, twice-daily digest check,
  and tests for pushes and pull requests. Successful hourly archive commits also keep
  the repository active, so no separate keepalive workflow is needed.

## Notes

- The archive keeps 90 days (`archive_days`). Only titles, links, dates, and short excerpts are stored.
- The repo is public, so never commit the webhook URL. It lives only in the repo secret.
- If every enabled feed fails, the update workflow fails. Partial failures show on the page.
- The update still publishes its health report and retained archive on total feed failure.
  `--check` returns a nonzero exit code if all enabled feeds fail or none are enabled.
- Politico returned HTTP 403 during verification on October 31, 2026. Its failure does
  not prevent the seven other enabled feeds from updating.
- The scheduled Teams checks cover 7:00 AM in `America/Chicago` across daylight saving
  time. If you change the timezone or digest hour, update the UTC schedules too.
- Respect each publisher's terms. This project links to articles and shows short excerpts only.

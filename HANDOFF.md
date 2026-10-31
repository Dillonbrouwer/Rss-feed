# Handoff: News Digest Project

**Repository:** https://github.com/Dillonbrouwer/Rss-feed (public, branch `main`)
**Live page (once Pages is enabled):** https://dillonbrouwer.github.io/Rss-feed/
**Owner:** Dillon Brouwer
**Time zone for all displayed and scheduled times:** America/Chicago

---

## 1. What this project is

A static news page built from RSS feeds, plus a daily summary posted to a Microsoft Teams channel.

- A Python script fetches about 10 news and policy feeds every hour on GitHub Actions.
- It removes duplicate articles, tags each one by topic keyword, and keeps a 90-day archive.
- It renders `docs/index.html`, which GitHub Pages serves. The page has topic filters, outlet filter, search, and a "Copy citation" button on each article.
- Every day at 7:00 AM Central, a Teams Workflows webhook receives an Adaptive Card with new items grouped by topic.

The project is for a team that works in Microsoft Teams. Topic areas for the season have **not been decided yet**, so the topic list is empty.

---

## 2. Current status (as of handoff)

| Item | Status |
|---|---|
| Code written (fetch, dedupe, tag, render, Teams digest) | Done |
| Unit tests (9 tests, `tests/test_digest_lib.py`) | Passing locally |
| Render and Teams dry-run locally | Verified |
| Live feed fetch | **Not verified.** The build environment could not reach publisher sites. Only Dillon's Mac or GitHub Actions can confirm feeds. |
| Repo contents uploaded to `main` | Done by Dillon by manual upload (verify with `git log` or the GitHub UI) |
| `OWNER` placeholder in `config/settings.yaml` | Dillon was asked to replace it with `Dillonbrouwer`. **Verify it was changed.** |
| GitHub Pages enabled (main, `/docs`) | **Verify.** Dillon was asked to enable it. |
| First successful workflow run | **Not yet confirmed.** The page was still empty at last check. |
| `TEAMS_WEBHOOK_URL` secret | **Not yet confirmed.** Needed for the digest only. |
| Topic keywords (`config/topics.yaml`) | **Empty.** Blocked on Dillon deciding topics. |
| Feed URLs | 5 confirmed, 3 need a live check, 2 disabled (see section 5). |

---

## 3. Repository layout

```
Rss-feed/
├── README.md                    # setup steps for the owner
├── requirements.txt             # feedparser, PyYAML, Jinja2, requests, tzdata, pytest
├── .gitignore
├── config/
│   ├── settings.yaml            # timezone, archive days, user_agent, digest hour, etc.
│   ├── feeds.yaml               # feed list with enabled and status fields
│   └── topics.yaml              # topic -> keywords; currently empty ({})
├── scripts/
│   ├── common.py                # paths, YAML/JSON helpers, timezone helper
│   ├── digest_lib.py            # PURE logic: normalize URL, parse feed, dedupe, tag, prune
│   ├── fetch_feeds.py           # network: fetch feeds, merge archive, write data/
│   ├── render_page.py           # writes docs/index.html from data/
│   ├── send_teams_digest.py     # posts Adaptive Card to Teams webhook
│   └── templates/index.html.j2  # page template (filters, search, copy button)
├── data/
│   ├── articles.json            # 90-day archive (generated)
│   ├── feed_status.json         # per-feed last success and last error (generated)
│   └── last_keepalive.txt       # written monthly by keepalive workflow
├── docs/                        # GitHub Pages source (generated)
│   ├── index.html
│   └── .nojekyll
├── tests/
│   ├── conftest.py              # adds scripts/ to import path
│   ├── test_digest_lib.py
│   └── fixtures/sample_feed.xml
└── .github/workflows/
    ├── update.yml               # hourly: test, fetch, render, commit data/ and docs/
    ├── digest.yml               # 12:00 and 13:00 UTC; script posts only at 7 AM Central
    └── keepalive.yml            # monthly commit so GitHub doesn't disable the schedule
```

### Key design points

- **`digest_lib.py` has no network or file I/O.** Keep it that way so it stays testable.
- **Article ID = normalized link** (lowercase host, no `www.`, no tracking params such as `utm_*` and `fbclid`, no trailing slash).
- **Dedupe:** by ID, then by normalized title plus UTC publish date (catches syndicated copies with different URLs). The earliest-seen record is kept, and other outlets are listed in `also_reported_by`.
- **Re-tagging:** every run re-tags the whole archive, so editing `topics.yaml` takes effect on old articles too.
- **Pruning:** articles older than `archive_days` (90) by `first_seen` are dropped.
- **Feed failures are isolated.** One feed failing logs a warning and the run continues. The run exits with an error only if every enabled feed fails.
- **Digest timing:** GitHub cron is UTC only. 7:00 AM Central is 12:00 UTC in daylight time and 13:00 UTC in standard time. The workflow runs at both times, and the script exits early unless the local hour is 7. Pass `--force` to bypass this.

---

## 4. Configuration reference

### `config/settings.yaml`
| Key | Current value | Notes |
|---|---|---|
| `site_title` | "News Digest" | Shown on the page |
| `timezone` | America/Chicago | Used for displayed dates and digest hour |
| `archive_days` | 90 | Retention window |
| `user_agent` | `news-digest/1.0 (+https://github.com/OWNER/news-digest)` | **Must replace `OWNER`** |
| `request_timeout_seconds` | 20 | Per feed |
| `stale_feed_hours` | 48 | Feeds with no success in this window get a warning on the page |
| `digest_local_hour` | 7 | Local hour the Teams digest posts |
| `digest_items_per_topic` | 5 | Cap per topic in the card |
| `post_on_quiet_days` | false | If true, posts a one-line note when nothing new matched |

### `config/feeds.yaml`
Each feed has `name`, `url`, `enabled`, and `status` (`confirmed`, `check`, or `disabled`). Only `enabled: true` feeds are fetched.

### `config/topics.yaml`
Shape:
```yaml
topics:
  Elections:
    - election
    - ballot
  Trade:
    - tariff
    - export controls
```
Matching is case-insensitive with word boundaries. An article can have several tags. Untagged articles still appear under "All" on the page.

---

## 5. Feed status

| Outlet | URL | Status |
|---|---|---|
| BBC World | https://feeds.bbci.co.uk/news/world/rss.xml | confirmed (enabled) |
| NPR | https://feeds.npr.org/1001/rss.xml | confirmed (enabled) |
| The Guardian | https://www.theguardian.com/world/rss | confirmed (enabled) |
| Al Jazeera | https://www.aljazeera.com/xml/rss/all.xml | confirmed (enabled) |
| Foreign Policy | https://foreignpolicy.com/feed/ | confirmed (enabled) |
| Politico | https://www.politico.com/rss/politicopicks.xml | **check** (enabled; listing was old) |
| SCOTUSblog | https://www.scotusblog.com/feed/ | **check** (enabled) |
| The Conversation | https://theconversation.com/us/politics/articles.atom | **check** (enabled) |
| Lawfare | — | **disabled.** No working site feed found. Lawfare's podcasts use Acast. |
| Brookings | — | **disabled.** Site links to an RSS subscribe page; URL not found. |

Feed URLs came from third-party directories, not from a live fetch. Treat every URL as unverified until a real run shows items for it.

---

## 6. Operating the system

### Verify a feed locally
```bash
pip3 install -r requirements.txt
python3 scripts/fetch_feeds.py --check
```
Prints per-feed status without writing data.

### Full local run
```bash
python3 -m pytest -q
python3 scripts/fetch_feeds.py
python3 scripts/render_page.py
python3 scripts/send_teams_digest.py --dry-run --force   # prints the card, posts nothing
```

### Manual GitHub runs
- **Actions → Update feeds and page → Run workflow** (fetches, renders, commits).
- **Actions → Teams daily digest → Run workflow**, check `force` to post now.

### Setup steps the owner still needs (if not yet done)
1. Replace `OWNER` in `config/settings.yaml` with `Dillonbrouwer`, then commit.
2. Settings → Pages → Deploy from branch `main`, folder `/docs`.
3. Settings → Secrets and variables → Actions → New secret `TEAMS_WEBHOOK_URL`. Create the webhook in Teams first: channel → Workflows → "Post to a channel when a webhook request is received."
4. Run the update workflow once and read the log.

### Reading the log
- `WARNING <feed> failed: ...` means that feed is broken. Fix the URL or disable it.
- `archive now holds N articles` with N = 0 means nothing was collected.
- `every enabled feed failed` means the run exited with an error. Usually a network or URL problem.

---

## 7. Known issues and gaps

1. **Feed URLs are unverified** (section 5). The first real run is the test.
2. **Lawfare and Brookings have no feed.** Each needs a verified URL or should stay out.
3. **GitHub Actions versions are tags, not SHAs.** The plan called for pinning `actions/checkout` and `actions/setup-python` to commit SHAs. This is not done. Pin before relying on the workflows.
4. **Teams delivery is untested live.** The Adaptive Card and webhook format were written from memory of the Workflows webhook format. Test with `--force` on the digest workflow. If the post fails, check whether the tenant allows Workflows webhooks.
5. **Topics are empty**, so the digest always reports "no new items." This is expected until Dillon defines topics.
6. **The page is empty until the first successful run.** The first run also shows every feed as stale, because no feed has a recorded success yet.
7. **`requirements.txt` pins exact versions** (feedparser 6.0.11, Jinja2 3.1.4, requests 2.32.3, etc.). They were chosen to be widely compatible, not checked against the latest releases.
8. **The public repo exposes everything in it.** The webhook URL must stay in the Actions secret. Never commit it to any file.
9. **Scheduled workflows can be disabled after 60 days of inactivity.** The monthly keepalive commit prevents this. Confirm it runs.
10. **Publisher terms:** the project shows titles, links, dates, and short excerpts (300 characters max). Do not add full-text republishing.

---

## 8. Decisions already made by the owner

- Host: GitHub Pages, free tier. Repo is public.
- Chat platform: Microsoft Teams (not Slack or Discord).
- Archive: 90 days.
- Time zone: Central Time.
- Topic areas: TBA by owner.

## 9. Open decisions for the owner

1. Topic areas and keywords for this season.
2. Whether quiet days should post a note (`post_on_quiet_days`).
3. Whether to add a custom domain (optional, free).

---

## 10. Suggested first steps for the incoming agent

1. Check the repo on GitHub. Confirm `OWNER` is replaced, Pages is enabled, and the secret exists.
2. Open the Actions tab. Confirm the update workflow ran and read the per-feed log lines.
3. For each feed that failed, replace the URL or set `enabled: false`. Update `status` to `confirmed` once a run shows items.
4. Pin the GitHub Actions to commit SHAs (known issue 3).
5. Once Dillon sends the topic list, fill in `config/topics.yaml`, then run the update workflow and check that tags appear on the page.
6. Test the Teams digest with `--force` and fix the card format if needed.
7. Keep `digest_lib.py` pure, and keep new tests in `tests/`.

## 11. Working rules

- Make changes on a branch and open a pull request unless the owner asks for direct commits to `main`.
- Never commit secrets, webhook URLs, or tokens.
- Do not force-push `main`.
- Keep excerpts short. Do not reproduce full articles.
- Check any new feed for its publisher's terms before adding it.

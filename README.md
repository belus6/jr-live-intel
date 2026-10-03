# Juniper Resilience Live Intelligence (free tier)

A live security-event feed that costs nothing to run. Every 15 minutes, GitHub's free automation pulls public sources (government travel advisories, disaster and health alerts, international news, and GDELT's global news monitoring). It turns each item into a standard event, tags the country and city, scores severity from 1 to 5, grades confidence on the Admiralty scale, merges duplicate reports of the same event, and publishes a live dashboard. The Global Risk Matrix is hosted alongside it.

## What you get

- **Live dashboard** (`docs/index.html`): a map, a filterable event feed, a 24-hour brief by region, and source health.
- **Watchlist**: put your travellers, events and offices in `config/watchlist.json`. Matching events are flagged on the dashboard, and severity 4 and 5 events can be pushed to Slack, Teams or Discord.
- **Archive**: every event ever seen is kept in `docs/data/archive/` by month, for trend analysis later.
- **Risk matrix** (`docs/matrix.html`): the full Global Risk Matrix 2026, served from the same site.

## Set it up (about 20 minutes, no coding)

1. **Create a free GitHub account** at github.com if you don't have one.
2. **Create a new repository.** Click New, name it something like `jr-live-intel`, and choose Private or Public.
   - GitHub Pages on a private repository needs a paid plan. Public is free, but anyone with the link can see it.
   - If the feed should stay private, keep the repository private and see "Keeping it private" below.
3. **Upload the files.** Open the repository, click "Add file", then "Upload files", and drag in everything from this folder.
   - Keep the folder structure, including the hidden `.github` folder.
   - If your computer hides it, upload `live-intel.yml` into a folder you create named `.github/workflows`.
4. **Allow the automation to save results.** Go to Settings, then Actions, then General. Under "Workflow permissions", choose "Read and write permissions" and save.
5. **Turn on the website.** Go to Settings, then Pages. Set Source to "Deploy from a branch", Branch to `main`, and folder to `/docs`. Save. After a minute or two GitHub shows your address, for example `https://yourname.github.io/jr-live-intel/`.
6. **Run it the first time.** Go to the Actions tab, open "Live intelligence feed", and click "Run workflow". When it finishes (about a minute), refresh your dashboard. The sample-data banner disappears and live events appear.

From then on it runs every 15 minutes on its own.

**Running cost check:** on a public repository, GitHub automation minutes are free and unlimited. On a private repository the free allowance is 2,000 minutes a month. Each run is billed as at least one minute, so every 15 minutes is about 2,900 minutes a month, which goes over the free allowance. For a private repository, either change the schedule in `.github/workflows/live-intel.yml` to `*/30 * * * *` (about 1,450 minutes, inside the allowance) or expect a small monthly charge.

## Optional: alerts to Slack, Teams or Discord

1. Create an incoming webhook in your chat tool. In Slack: Apps, then Incoming Webhooks.
2. In GitHub, go to Settings, then Secrets and variables, then Actions, then New repository secret.
3. Name it `ALERT_WEBHOOK_URL` and paste the webhook address.

You'll get one message per new severity 4 or 5 event at a watched location.

## Day-to-day use

- **Change what you watch:** edit `config/watchlist.json` on GitHub (click the file, then the pencil icon). City names must match the matrix's city list in `pipeline/cities.json`.
- **Add or remove sources:** edit `config/sources.json`.
  - Any RSS feed can be added with `"type": "rss"`.
  - Give each source a tier: A official, B established news, C regional or aggregator, D social or unverified.
  - Set `"enabled": false` to switch a source off.
  - The Sources tab on the dashboard shows which ones worked on the last run.
- **Telegram and Bluesky** are included but switched off.
  - Telegram reads a public channel's web preview. Add the channel name and enable it.
  - Bluesky's public search may require login in future.
  - Both are tier D: treat them as tips, not facts.

## How scoring works

- **Category:** keyword rules sort each item into one of these categories:
  - armed conflict
  - terrorism
  - protest and unrest
  - crime
  - political
  - natural hazard
  - health
  - transport disruption
  - cyber
  - travel advisory

  Items with no security relevance or no recognisable place are dropped.
- **Location:** cities in the matrix and places after words like "in", "near" or "hit" win over nationality words. "Israeli strikes hit southern Lebanon" is placed in Lebanon.
- **Severity (1 to 5):**
  - Each category has a starting level, for example terrorism 4 and protest 2.
  - It rises with reported deaths (1 or more, 10 or more, 50 or more) and with escalation words like curfew, coup, state of emergency, airport closed or evacuation.
  - Earthquakes are scored by magnitude, GDACS by its red, orange or green alert, and advisories by level.
- **Confidence:** the Admiralty grade. The letter is the most reliable source, from A (official) to D (social). The number is corroboration:
  - 1: an official source, or three or more independent sources
  - 2: two independent sources
  - 3: one established outlet
  - 4: one regional or aggregated report
  - 5: one unverified post

  Reports of the same event within 12 hours are merged, so corroboration grows as more outlets report it.
- **Expiry:** events drop off the live feed after a set time. Protests and crime after 48 hours, conflict after 72, hazards after 5 days, health after 14 days, advisories after 30. Everything stays in the archive.

## Limits to know

- This is automated triage, not verified intelligence. Confirm grades 4 and 5 with the original source before acting, and keep a person reviewing before anything goes to a client.
- Keyword rules miss some events and mis-tag others, especially sarcasm, historical references and non-English text beyond Spanish and French. The usual next step is adding an AI classification step (for example the Claude API), which costs a small amount per run.
- GitHub can delay scheduled runs by several minutes at busy times. For true minute-by-minute alerting, a paid feed or server is needed.
- Respect each source's terms. These feeds are public, but GDELT and ACLED have their own licences for commercial reuse.

## Keeping it private

GitHub Pages on a private repository needs a paid plan. Free alternatives:

- **Cloudflare Pages** with Cloudflare Access: free for small teams, login-protected.
- **Netlify** with password protection: a paid feature.

Either can host the `docs` folder while the GitHub automation keeps updating it.

## Licence and copyright

- **This repository is proprietary.** `LICENSE` reserves all rights to Juniper Resilience LLC. A public repository lets people view the files, but does not give them permission to reuse them.
- **Content from news outlets:** only headlines and links are stored. Article text is never stored. Official government feeds also keep a short summary.
- **Source terms:** `NOTICE.md` lists every source and software component with the terms to check before any commercial redistribution.

## Test without internet

```
pip install -r requirements.txt
python pipeline/run.py --offline
```

This uses the sample files in `tests/fixtures` and writes sample data the dashboard can show.

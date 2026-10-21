# Working in this repository

The Basketball Injury Project: an NBA injury-risk model, tests of the plays that come before injuries, player
profiles, and a public site in `docs/`. `README.md` explains each part. The current task is in
`specs/injury-news.md`.

## Running things

- Use Python 3.11 or newer. Run `pip install -r requirements.txt`, and set `PYTHONPATH=src` for every command.
- Every step is `python -m injury_risk <step>`; the README's table lists them.
- Run the tests with `python -m unittest discover -s tests`. They must all pass before you call anything done.
- Build the site with `python -m injury_risk site`. Its link preview needs Chrome; from Python,
  `site_build.build(card=False)` skips it.

## Rules

- Never commit, push or open a pull request unless the owner asks.
- `data/` holds downloads and caches and is never committed. Put anything you download there; the news work goes in
  `data/news/`.
- Never publish other people's text: Covers' notes, news articles or quotes. The site carries facts and links only.
- Follow each site's robots.txt and terms. Don't get around paywalls or logins, and pause between requests to the
  same site.
- Don't change the site's look (`docs/`, `src/injury_risk/site/`) unless asked. `DESIGN.md` is its design system.
- Match the surrounding code: its names, how much it comments, and plain-words comments.
- Refer to players as they/them in prose.
- Don't hand-edit data the analysis builds. Change the code that makes it and rerun the step.

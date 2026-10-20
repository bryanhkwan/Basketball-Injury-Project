---
version: beta
name: Basketball-Injury-Project
description: The design system of the Basketball Injury Project's public site, in the same family as Bryan Kwan's portfolio (bryanhkwan.github.io/portfolio). The overview (docs/index.html) is always dark, like a broadcast graphics package. A near-black navy ground with an ice-blue court floor, huge uppercase Barlow Condensed headlines with one gold phrase, square gold buttons and small monospace labels. Real pieces of the dashboards carry the story. The dashboards (docs/dashboard.html) are the working tool, a navy-tinted frame around a white sheet (dark in dark mode), where colour goes on data and nowhere else.

colors:
  # brand
  navy: "#071b32"
  gold: "#ffd200"
  gold-hover: "#ffe15c"
  on-gold: "#091428"
  ice: "#85bfff"               # the court lines, hover rings, the live board's label
  # overview (always dark)
  home-paper: "#030b1a"
  home-paper-2: "#061428"      # alternate sections
  home-panel: "#0a1a30"
  home-panel-2: "#0c1e36"      # the live board
  home-line: "#1a2c43"
  home-line-strong: "#2d4a6b"
  home-ink: "#f4f7fb"
  home-ink-2: "#c0cee0"        # running text
  home-ink-3: "#99abc4"        # meta, labels
  home-hurt: "#ff8a80"         # a new injury, as text on navy
  # dashboards, light
  frame: "#eef2f6"
  surface: "#ffffff"
  border: "#e1e7ee"
  rule: "#edf1f5"
  ink: "#12263b"
  muted: "#53616f"
  primary: "#071b32"
  negative: "#c4242a"
  pill-negative-bg: "#fdecea"
  pill-negative-ink: "#8a1c17"
  # dashboards, dark (prefers-color-scheme: dark)
  dark-frame: "#051426"
  dark-surface: "#0a1f38"
  dark-border: "#1b3556"
  dark-ink: "#f4f7fb"
  dark-primary: "#ffd200"
  # data
  chart-nba: "#2a78d6"         # light; #3987e5 on dark grounds, the overview included
  chart-college: "#ffd200"     # college results on dark grounds; #d99a00 on the light dashboards, #eda100 in the light report
  chart-muted: "#c3ccd6"       # light; #3a5373 on dark

typography:
  home-display:
    fontFamily: Barlow Condensed, Arial Narrow, Segoe UI, sans-serif
    fontSize: clamp(64px, 8.4vw, 136px)
    fontWeight: 800
    lineHeight: 0.86
    textTransform: uppercase
  home-heading:
    fontFamily: Barlow Condensed, Arial Narrow, Segoe UI, sans-serif
    fontSize: clamp(42px, 5.2vw, 76px)
    fontWeight: 800
    lineHeight: 0.92
    textTransform: uppercase
  home-figure:
    fontFamily: Barlow Condensed, Arial Narrow, Segoe UI, sans-serif
    fontSize: clamp(104px, 12vw, 176px)
    fontWeight: 800
    lineHeight: 0.82
  home-kicker:
    fontFamily: Consolas, SFMono-Regular, ui-monospace, monospace
    fontSize: 13px
    fontWeight: 600
    letterSpacing: 0.14em
    textTransform: uppercase
  home-lead:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.62
  home-body:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.65
  app-title:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 24px
    fontWeight: 600
    lineHeight: 30px
  app-body:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
  app-meta:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 12px
    lineHeight: 16px

rounded:
  button: 4px                  # square-cornered, like the portfolio's buttons
  panel: 16px                  # overview panels and the app's sheet
  board: 18px                  # the live board
  card: 10px                   # dashboard cards
  control: 6px
  chip: 999px                  # player chips and kind-of-injury tabs

spacing:
  page-pad: clamp(18px, 4vw, 40px)
  wrap: 1200px
  section: clamp(72px, 8vw, 112px)
  nav: 72px                    # 64px on a phone
  app-canvas: 24px
  app-card-gap: 16px

components:
  nav:
    background: transparent, then "rgba(3, 11, 26, 0.94)" with a bottom line once the page scrolls
    height: "{spacing.nav}"
  button-gold:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.on-gold}"
    rounded: "{rounded.button}"
    height: 52px
  button-line:
    borderColor: "{colors.home-line-strong}"
    textColor: "{colors.home-ink}"
    rounded: "{rounded.button}"
    height: 52px
  live-board:
    backgroundColor: "{colors.home-panel-2}"
    borderColor: "{colors.home-line-strong}"
    rounded: "{rounded.board}"
    marker: data-ui
  panel:
    backgroundColor: "{colors.home-panel}"
    borderColor: "{colors.home-line}"
    rounded: "{rounded.panel}"
  app-sheet:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.panel}"
  injury-pill:
    backgroundColor: "{colors.pill-negative-bg}"
    textColor: "{colors.pill-negative-ink}"
    rounded: "{rounded.chip}"
---

## Overview

The site serves two readers. The first clicks a LinkedIn link and should know in five seconds what this is, and want to touch it. The second checks the work. The overview speaks to the first: a big question ("Who gets hurt next?"), one sentence on what was built and how well it did, and the live risk board right beside it. Below that come the proof, the four questions the project answers (each with a real chart), how it was built, and who built it. The dashboards serve the second reader with quiet working screens.

The look comes from the user's own brand: the portfolio's near-black navy, gold actions and monospace labels, and the report's and LinkedIn images' uppercase Barlow Condensed headlines. The hero's court floor echoes the portfolio's wireframe arena.

## Colors

- **Grounds:** the overview is always dark. `home-paper` `#030b1a`, with `home-paper-2` for alternate sections and navy panels (`home-panel`) with a 1px line. The dashboards follow the reader's light or dark setting.
- **Gold** `#ffd200` is for actions (buttons, links) and one phrase per headline ("hurt next?", "See who it flagged."). It is also the record figure and the riskiest group's bar, and the college series. On white, gold text uses `#806200`.
- **Ice blue** `#85bfff` draws the court, the hover rings and the live board's label. It is chrome, not data.
- **Data** is NBA blue: `#2a78d6` on light, `#3987e5` on dark. Comparisons are muted slate. A new injury is red, as `home-hurt` text on the overview and pale pills in the dashboards.
- **College** results are gold (`chart-college`), the one second data hue, used only where the two leagues are compared.

## Typography

- **Barlow Condensed 800, uppercase**, for every headline and big figure. It is the broadcast voice of the report and the LinkedIn images.
- **DM Sans** for everything people read, and every number in a table or chart (tabular figures).
- **A monospace** (Consolas, SF Mono, the system's) only for small tracked labels above headings and on the live board, as on the portfolio.
- Headlines stay at two lines or fewer at every width. Typographic apostrophes (’), and an ellipsis character (…).

## Layout

- **Overview:** one centred 1200px column with `page-pad` sides.
  - The hero is two columns: copy and stats on the left, the live board on the right. The court floor is clipped to the hero's lower 58% and fades upward.
  - Sections alternate between `home-paper` and `home-paper-2`.
  - The four questions alternate their copy and their chart from side to side.
- **Dashboards:** a 236px sidebar and a 48px top bar on the tinted frame, with the work on a sheet inset 8px. Each view has a title row with its finding, a KPI strip, then cards on a 12-column grid with a 16px gap.

## Elevation & Depth

On the overview, depth comes from a lighter panel on the dark ground. Only the live board gets a deep shadow and a soft blue glow, because it is the product shot. The hero and the closing band have a soft radial light. The dashboards have no shadows at rest; only the search results and tooltips float.

## Shapes

- Square-cornered buttons (4px).
- Panels: 16px on the overview and for the app's sheet; the live board is 18px.
- Dashboard cards are 10px.
- Chips and tabs are full pills.

## Components

### Overview
- **Live board:** a real piece of the dashboard, with a pulsing gold dot, a night stepper and picker, five rows and a summary line in a live region.
  - Each row shows the rank, the player, the matchup with what happened (red if hurt), a blue chance bar and the percentage.
  - On short desktop screens it shows four or three rows.
- **Hero stats:** four figures divided by lines: reports read, injuries studied, AUC, and the top-vs-bottom ratio in gold.
- **The record:** the 5.3× figure with a three-bar ladder, the calibration chart, and every night of the season as bars (click a night to open it).
- **Feature rows:** a kicker, a headline, copy, check-mark ticks, a gold text link, and a live chart panel.
  - The panels: player chips over a risk timeline; kind-of-injury tabs over ranked findings; paired bars for the injury moments; NBA-vs-college dots on a log scale.
- **Steps:** four panels, each a big number, a monospace step name and one sentence. Below them, "What it can't tell you".

### Dashboards
KPI strips, the board table (rank, player link, chance and bar, the top two reasons, an outcome pill), the season strip, ratio rows on a log scale, and charts from `charts.js` with 3 to 5 faint gridlines, 2px lines and a bare tooltip.

The NBA vs college view adds two pieces:
- **League rows** (`Site.vsRows`): two dots with their likely ranges on one log scale, the NBA's in blue above and college's in gold below. The 1× line marks no difference.
- **The agreement scatter** (`Charts.logScatter`): the NBA's ratio across and college's up, on matching log scales.
  - Faint shading marks the two corners where both leagues point the same way, and a dashed line marks where they are equal.
  - Dots with a clear NBA signal are blue; the rest are muted, underneath.
  - One hover layer finds the nearest dot. Its list below the chart is the accessible version.

## Do's and Don'ts

### Do
- Lead with the question and the proof, and show the product in the first screen.
- Use one gold phrase per headline, and gold for actions.
- Give every relative figure its baseline ("against 15.6% for everyone").
- Name NBA players; keep college athletes as totals only.
- Keep motion to the court drawing itself, entrances and hover feedback, all of them off under reduced motion.

### Don't
- Don't put gold on long text, or colour on chrome in the dashboards.
- Don't use a second data hue for one series, or colour a change by direction instead of whether it is good or bad.
- Don't use stock photographs of people.
- Don't let a headline run past two lines.

## Responsive Behavior

- **Overview, 1080px and below:** the hero stacks (copy, then the board), and every grid becomes one column.
- **Overview, 760px and below:** the nav keeps only the brand and the Dashboards button. The stats become 2×2, the buttons stretch to full width, and the board's bars hide while its outcomes wrap.
- **Dashboards, 1100px and below:** the sidebar folds into a menu. At 640px tables become two-line rows and controls wrap.

## Iteration Guide

- Tokens: `src/injury_risk/site/site.css` (`:root` and the `.home` set). The overview's styles are in the same file and the dashboards' in `app.css`. Charts read the CSS variables.
- Build with `PYTHONPATH=src python -m injury_risk site`. It writes `docs/data/*.json`, renders `docs/index.html` with every figure from the data, copies the dashboards, renders the report and the link preview.
- Check with tasteskill's inspector, allowing the brand devices: `--allow eyebrow,mono,micro-label,gradient,shadow,hairline,outlined-box,font-count,font-fallback,card-rows`. Use `--app` for the dashboards. Then click through in a real browser (playwright-cli).

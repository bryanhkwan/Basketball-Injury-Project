---
version: alpha
name: Basketball-Injury-Project
description: The design system of the Basketball Injury Project's public site. Two layouts share one brand. The overview (docs/index.html) reads like a printed annual in two colours, Midnight Blue and Rocket Gold, on white paper. The dashboards (docs/dashboard.html) are a working tool, a navy-tinted frame around a white sheet, where colour goes on data and nowhere else. Barlow Condensed sets display type; DM Sans sets everything people read.

colors:
  # brand
  navy: "#071b32"
  gold: "#ffd200"
  gold-ink: "#806200"          # gold as text on paper (5.3:1)
  # page, light
  paper: "#ffffff"
  tone: "#eef2f6"              # one step from paper: tiles, the stage, the app frame
  tone-2: "#e1e8ef"            # a second step: hover, alternate bands
  ink: "#12263b"
  ink-soft: "#4d5b6a"
  block: "#071b32"             # navy tiles, buttons, selected tabs
  field: "#071b32"             # a whole section in navy
  on-field: "#f4f7fb"
  on-field-soft: "#b4c5da"
  # app, light
  frame: "#eef2f6"
  surface: "#ffffff"
  raised: "#f5f7fa"
  active: "#dfe6ee"            # the active nav pill
  border: "#e1e7ee"            # card and sheet edges, about 1.2:1 on white
  rule: "#edf1f5"              # row rules inside tables
  control: "#c9d2dc"           # inputs and outlined buttons
  muted: "#53616f"
  faint: "#5c6876"
  primary: "#071b32"
  on-primary: "#ffffff"
  positive: "#247b50"
  negative: "#c4242a"          # a new injury
  pill-negative-bg: "#fdecea"
  pill-negative-ink: "#8a1c17"
  pill-neutral-bg: "#eef1f5"
  pill-neutral-ink: "#3d4a58"
  # data
  chart-nba: "#2a78d6"         # the one data hue: every main series
  chart-nba-soft: "#8db6ea"
  chart-college: "#eda100"     # college results, report page only
  chart-muted: "#c3ccd6"       # comparisons and the rest
  grid: "#e6ebf0"
  axis-ink: "#5c6876"
  # dark mode (prefers-color-scheme: dark)
  dark-paper: "#071b32"
  dark-tone: "#0d2744"
  dark-ink: "#f4f7fb"
  dark-ink-soft: "#b4c5da"
  dark-block: "#030d1b"
  dark-frame: "#051426"
  dark-surface: "#0a1f38"
  dark-border: "#1b3556"
  dark-primary: "#ffd200"      # the primary button turns gold with navy text
  dark-negative: "#ff7b72"
  dark-chart-nba: "#3987e5"
  dark-chart-college: "#c98500"
  dark-chart-muted: "#3a5373"

typography:
  page-figure:
    fontFamily: Barlow Condensed, Arial Narrow, Segoe UI, sans-serif
    fontSize: clamp(150px, 23vw, 380px)
    fontWeight: 600
    lineHeight: 0.8
    letterSpacing: -0.03em
  page-name:
    fontFamily: Barlow Condensed, Arial Narrow, Segoe UI, sans-serif
    fontSize: clamp(56px, 9.2vw, 170px)
    fontWeight: 600
    lineHeight: 0.86
    letterSpacing: -0.02em
  page-heading:
    fontFamily: Barlow Condensed, Arial Narrow, Segoe UI, sans-serif
    fontSize: clamp(38px, 4.2vw, 64px)
    fontWeight: 600
    lineHeight: 1
    letterSpacing: -0.01em
  page-statement:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 24px
    fontWeight: 500
    lineHeight: 1.3
  page-body:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.55
  page-small:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.5
  app-title:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 24px
    fontWeight: 600
    lineHeight: 30px
    letterSpacing: -0.01em
  app-card-title:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 16px
    fontWeight: 600
    lineHeight: 22px
  app-kpi:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 26px              # 34px for the screen's lead figure
    fontWeight: 500
    lineHeight: 32px
    fontFeature: tabular-nums
  app-body:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
  app-meta:
    fontFamily: DM Sans, Segoe UI, system-ui, sans-serif
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  app-wordmark:
    fontFamily: Barlow Condensed, Arial Narrow, sans-serif
    fontSize: 18px
    fontWeight: 700
    lineHeight: 1.05

rounded:
  page: 0px                    # every tile, field, band and button on the overview is square
  sheet: 16px                  # the app's white sheet and the live pieces of it on the overview
  card: 10px
  control: 6px
  segmented: 8px
  pill: 999px

spacing:
  margin: clamp(16px, 2.2vw, 32px)       # the page's one pair of outer margins
  gap: clamp(12px, 1.7vw, 24px)          # the 12-column grid's gutter
  section: clamp(96px, 12vw, 176px)      # between overview sections
  tile-gap: 8px                          # inside the hero board (6px on a phone)
  app-canvas: 24px                       # inside the sheet (16px on a phone)
  app-card-gap: 16px
  app-card-pad: 18px 20px
  app-row: 44px                          # table rows; two-line rows grow to about 52px
  sidebar: 236px
  topbar: 48px

components:
  hero-tile:
    backgroundColor: "{colors.tone}"
    rounded: "{rounded.page}"
    padding: 24px
  hero-statement-dark:
    backgroundColor: "{colors.block}"
    textColor: "{colors.on-field}"
    typography: "{typography.page-statement}"
  hero-statement-gold:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.navy}"
    typography: "{typography.page-statement}"
  page-button:
    backgroundColor: "{colors.block}"
    textColor: "#ffffff"
    rounded: "{rounded.page}"
    height: 48px
    padding: 0 22px
    typography: "{typography.page-small}"
  record-field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.on-field}"
    figureColor: "{colors.gold}"
  finding-band:
    backgroundColor: "{colors.tone}"     # alternates with tone-2
    minHeight: 76px
    gap: 4px
  live-sheet:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.sheet}"
    marker: data-ui
  app-frame:
    backgroundColor: "{colors.frame}"
  app-sheet:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.sheet}"
    inset: 0 8px 8px 0
  app-card:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.card}"
    padding: "{spacing.app-card-pad}"
  app-nav-active:
    backgroundColor: "{colors.active}"
    textColor: "{colors.ink}"
    rounded: 8px
  app-primary-button:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.control}"
    height: 32px
  injury-pill:
    backgroundColor: "{colors.pill-negative-bg}"
    textColor: "{colors.pill-negative-ink}"
    rounded: "{rounded.pill}"
    height: 22px
---

## Overview

The site has one job for two kinds of visitor: someone who clicks a link and wants to see in five seconds what this is, and someone who wants to check the work. The overview answers the first with a printed-annual layout: the project's name set large, a live risk board in the first screen, and whole sections in solid navy or gold. The dashboards answer the second with quiet working screens, where the only strong colour is on the data.

The idea of the overview: each night of the 2025-26 season, the model's twelve picks and what happened to them, becomes the annual's table of results, a report card the reader can turn night by night.

## Colors

### Brand
- **Midnight Blue** `#071b32` and **Rocket Gold** `#ffd200` are the two print colours. Navy carries tiles, buttons, the record section and the footer. Gold is kept for moments: the mark, the gold statement tile, the record figure, the place links in the footer and the marker on the selected dashboard.
- Gold is never text on white. Where gold must be read on paper, use `gold-ink` `#806200`.

### Surfaces
- The page is white paper with one tone step, `tone` `#eef2f6`, for tiles and the stage, and a second, `tone-2`, for hover and alternating bands.
- The app sits on a navy-tinted frame (`frame`) with the work on a white sheet. Cards are white with a whisper border (`border`, about 1.2:1).

### Data
- **One data hue:** NBA blue `#2a78d6` (`#3987e5` in dark mode) on the main series of every chart: the selected night, the chance bars, the player's line, the "more likely" dots, the injury-exit bars.
- Everything else in a chart is `chart-muted` or ink. Comparisons are grey, never a second hue.
- **College gold** `#eda100` appears only in the injury-moment report, for college results.
- **A new injury** is the negative red `#c4242a`, as a pale pill with dark text or a small dot. Never more than one red mark per row.

### Dark mode
Dark mode is selected, not inverted: paper becomes Midnight Blue, navy blocks become a deeper `#030d1b` so they still read as blocks, the primary button turns gold with navy text, and the data hue lifts to `#3987e5`.

## Typography

### Faces
- **Barlow Condensed** (600; 700 for the app wordmark) for display: the name, the record figure, section headings, the dashboard names on the overview and the footer's places.
- **DM Sans** (400, 500, 600) for everything people read, and for every number in a table or chart.
- Two faces only. No monospace anywhere, no italics for emphasis, no all-caps labels.

### Hierarchy
- The overview uses six steps: figure (23vw), name (9.2vw), heading (4.2vw), statement (24px), body (18px), small (15px).
- The dashboards use app sizes: title 24px, card title 16px, KPI 26px (34px for the screen's lead figure), body 14px, meta 12px.

### Principles
- Sentence case everywhere, headings two lines or fewer at every width.
- Tabular figures on every number that is compared or updates; numbers right-aligned in tables.
- Typographic apostrophes and quotes (’ “ ”), an ellipsis character (…), and a true minus where a sign matters.

## Layout

### The overview: a printed annual
- One 12-column grid with one pair of outer margins (`margin`). The main axis is the start of column 6: section headings begin on it, and columns 1 to 5 hold a side figure, a photograph or the tabs.
- Sections alternate between text pages on paper and full-bleed colour pages (the record in navy, the footer in navy).
- The hero is a two-by-two board of tiles with 8px gaps. The top-left tile holds the name, the top-right holds the live risk board, the bottom-left holds a photograph, and the bottom-right holds two statements, one navy and one gold.

### The dashboards: a framed sheet
- A 236px labelled sidebar and a 48px top bar share the tinted frame, with no line between them. The work sits on a white sheet inset 8px from the window's right and bottom edges.
- Each view opens with a title row (the h1, one sentence stating that view's finding, then the controls), then a divided KPI strip, then cards on a 12-column grid with one 16px gap.
- The screen's question is answered by its biggest block (the night's board, the player's line, the model comparison).

## Elevation & Depth

Nothing at rest has a shadow. Depth comes from one tone step (paper to tone, frame to sheet) or a whisper border. Only what floats gets a shadow: the player-search results and chart tooltips.

## Shapes

- The overview is square: tiles, fields, bands, buttons and photographs have no radius.
- The app is soft: the sheet is 16px, cards 10px, controls 6px, the segmented track 8px, and pills fully round.
- Pieces of the app shown on the overview keep the app's radii and borders. Their root carries `data-ui`.
- Photographs are greyscale (`grayscale(1) contrast(1.06)`), cropped with `object-fit: cover`, and credited in the footer.

## Components

### Overview
- **Live risk board** (hero, top-right): a real piece of the dashboard. It shows a night's top five (three or four on short screens), a stepper and night picker, and a summary line with a live region.
- **The record** (navy field): a two-to-five-word claim, one gold figure, a caption, and three bars of evidence. The photograph sits in the left zone.
- **Output index** (dashboards): five names set at heading size and used as tabs, with a short description and one button. The stage on the right holds the selected dashboard as a working sheet.
- **Kinds of injury**: tabs in a column, a side figure, and findings as alternating bands. Each band holds the ratio, the situation, what it is compared with, and the verdict.
- **Many into one**: a diagram of squares. Scattered report lines are pulled into a ribbon of player-games, then laid out as gold rows of a ranking.
- **Footer**: the name fitted to the content width, three places in gold, three link columns, then the credits.

### Dashboards
- **KPI strip**: one container split by 1px dividers. Each KPI is a label over a value over a grey phrase saying what it is against.
- **Board table**: rank, player (a link, with team vs opponent below), chance as a number and a blue bar, the top two reasons, and what happened (a red pill with the games missed, or grey "No new injury").
- **Season strip**: every night of 2025-26 as one bar. The chosen night is in blue and clicking a bar opens that night.
- **Ratio rows**: a ratio with its likely range on a shared log scale, marked at 1×. A filled blue dot means more likely, an open ring less likely, grey no clear difference.
- **Charts** come from `charts.js`: 3 to 5 faint gridlines, round ticks, 2px straight lines, square bars, a bare tooltip, and legends only for two or more series. Every swatch is the mark it explains.

## Do's and Don'ts

### Do
- Put colour on data, status and the one primary action, and keep the chrome neutral.
- State each screen's finding in its title row, with the baseline named ("against 15.6% of all players").
- Print real zeros, use a grey dash for a missing value, and size small numbers honestly.
- Name NBA players. The league's injury reports are public.
- Keep college athletes anonymous: totals only, no names, no lists of injured players.
- Credit every photograph on the page, with its licence.
- Refer to people with they/them in all copy.

### Don't
- Don't use gradients, glows, glass, or shadows on resting elements.
- Don't use eyebrow labels, tiny uppercase tracked labels, 01/02/03 numbering or monospace.
- Don't add a second data hue to a chart, and don't colour a change by its direction instead of whether it is good or bad.
- Don't use violet, indigo, or cream with terracotta.
- Don't round the overview's tiles or buttons, or square off the app's sheet and cards.
- Don't use stock photographs of people that could pass as the project's own.

## Responsive Behavior

- **Overview, 1100px and below**: the hero stacks the name across the width, then the board, then the photograph and statements. The dashboard names wrap onto lines and the kind tabs become a grid.
- **Overview, 640px and below**: the grid drops to four columns, the hero goes to one column (name, statements, board, photograph), and every block takes the full width.
- **Overview, short desktop screens** (815px tall or less): the live board shows four rows, and three at 733px, so its summary stays visible.
- **Dashboards, 1100px and below**: the sidebar folds into the top bar's menu button, which opens a full-screen sheet. Every card takes the full width except the small factor charts, which go two across.
- **Dashboards, 640px and below**: tables become two-line rows, the KPI strip becomes a two-column grid, and segmented controls wrap.

## Iteration Guide

- Tokens live in `src/injury_risk/site/site.css` (`:root`, with the dark set below it). The overview's styles are in the same file, and the dashboards' styles are in `app.css`. Charts read the CSS variables, so a token change reaches them.
- Build with `PYTHONPATH=src python -m injury_risk site`. It writes `docs/data/*.json`, renders `docs/index.html` with its figures filled from the data, copies the dashboards and assets, renders the report and the link preview.
- Check with the tasteskill gate: `lint.mjs` on the overview's files, `lint.mjs --app` on the dashboard's, then `inspect.mjs` (page) and `inspect.mjs --app`. The Windows machine this was built on asks for reduced motion and dark mode, so run the inspector with those set explicitly.
- Before shipping a change, click through it in a real browser (playwright-cli): night stepping, the dashboard previews, the kind tabs, the player search, and the phone menu.

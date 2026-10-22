// dashboard.js: the dashboards (dashboard.html). One view per question, chosen by the address: #board/2025-10-21,
// #board/2025-10-21/after, #players/1627936, #model/serious_g5, #factors, #when/muscle, #types/knee, #how, #careers/acl/2,
// #careers/college/acl, #college/ankle. Every view is drawn
// from the files in data/ (written by site_build.py) and keeps its state while the reader moves between nights,
// players or kinds of injury.
(() => {
  const { load, esc, pct, int, dec, signed, times, day, shortDay, longDay, dateOf, daysBetween, splitOutcome, bodyPart, dotRows, pairs, changeRows,
    vsRows } = window.Site;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const NAMES = { board: 'Risk board', players: 'Players', model: 'Model check', factors: 'What raises risk', when: 'When and who', types: 'Injury types',
    how: 'How it happened', careers: 'After an injury', college: 'NBA vs college' };
  const KINDS = [['any', 'Any injury'], ['muscle', 'Muscles'], ['sprain', 'Ankles'], ['contact', 'Knocks'], ['knee', 'Knees'], ['back', 'Backs'], ['other', 'Other']];
  const fail = (el, err) => { el.innerHTML = `<div class="empty error">Couldn’t load this view: ${esc(err.message)}. Reload the page to try again.</div>`; };
  const segmented = (label, items, on) => `<div class="segmented" role="group" aria-label="${esc(label)}">${items.map(([k, t]) => `<button type="button" data-key="${k}" aria-pressed="${k === on}">${esc(t)}</button>`).join('')}</div>`;
  const press = (root, key) => $$('.segmented button', root).forEach((b) => b.setAttribute('aria-pressed', b.dataset.key === key));
  const SEASON_END = 2026;                            // 2025-26, the season the boards show
  const seasonName = (y) => `${y - 1}-${String(y).slice(2)}`;

  // ======================================================================================================== board
  const board = {
    async init(el) {
      this.data = await load('board');
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="board-title">Risk board</h1><p class="sub" id="b-sub" aria-live="polite"></p></div>
          <div class="controls">
            ${segmented('When the board is scored', [['before', 'Before tip-off'], ['after', 'After the game']], 'before')}
            <button type="button" class="btn icon" id="b-prev" aria-label="Previous night">‹</button>
            <label class="sr-only" for="b-night">Night</label><select class="select" id="b-night"></select>
            <button type="button" class="btn icon" id="b-next" aria-label="Next night">›</button>
          </div>
        </div>
        <div class="kpis" id="b-kpis"></div>
        <div class="cards">
          <article class="card span-12">
            <header><h2 id="b-table-title">The night’s board</h2><p class="meta" id="b-table-meta"></p></header>
            <div class="table-wrap"><table class="data stackable board-data" id="b-table">
              <thead><tr><th class="n" scope="col">#</th><th scope="col">Player</th><th class="n" scope="col">Chance</th><th scope="col" class="bar-cell"><span class="sr-only">Chance as a bar</span></th><th scope="col">What pushed the score up</th><th scope="col" id="b-outcome-head">Next 5 games</th></tr></thead>
              <tbody></tbody></table></div>
          </article>
          <article class="card span-8">
            <header><h2>Every night of 2025-26</h2><p class="meta" id="b-strip-meta"></p></header>
            <div class="chart" id="b-strip"></div>
            <div class="prose" id="b-read" style="margin-top:14px"></div>
          </article>
          <article class="card span-4"><header><h2>Across 2025-26</h2><p class="meta" id="b-check-meta"></p></header><div id="b-check"></div><p class="note" id="b-check-note"></p></article>
        </div>`;
      $$('.segmented button', el).forEach((b) => b.addEventListener('click', () => this.go(this.day, b.dataset.key)));
      $('#b-night', el).addEventListener('change', (e) => this.go(this.nights[+e.target.value][0], this.mode));
      $('#b-prev', el).addEventListener('click', () => this.go(this.nights[this.at - 1][0], this.mode));
      $('#b-next', el).addEventListener('click', () => this.go(this.nights[this.at + 1][0], this.mode));
    },
    go(dayIso, mode) { location.hash = `board/${dayIso}${mode === 'after' ? '/after' : ''}`; },
    show(el, [dayArg, modeArg]) {
      const mode = modeArg === 'after' ? 'after' : 'before', m = this.data.modes[mode], nights = m.nights;
      if (mode !== this.mode) { this.mode = mode; this.nights = nights; $('#b-night', el).innerHTML = nights.map(([d], i) => `<option value="${i}">${day(d)}</option>`).join(''); this.strip = null; }
      let at = nights.findIndex(([d]) => d === dayArg);
      if (at < 0) at = 0;
      this.at = at; this.day = nights[at][0];
      const [d, rows] = nights[at], hurt = rows.filter((r) => r[6]).length, check = this.data.check[mode];
      press(el, mode);
      $('#b-night', el).value = String(at); $('#b-prev', el).disabled = at === 0; $('#b-next', el).disabled = at === nights.length - 1;
      const what = mode === 'before' ? 'had a new injury within 5 games' : 'missed the next game with a new injury';
      $('#b-sub', el).innerHTML = `${esc(longDay(d))}: <b>${hurt} of the ${rows.length}</b> players the model flagged ${mode === 'before' ? 'before tip-off' : 'after the game'} ${what}.`;
      $('#b-table-title', el).textContent = `${rows.length} highest chances, ${mode === 'before' ? 'before tip-off' : 'after the game'}`;
      $('#b-table-meta', el).textContent = mode === 'before' ? 'Chance of a new injury in the next 5 games' : 'Chance of missing the next game with a new injury';
      $('#b-outcome-head', el).textContent = mode === 'before' ? 'Next 5 games' : 'Next game';
      const top = Math.max(...rows.map((r) => r[4]));
      const driver = ([k2, v]) => esc(v ? `${this.data.drivers[k2]} ${v}` : this.data.drivers[k2]);
      $('#b-table tbody', el).innerHTML = rows.map((r, k) => {
        const [injury, cost] = r[6] ? splitOutcome(r[7]) : ['', ''];
        const outcome = r[6] ? `<td class="outcome hurt wide"><span class="pill neg" title="${esc(injury)}">${esc(injury)}</span><span class="sub">${esc(cost)}</span></td>` : '<td class="outcome none wide">No new injury</td>';
        return `<tr><td class="n rank">${k + 1}</td><td class="who"><a class="name" href="#players/${r[0]}">${esc(r[1])}</a><span class="sub">${esc(r[2])} vs ${esc(r[3])}</span></td>`
          + `<td class="n chance"><b>${Math.round(r[4] / 10)}%</b></td><td class="bar-cell"><div class="mini-bar"><span style="width:${(100 * r[4]) / Math.max(top, 1)}%"></span></div></td>`
          + `<td class="drivers wide" title="${r[5].map(driver).join(' · ')}">${r[5].slice(0, 2).map(driver).join('<br>')}</td>${outcome}</tr>`;
      }).join('');
      const best = rows[0], others = rows.length - hurt;
      $('#b-kpis', el).innerHTML = `<div class="kpi lead"><div class="kpi-label">${mode === 'before' ? 'Hurt within 5 games' : 'Missed the next game hurt'}</div><div class="kpi-value">${hurt}<small>of ${rows.length}</small></div><div class="delta">${others} had no new injury</div></div>`
        + `<div class="kpi"><div class="kpi-label">Highest chance</div><div class="kpi-value">${Math.round(best[4] / 10)}%</div><div class="delta">${esc(best[1])}, ${esc(best[2])}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Average on this board</div><div class="kpi-value">${pct(rows.reduce((a, r) => a + r[4], 0) / rows.length / 1000, 0)}</div><div class="delta">${esc(day(d))}</div></div>`
        + `<div class="kpi"><div class="kpi-label">All players, whole season</div><div class="kpi-value">${pct(check.all.rate)}</div><div class="delta">${esc(check.all.outcome)}</div></div>`;
      $('#b-check-meta', el).textContent = `Share that ${check.top.outcome.startsWith('a new') ? 'had ' + check.top.outcome : check.top.outcome}`;
      pairsOf($('#b-check', el), check);
      $('#b-check-note', el).innerHTML = `<b>${esc(check.top.label)}</b> got hurt ${times(check.top.rate / check.all.rate)} as often as all players, and ${times(check.top.rate / check.bottom.rate)} as often as ${esc(check.bottom.label.toLowerCase())}.`;
      $('#b-read', el).innerHTML = mode === 'before'
        ? '<p><b>Chance</b> is the model’s estimate, before tip-off, that the player gets a new injury in the team’s next 5 games.</p><p><b>What pushed the score up</b> lists the inputs that raised it most. <b>Next 5 games</b> is the first new injury on the league’s official report, if there was one.</p>'
        : '<p><b>Chance</b> is scored right after the game, with its play-by-play: will the player miss the next game with a new injury?</p><p>It sees things a pre-game score can’t, such as a starter leaving a close game early.</p>';
      // the season’s record: how many on each night’s board got hurt, the chosen night in the hue
      const hits = nights.map(([, rs]) => rs.filter((r) => r[6]).length), total = hits.reduce((a, v) => a + v, 0);
      $('#b-strip-meta', el).textContent = `${mode === 'before' ? 'Hurt within 5 games' : 'Missed the next game hurt'}, of each night’s ${rows.length}. Click a night, or use the picker above, to open it.`;
      Charts.bars($('#b-strip', el), { labels: nights.map(([dd]) => shortDay(dd)), values: hits, highlight: at, height: 170, format: Charts.fmt.int,
        reference: { value: total / nights.length, label: `Average ${dec(total / nights.length)}` }, onSelect: (i) => this.go(nights[i][0], mode) });
    },
  };
  // top, all and bottom of each night’s ranking, as three bars
  function pairsOf(el, check) {
    const rows = [check.top, check.all, check.bottom], max = check.top.rate;
    el.innerHTML = `<div class="pairs">${rows.map((r, i) => `<div class="pair"><span class="label">${esc(r.label)}</span><span class="bars"><span><i style="width:${(100 * r.rate) / max}%;${i ? 'background:var(--chart-muted)' : ''}"></i>${pct(r.rate)}</span></span></div>`).join('')}</div>`;
  }

  // ====================================================================================================== players
  // Profiles: every NBA player since 2018-19 (#players/1627936), with the model's 2025-26 chances when it scored
  // them, and every college player Covers listed injured (#players/c2745).
  const SHOWN = 12;                                   // injuries in the table before "Show all"
  const players = {
    async init(el) {
      const [p, h] = await Promise.all([load('players'), load('history')]);
      this.data = p; this.hist = h;
      this.scored = new Map(p.players.map((x) => [x.id, x]));
      this.nba = new Map(h.players.map((x) => [x.id, x]));
      this.groups = Object.fromEntries(h.groups.map((g) => [g.key, g]));
      this.saved = Object.fromEntries(h.saved.map((s) => [s.season, s.days]));
      this.start = p.dates[0]; this.span = daysBetween(this.start, p.dates.at(-1)) + 1;
      this.league = p.avg.reduce((a, v) => a + v, 0) / p.avg.length / 1000;
      this.featured = [...p.players].sort((a, b) => b.b - a.b || b.inj.length - a.inj.length)[0];
      const roster = h.players.filter((x) => x.tm.some(([s]) => s === SEASON_END)).sort((a, b) => a.n.localeCompare(b.n));
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="players-title">Players</h1><p class="sub" id="p-sub"></p></div>
          <div class="controls"><label class="sr-only" for="p-pick">A 2025-26 player</label><select class="select" id="p-pick"><option value="">A 2025-26 player…</option>${roster.map((x) => `<option value="${x.id}">${esc(x.n)}</option>`).join('')}</select></div>
        </div>
        <div class="kpis" id="p-kpis"></div>
        <div class="cards" id="p-cards"></div>`;
      $('#p-pick', el).addEventListener('change', (e) => { if (e.target.value) location.hash = `players/${e.target.value}`; });
    },
    async show(el, [idArg = '']) {
      if (idArg.startsWith('c')) return this.showCollege(el, +idArg.slice(1));
      const x = this.nba.get(+idArg) || this.nba.get(this.featured.id), s = this.scored.get(x.id);
      this.current = x;
      $('#p-pick', el).value = x.tm.some(([y]) => y === SEASON_END) ? String(x.id) : '';
      $('#players-title', el).textContent = x.n;
      const inj = x.inj, missed = inj.reduce((a, e) => a + e[4], 0), seasons = [...new Set(x.tm.map(([y]) => y))];
      const teams = [...new Set(x.tm.map(([, t]) => t))].join(', ');
      $('#p-sub', el).innerHTML = `${esc(teams)} · ${seasons.length > 1 ? `${seasonName(seasons[0])} to ${seasonName(seasons.at(-1))}` : seasonName(seasons[0])}`
        + (x.st ? ` · <span class="pill neg">${esc(x.st)}</span>` : '');
      const big = [...inj].sort((a, b) => b[4] - a[4])[0];
      const regions = Object.entries(inj.reduce((m, e) => ((m[e[3]] = (m[e[3]] || 0) + 1), m), {})).sort((a, b) => b[1] - a[1]);
      const season = s ? (() => { const mean = s.r.reduce((a, v) => a + v, 0) / s.r.length / 1000;
        return `<div class="kpi"><div class="kpi-label">Average chance, 2025-26</div><div class="kpi-value">${pct(mean, 0)}</div><div class="delta">League average ${pct(this.league, 0)} · ${s.r.length} games scored</div></div>`; })()
        : (() => { const g = (x.gp.find(([y]) => y === SEASON_END) || [0, 0])[1], on = x.tm.some(([y]) => y === SEASON_END);
          return `<div class="kpi"><div class="kpi-label">2025-26</div><div class="kpi-value">${int(g)}<small>${g === 1 ? 'game' : 'games'}</small></div>`
            + `<div class="delta">${!on ? 'Not on a 2025-26 roster' : g ? 'Too few games for the model to score' : 'No chance to score: they didn’t play'}</div></div>`; })();
      $('#p-kpis', el).innerHTML = `<div class="kpi lead"><div class="kpi-label">Injuries since 2018-19</div><div class="kpi-value">${inj.length}</div><div class="delta">${int(missed)} games missed</div></div>`
        + `<div class="kpi"><div class="kpi-label">Biggest injury</div><div class="kpi-value">${big ? `${int(big[4])}<small>games</small>` : '–'}</div><div class="delta">${big ? esc(`${this.kindName(big)} · ${shortMonth(big[0])}`) : 'None on record'}</div></div>`
        + season
        + `<div class="kpi"><div class="kpi-label">Most often hurt</div><div class="kpi-value">${regions.length ? `${regions[0][1]}<small>times</small>` : '–'}</div><div class="delta">${regions.length ? esc(this.regionName(regions[0][0])) : 'None on record'}</div></div>`;

      // two columns, each a stack, so a short card on one side leaves no gap on the other
      const main = [s ? `<article class="card"><header><h2>Chance of a new injury, game by game</h2><p class="meta">Before each game of 2025-26, for the next 5 games</p></header>
          <p class="legend" aria-hidden="true"><span><i class="line"></i>This player</span><span><i class="dash"></i>League average</span><span><i class="marker"></i>New injury, labelled at its first missed game</span></p>
          <div class="chart" id="p-chart" style="margin-top:8px"></div><p class="note">Gaps are stretches of a week or more without a game, usually time out hurt.</p></article>` : this.seasonCard(x),
        `<article class="card"><header><h2>Every injury</h2><p class="meta">From the official injury reports, December 2018 to June 2026</p></header><div id="p-inj"></div></article>`];
      const side = [`<article class="card"><header><h2>What usually happens next</h2><p class="meta" id="p-next-meta"></p></header><div id="p-next"></div></article>`];
      if (s) side.push(this.seasonCard(x));
      if (x.col) side.push(`<article class="card"><header><h2>In college</h2><p class="meta">Division I men’s basketball</p></header><div id="p-col"></div></article>`);
      if (inj.length) side.push(`<article class="card"><header><h2>Where they get hurt</h2><p class="meta">Injuries by body part, with the games they cost</p></header><div id="p-where"></div></article>`);
      $('#p-cards', el).innerHTML = `<div class="stack span-8">${main.join('')}</div><div class="stack span-4">${side.join('')}</div>`;
      if (inj.length) {
        const cost = inj.reduce((m, e) => ((m[e[3]] = (m[e[3]] || 0) + e[4]), m), {});
        Charts.barList($('#p-where', el), regions.slice(0, 6).map(([r, n]) => ({ label: `${this.regionName(r)} · ${int(cost[r])} ${cost[r] === 1 ? 'game' : 'games'} missed`, value: n })),
          { format: (v) => `${v} ${v === 1 ? 'injury' : 'injuries'}`, thin: true });
      }

      if (s) {
        const p = this.data;
        const points = s.d.map((di, k) => ({ x: daysBetween(this.start, p.dates[di]), v: s.r[k] / 1000, label: longDay(p.dates[di]) }));
        const ticksAt = []; for (let k = 0; k < this.span; k++) { const dt = new Date(dateOf(this.start).getTime() + k * 86400000); if (dt.getDate() === 1) ticksAt.push({ at: k, label: dt.toLocaleString('en-US', { month: 'short' }) }); }
        const markers = s.inj.map(([d, why]) => ({ at: daysBetween(this.start, d), label: bodyPart(why) }));
        Charts.timeLine($('#p-chart', el), { points, days: this.span, ticksAt, markers, height: 280, reference: { value: this.league, label: 'League average' } });
      }
      this.drawSeasons(el, x);
      // the injury the numbers are about: the one they are out with now, else their biggest
      const focus = (x.st && x.st.startsWith('Out') ? [...inj].reverse().find((e) => e[4] >= 5) : null) || big;
      this.nextCard(el, focus, focus ? this.kindOf(focus) : null, focus === big && !x.st ? 'Their biggest' : 'This one');
      this.injuryTable(el, inj);
      this.withDetails(x, () => this.injuryTable(el, inj, this.showAll));
      if (x.col) {
        const [school, last, n, games, cid, listed] = x.col;
        $('#p-col', el).innerHTML = `<p><b>${esc(school)}</b>, ${n} ${n === 1 ? 'season' : 'seasons'} to ${seasonName(last)}, ${int(games)} games.</p>`
          + (cid ? `<p class="note">Covers listed ${listed} college ${listed === 1 ? 'injury' : 'injuries'}. <a href="#players/c${cid}">See the college profile</a></p>`
            : `<p class="note">No injury of theirs is on the saved Covers pages, which were saved on ${int(this.saved[last] || 0)} days in ${seasonName(last)}.</p>`);
      }
    },
    kindOf(e) { return this.groups[e[2]] ? e[2] : this.groups[`region:${e[3]}`] ? `region:${e[3]}` : 'any'; },
    kindName(e) { const g = this.groups[e[2]]; return g && !e[2].startsWith('region:') ? g.name : e[1]; },
    regionName(r) { const g = this.groups[`region:${r}`]; return g ? g.name : r.replace('_', ' '); },
    seasonCard() {
      return `<article class="card"><header><h2>Season by season</h2><p class="meta">Games played and games missed hurt</p></header>
        <p class="legend" aria-hidden="true"><span><i></i>Played</span><span><i class="hurt-bar"></i>Missed hurt</span></p><div id="p-seasons"></div></article>`;
    },
    drawSeasons(el, x) {
      const played = Object.fromEntries(x.gp), hurt = Object.fromEntries(x.hurt);
      const seasons = [...new Set(x.tm.map(([y]) => y))];
      const top = Math.max(...seasons.map((y) => (played[y] || 0) + (hurt[y] || 0)), 1);
      $('#p-seasons', el).innerHTML = `<div class="seasons">${seasons.map((y) => {
        const a = played[y] || 0, b = hurt[y] || 0;
        return `<div class="season-row"><span class="label">${seasonName(y)}</span><span class="season-bar" role="img" aria-label="${seasonName(y)}: ${a} games played, ${b} missed hurt">`
          + `<i style="width:${(100 * a) / top}%"></i><i class="hurt-bar" style="width:${(100 * b) / top}%"></i></span><span class="n">${a} · <b>${b}</b></span></div>`;
      }).join('')}</div>`;
    },
    // league numbers for one kind of injury: how often players hurt the same place again within a year of coming
    // back, and what it cost; ``whose`` adds this player's own case ("This one: 104 games, not back by June 2026")
    nextCard(el, e, key, whose) {
      if (!e) { $('#p-next-meta', el).textContent = ''; $('#p-next', el).innerHTML = '<div class="empty">No injuries on record.</div>'; return; }
      const g = this.groups[key], all = this.groups.any, region = e[3];
      const again = region === 'concussion' ? 'had another concussion' : region === 'head_neck' ? 'hurt their head or neck again'
        : region === 'other' || key === 'any' ? 'got hurt in the same place again' : `hurt the ${lowerFirst(this.regionName(region))} again`;
      const what = PHRASE[key] || (key === 'any' || key === 'region:other' ? 'any injury'
        : `${/^[aeiou]/i.test(g.name) ? 'an' : 'a'} ${lowerFirst(g.name)} injury`);
      $('#p-next-meta', el).textContent = `After ${what}, in the NBA since 2018-19`;
      const n = g.again_same == null ? null : Math.round(g.again_same * g.watched);
      $('#p-next', el).innerHTML = (n == null ? '' : `<div class="next-figure">${pct(g.again_same, 0)}</div>`
        + `<p>${esc(again)} within a year of coming back: ${n} of ${g.watched} ${g.watched === 1 ? 'player' : 'players'} with a full year back. For any injury it is ${pct(all.again_same, 0)}.</p>`)
        + `<p class="note">It cost ${dec(g.median_missed, g.median_missed % 1 ? 1 : 0)} games at the median, across ${int(g.injuries)} ${g.injuries === 1 ? 'injury' : 'injuries'}.`
        + (whose ? ` ${esc(whose)}: ${int(e[4])} games, ${e[5] ? `back ${esc(shortMonth(e[5]))}` : 'not back by June 2026'}.` : '') + '</p>'
        + `<p class="note"><a href="#careers/${CAREER_OF[key] || 'all'}">What ${CAREER_OF[key] ? esc(what) : 'an injury'} does to a career <span aria-hidden="true">→</span></a></p>`;
    },
    // the news and the career study say more about some injuries (details.json, loaded once the profile is drawn): the
    // tables are drawn again with those injuries opening to their details
    withDetails(x, redraw) {
      if (this.details) return;
      load('details').then((d) => { this.details = d; if (this.current === x) redraw(); }).catch(() => {});
    },
    injuryTable(el, inj, all = false) {
      this.showAll = all;
      const x = this.current, rows = [...inj].reverse(), shown = all ? rows : rows.slice(0, SHOWN);
      $('#p-inj', el).innerHTML = !rows.length ? '<div class="empty">No injuries on the reports since December 2018.</div>'
        : `<div class="table-wrap"><table class="data injuries"><thead><tr><th scope="col">First listed</th><th scope="col">Injury</th><th class="n" scope="col">Games missed</th><th scope="col">Back</th></tr></thead><tbody>${shown.map((e, k) => {
          const news = this.details?.news[`${x.id}:${e[0]}:${e[3]}`], after = this.details?.after[`${x.id}:${e[0]}`];
          const kind = this.groups[e[2]] && !e[2].startsWith('region:') ? this.groups[e[2]].name : '', said = named(news);
          const notes = [said && said !== kind && saysMore(said, e[1]) ? `${said}, per reports` : kind];
          if (e[8]) notes.push(`first listed as ${e[8].toLowerCase()}`);
          if (e[6] != null) notes.push(e[6] < 0 ? 'listed before their first NBA game' : `listed ${int(e[6])} days after their last game`);
          const sub = notes.filter(Boolean).join(' · '), open = news || (after && after.back);
          return `<tr><td class="when nowrap">${esc(shortMonth(e[0]))}</td><td class="what">${toggle(e[1], open, `p-inj-${k}`)}${sub ? `<span class="sub">${esc(sub)}</span>` : ''}</td><td class="n">${int(e[4])}<span class="unit"> ${e[4] === 1 ? 'game' : 'games'}</span></td><td class="back nowrap">${e[5] ? esc(shortMonth(e[5])) : '<span class="pill neg">Not back</span>'}</td></tr>`
            + (open ? `<tr class="more" id="p-inj-${k}" hidden><td colspan="4">${details(news, after)}</td></tr>` : '');
        }).join('')}</tbody></table></div>`
          + (rows.length > SHOWN ? `<button type="button" class="btn" id="p-all" style="margin-top:12px">${all ? 'Show the latest' : `Show all ${rows.length}`}</button>` : '');
      opening($('#p-inj', el));
      const more = $('#p-all', el);
      if (more) more.addEventListener('click', () => this.injuryTable(el, inj, !all));
    },
    collegeTable(el, x) {
      $('#c-inj', el).innerHTML = `<div class="table-wrap"><table class="data injuries"><thead><tr><th scope="col">Listed</th><th scope="col">Injury</th><th scope="col">Status</th><th class="n" scope="col">Games missed</th></tr></thead><tbody>${[...x.inj].reverse().map((e, k) => {
        const news = this.details?.news[`c${x.id}:${e[0]}:${e[4]}`], said = named(news);
        const what = [said && said !== e[10] && saysMore(said, e[3]) ? `${said}, per reports` : e[10] || COLLEGE_KIND[e[5]] || '', e[12] ? 'surgery' : ''].filter(Boolean).join(' · ');
        return `<tr><td class="when nowrap">${esc(shortMonth(e[0]))}${e[1] !== e[0] ? `<span class="sub">to ${esc(shortMonth(e[1]))}</span>` : ''}</td>`
          + `<td class="what">${toggle(e[11] ? `${e[11] === 'left' ? 'Left' : 'Right'} ${e[3].toLowerCase()}` : e[3], news, `c-inj-${k}`)}${what ? `<span class="sub">${esc(what.charAt(0).toUpperCase() + what.slice(1))}</span>` : ''}</td>`
          + `<td class="status">${esc(e[6])}</td><td class="n">${e[7] == null ? '–' : `${int(e[7])}<span class="unit"> ${e[7] === 1 ? 'game' : 'games'}</span>`}${e[8] === false && e[7] ? '<span class="sub">season over</span>' : ''}</td></tr>`
          + (news ? `<tr class="more" id="c-inj-${k}" hidden><td colspan="4">${details(news, null)}</td></tr>` : '');
      }).join('')}</tbody></table></div>`;
      opening($('#c-inj', el));
    },

    // ---- a college player
    async showCollege(el, id) {
      const c = await load('college'), x = (this.college ||= new Map(c.people.map((p) => [p.id, p]))).get(id);
      $('#p-pick', el).value = '';
      if (!x) { $('#players-title', el).textContent = 'Player not found'; $('#p-sub', el).textContent = ''; $('#p-kpis', el).innerHTML = ''; $('#p-cards', el).innerHTML = '<div class="empty span-12">No college player has this address.</div>'; return; }
      $('#players-title', el).textContent = x.n;
      const seasons = x.sch.map(([y]) => y), schools = [...new Set(x.sch.map(([, t]) => t))].join(', ');
      const pro = x.nba && this.nba.get(x.nba);
      $('#p-sub', el).innerHTML = `${esc(schools)} · ${seasons.length > 1 ? `${seasonName(seasons[0])} to ${seasonName(seasons.at(-1))}` : seasonName(seasons[0])} · Division I men’s basketball`
        + (pro ? ` · <a href="#players/${pro.id}">Now in the NBA: their NBA profile</a>` : '');
      const known = x.inj.filter((e) => e[7] != null), missed = known.reduce((a, e) => a + e[7], 0), gp = x.gp.reduce((a, [, n]) => a + n, 0);
      $('#p-kpis', el).innerHTML = `<div class="kpi lead"><div class="kpi-label">Listed injuries</div><div class="kpi-value">${x.inj.length}</div><div class="delta">On Covers’ saved pages</div></div>`
        + `<div class="kpi"><div class="kpi-label">Games missed</div><div class="kpi-value">${known.length ? int(missed) : '–'}</div><div class="delta">${known.length < x.inj.length ? `For ${known.length} of ${x.inj.length} injuries` : 'From the box scores'}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Seasons listed</div><div class="kpi-value">${seasons.length}</div><div class="delta">${esc(schools)}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Games played</div><div class="kpi-value">${gp ? int(gp) : '–'}</div><div class="delta">${gp ? 'In those seasons' : 'Not found in the box scores'}</div></div>`;
      const carry = (await load('study')).carry;
      $('#p-cards', el).innerHTML = `<div class="stack span-8">
        <article class="card"><header><h2>Every listed injury</h2><p class="meta">Facts from Covers’ college injury page, as saved by the Internet Archive</p></header><div id="c-inj"></div>
          <p class="note">Games missed are team games they didn’t play while listed, from the NCAA box scores. A dash means the box scores don’t show the player that season.</p></article>
        ${carry ? `<article class="card"><header><h2>College injuries and the NBA</h2><p class="meta">Exploratory: every NBA rookie found in college, first two NBA seasons</p></header><div id="c-carry"></div></article>` : ''}
        </div>
        <div class="stack span-4">
          <article class="card"><header><h2>How complete this is</h2><p class="meta">Days Covers’ page was saved</p></header><div id="c-saved"></div>
            <p class="note">An injury that began and ended between saves isn’t here. College teams publish no injury report, so this page is the record.</p></article>
          <article class="card"><header><h2>What usually happens next</h2><p class="meta" id="p-next-meta"></p></header><div id="p-next"></div></article>
        </div>`;
      this.current = x;
      this.collegeTable(el, x);
      this.withDetails(x, () => this.collegeTable(el, x));
      $('#c-saved', el).innerHTML = `<dl class="facts">${seasons.map((y) => `<div><dt>${seasonName(y)}</dt><dd>${int(this.saved[y] || 0)} ${this.saved[y] === 1 ? 'day' : 'days'}</dd></div>`).join('')}</dl>`;
      // the NBA numbers for their most serious listed injury: the one that cost the most games, else the latest
      const last = [...x.inj].sort((a, b) => (b[7] || 0) - (a[7] || 0) || b[0].localeCompare(a[0]))[0];
      const key = this.groups[last[13]] ? last[13] : 'any';
      this.nextCard(el, [last[0], last[3], key, REGION_OF[key] || (key.startsWith('region:') ? key.slice(7) : 'other')], key, null);
      $('#p-next', el).insertAdjacentHTML('beforeend', '<p class="note">These are NBA numbers: the saved college pages miss too many injuries to measure this in college.</p>');
      if (carry) {
        const w = carry.well_saved;
        $('#c-carry', el).innerHTML = `<p>Of ${int(w.listed.players + w.not_listed.players)} NBA rookies whose last college season was saved on 30 or more days, those with a listed college injury got hurt <b>${dec(w.ratio)}×</b> as often in their first two NBA seasons: ${dec(w.listed.per_100)} new injuries per 100 games against ${dec(w.not_listed.per_100)}.</p>`
          + `<p class="note">The likely range is ${dec(w.lo, 2)}× to ${dec(w.hi, 2)}×, resampling players. Across every season it is ${dec(carry.all.ratio, 2)}× (${dec(carry.all.lo, 2)}× to ${dec(carry.all.hi, 2)}×), weaker because many college injuries were never saved, so some listed players count as never hurt. Not adjusted for position, age or minutes.</p>`;
      }
    },
  };
  const COLLEGE_KIND = { bone: 'Fracture', ligament: 'Sprain or ligament', muscle_tendon: 'Strain', surgery: 'Surgery', concussion: 'Concussion', soreness: 'Soreness', impact: 'Bruise', other: '' };
  const PHRASE = { acl: 'a torn ACL', achilles: 'an Achilles tear', meniscus: 'a meniscus tear', mcl: 'an MCL sprain', concussion: 'a concussion',
    ankle_sprain: 'an ankle sprain', hamstring: 'a hamstring strain', calf: 'a calf strain', groin: 'a groin strain', foot_fracture: 'a broken foot',
    hand_fracture: 'a broken hand or finger' };
  // the body region each named kind of injury belongs to, for "hurt the knee again"
  const REGION_OF = { acl: 'knee', mcl: 'knee', meniscus: 'knee', achilles: 'achilles', concussion: 'concussion', ankle_sprain: 'ankle',
    hamstring: 'hamstring', calf: 'calf', groin: 'groin', foot_fracture: 'foot', hand_fracture: 'hand', any: 'other' };
  const lowerFirst = (s) => (s === 'Achilles' ? s : s.charAt(0).toLowerCase() + s.slice(1));
  const shortMonth = (iso) => { const d = dateOf(iso); return `${d.toLocaleString('en-US', { month: 'short' })} ${d.getDate()}, ${d.getFullYear()}`; };
  // ---- an injury's details on a profile: what the reports said it was, how it happened, surgery, the team's first
  // timeline and how the player came back, then the sources (facts and their sources, never a report's own words)
  const named = (n) => (n && (n.status === 'confirmed' || n.status === 'reported') && n.diagnosis?.label && n.diagnosis.label !== 'Other' ? n.diagnosis.label : null);
  // whether the reports' name says more than the listing: a word the listing lacks ("Torn meniscus" for "Left knee soreness")
  const saysMore = (label, listed) => !!label && label.toLowerCase().split(/[\s/-]+/).filter((w) => !['or', 'and', 'of', 'the', 'a'].includes(w))
    .some((w) => !listed.toLowerCase().includes(w.replace(/(es|s)$/, '')));
  const toggle = (text, open, id) => (open ? `<button type="button" class="inj-toggle" aria-expanded="false" aria-controls="${id}">${esc(text)}<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5 6 7.5 9 4.5"/></svg></button>` : esc(text));
  const opening = (root) => $$('.inj-toggle', root).forEach((b) => b.addEventListener('click', () => {
    const row = document.getElementById(b.getAttribute('aria-controls')), open = row.hidden;
    row.hidden = !open; b.setAttribute('aria-expanded', String(open));
  }));
  const STATUS = { confirmed: 'Confirmed by the team or two outlets', reported: 'Reported by one outlet', conflicting: 'The reports disagree',
    partial: 'No report names the injury' };
  const HOW = { stepped_on_foot: 'on someone’s foot', landing: 'landing', cutting_or_planting: 'cutting or planting', collision: 'a collision',
    struck: 'hit by a player', fall: 'a fall', overextension: 'bent too far', overuse: 'overuse' };
  const DOING = { drive: 'driving', drew_foul: 'being fouled', rebound: 'rebounding', steal: 'after a steal', defending_the_rim: 'defending the rim',
    jump_shot: 'on a jump shot', transition: 'in transition', screen: 'at a screen', loose_ball: 'chasing a loose ball' };
  const WHERE = { game: 'In a game', practice: 'In practice', workout: 'In a workout', offseason: 'In the offseason' };
  const weeksText = ([lo, hi]) => (hi == null ? `at least ${lo} ${lo === 1 ? 'week' : 'weeks'}` : lo === hi ? `${lo} ${lo === 1 ? 'week' : 'weeks'}` : `${lo} to ${hi} weeks`);
  function details(n, a) {
    const facts = [];
    if (n) {
      const d = n.diagnosis || {}, label = d.label && d.label !== 'Other' ? d.label : '';
      const what = [label ? `${label}${d.detail ? ` (${d.detail})` : ''}` : d.detail, n.side, n.grade && `grade ${n.grade}`].filter(Boolean).join(', ');
      facts.push(['What it was', `${esc(what || 'Not named')}<span class="sub">${esc(STATUS[n.status] || '')}</span>`]);
      const date = n.game?.date ? `In a game on ${shortMonth(n.game.date)}` : '';
      const how = [n.setting === 'game' || !n.setting ? date : WHERE[n.setting], n.game?.play && DOING[n.game.play], n.mechanism && HOW[n.mechanism],
        n.contact === 'non_contact' ? 'no contact' : n.contact === 'contact' ? 'contact' : ''].filter(Boolean);
      if (how.length) facts.push(['How it happened', esc(how.join(' · '))]);
      if (n.surgery?.had != null) facts.push(['Surgery', n.surgery.had ? `Yes${n.surgery.date ? `, ${esc(shortMonth(n.surgery.date))}` : ''}` : 'No']);
      const ex = n.expected || {};
      const said = [ex.season_ending && 'Out for the season', ex.weeks && `Out ${weeksText(ex.weeks)}`, ex.reevaluate_weeks && `Re-evaluated in ${weeksText(ex.reevaluate_weeks)}`].filter(Boolean);
      if (said.length) facts.push(['The team’s first timeline', esc(said.join(' · '))]);
    }
    if (a && a.back) {
      const back = `Back ${shortMonth(a.back)}${a.days != null ? `, ${int(a.days)} days after it${a.offseason ? ', counting the offseason' : ''}` : ''}${a.two_injuries ? ', after a second injury in the same absence' : ''}`;
      const y = a.year_1;
      const line = y ? `First year back: ${dec(y.mpg[1])} minutes a game, from ${dec(y.mpg[0])} the year before (players like them: ${signed(y.mpg[2])}). Production per 36: ${dec(y.production36[1])}, from ${dec(y.production36[0])}.` : '';
      facts.push(['Coming back', `${esc(back)}${line ? `<span class="sub">${esc(line)}</span>` : ''}${a.group && !a.two_injuries ? `<span class="sub"><a href="#careers/${a.group}">What this kind of injury does to a career</a></span>` : ''}`]);
    }
    const src = (n && n.sources) || [];
    return `<dl class="facts compact">${facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>`
      + (src.length ? `<ul class="sources" aria-label="Sources">${src.map(([outlet, published, headline, url]) => `<li>${url && url.startsWith('https://') ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(headline || outlet)}</a>` : esc(headline ? `“${headline}”` : outlet)}`
        + `<span class="sub">${esc(outlet)}${published ? ` · ${esc(shortMonth(published))}` : ''}${url ? '' : ' · on NBA.com, which asks not to be linked'}</span></li>`).join('')}</ul>` : '');
  }
  // the career study's kind of injury for a profile's kind, for "What it does to a career"
  const CAREER_OF = { acl: 'acl', achilles: 'achilles', meniscus: 'meniscus', mcl: 'knee_sprain', concussion: 'concussion', ankle_sprain: 'ankle',
    hamstring: 'muscle', calf: 'muscle', groin: 'muscle', foot_fracture: 'foot_fracture', hand_fracture: 'hand_fracture', 'region:back': 'back',
    'region:shoulder': 'shoulder' };

  // ======================================================================================================== model
  const QUESTIONS = [['pregame_g5', 'Next 5 games'], ['pregame_y14', 'Next 14 days'], ['serious_g5', 'Costing 3+ games'], ['aftergame_g1', 'Misses next game']];
  const model = {
    async init(el) {
      this.data = (await load('study')).model;
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="model-title">Model check</h1><p class="sub" id="m-sub"></p></div>
          <div class="controls">${segmented('Question', QUESTIONS, 'pregame_g5')}</div>
        </div>
        <div class="kpis" id="m-kpis"></div>
        <div class="cards">
          <article class="card span-7"><header><h2>How each model ranks risk</h2><p class="meta">AUC with its 95% interval, resampling whole players. 0.5 is a coin flip.</p></header><div id="m-compare"></div></article>
          <article class="card span-5"><header><h2>Do the percentages come true?</h2><p class="meta" id="m-cal-meta"></p></header><div class="chart" id="m-cal"></div><p class="note" id="m-cal-note"></p></article>
          <article class="card span-6"><header><h2>By season</h2><p class="meta">The main model on each test season</p></header><div id="m-seasons"></div></article>
          <article class="card span-6"><header><h2>What the model leans on</h2><p class="meta">AUC lost when each input is shuffled</p></header><div id="m-drivers"></div></article>
        </div>`;
      $$('.segmented button', el).forEach((b) => b.addEventListener('click', () => { location.hash = `model/${b.dataset.key}`; }));
    },
    show(el, [qArg]) {
      const q = QUESTIONS.some(([k]) => k === qArg) ? qArg : 'pregame_g5', s = this.data;
      press(el, q);
      const rows = s.scores.filter((r) => r.question === q), main = rows.find((r) => r.model === (q === 'aftergame_g1' ? 'after_game_gbm' : 'full_gbm')) || rows.at(-1);
      $('#m-sub', el).innerHTML = `${esc(main.question_label)}. Scored on <b>${int(main.rows)} player-games</b> in 2024-25 and 2025-26, seasons no model choice ever saw. ${pct(main.rate)} of them came before ${q === 'aftergame_g1' ? 'a missed game' : 'a new injury'}.`;
      $('#m-kpis', el).innerHTML = `<div class="kpi lead"><div class="kpi-label">AUC</div><div class="kpi-value">${dec(main.auc, 2)}</div><div class="delta">95% interval ${dec(main.auc_lo, 2)} to ${dec(main.auc_hi, 2)}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Riskiest tenth</div><div class="kpi-value">${dec(main.top10_lift)}<small>×</small></div><div class="delta">the average rate</div></div>`
        + `<div class="kpi"><div class="kpi-label">Injuries in that tenth</div><div class="kpi-value">${pct(main.top10_capture, 0)}</div><div class="delta">of all ${int(main.positives)}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Brier skill</div><div class="kpi-value">${dec(main.brier_skill, 3)}</div><div class="delta">above 0 beats the average rate</div></div>`;
      const lo = 0.5, hi = 0.85, at = (v) => ((v - lo) / (hi - lo)) * 100;
      $('#m-compare', el).innerHTML = `<div class="dots" style="--track:300px">${rows.map((r) => `<div class="dot-row ${r === main ? 'up' : 'none'}" style="--one:${at(0.5)}%;--lo:${at(r.auc_lo)}%;--hi:${at(r.auc_hi)}%;--x:${at(r.auc)}%"><span class="label">${esc(r.model_label)}${r === main ? '<small>The model behind the board</small>' : ''}</span><span class="track" role="img" aria-label="${esc(`${r.model_label}: AUC ${dec(r.auc, 3)}, ${dec(r.auc_lo, 3)} to ${dec(r.auc_hi, 3)}`)}"><span class="range"></span><span class="dot"></span></span><span class="val">${dec(r.auc, 2)}</span></div>`).join('')}</div>`
        + `<div class="dot-scale" style="--track:300px" aria-hidden="true"><span></span><span>${[0.5, 0.6, 0.7, 0.8].map((v) => `<i style="left:${at(v)}%">${dec(v, 1)}</i>`).join('')}</span><span></span></div>`;
      const cal = s.calibration.filter((r) => r.question === q).sort((a, b) => a.decile - b.decile);
      if (cal.length) {
        $('#m-cal-meta', el).textContent = 'Test player-games in tenths by predicted chance';
        Charts.calibration($('#m-cal', el), { rows: cal.map((r) => ({ predicted: r.predicted, observed: r.observed, label: `Tenth ${r.decile} · ${int(r.rows)} player-games` })), height: 250, xLabel: 'Predicted chance', yLabel: '' });
        const t = cal.at(-1);
        $('#m-cal-note', el).innerHTML = `On the dashed line, the chances came true exactly. The riskiest tenth was given <b>${pct(t.predicted, 0)}</b> on average; <b>${pct(t.observed, 0)}</b> of them ${q === 'aftergame_g1' ? 'missed the next game' : 'got hurt'}.`;
      } else {
        $('#m-cal-meta', el).textContent = '';
        $('#m-cal', el).innerHTML = '<div class="empty">Checked for the before-game and after-game boards only. Choose Next 5 games or Misses next game.</div>';
        $('#m-cal-note', el).textContent = '';
      }
      const seasons = s.seasons.filter((r) => r.question === q);
      $('#m-seasons', el).innerHTML = `<table class="data"><thead><tr><th scope="col">Season</th><th class="n" scope="col">Player-games</th><th class="n" scope="col">Rate</th><th class="n" scope="col">AUC</th><th class="n" scope="col">Riskiest tenth</th></tr></thead><tbody>${seasons.map((r) => `<tr><td>${esc(r.season)}</td><td class="n">${int(r.rows)}</td><td class="n">${pct(r.rate)}</td><td class="n">${dec(r.auc, 2)}</td><td class="n">${dec(r.top10_lift)}×</td></tr>`).join('')}</tbody></table>`
        + `<p class="note">The same features and settings in both seasons; 2025-26 was held out until the end.</p>`;
      const dq = q === 'aftergame_g1' ? 'aftergame_g1' : 'pregame_g5';
      const drivers = s.drivers.filter((r) => r.question === dq).sort((a, b) => a.rank - b.rank).slice(0, 8);
      Charts.barList($('#m-drivers', el), drivers.map((r) => ({ label: r.label, value: r.auc_drop })), { format: (v) => dec(v, 3), thin: true });
      if (dq !== q) $('#m-drivers', el).insertAdjacentHTML('beforeend', '<p class="note">Shown for the 5-game model, which this question shares its inputs with.</p>');
    },
  };

  // ====================================================================================================== factors
  const FACTORS = ['games_since_return', 'inj_365', 'age', 'min_avg10', 'b2b', 'listed_played_21', 'acwr'];
  const factors = {
    async init(el) {
      const f = (await load('study')).factors, overall = f.risk.find((r) => r.factor === 'overall');
      el.innerHTML = `
        <div class="title-row"><div><h1 id="factors-title">What raises risk</h1>
          <p class="sub">Share of player-games followed by a new injury in the team’s next 5 games, 2019-20 to 2025-26. The dashed line is the rate for all <b>${int(overall.rows)}</b> player-games, <b>${pct(overall.rate)}</b>; bars in blue are above it.</p></div></div>
        <div class="cards" id="f-cards">
          ${FACTORS.map((k) => `<article class="card span-3 factor"><header><h2>${esc(f.risk.find((r) => r.factor === k).factor_label)}</h2></header><div class="chart" data-factor="${k}"></div></article>`).join('')}
          <article class="card span-3 pairs-stacked"><header><h2>Early exits look back</h2></header><div id="f-early"></div><p class="note" id="f-early-note"></p></article>
          <article class="card span-6"><header><h2>Most injury-prone regulars</h2><p class="meta">New injuries per 100 games, at least 200 games</p></header><div id="f-prone"></div></article>
          <article class="card span-6"><header><h2>New injuries per 1,000 player-games</h2><p class="meta">By season</p></header><div class="chart" id="f-trend"></div><p class="note">Part of the rise is reporting: since 2023 teams must give a reason when a star sits.</p></article>
        </div>`;
      for (const k of FACTORS) {
        const rows = f.risk.filter((r) => r.factor === k).sort((a, b) => a.bucket_order - b.bucket_order);
        Charts.bars($(`[data-factor="${k}"]`, el), { labels: rows.map((r) => r.bucket), values: rows.map((r) => r.rate), format: (v) => pct(v, 0), tickFormat: (v) => pct(v, 0), height: 170,
          highlight: rows.map((r, i) => (r.rate > overall.rate ? i : -1)).filter((i) => i >= 0), reference: { value: overall.rate } });
      }
      const ee = Object.fromEntries(f.early.map((r) => [`${r.question}:${r.group}`, r]));
      pairs($('#f-early', el), [
        { label: 'Missed the next game hurt', a: ee['next_game:left_early'].rate, b: ee['next_game:other'].rate },
        { label: 'Then hurt within 5 games, if they played the next one', a: ee['played_next:left_early'].rate, b: ee['played_next:other']?.rate ?? overall.rate },
      ]);
      $('#f-early-note', el).innerHTML = `<b>Blue:</b> a starter left a close game early (${int(ee['next_game:left_early'].n)} times). Grey: other starter games. ${pct(ee['share_played:left_early']?.rate ?? 0, 0)} played the next game anyway.`;
      const prone = f.prone;
      $('#f-prone', el).innerHTML = `<table class="data"><thead><tr><th scope="col">Player</th><th class="n" scope="col">Games</th><th class="n" scope="col">Injuries</th><th class="n" scope="col">Per 100 games</th></tr></thead><tbody>${prone.slice(0, 8).map((r) => `<tr><td class="name">${esc(r.player)}</td><td class="n">${int(r.games)}</td><td class="n">${int(r.injuries)}</td><td class="n">${dec(r.per_100)}</td></tr>`).join('')}</tbody></table>`
        + (prone.length > 8 ? `<p class="note">The median regular: ${dec(prone.at(-1).per_100)} per 100 games.</p>` : '');
      Charts.bars($('#f-trend', el), { labels: f.trend.map((r) => r.season), values: f.trend.map((r) => r.per_1000), format: (v) => dec(v, 1), tickFormat: Charts.fmt.int, height: 200, highlight: f.trend.length - 1 });
    },
    show() {},
  };

  // ========================================================================================================= when
  const when = {
    async init(el) {
      this.data = (await load('study')).causes;
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="when-title">When and who</h1><p class="sub">How much more or less likely a new injury is in each situation and for each kind of player, 2019-20 to 2025-26. A pattern counts only if it is clear and held in both 2019-22 and 2022-26.</p></div>
          <div class="controls">${segmented('Kind of injury', KINDS, 'any')}</div>
        </div>
        <div class="cards">
          <article class="card span-7"><header><h2>When the risk goes up</h2><p class="meta">Each player against their own other games in the same month</p></header>
            <p class="legend" aria-hidden="true"><span><i class="dot"></i>More likely</span><span><i class="ring"></i>Less likely</span><span><i class="dot muted"></i>No clear difference</span></p>
            <div id="w-sit" style="margin-top:10px"></div></article>
          <div class="stack span-5">
            <article class="card"><header><h2>Who is most at risk</h2><p class="meta">Players against one another</p></header><div id="w-who"></div></article>
            <article class="card"><header><h2>What a team could do with this</h2></header><ul class="prose" id="w-do" style="padding-left:18px;display:grid;gap:8px"></ul></article>
          </div>
        </div>`;
      $$('.segmented button', el).forEach((b) => b.addEventListener('click', () => { location.hash = `when/${b.dataset.key}`; }));
      const c = this.data, get = (list, key, g, field) => list.find((r) => r[field] === key && r.group === g);
      const s = (key, g = 'any') => get(c.situations, key, g, 'situation'), t = (key, g = 'any') => get(c.traits, key, g, 'trait');
      const more = (r) => (r.ratio >= 1.5 ? `${dec(r.ratio)} times as likely` : `${Math.round(100 * (r.ratio - 1))}% more likely`);
      const fewer = (r) => `${Math.round(100 * (1 - r.ratio))}% fewer`;
      $('#w-do', el).innerHTML = [
        `<li><b>Ease players back.</b> The first three games after an injury: ${more(s('first_back'))} to get hurt, and ${more(s('first_back', 'muscle'))} to pull a muscle.</li>`,
        `<li><b>Protect rest days.</b> Three or more days off before a game: ${fewer(s('rested'))} injuries and ${fewer(s('rested', 'muscle'))} pulled muscles.</li>`,
        `<li><b>Plan for the second half.</b> From game 60 on, injuries are ${dec(s('late_season').ratio)} times as likely as in the first 40 games.</li>`,
        `<li><b>Know the repeat risks.</b> Two or more injuries in the past year: ${dec(t('injury_history').ratio)} times as likely to get hurt again.</li>`,
        `<li><b>Don’t over-manage travel.</b> Back-to-backs, three games in four nights, long flights and time zones made no clear difference.</li>`,
      ].join('');
    },
    show(el, [kindArg]) {
      const g = KINDS.some(([k]) => k === kindArg) ? kindArg : 'any', c = this.data;
      press(el, g);
      const shape = (r, sub) => ({ ...r, level: r.headline ? r.level : 0, sub });
      const sit = c.situations.filter((r) => r.group === g).sort((a, b) => b.ratio - a.ratio).map((r) => shape(r, `vs ${r.versus}`));
      const who = c.traits.filter((r) => r.group === g).sort((a, b) => b.ratio - a.ratio).map((r) => shape(r, ''));
      dotRows($('#w-sit', el), sit, { track: 230 });
      dotRows($('#w-who', el), who, { track: 150 });
    },
  };

  // ======================================================================================================== types
  const types = {
    async init(el) {
      const st = await load('study');
      this.c = st.causes; this.f = st.factors;
      el.innerHTML = `
        <div class="title-row"><div><h1 id="types-title">Injury types</h1><p class="sub">Which injuries cost teams the most games, how often they come back, and when in the season they happen. ${int(this.c.facts.find((r) => r.metric === 'injuries').value)} new injuries, 2019-20 to 2025-26.</p></div></div>
        <div class="cards">
          <article class="card span-7"><header><h2>What each kind of injury costs</h2><p class="meta">Per team each season. Choose a row to see its months.</p></header><div class="table-wrap" id="t-groups"></div></article>
          <article class="card span-5"><header><h2 id="t-months-title">The season wears players down</h2><p class="meta">New injuries per 1,000 player-games, by month</p></header><div class="chart" id="t-months"></div><p class="note" id="t-months-note"></p></article>
          <article class="card span-12"><header><h2>Injuries by type and body region</h2><div class="controls">${segmented('Group by', [['type', 'Type'], ['region', 'Body region']], 'type')}</div></header>
            <div class="split"><div id="t-mix"></div><div class="prose" id="t-mix-note"></div></div></article>
        </div>`;
      $$('.segmented button', el).forEach((b) => b.addEventListener('click', () => { location.hash = `types/${this.group}/${b.dataset.key}`; }));
    },
    mix(el, dim) {
      const rows = this.f.mix.filter((r) => r.dimension === dim).sort((a, b) => b.injuries - a.injuries).slice(0, 10);
      const all = this.f.mix.filter((r) => r.dimension === dim), total = all.reduce((a, r) => a + r.injuries, 0);
      const top = rows[0], costly = [...all].filter((r) => r.injuries >= 50).sort((a, b) => b.median_games_missed - a.median_games_missed)[0];
      $('#t-mix-note', el).innerHTML = `<p><b>${esc(top.label)}</b> is the most common listing: ${int(top.injuries)} of ${int(total)} new injuries (${pct(top.injuries / total, 0)}), usually costing ${dec(top.median_games_missed, 0)} games.</p>`
        + `<p><b>${esc(costly.label)}</b> costs the most, a median of ${dec(costly.median_games_missed, costly.median_games_missed % 1 ? 1 : 0)} games, across ${int(costly.injuries)} injuries.</p>`
        + '<p>The bar is the number of injuries; the median games missed are in each label.</p>';
      Charts.barList($('#t-mix', el), rows.map((r) => ({ label: `${r.label} · median ${dec(r.median_games_missed, r.median_games_missed % 1 ? 1 : 0)} games`, value: r.injuries })), { format: Charts.fmt.int });
    },
    show(el, [gArg, dimArg]) {
      const groups = [...this.c.groups].sort((a, b) => b.games_lost_per_team_season - a.games_lost_per_team_season);
      const g = groups.some((r) => r.group === gArg) ? gArg : 'any', dim = dimArg === 'region' ? 'region' : 'type';
      this.group = g;
      press(el, dim); this.mix(el, dim);
      const max = Math.max(...groups.map((r) => r.games_lost_per_team_season));
      $('#t-groups', el).innerHTML = `<table class="data"><thead><tr><th scope="col">Kind</th><th class="n" scope="col">Injuries</th><th class="n" scope="col">Games lost</th><th scope="col" class="bar-cell"><span class="sr-only">Games lost as a bar</span></th><th class="n" scope="col">Out 5+ games</th><th class="n" scope="col">Same part again</th></tr></thead><tbody>`
        + groups.map((r) => `<tr aria-selected="${r.group === g}"><td><a class="name" href="#types/${r.group}/${dim}">${esc(r.name)}</a><span class="sub">${esc(r.covers)}</span></td><td class="n">${dec(r.per_team_season)}</td><td class="n">${dec(r.games_lost_per_team_season)}</td><td class="bar-cell"><div class="mini-bar"><span style="width:${(100 * r.games_lost_per_team_season) / max}%"></span></div></td><td class="n">${pct(r.share_5plus, 0)}</td><td class="n">${pct(r.repeat_share, 0)}</td></tr>`).join('')
        + `</tbody></table><p class="note">Same part again: the share that hit the same body part again within a year. ${g !== 'any' ? `<a href="#types/any/${dim}">Show all injuries by month</a>` : ''}</p>`;
      const months = this.c.months.filter((r) => r.group === g).sort((a, b) => a.order - b.order);
      const name = g === 'any' ? 'Any new injury' : this.c.groups.find((r) => r.group === g).name;
      $('#t-months-title', el).textContent = g === 'any' ? 'The season wears players down' : `${name}, month by month`;
      Charts.bars($('#t-months', el), { labels: months.map((r) => r.month), values: months.map((r) => r.per_1000), format: (v) => dec(v, 1), tickFormat: Charts.fmt.int, height: 220, highlight: months.length - 1 });
      $('#t-months-note', el).innerHTML = `By April, ${esc(name.toLowerCase())} come <b>${dec(months.at(-1).per_1000 / months[0].per_1000)} times</b> as often as in October. Some late-season soreness is rest listed as an injury.`;
    },
  };


  // ====================================================================================================== college
  // The same injury-moment test in both leagues, every play lined up, and whether college injuries carry into the NBA.
  const COMPARE_KINDS = [['any', 'Any injury'], ['ankle', 'Ankle'], ['knee', 'Knee'], ['foot', 'Foot'], ['muscle', 'Muscle'],
    ['back_hip', 'Back & hip'], ['hand', 'Hand & arm'], ['head', 'Head'], ['shoulder', 'Shoulder'], ['other', 'Other']];
  const STOPS = { 'own timeout': 'The team’s own timeout', 'opponent timeout': 'The other team’s timeout', 'media timeout': 'A media timeout',
    foul: 'A foul', 'free throws': 'Free throws', break: 'A break between periods', 'turnover or violation': 'A turnover or violation',
    'team rebound': 'A team rebound', 'no logged stoppage': 'Nothing logged: play just stopped', 'jump ball': 'A jump ball' };
  const TESTS = { H1: 'Ankle injury, after drawing a foul', H2: 'Any injury, after a steal', H3: 'Hand or arm injury, after a rim attack',
    H4: 'Pulled muscle or Achilles, after a drive', H5: 'Ankle injury, after a rebound' };
  // a ratio is clear when its likely range stays on one side of 1×; v = [ratio, lo, hi]
  const clear = (v) => v[1] > 1 || v[2] < 1;
  const sameWay = (r) => (r.nba[0] - 1) * (r.col[0] - 1) > 0;
  const clarity = (r) => (clear(r.nba) && clear(r.col) ? 'clear in both' : clear(r.nba) ? 'clear in the NBA only' : clear(r.col) ? 'clear in college only' : 'clear in neither');
  const ratioRange = (v) => `<b style="font-weight:600">${dec(v[0], 2)}×</b> (${dec(v[1], 2)} to ${dec(v[2], 2)})`;
  const college = {
    async init(el) {
      const st = await load('study');
      this.c = st.compare; this.m = st.moments;
      const f = this.m.facts, c = this.c, a = c.agreement, primaries = this.m.college.filter((t) => t.primary).length;
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="college-title">NBA vs college</h1><p class="sub">The same injury-moment test on NBA games and on Division I men’s games, ${seasonName(c.seasons[0].season)} to ${seasonName(c.seasons.at(-1).season)}. The college test followed a plan written down and fingerprinted before any college result. Every college player Covers listed injured has a profile: search for one.</p></div>
          <div class="controls"><a class="btn" href="moments.html#college">Read the college test</a></div>
        </div>
        <div class="kpis">
          <div class="kpi lead"><div class="kpi-label">Planned tests pointing the same way</div><div class="kpi-value">${f.college_same_direction}<small>of ${f.college_tests}</small></div><div class="delta">in ${int(f.college_traced)} college injury exits</div></div>
          <div class="kpi"><div class="kpi-label">Main checks cleared</div><div class="kpi-value">${f.college_passed}<small>of ${primaries}</small></div><div class="delta">against a bar set before the test</div></div>
          <div class="kpi"><div class="kpi-label">All five together</div><div class="kpi-value">${dec(c.pooled.odds_ratio)}<small>×</small></div><div class="delta">likely ${dec(c.pooled.lo)}× to ${dec(c.pooled.hi)}×</div></div>
          <div class="kpi"><div class="kpi-label">Every play: same way in college</div><div class="kpi-value">${a.nba_clear_same}<small>of ${a.nba_clear}</small></div><div class="delta">clear NBA signals · exploratory</div></div>
        </div>
        <div class="cards">
          <article class="card span-7"><header><h2>The five NBA patterns, checked in college</h2><p class="meta">How many times as likely, with the likely range</p></header>
            <p class="legend" aria-hidden="true"><span><i class="dot nba"></i>NBA</span><span><i class="dot college"></i>College</span></p>
            <div id="c-tests" style="margin-top:6px"></div></article>
          <article class="card span-5"><header><h2>How players leave hurt</h2><p class="meta">What stopped play when they left</p></header>
            <p class="legend" aria-hidden="true"><span><i></i>Injury exits</span><span><i class="muted"></i>Ordinary substitutions</span></p>
            <div id="c-stops"></div><p class="note" id="c-stops-note"></p></article>
          <article class="card span-12"><header><h2>Do the same plays come before injuries in both leagues?</h2><p class="meta">One dot per play and kind of injury: how much more often it came before injury exits</p></header>
            <div class="split">
              <div><p class="legend" aria-hidden="true"><span><i class="dot nba"></i>Clear in the NBA</span><span><i class="dot muted"></i>Not clear in the NBA</span><span><i class="dash"></i>The same in both</span></p>
                <div class="chart" id="c-scatter" style="margin-top:8px"></div></div>
              <div class="prose" id="c-agree" style="align-self:center"></div>
            </div></article>
          ${st.carry ? `<article class="card span-12"><header><h2>Do college injuries carry into the NBA?</h2><p class="meta">New injuries per 100 games in their first two NBA seasons, NBA debuts since 2020-21</p></header>
            <div class="split">
              <div><p class="legend" aria-hidden="true"><span><i></i>A college injury on record</span><span><i class="muted"></i>None on record</span></p>
                <div id="c-carry-bars" style="margin-top:8px"></div></div>
              <div class="prose" id="c-carry-text" style="align-self:center"></div>
            </div></article>` : ''}
          <article class="card span-12"><header><h2>Every play, both leagues</h2><div class="controls">${segmented('Kind of injury', COMPARE_KINDS, 'any')}</div></header>
            <p class="meta" id="c-plays-meta"></p>
            <p class="legend" aria-hidden="true" style="margin-top:8px"><span><i class="dot nba"></i>NBA</span><span><i class="dot college"></i>College</span></p>
            <div id="c-plays" style="margin-top:6px"></div>
            <p class="note">How much more often each play came in the 30 seconds before an injury exit than before the same players’ other exits. 1× is no difference, and a range that crosses 1× isn’t clear. Ranges past the axis run to its edge. Plays no injured player made in a league are left out.</p></article>
          <article class="card span-6"><header><h2>What can be traced, by kind of injury</h2><p class="meta">Share of new injuries that ended in an injury exit</p></header>
            <p class="legend" aria-hidden="true"><span><i></i>NBA</span><span><i class="college"></i>College</span></p><div id="c-traced"></div></article>
          <article class="card span-6"><header><h2>The college data</h2><p class="meta">Division I men’s games, by season</p></header><div id="c-data"></div></article>
        </div>`;
      $$('.segmented button', el).forEach((b) => b.addEventListener('click', () => { location.hash = `college/${b.dataset.key}`; }));

      const byKey = Object.fromEntries(this.m.patterns.map((r) => [r.key, r]));
      vsRows($('#c-tests', el), [...this.m.college].sort((a, b) => a.order - b.order).map((t) => {
        const n = byKey[t.nba_key], label = TESTS[t.key] || t.label;
        return { label, sub: `NBA ${times(n.times)} · college ${times(t.times)} · ${t.verdict_label}`, nba: [n.times, n.lo, n.hi], col: [t.times, t.lo, t.hi],
          aria: `${label}: NBA ${dec(n.times)} times, college ${dec(t.times)} times. ${t.verdict_label}.` };
      }));

      // every play before every kind of injury, the NBA's ratio against college's
      const kindName = Object.fromEntries(c.groups.map((g) => [g.group, g.name]));
      const agreeing = `${a.nba_clear_same} of the ${a.nba_clear}`;
      Charts.logScatter($('#c-scatter', el), {
        points: c.plays.map((r) => ({ x: r.nba[0], y: r.col[0], strong: clear(r.nba),
          tip: `<div style="opacity:.7">${esc(kindName[r.group] || r.group)} · ${esc(r.label)}</div><div>NBA ${ratioRange(r.nba)}</div><div>College ${ratioRange(r.col)}</div>` })),
        xLabel: 'NBA', yLabel: 'College', corners: ['More often in both', 'Less often in both'],
        aria: `${a.pairs} plays and kinds of injury, the NBA’s ratio against college’s. ${agreeing} with a clear NBA signal point the same way in college. Every pair is listed under Every play, both leagues.` });
      $('#c-agree', el).innerHTML = `<p><b>${agreeing}</b> plays with a clear NBA signal point the same way in college${a.both_clear ? `, and ${a.both_clear_same === a.both_clear ? `all ${a.both_clear}` : `${a.both_clear_same} of the ${a.both_clear}`} that are clear in both leagues agree` : ''}.</p>`
        + `<p>For any injury, where both leagues have the most cases, the two leagues’ ratios line up with a correlation of <b>${dec(a.r_any, 2)}</b> across ${a.any_plays} plays. Across all ${a.pairs} pairs it is ${dec(a.r_all, 2)}, because the smaller college groups add noise.</p>`
        + `<p class="note">Exploratory. These pairs were lined up after the planned test, and they overlap (any injury includes the ankle ones), so they show what to test next rather than prove it. Ratios past 8× sit on the edge.</p>`;

      if (st.carry) {
        const k = st.carry, w = k.well_saved, a = k.all;
        pairs($('#c-carry-bars', el), [
          { label: `Last college season saved on 30+ days (${int(w.listed.players + w.not_listed.players)} players)`, a: w.listed.per_100, b: w.not_listed.per_100 },
          { label: `Every season (${int(a.listed.players + a.not_listed.players)} players)`, a: a.listed.per_100, b: a.not_listed.per_100 },
        ], { format: (v) => dec(v) });
        $('#c-carry-text', el).innerHTML = `<p>${int(k.matched)} of the ${int(k.rookies)} NBA debuts since 2020-21 were found in college, ${int(k.with_profile)} of them with an injury on Covers’ saved pages. Where their last college season was saved on 30 or more days, those with a college injury on record got hurt <b>${dec(w.ratio)}×</b> as often in their first two NBA seasons (likely ${dec(w.lo, 2)}× to ${dec(w.hi, 2)}×).</p>`
          + `<p>Across every season it is ${dec(a.ratio, 2)}× (${dec(a.lo, 2)}× to ${dec(a.hi, 2)}×): in the seasons saved on only a few days, many college injuries were never recorded, so injured players count as never hurt and the difference shrinks.</p>`
          + `<p class="note">Exploratory: new NBA injuries per game played, not adjusted for position, age or minutes; ranges resample players.</p>`;
      }

      // how players leave hurt: the three stoppages that differ most between injury exits and ordinary substitutions
      const top = (league) => {
        const inj = c.stoppages[league]['injury exits'], ord = c.stoppages[league]['ordinary exits'];
        return Object.keys(inj).map((k) => ({ k, a: inj[k], b: ord[k] || 0 })).sort((x, y) => Math.abs(y.a - y.b) - Math.abs(x.a - x.b)).slice(0, 3);
      };
      const nbaStops = top('nba'), colStops = top('col');
      $('#c-stops', el).innerHTML = '<h3 class="sub-head">NBA</h3><div id="c-stops-nba"></div><h3 class="sub-head">College</h3><div id="c-stops-col"></div>';
      pairs($('#c-stops-nba', el), nbaStops.map((r) => ({ label: STOPS[r.k] || r.k, a: r.a, b: r.b })), { format: (v) => pct(v, 0) });
      pairs($('#c-stops-col', el), colStops.map((r) => ({ label: STOPS[r.k] || r.k, a: r.a, b: r.b })), { format: (v) => pct(v, 0) });
      const nt = c.stoppages.nba['injury exits']['own timeout'], no = c.stoppages.nba['ordinary exits']['own timeout'];
      const cl = c.stoppages.col['injury exits']['no logged stoppage'], co = c.stoppages.col['ordinary exits']['no logged stoppage'];
      $('#c-stops-note', el).innerHTML = `NBA teams call their own timeout to get a hurt player off: <b>${pct(nt, 0)}</b> of injury exits, against ${pct(no, 0)} of ordinary substitutions. In college, play most often just stops with nothing logged (<b>${pct(cl, 0)}</b> against ${pct(co, 0)}), usually the officials stopping play for a hurt player.`;

      pairs($('#c-traced', el), c.groups.map((g) => ({ label: g.name, a: g.nba[1], b: g.col[3] })), { format: (v) => pct(v, 0), second: 'college' });

      const rows = c.seasons.map((r) => `<tr><td class="nowrap">${seasonName(r.season)}</td><td class="n">${int(r.games)}</td><td class="n">${int(r.games_kept)}</td><td class="n">${int(r.player_games_kept)}</td></tr>`).join('');
      const sum = (k) => c.seasons.reduce((n, r) => n + r[k], 0);
      $('#c-data', el).innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th scope="col">Season</th><th class="n" scope="col">Games</th><th class="n" scope="col">Games kept</th><th class="n" scope="col">Player-games</th></tr></thead>`
        + `<tbody>${rows}<tr><td><b>All</b></td><td class="n"><b>${int(sum('games'))}</b></td><td class="n"><b>${int(sum('games_kept'))}</b></td><td class="n"><b>${int(sum('player_games_kept'))}</b></td></tr></tbody></table></div>`
        + `<p class="note">Games kept are those with clean play-by-play. College injuries come from ${int(c.listings.named)} listings on Covers’ public college injury page, read from ${int(f.college_saved_pages)} copies saved by the Internet Archive; ${pct(c.listings.matched, 0)} matched to a player in the box scores. Profiles show the listings’ facts (dates, body part, status), checked against the box scores, never Covers’ own words.</p>`;
    },
    show(el, [kindArg]) {
      const kind = COMPARE_KINDS.some(([k]) => k === kindArg) ? kindArg : 'any';
      press(el, kind);
      const rows = this.c.plays.filter((r) => r.group === kind).sort((a, b) => b.nba[0] - a.nba[0]);
      const name = (this.c.groups.find((g) => g.group === kind) || {}).name || COMPARE_KINDS.find(([k]) => k === kind)[1];
      if (!rows.length) { $('#c-plays-meta', el).textContent = ''; $('#c-plays', el).innerHTML = '<div class="empty">No plays to compare for this kind of injury.</div>'; return; }
      const strong = rows.filter((r) => clear(r.nba)), agree = strong.filter(sameWay).length;
      $('#c-plays-meta', el).textContent = `${name}: ${int(rows[0].nba[5])} NBA injury exits and ${int(rows[0].col[5])} college ones, with what each player did in the 30 seconds before. `
        + (strong.length ? `${agree} of the ${strong.length} plays with a clear NBA signal point the same way in college.` : 'No play here has a clear NBA signal.');
      vsRows($('#c-plays', el), rows.map((r) => ({ label: r.label, sub: `NBA ${times(r.nba[0])} · college ${times(r.col[0])} · ${clarity(r)}`,
        nba: r.nba.slice(0, 3), col: r.col.slice(0, 3), aria: `${r.label}: NBA ${dec(r.nba[0])} times, college ${dec(r.col[0])} times, ${clarity(r)}.` })),
      { min: 0.2, max: 40, ticks: [0.5, 1, 2, 5, 10, 25] });
    },
  };

  // ===================================================================================================== careers
  // What an injury does to a career, in the NBA (#careers/acl, #careers/acl/2 for the second year back) and in Division I
  // (#careers/college/acl): how long it keeps players out, whether they come back the same, whether they get hurt again
  // and what comes after, each set against the ten players most like them the day they were hurt (aftermath.py,
  // college_aftermath.py).
  const SAME = [['mpg', 'Minutes a game', 'n'], ['starter', 'Games started', 'share'], ['production36', 'Production per 36 minutes', 'n'],
    ['pts36', 'Points per 36 minutes', 'n'], ['ts', 'True shooting', 'share'], ['rim36', 'Shots at the rim per 36 minutes', 'n']];
  // each league's file and measures: what the "hurt again" and "after" cards show, the table's columns, the placebo's rows
  const LEAGUES = {
    nba: {
      file: 'careers', since: '2018-19', name: 'NBA',
      again: [['same_region', 'Hurt in the same place again', 'share'], ['other_regions', 'New injuries elsewhere in the body', 'count'],
        ['played_share', 'Share of the team’s games they played', 'share']],
      againMeta: 'The full year back',
      after: [['playing_2', 'Still playing two seasons on', 'share'], ['playing_3', 'Still playing three seasons on', 'share'],
        ['new_team', 'On a new team in the year back', 'share']],
      afterTitle: 'Staying in the league', afterMeta: 'The seasons after',
      alike: [['age', 'Age', 'n'], ['mpg', 'Minutes a game', 'n'], ['production36', 'Production per 36', 'n'], ['played_share', 'Share of games played', 'share']],
      placebo: [['mpg', 'Minutes a game'], ['production36', 'Production per 36'], ['same_region', 'Hurt in the same place again'], ['playing_2', 'Still playing two seasons on']],
      profile: (c) => `#players/${c.player_id}`,
    },
    college: {
      file: 'college_careers', since: '2019-20', name: 'college',
      again: [['listed_again', 'Listed hurt again', 'share'], ['played_share', 'Share of the team’s games they played', 'share']],
      againMeta: 'The full year back; listed hurt again only where Covers’ page was well saved',
      after: [['next_season', 'Still in Division I the next season', 'share'], ['moved', 'At another school the next season, of those still playing', 'share'],
        ['nba', 'Reached the NBA', 'share']],
      afterTitle: 'What came next', afterMeta: 'The next season, and the NBA',
      alike: [['seasons', 'Seasons already played', 'n'], ['mpg', 'Minutes a game', 'n'], ['production36', 'Production per 36', 'n'],
        ['played_share', 'Share of games played', 'share'], ['won', 'Share of their team’s games won', 'share']],
      placebo: [['mpg', 'Minutes a game'], ['production36', 'Production per 36'], ['next_season', 'Still in Division I the next season'], ['nba', 'Reached the NBA']],
      profile: (c) => `#players/c${c.covers_id}`,
    },
  };
  const amount = (v, unit) => (unit === 'share' ? pct(v, 0) : dec(v, 1));
  const gap = (v, unit) => (unit === 'share' ? `${signed(100 * v, 1)} points` : signed(v, unit === 'count' ? 2 : 1));
  const span = (r, unit) => `${gap(r.difference ?? r.effect, unit)} (${unit === 'share' ? `${signed(100 * r.lo, 1)} to ${signed(100 * r.hi, 1)}` : `${gap(r.lo, unit)} to ${gap(r.hi, unit)}`})`;
  const clearOf = (r) => r.lo > 0 || r.hi < 0;
  const one = (list, k) => (list || []).find((r) => (r.metric || r.outcome) === k);
  // a week of the recovery curve as people say it, on an axis of `span` weeks
  const weekName = (i, span) => (i === 0 ? 'Hurt' : span <= 26 || i < 13 ? `${i} ${i === 1 ? 'week' : 'weeks'}`
    : i % 52 === 0 ? `${i / 52} ${i === 52 ? 'year' : 'years'}` : i % 13 === 0 ? `${(i / 13) * 3} months` : `${i} weeks`);
  const careers = {
    data: {},
    async init(el) {
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="careers-title">After an injury</h1><p class="sub" id="a-sub" aria-live="polite"></p></div>
          <div class="controls"><div id="a-league">${segmented('League', [['nba', 'NBA'], ['college', 'College']], 'nba')}</div>
            <label class="sr-only" for="a-pick">Kind of injury</label><select class="select" id="a-pick"></select></div>
        </div>
        <div class="kpis" id="a-kpis"></div>
        <div class="cards">
          <article class="card span-7"><header><h2>Did they come back the same?</h2><div class="controls" id="a-years">${segmented('Year back', [['1', 'First year back'], ['2', 'Second year back']], '1')}</div></header>
            <p class="meta" id="a-same-meta"></p><div id="a-same" style="margin-top:10px"></div><p class="note" id="a-same-note"></p></article>
          <article class="card span-5"><header><h2>How long it keeps players out</h2><p class="meta">Share still out, week by week</p></header>
            <p class="legend" id="a-curve-legend" aria-hidden="true"></p><div class="chart" id="a-curve" style="margin-top:8px"></div><p class="note" id="a-curve-note"></p></article>
          <article class="card span-6"><header><h2>Getting hurt again</h2><p class="meta" id="a-again-meta"></p></header>
            <p class="legend" aria-hidden="true"><span><i></i>After this injury</span><span><i class="muted"></i>Players like them</span></p><div id="a-again" style="margin-top:12px"></div></article>
          <article class="card span-6"><header><h2 id="a-after-title"></h2><p class="meta" id="a-after-meta"></p></header>
            <p class="legend" aria-hidden="true"><span><i></i>After this injury</span><span><i class="muted"></i>Players like them</span></p><div id="a-after" style="margin-top:12px"></div></article>
          <article class="card span-12" id="a-cases-card"><header><h2 id="a-cases-title"></h2><p class="meta" id="a-cases-meta"></p></header><div id="a-cases"></div></article>
          <article class="card span-12"><header><h2>Every kind of injury</h2><p class="meta">Choose one to see it above</p></header><div class="table-wrap" id="a-table"></div>
            <p class="note" id="a-table-note"></p></article>
          <article class="card span-12"><header><h2>How this was measured</h2><p class="meta" id="a-method-meta"></p></header>
            <div class="prose" id="a-method"></div><div class="split" style="margin-top:16px"><div id="a-alike"></div><div id="a-placebo"></div></div></article>
        </div>`;
      $('#a-pick', el).addEventListener('change', (e) => this.go(this.league, e.target.value, this.year));
      $$('#a-league button', el).forEach((b) => b.addEventListener('click', () => this.go(b.dataset.key, 'all', '1')));
      $$('#a-years button', el).forEach((b) => b.addEventListener('click', () => this.go(this.league, this.key, b.dataset.key)));
    },
    go(league, key, year) { location.hash = `careers/${league === 'college' ? 'college/' : ''}${key}${year === '2' ? '/2' : ''}`; },
    async show(el, args) {
      const league = args[0] === 'college' ? 'college' : 'nba', [keyArg, yearArg] = league === 'college' ? args.slice(1) : args;
      const L = LEAGUES[league], c = (this.data[league] ||= await load(L.file));
      if (league !== this.league) this.setLeague(el, league, c);
      const groups = Object.fromEntries(c.groups.map((g) => [g.key, g]));
      const g = groups[keyArg] || groups.all, year = yearArg === '2' ? '2' : '1', all = groups.all;
      this.key = g.key; this.year = year;
      $('#a-pick', el).value = g.key;
      press($('#a-league', el), league); press($('#a-years', el), year);
      $$('#a-table tbody tr', el).forEach((tr) => tr.setAttribute('aria-selected', String(tr.dataset.key === g.key)));
      const mpg = one(g.year_1, 'mpg');
      $('#a-sub', el).innerHTML = league === 'college' ? this.collegeFinding(g, mpg) : this.finding(g, mpg, one(g.year_1, 'production36'));
      const kpi = (label, value, delta, lead = false) => `<div class="kpi${lead ? ' lead' : ''}"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="delta">${delta}</div></div>`;
      const vs = (r, none) => (r ? [pct(r.them, 0), `${pct(r.matched, 0)} for players like them`] : ['–', none]);
      const minutes = kpi('Minutes a game, first year back', mpg ? signed(mpg.effect) : '–', mpg ? `against players like them · ${int(mpg.injuries)} injuries` : 'Too few with a year back to judge');
      $('#a-kpis', el).innerHTML = league === 'college'
        ? kpi('Games missed', `${dec(g.games_missed.median, 0)}<small>at the median</small>`, `${pct(g.season_over, 0)} didn’t play again that season`, true) + minutes
          + kpi('In Division I the next season', ...vs(one(g.outcomes, 'next_season'), 'Too recent to tell'))
          + kpi('Reached the NBA', ...vs(one(g.outcomes, 'nba'), 'Too recent to tell'))
        : kpi('Half back within', g.median_days == null ? '–' : `${int(g.median_days)}<small>days</small>`,
          `${dec(g.games_missed.median, 0)} games missed at the median · ${pct(g.back_within_a_year, 0)} back within a year`, true) + minutes
          + kpi('Hurt there again within a year', ...vs(one(g.outcomes, 'same_region'), 'Too few with a full year back'))
          + kpi('Still playing two seasons on', ...vs(one(g.outcomes, 'playing_2'), 'Too recent to tell'));
      this.same(el, g, year);
      this.curve(el, g, all, league);
      this.pairsOf($('#a-again', el), g, L.again);
      this.pairsOf($('#a-after', el), g, L.after);
      this.cases(el, g, L, c.end_of_data);
    },
    // a league's picker, cards' titles, table and method, drawn once each time the league changes
    setLeague(el, league, c) {
      const L = LEAGUES[league];
      this.league = league; this.allCases = null;
      $('#a-pick', el).innerHTML = c.groups.map((g) => `<option value="${g.key}">${esc(g.key === 'all' ? 'Every injury' : g.name)}</option>`).join('');
      $('#a-again-meta', el).textContent = L.againMeta;
      $('#a-after-title', el).textContent = L.afterTitle;
      $('#a-after-meta', el).textContent = L.afterMeta;
      $('#a-method-meta', el).textContent = `Games through ${longDay(c.end_of_data)}`;
      this.table(el, c, league);
      this.method(el, c, league);
    },
    // the line under the title: what the selected injury did, in one sentence
    finding(g, mpg, prod) {
      const what = g.key === 'all' ? `${int(g.injuries)} injuries since 2018-19, ${int(g.players)} players`
        : `${esc(g.name)}: ${int(g.injuries)} ${g.injuries === 1 ? 'injury' : 'injuries'} since 2018-19`;
      const back = g.median_days != null ? `Half were back within <b>${int(g.median_days)} days</b>` : 'Fewer than half were back by June 2026';
      let came = '';
      if (mpg) {
        came = clearOf(mpg) ? `in their first year back they played <b>${dec(Math.abs(mpg.effect))} ${mpg.effect < 0 ? 'fewer' : 'more'} minutes a game</b> than players like them`
          : 'their minutes in the first year back were about those of players like them';
        if (prod) came += clearOf(prod) ? `, and produced ${dec(Math.abs(prod.effect))} ${prod.effect < 0 ? 'less' : 'more'} per 36 minutes` : ', and they were as productive per minute';
      }
      return `${what}. ${back}${came ? `; ${came}` : ''}.`;
    },
    // college players grow into bigger roles each season, so the finding is the growth an injury cost
    collegeFinding(g, mpg) {
      const what = g.key === 'all' ? `${int(g.injuries)} Division I injuries since 2019-20, ${int(g.players)} players`
        : `${esc(g.name)} in college: ${int(g.injuries)} ${g.injuries === 1 ? 'injury' : 'injuries'} since 2019-20`;
      const out = `${dec(g.games_missed.median, 0)} games missed at the median, and ${pct(g.season_over, 0)} didn’t play again that season`;
      let came = '';
      if (mpg) {
        came = clearOf(mpg) && mpg.effect < 0 && mpg.matched_change > 0
          ? `in their first year back they went from ${dec(mpg.before)} to ${dec(mpg.after)} minutes a game while players like them gained ${dec(mpg.matched_change)}: <b>${dec(-mpg.effect)} minutes behind</b>`
          : clearOf(mpg) ? `in their first year back they played <b>${dec(Math.abs(mpg.effect))} ${mpg.effect < 0 ? 'fewer' : 'more'} minutes a game</b> than players like them`
            : 'their minutes in the first year back moved like those of players like them';
      }
      return `${what}. ${out}${came ? `; ${came}` : ''}.`;
    },
    same(el, g, year) {
      const rows = SAME.map(([k, label, unit]) => [(g[`year_${year}`] || []).find((r) => r.metric === k), label, unit]).filter(([r]) => r && r.before);
      $('#a-same-meta', el).textContent = rows.length
        ? `${int(Math.min(...rows.map(([r]) => r.injuries)))} injuries with a ${year === '2' ? 'second' : 'first'} year back to judge by, against players like them over the same dates`
        : '';
      if (!rows.length) { $('#a-same', el).innerHTML = `<div class="empty">Too few ${year === '2' ? 'second years' : 'years'} back to judge by.</div>`; $('#a-same-note', el).textContent = ''; return; }
      changeRows($('#a-same', el), rows.map(([r, label, unit]) => ({
        label, value: r.effect / r.before, lo: r.lo / r.before, hi: r.hi / r.before, text: `${signed((100 * r.effect) / r.before, 0)}%`,
        sub: `${amount(r.before, unit)} before, ${amount(r.after, unit)} after · players like them ${gap(r.matched_change, unit)}`,
        aria: `${label}: ${amount(r.before, unit)} before and ${amount(r.after, unit)} after; against players like them ${gap(r.effect, unit)}, likely ${gap(r.lo, unit)} to ${gap(r.hi, unit)}`,
      })), { track: 170 });
      $('#a-same-note', el).innerHTML = 'Each dot is the change against players like them, as a share of where the injured player started; the bar is its likely range, and a grey dot means no clear difference. <b>Production</b> adds points, rebounds, assists, steals and blocks, and takes off turnovers.';
    },
    curve(el, g, all, league) {
      const span = (g.still_out[26] < 0.1 && all.still_out[26] < 0.1) || g.key === 'concussion' ? 26 : g.still_out[52] < 0.1 ? 52 : 104;
      const labels = Array.from({ length: span + 1 }, (_, i) => weekName(i, span));
      const ticks = span === 26 ? [0, 5, 10, 15, 20, 25] : span === 52 ? [0, 13, 26, 39, 52] : [0, 26, 52, 78, 104];
      const style = getComputedStyle(el), blue = style.getPropertyValue('--chart-1').trim(), grey = style.getPropertyValue('--chart-muted').trim();
      const series = g.key === 'all' ? [{ name: 'Every injury', values: all.still_out.slice(0, span + 1), colour: blue }]
        : [{ name: 'Every injury', values: all.still_out.slice(0, span + 1), colour: grey }, { name: g.name, values: g.still_out.slice(0, span + 1), colour: blue }];
      $('#a-curve-legend', el).innerHTML = g.key === 'all' ? '' : `<span><i class="line"></i>${esc(g.name)}</span><span><i class="line muted"></i>Every injury</span>`;
      Charts.line($('#a-curve', el), { labels, series, step: true, height: 230, yTicks: [0, 0.25, 0.5, 0.75, 1], format: (v) => pct(v, 0), xAt: ticks,
        reference: { value: 0.5, label: 'Half back' } });
      const t = g.timelines;
      $('#a-curve-note', el).innerHTML = league === 'college'
        ? `${pct(g.back_within_a_year, 0)} were back within a year; ${pct(g.season_over, 0)} didn’t play again that season, so the summer is in most of these days.`
          + ` Days count from their last game before the injury${g.not_back ? `, and ${int(g.not_back)} hadn’t played Division I again by April 2026` : ''}.`
        : `${pct(g.back_within_a_year, 0)} were back within a year and ${pct(g.back_within_two_years, 0)} within two${g.not_back ? `; ${int(g.not_back)} hadn’t played again by June 2026` : ''}. Days count from the game they were hurt in and include any offseason.`
          + (t ? ` <b>The team’s first timeline:</b> ${int(t.later)} of ${int(t.injuries)} came back later than its longest estimate${t.late_by != null ? ` (a median ${dec(t.late_by)} weeks late)` : ''}, ${int(t.sooner)} sooner.` : '');
    },
    pairsOf(target, g, list) {
      const rows = list.map(([k, label, unit]) => [g.outcomes.find((r) => r.outcome === k), label, unit]).filter(([r]) => r);
      const missing = list.filter(([k]) => !g.outcomes.some((r) => r.outcome === k)).map(([, label]) => label);
      if (!rows.length) { target.innerHTML = '<div class="empty">Too few injuries with the years to follow yet.</div>'; return; }
      pairs(target, rows.map(([r, label, unit]) => ({ label, a: r.them, b: r.matched, format: (v) => amount(v, unit),
        sub: `${span(r, unit)}${clearOf(r) ? '' : ', no clear difference'} · ${int(r.injuries)} injuries` })), { scale: 'row' });
      if (missing.length) target.insertAdjacentHTML('beforeend', `<p class="note">${esc(missing.join(', '))}: too few of these injuries to tell yet.</p>`);
    },
    cases(el, g, L, end) {
      const card = $('#a-cases-card', el);
      card.hidden = !g.cases;
      if (!g.cases) return;
      const rows = [...g.cases].reverse(), all = this.allCases === g.key, shown = all ? rows : rows.slice(0, 10);
      $('#a-cases-title', el).textContent = `Every ${g.name.charAt(0).toLowerCase()}${g.name.slice(1)}${L.name === 'college' ? ' in college' : ''} since ${L.since}`;
      $('#a-cases-meta', el).textContent = 'Newest first. The year before the injury, then the first year back, in regular-season games.';
      const pair = (a, b) => (a == null ? '–' : `${dec(a)}<span class="arrow" aria-hidden="true"> → </span><span class="sr-only"> before, then </span>${b == null ? '–' : dec(b)}`);
      $('#a-cases', el).innerHTML = `<div class="table-wrap"><table class="data cases"><thead><tr><th scope="col">Player</th><th scope="col">Back</th><th class="n" scope="col">Days out</th><th class="n" scope="col">Games missed</th><th class="n" scope="col">Minutes a game</th><th class="n" scope="col">Production per 36</th></tr></thead><tbody>`
        + shown.map((r) => `<tr><td class="who"><a class="name" href="${L.profile(r)}">${esc(r.player)}</a><span class="sub">${r.hurt ? `Hurt ${esc(shortMonth(r.hurt))}` : `First listed ${esc(shortMonth(r.listed))}`}${r.nba ? ' · reached the NBA' : ''}</span></td>`
          + `<td class="nowrap">${r.back ? esc(shortMonth(r.back)) : `<span class="pill neg">${daysBetween(r.hurt || r.listed, end) < 400 ? 'Not back yet' : 'Not back'}</span>`}</td>`
          + `<td class="n">${r.back && r.hurt ? int(daysBetween(r.hurt, r.back)) : '–'}<span class="unit"> days out</span></td><td class="n">${int(r.games_missed)}<span class="unit"> games missed</span></td>`
          + `<td class="n">${pair(r.mpg_before, r.mpg_after)}<span class="unit"> minutes a game</span></td><td class="n">${pair(r.production_before, r.production_after)}<span class="unit"> production per 36</span></td></tr>`).join('')
        + '</tbody></table></div><p class="note">A dash after the arrow: not back yet, or too few games back to judge by.</p>'
        + (rows.length > 10 ? `<button type="button" class="btn" id="a-more" style="margin-top:12px">${all ? 'Show the latest 10' : `Show all ${rows.length}`}</button>` : '');
      const more = $('#a-more', el);
      if (more) more.addEventListener('click', () => { this.allCases = all ? null : g.key; this.cases(el, g, L, end); });
    },
    table(el, c, league) {
      const versus = (r, unit) => (r ? `${pct(r.them, 0)}<span class="unit"> ${unit}</span><span class="sub">vs ${pct(r.matched, 0)}</span>` : '–');
      const college = league === 'college';
      const head = college
        ? '<th class="n" scope="col">Injuries</th><th class="n" scope="col">Games missed</th><th class="n hide-sm" scope="col">Season over</th><th class="n" scope="col">Minutes a game</th><th class="n" scope="col">Next season</th><th class="n hide-sm" scope="col">Reached the NBA</th>'
        : '<th class="n" scope="col">Injuries</th><th class="n" scope="col">Games missed</th><th class="n hide-sm" scope="col">Days to return</th><th class="n hide-sm" scope="col">Back in a year</th><th class="n" scope="col">Minutes a game</th><th class="n" scope="col">Hurt there again</th>';
      $('#a-table', el).innerHTML = `<table class="data kinds"><thead><tr><th scope="col">Injury</th>${head}</tr></thead><tbody>`
        + c.groups.map((g) => {
          const m = one(g.year_1, 'mpg'), faint = (r) => (r && !clearOf(r) ? ' faint' : '');
          const middle = college
            ? `<td class="n hide-sm">${pct(g.season_over, 0)}</td>`
            : `<td class="n hide-sm">${g.median_days == null ? '–' : int(g.median_days)}</td><td class="n hide-sm">${pct(g.back_within_a_year, 0)}</td>`;
          const end = college
            ? `<td class="n${faint(one(g.outcomes, 'next_season'))}">${versus(one(g.outcomes, 'next_season'), 'in Division I the next season')}</td><td class="n hide-sm${faint(one(g.outcomes, 'nba'))}">${versus(one(g.outcomes, 'nba'), 'reached the NBA')}</td>`
            : `<td class="n${faint(one(g.outcomes, 'same_region'))}">${versus(one(g.outcomes, 'same_region'), 'hurt there again')}</td>`;
          return `<tr data-key="${g.key}"><td><a class="name" href="#careers/${college ? 'college/' : ''}${g.key}">${esc(g.key === 'all' ? 'Every injury' : g.name)}</a></td><td class="n">${int(g.injuries)}<span class="unit"> injuries</span></td>`
            + `<td class="n">${dec(g.games_missed.median, 0)}<span class="unit"> games out</span></td>${middle}`
            + `<td class="n${faint(m)}">${m ? signed(m.effect) : '–'}<span class="unit"> minutes a game</span></td>${end}</tr>`;
        }).join('') + '</tbody></table>';
      $('#a-table-note', el).textContent = college
        ? 'Minutes a game: the change in the first year back against players like them. Season over: the share that didn’t play again that season. Next season and the NBA: the injured players against players like them. Grey: no clear difference.'
        : 'Minutes a game: the change in the first year back against players like them. Hurt there again: within a year of coming back. Grey: no clear difference.';
    },
    method(el, c, league) {
      const L = LEAGUES[league], b = Object.fromEntries(c.balance.map((r) => [r.measure, r]));
      const p = Object.fromEntries([...c.placebo.came_back.map((r) => [r.metric, r]), ...c.placebo.outcomes.map((r) => [r.outcome, r])]);
      $('#a-method', el).innerHTML = league === 'college'
        ? `<p>Every Covers-listed injury to a Division I men’s player since 2019-20 that cost the team 4 or more games, every torn ACL, Achilles and meniscus the notes name, and every concussion: <b>${int(c.followed)} of ${int(c.injuries)}</b> had the games before them to compare against. Players are followed in ESPN’s box scores, whose ids hold across seasons and transfers.</p>`
          + '<p>Each player is set against the <b>ten players most like them</b> the day they were hurt: seasons already played in Division I, minutes, production per 36, the share of their team’s games they played and how often their team won, with the same correction as the NBA study.</p>'
          + '<p>Two limits. Covers’ page was saved on 2 to 76 days a season, so some injuries are missing, and “listed hurt again” rests on the two seasons saved on 30 or more days. And there is no class year, so a senior who graduates looks like a player who stopped. Ranges are 95%, resampling players; with this many measures, a few will miss zero by chance.</p>'
        : `<p>Every NBA injury since 2018-19 that cost 10 or more games, every torn ACL, Achilles and meniscus, and every concussion: <b>${int(c.followed)} of ${int(c.injuries)}</b> had a year of games before them to compare against. The diagnosis is the news’s where the research named it, else the injury report’s.</p>`
          + '<p>Each player is set against the <b>ten players most like them</b> the day they were hurt: age, minutes, production per 36 and the share of their team’s games they played. Their change over the same dates takes out aging and the league’s drift, and a straight line fitted across everyone playing that day corrects what is left of the gap between them.</p>'
          + '<p>These are associations in public data, not proof: who gets hurt, and who comes back, isn’t random. Ranges are 95%, resampling players. With 13 kinds of injury and many measures, a few will miss zero by chance.</p>';
      const fact = (label, value) => `<div><dt>${label}</dt><dd>${value}</dd></div>`;
      const share = (k) => ['same_region', 'playing_2', 'next_season', 'nba'].includes(k);
      const ci = (r, f) => `${f(r.effect ?? r.difference)} <span class="faint">(${f(r.lo)} to ${f(r.hi)})</span>`;
      const rows = L.placebo.filter(([k]) => p[k]), off = rows.filter(([k]) => clearOf(p[k]));
      $('#a-alike', el).innerHTML = '<h3 class="sub-head">How alike they were, the day they were hurt</h3><p class="note" style="margin-top:0">The injured players against the ten like each of them:</p><dl class="facts">'
        + L.alike.filter(([k]) => b[k]).map(([k, label, unit]) => fact(label, `${amount(b[k].injured, unit)} against ${amount(b[k].matched, unit)}`)).join('') + '</dl>';
      $('#a-placebo', el).innerHTML = '<h3 class="sub-head">The placebo: players who weren’t hurt</h3><p class="note" style="margin-top:0">Five healthy players for each injury, through the same steps over the same dates. '
        + (off.length ? `The method found nothing, except a small bias on ${off.map(([, label]) => label.toLowerCase()).join(' and ')}: changes that small aren’t findings.` : 'The method found nothing:')
        + '</p><dl class="facts">' + rows.map(([k, label]) => fact(label, ci(p[k], share(k) ? (v) => `${signed(100 * v, 1)} pts` : (v) => signed(v, 2)))).join('') + '</dl>';
    },
  };

  // ========================================================================================================== how
  // How NBA players got hurt, from the reviewed news research (news_summary.py), and the earlier studies checked against
  // it (validation.py). Every count says how many injuries it rests on: the news covers stars and severe injuries best.
  const KNOWN = 5;   // injuries with a known cause a kind of injury needs for its row
  const OUTLETS = { national: 'National outlets', wire: 'Wire services', local: 'Local outlets', team: 'The teams', aggregator: 'Aggregators',
    league_media: 'NBA.com', blog: 'Blogs', league: 'The league', school: 'Schools', conference: 'Conferences', student: 'Student papers' };
  const how = {
    async init(el) {
      const st = await load('study'), n = st.news, checks = st.checks;
      if (!n) throw new Error('the news summary is missing');
      const by = Object.fromEntries(n.groups.map((g) => [g.key, g])), mech = n.labels.mechanisms;
      const named = (n.status.confirmed || 0) + (n.status.reported || 0);
      el.innerHTML = `
        <div class="title-row"><div><h1 id="how-title">How it happened</h1><p class="sub">${this.finding(n, by, named)}</p></div></div>
        <div class="kpis">
          <div class="kpi lead"><div class="kpi-label">Diagnosis named</div><div class="kpi-value">${int(named)}<small>of ${int(n.researched)}</small></div><div class="delta">NBA injuries looked up, confirmed or reported</div></div>
          <div class="kpi"><div class="kpi-label">Vague listings named</div><div class="kpi-value">${int(n.vague.named)}<small>of ${int(n.vague.listed)}</small></div><div class="delta">“Knee soreness” and the like</div></div>
          <div class="kpi"><div class="kpi-label">The game it happened in</div><div class="kpi-value">${int(n.game)}</div><div class="delta">Dated, often with the play</div></div>
          <div class="kpi"><div class="kpi-label">How it happened</div><div class="kpi-value">${int(n.all.mechanisms.known)}</div><div class="delta">Contact or not for ${int(n.all.contact.known)}</div></div>
        </div>
        <div class="cards">
          <article class="card span-12"><header><h2>What causes each injury</h2><p class="meta">Injuries where the news says how it happened. Darker: a bigger share of that injury’s known causes.</p></header>
            <div class="table-wrap" id="h-causes"></div>
            <p class="note">The news covers stars and long injuries best, so these counts lean toward them. A cause no report gave is left out rather than guessed. Choose an injury to see what it does to a career.</p></article>
          <article class="card span-6"><header><h2>What they were doing</h2><p class="meta">${int(n.all.plays.known)} injuries where the news names the play</p></header><div id="h-plays"></div></article>
          <article class="card span-6"><header><h2>Contact or not</h2><p class="meta">Share with no contact, where the news says</p></header><div id="h-contact"></div>
            <p class="note">Torn Achilles tendons and pulled muscles happen on their own; sprains, breaks and concussions come from contact.</p></article>
          <article class="card span-6"><header><h2>What the vague listings turned out to be</h2><p class="meta">Injury reports that named only a body part</p></header><div class="table-wrap" id="h-vague"></div></article>
          <article class="card span-6"><header><h2>Where the facts come from</h2><p class="meta">${int(n.sources.citations)} citations from ${int(n.sources.outlets)} outlets</p></header><div id="h-sources"></div>
            <p class="note">Facts with their sources, never a report’s own words. Every fact was checked by rule and a sample of every batch by hand. Pages on NBA.com are named without a link, as its terms ask.</p></article>
          ${checks ? `<article class="card span-12"><header><h2>The other studies, checked against the news</h2><p class="meta">Where the news says what happened, does it agree?</p></header>
            <div class="split"><div><p class="legend" aria-hidden="true"><span><i></i>The play-by-play caught the play</span><span><i class="muted"></i>It didn’t</span></p><div id="h-plays-check" style="margin-top:12px"></div></div>
            <div class="prose" id="h-model-check"></div></div></article>` : ''}
        </div>`;

      // what causes each injury: a count per cause, shaded by its share of the injury's known causes
      const rows = n.groups.filter((g) => g.mechanisms.known >= KNOWN).sort((a, b) => b.mechanisms.known - a.mechanisms.known);
      const cols = Object.keys(mech).filter((k) => n.all.mechanisms.counts.some(([m]) => m === k));
      const cell = (counts, known, k) => {
        const c = (counts.find(([m]) => m === k) || [k, 0])[1], s = c / known;
        return c ? `<td class="n heat" style="--p:${Math.round(s * 70)}%" title="${esc(`${c} of ${known}`)}">${int(c)}</td>` : '<td class="n heat"><span class="faint">·</span></td>';
      };
      const row = (g, name, link) => `<tr><th scope="row">${link ? `<a class="name" href="#careers/${g.key}">${esc(name)}</a>` : `<b>${esc(name)}</b>`}<span class="sub">${int(g.mechanisms.known)} with a known cause</span></th>`
        + cols.map((k) => cell(g.mechanisms.counts, g.mechanisms.known, k)).join('')
        + `<td class="n">${g.contact.known ? `${pct(g.contact.non_contact / g.contact.known, 0)}<span class="sub">${int(g.contact.non_contact)} of ${int(g.contact.known)}</span>` : '–'}</td></tr>`;
      $('#h-causes', el).innerHTML = `<table class="data causes"><thead><tr><th scope="col">Injury</th>${cols.map((k) => `<th class="n" scope="col">${esc(mech[k])}</th>`).join('')}<th class="n" scope="col">No contact</th></tr></thead>`
        + `<tbody>${rows.map((g) => row(g, g.name, true)).join('')}${row(n.all, 'Every injury', false)}</tbody></table>`;

      const playRows = n.all.plays.counts.filter(([k]) => k !== 'other').sort((a, b) => b[1] - a[1]).concat(n.all.plays.counts.filter(([k]) => k === 'other'));
      Charts.barList($('#h-plays', el), playRows.map(([k, c]) => ({ label: n.labels.plays[k], value: c })), { format: Charts.fmt.int });
      const contact = n.groups.filter((g) => g.contact.known >= KNOWN).sort((a, b) => b.contact.non_contact / b.contact.known - a.contact.non_contact / a.contact.known || b.contact.known - a.contact.known);
      Charts.barList($('#h-contact', el), contact.map((g) => ({ label: `${g.name} · ${g.contact.non_contact} of ${g.contact.known}`, value: g.contact.non_contact / g.contact.known })), { format: (v) => pct(v, 0) });

      $('#h-vague', el).innerHTML = `<table class="data vague"><thead><tr><th scope="col">Listed as</th><th class="n" scope="col">Named</th><th scope="col">What the news called them</th></tr></thead><tbody>`
        + n.vague.regions.filter((r) => r.named).slice(0, 6).map((r) => `<tr><td class="name">${esc(r.name)}</td><td class="n">${int(r.named)}<span class="sub">of ${int(r.listed)}</span></td>`
          + `<td class="labels">${r.labels.slice(0, 3).map(([l, c]) => `<span>${esc(l)} <b>${int(c)}</b></span>`).join('')}${r.labels.length > 3 || r.other ? `<span class="faint">${int(r.labels.slice(3).reduce((a, [, c]) => a + c, 0) + r.other)} more</span>` : ''}</td></tr>`).join('')
        + '</tbody></table>';
      Charts.barList($('#h-sources', el), Object.entries(n.sources.kinds).filter(([k, c]) => OUTLETS[k] && c >= 5).map(([k, c]) => ({ label: OUTLETS[k], value: c })), { format: Charts.fmt.int });

      if (checks) this.checks(el, checks);
    },
    finding(n, by, named) {
      const ankle = by.ankle, achilles = by.achilles;
      const top = ankle && [...ankle.mechanisms.counts].sort((a, b) => b[1] - a[1])[0];
      const parts = [`The news named <b>${int(named)} of the ${int(n.researched)}</b> NBA injuries it was searched for`];
      if (top && top[0] === 'stepped_on_foot' && top[1] / ankle.mechanisms.known > 0.5) parts.push(`most ankle sprains came from landing on someone’s foot (${int(top[1])} of ${int(ankle.mechanisms.known)} with a known cause)`);
      if (achilles && achilles.contact.known >= KNOWN && achilles.contact.non_contact / achilles.contact.known >= 0.8) parts.push(`a torn Achilles almost never involved contact (${int(achilles.contact.non_contact)} of ${int(achilles.contact.known)})`);
      return `${parts[0]}${parts.length > 1 ? `. ${parts.slice(1).join(', and ').replace(/^./, (c) => c.toUpperCase())}` : ''}.`;
    },
    checks(el, c) {
      const m = c.moments_vs_news, rows = m.patterns.filter((r) => r.flagged && r.unflagged);
      const p = (v) => (v < 0.001 ? 'p < 0.001' : `p ${dec(v, v < 0.01 ? 3 : 2)}`);
      pairs($('#h-plays-check', el), rows.map((r) => ({ label: r.pattern, a: r.flagged_said / r.flagged, b: r.unflagged_said / r.unflagged, format: (v) => pct(v, 0),
        sub: `${int(r.flagged_said)} of ${int(r.flagged)} against ${int(r.unflagged_said)} of ${int(r.unflagged)} · odds ratio ${dec(r.odds_ratio)} · ${p(r.p)}` })));
      const k = c.model_by_kind, news = k.comparisons.find((r) => /contact/i.test(r.comparison) && /news/i.test(r.comparison));
      $('#h-model-check', el).innerHTML = `<p>The news names the game for <b>${int(m.pinned_exits_with_a_reported_game)}</b> of the injury exits the play-by-play study pinned down, and the play for ${int(m.with_a_reported_play)}. Where the play-by-play caught a foul or a rebound in the 30 seconds before the exit, the news named that play far more often than for the other exits, and after their own steal it described the break or the scramble that followed.</p>`
        + (news ? `<p>The risk model ranks upcoming injuries with an AUC of <b>${dec(k.test_auc, 2)}</b> on the test seasons. It ranked the players about to get a contact injury (<b>${dec(news.auc_b, 2)}</b>, ${int(news.injuries_b)} injuries) ${news.hi < 0 ? 'higher than' : 'about as high as'} those about to get a non-contact one (<b>${dec(news.auc_a, 2)}</b>, ${int(news.injuries_a)}): it flags who gets hurt, not how.</p>` : '')
        + '<p class="note">Each comparison counts only injuries where the news says what happened. Odds ratios and p from Fisher’s exact test; the AUCs from the model refit on the training seasons.</p>';
    },
    show() {},
  };

  // ======================================================================================================== router
  const VIEWS = { board, players, model, factors, when, types, how, careers, college };
  const ready = {};
  async function route() {
    const [name = 'board', ...args] = location.hash.slice(1).split('/');
    const key = VIEWS[name] ? name : 'board';
    $$('.view').forEach((v) => { v.hidden = v.id !== `view-${key}`; });
    $$('.nav-item[data-view]').forEach((a) => (a.dataset.view === key ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
    $('#crumb').textContent = NAMES[key];
    document.title = `${NAMES[key]} · Basketball Injury Project`;
    closeMenu();
    const el = $(`#view-${key}`);
    try {
      if (!ready[key]) { el.innerHTML = '<div class="title-row"><div><div class="skeleton" style="width:220px;height:30px"></div><div class="skeleton" style="width:420px;height:18px;margin-top:8px"></div></div></div>'; ready[key] = VIEWS[key].init(el); }
      await ready[key];
      await VIEWS[key].show(el, args.map(decodeURIComponent));
    } catch (err) { ready[key] = null; fail(el, err); }
  }

  // ---- the phone menu --------------------------------------------------------------------------------------------
  const side = $('#side'), open = $('#menu-open');
  function closeMenu() { side.classList.remove('open'); open.setAttribute('aria-expanded', 'false'); }
  open.addEventListener('click', () => { side.classList.add('open'); open.setAttribute('aria-expanded', 'true'); $('.nav-item', side).focus(); });
  $('#menu-close').addEventListener('click', () => { closeMenu(); open.focus(); });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && side.classList.contains('open')) { closeMenu(); open.focus(); } });

  // ---- find a player -----------------------------------------------------------------------------------------------
  const find = $('#find'), list = $('#find-results');
  const plain = (s) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
  let matches = [], pick = -1;
  // every profile: [id, name, team or school, injuries, league]; college ids start with "c"
  const draw = () => {
    const none = !matches.length && find.value.trim().length > 1;
    list.hidden = !matches.length && !none; find.setAttribute('aria-expanded', String(!list.hidden));
    if (none) { list.innerHTML = `<p class="no-match" role="option" aria-disabled="true">No NBA or college player matches “${esc(find.value.trim())}”.</p>`; find.removeAttribute('aria-activedescendant'); return; }
    list.innerHTML = matches.map(([id, n, team, k, league], i) => `<button type="button" role="option" id="opt-${id}" aria-selected="${i === pick}" data-id="${id}"><span>${esc(n)}</span>`
      + `<small>${esc(team)}${league === 'college' ? ' · College' : ''} · ${k} ${k === 1 ? 'injury' : 'injuries'}</small></button>`).join('');
    if (pick >= 0) find.setAttribute('aria-activedescendant', `opt-${matches[pick][0]}`); else find.removeAttribute('aria-activedescendant');
  };
  const go = (id) => { location.hash = `players/${id}`; find.value = ''; matches = []; pick = -1; draw(); find.blur(); };
  find.addEventListener('focus', () => load('people'));
  find.addEventListener('input', async () => {
    const q = plain(find.value.trim());
    const people = await load('people');
    // NBA players first among equally good matches: their profiles have the most to show
    matches = q ? people.filter((x) => plain(x[1]).includes(q)).sort((a, b) => plain(a[1]).indexOf(q) - plain(b[1]).indexOf(q)
      || (a[4] === 'nba' ? 0 : 1) - (b[4] === 'nba' ? 0 : 1) || a[1].localeCompare(b[1])).slice(0, 8) : [];
    pick = matches.length ? 0 : -1; draw();
  });
  find.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (matches.length) { pick = (pick + (e.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length; draw(); } }
    else if (e.key === 'Enter' && pick >= 0) { e.preventDefault(); go(matches[pick][0]); }
    else if (e.key === 'Escape') { matches = []; draw(); }
  });
  list.addEventListener('click', (e) => { const b = e.target.closest('[data-id]'); if (b) go(b.dataset.id); });
  find.addEventListener('blur', () => setTimeout(() => { matches = []; pick = -1; draw(); }, 150));
  addEventListener('keydown', (e) => { if (e.key === '/' && document.activeElement !== find && !/input|select|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); find.focus(); } });

  addEventListener('hashchange', () => { route(); scrollTo(0, 0); });
  route();
})();

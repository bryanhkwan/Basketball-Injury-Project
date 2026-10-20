// dashboard.js: the dashboards (dashboard.html). One view per question, chosen by the address: #board/2025-10-21,
// #board/2025-10-21/after, #players/1627936, #model/serious_g5, #factors, #when/muscle, #types/knee. Every view is drawn
// from the files in data/ (written by site_build.py) and keeps its state while the reader moves between nights,
// players or kinds of injury.
(() => {
  const { load, esc, pct, int, dec, times, day, shortDay, longDay, dateOf, daysBetween, splitOutcome, bodyPart, dotRows, pairs, vsRows } = window.Site;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const NAMES = { board: 'Risk board', players: 'Players', model: 'Model check', factors: 'What raises risk', when: 'When and who', types: 'Injury types', college: 'NBA vs college' };
  const KINDS = [['any', 'Any injury'], ['muscle', 'Muscles'], ['sprain', 'Ankles'], ['contact', 'Knocks'], ['knee', 'Knees'], ['back', 'Backs'], ['other', 'Other']];
  const fail = (el, err) => { el.innerHTML = `<div class="empty error">Couldn’t load this view: ${esc(err.message)}. Reload the page to try again.</div>`; };
  const segmented = (label, items, on) => `<div class="segmented" role="group" aria-label="${esc(label)}">${items.map(([k, t]) => `<button type="button" data-key="${k}" aria-pressed="${k === on}">${esc(t)}</button>`).join('')}</div>`;
  const press = (root, key) => $$('.segmented button', root).forEach((b) => b.setAttribute('aria-pressed', b.dataset.key === key));

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
  const players = {
    async init(el) {
      this.data = await load('players');
      const p = this.data;
      this.byId = new Map(p.players.map((x) => [x.id, x]));
      this.start = p.dates[0]; this.span = daysBetween(this.start, p.dates.at(-1)) + 1;
      this.league = p.avg.reduce((a, v) => a + v, 0) / p.avg.length / 1000;
      this.featured = [...p.players].sort((a, b) => b.b - a.b || b.inj.length - a.inj.length)[0];
      el.innerHTML = `
        <div class="title-row">
          <div><h1 id="players-title">Players</h1><p class="sub" id="p-sub"></p></div>
          <div class="controls"><label class="sr-only" for="p-pick">Player</label><select class="select" id="p-pick">${[...p.players].sort((a, b) => a.n.localeCompare(b.n)).map((x) => `<option value="${x.id}">${esc(x.n)}</option>`).join('')}</select></div>
        </div>
        <div class="kpis" id="p-kpis"></div>
        <div class="cards">
          <div class="stack span-8">
            <article class="card"><header><h2>Chance of a new injury, game by game</h2><p class="meta">Before each game of 2025-26, for the next 5 games</p></header>
              <p class="legend" aria-hidden="true"><span><i class="line"></i>This player</span><span><i class="dash"></i>League average</span><span><i class="marker"></i>New injury, labelled at its first missed game</span></p>
              <div class="chart" id="p-chart" style="margin-top:8px"></div><p class="note">Gaps are stretches of a week or more without a game, usually time out hurt.</p></article>
            <article class="card"><header><h2>Most nights on the board</h2><p class="meta">Before tip-off, 2025-26</p></header><div id="p-most"></div></article>
          </div>
          <article class="card span-4"><header><h2>New injuries</h2><p class="meta">From the official injury reports</p></header><div id="p-inj"></div></article>
        </div>`;
      $('#p-pick', el).addEventListener('change', (e) => { location.hash = `players/${e.target.value}`; });
      const most = [...p.players].sort((a, b) => b.b - a.b).slice(0, 8);
      $('#p-most', el).innerHTML = `<table class="data"><thead><tr><th scope="col">Player</th><th scope="col">Team</th><th class="n" scope="col">Nights</th><th class="n" scope="col">New injuries</th><th class="n" scope="col">Average chance</th></tr></thead><tbody>${most.map((x) => `<tr><td><a class="name" href="#players/${x.id}">${esc(x.n)}</a></td><td>${esc(x.tm.at(-1)[1])}</td><td class="n">${x.b}</td><td class="n">${x.inj.length}</td><td class="n">${pct(x.r.reduce((a, v) => a + v, 0) / x.r.length / 1000, 0)}</td></tr>`).join('')}</tbody></table>`;
    },
    show(el, [idArg]) {
      const x = this.byId.get(+idArg) || this.featured, p = this.data;
      $('#p-pick', el).value = String(x.id);
      $('#players-title', el).textContent = x.n;
      const teams = x.tm.map(([, t]) => t).join(', then ');
      const games = x.r.length, mean = x.r.reduce((a, v) => a + v, 0) / games / 1000;
      const peakAt = x.r.indexOf(Math.max(...x.r)), missed = x.inj.reduce((a, r) => a + r[2], 0);
      $('#p-sub', el).innerHTML = `${esc(teams)} · ${games} games scored in 2025-26 · ${x.inj.length ? `<b>${x.inj.length} new ${x.inj.length === 1 ? 'injury' : 'injuries'}</b>` : 'no new injuries'}`;
      $('#p-kpis', el).innerHTML = `<div class="kpi lead"><div class="kpi-label">Average chance</div><div class="kpi-value">${pct(mean, 0)}</div><div class="delta">League average ${pct(this.league, 0)}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Highest chance</div><div class="kpi-value">${pct(x.r[peakAt] / 1000, 0)}</div><div class="delta">${esc(day(p.dates[x.d[peakAt]]))}</div></div>`
        + `<div class="kpi"><div class="kpi-label">Nights on the board</div><div class="kpi-value">${x.b}</div><div class="delta">Of ${p.dates.length} nights</div></div>`
        + `<div class="kpi"><div class="kpi-label">New injuries</div><div class="kpi-value">${x.inj.length}</div><div class="delta">${missed ? `${missed} games missed` : '–'}</div></div>`;
      const points = x.d.map((di, k) => ({ x: daysBetween(this.start, p.dates[di]), v: x.r[k] / 1000, label: longDay(p.dates[di]) }));
      const ticksAt = []; for (let k = 0; k < this.span; k++) { const dt = new Date(dateOf(this.start).getTime() + k * 86400000); if (dt.getDate() === 1) ticksAt.push({ at: k, label: dt.toLocaleString('en-US', { month: 'short' }) }); }
      const markers = x.inj.map(([d, why]) => ({ at: daysBetween(this.start, d), label: bodyPart(why) }));
      Charts.timeLine($('#p-chart', el), { points, days: this.span, ticksAt, markers, height: 280, reference: { value: this.league, label: 'League average' } });
      $('#p-inj', el).innerHTML = x.inj.length
        ? `<table class="data"><thead><tr><th scope="col">First game missed</th><th scope="col">Injury</th><th class="n" scope="col">Games</th></tr></thead><tbody>${x.inj.map(([d, why, g]) => `<tr><td>${esc(shortDay(d))}</td><td>${esc(why)}</td><td class="n">${g}</td></tr>`).join('')}</tbody></table>`
        : '<div class="empty">No new injuries in 2025-26.</div>';
    },
  };

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
  // The same injury-moment test in both leagues. College players appear only as totals.
  const COMPARE_KINDS = [['any', 'Any injury'], ['ankle', 'Ankle'], ['knee', 'Knee'], ['foot', 'Foot'], ['muscle', 'Muscle'],
    ['back_hip', 'Back & hip'], ['hand', 'Hand & arm'], ['head', 'Head'], ['shoulder', 'Shoulder'], ['other', 'Other']];
  const STOPS = { 'own timeout': 'The team’s own timeout', 'opponent timeout': 'The other team’s timeout', 'media timeout': 'A media timeout',
    foul: 'A foul', 'free throws': 'Free throws', break: 'A break between periods', 'turnover or violation': 'A turnover or violation',
    'team rebound': 'A team rebound', 'no logged stoppage': 'Nothing logged: play just stopped', 'jump ball': 'A jump ball' };
  const TESTS = { H1: 'Ankle injury, after drawing a foul', H2: 'Any injury, after a steal', H3: 'Hand or arm injury, after a rim attack',
    H4: 'Pulled muscle or Achilles, after a drive', H5: 'Ankle injury, after a rebound' };
  const seasonName = (y) => `${y - 1}-${String(y).slice(2)}`;
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
          <div><h1 id="college-title">NBA vs college</h1><p class="sub">The same injury-moment test on NBA games and on Division I men’s games, ${seasonName(c.seasons[0].season)} to ${seasonName(c.seasons.at(-1).season)}. The college test followed a plan written down and fingerprinted before any college result. College players appear only as totals.</p></div>
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
        + `<p class="note">Games kept are those with clean play-by-play. College injuries come from ${int(c.listings.named)} listings on Covers’ public college injury page, read from ${int(f.college_saved_pages)} copies saved by the Internet Archive; ${pct(c.listings.matched, 0)} matched to a player in the box scores. The listings only point to the injuries. No college player is named on this site.</p>`;
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

  // ======================================================================================================== router
  const VIEWS = { board, players, model, factors, when, types, college };
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
      VIEWS[key].show(el, args.map(decodeURIComponent));
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
  const draw = () => {
    const none = !matches.length && find.value.trim().length > 1;
    list.hidden = !matches.length && !none; find.setAttribute('aria-expanded', String(!list.hidden));
    if (none) { list.innerHTML = `<p class="no-match" role="option" aria-disabled="true">No player matches “${esc(find.value.trim())}” in 2025-26.</p>`; find.removeAttribute('aria-activedescendant'); return; }
    list.innerHTML = matches.map((x, i) => `<button type="button" role="option" id="opt-${x.id}" aria-selected="${i === pick}" data-id="${x.id}"><span>${esc(x.n)}</span><small>${esc(x.tm.at(-1)[1])} · ${x.inj.length} ${x.inj.length === 1 ? 'injury' : 'injuries'}</small></button>`).join('');
    if (pick >= 0) find.setAttribute('aria-activedescendant', `opt-${matches[pick].id}`); else find.removeAttribute('aria-activedescendant');
  };
  const go = (id) => { location.hash = `players/${id}`; find.value = ''; matches = []; pick = -1; draw(); find.blur(); };
  find.addEventListener('focus', () => load('players'));
  find.addEventListener('input', async () => {
    const q = plain(find.value.trim());
    const p = await load('players');
    matches = q ? p.players.filter((x) => plain(x.n).includes(q)).sort((a, b) => plain(a.n).indexOf(q) - plain(b.n).indexOf(q) || a.n.localeCompare(b.n)).slice(0, 8) : [];
    pick = matches.length ? 0 : -1; draw();
  });
  find.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (matches.length) { pick = (pick + (e.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length; draw(); } }
    else if (e.key === 'Enter' && pick >= 0) { e.preventDefault(); go(matches[pick].id); }
    else if (e.key === 'Escape') { matches = []; draw(); }
  });
  list.addEventListener('click', (e) => { const b = e.target.closest('[data-id]'); if (b) go(b.dataset.id); });
  find.addEventListener('blur', () => setTimeout(() => { matches = []; pick = -1; draw(); }, 150));
  addEventListener('keydown', (e) => { if (e.key === '/' && document.activeElement !== find && !/input|select|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); find.focus(); } });

  addEventListener('hashchange', () => { route(); scrollTo(0, 0); });
  route();
})();

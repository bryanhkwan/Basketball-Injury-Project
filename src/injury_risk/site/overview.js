// overview.js: the overview page (index.html). The live risk board in the first screen, the five dashboards shown as
// working sheets, the kinds of injury as tabs, the diagram of how it is built, and the motion layer. Everything is
// readable without it: the first night’s board and every finding are in the HTML.
(() => {
  const { load, esc, pct, int, dec, times, day, shortDay, longDay, boardRow, dotRows, pairs } = window.Site;
  const $ = (s, root = document) => root.querySelector(s);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- motion: each part enters once, staggered within its section ------------------------------------------------
  document.querySelectorAll('main section, .board').forEach((sec) => {
    sec.querySelectorAll('[data-rise]').forEach((el, i) => { if (!el.style.getPropertyValue('--i')) el.style.setProperty('--i', i); });
  });
  const io = 'IntersectionObserver' in window && !reduce
    ? new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { rootMargin: '0px 0px -6% 0px' })
    : null;
  const reveal = (el) => (io ? io.observe(el) : el.classList.add('in'));
  document.querySelectorAll('[data-rise], .shutter, .record-bars, .how-diagram').forEach(reveal);

  // the record’s photograph settles as it crosses the screen
  const photo = $('.record-photo');
  if (photo && !reduce) {
    let ticking = false;
    const drift = () => {
      ticking = false;
      const r = photo.getBoundingClientRect(), h = innerHeight;
      const t = Math.min(1, Math.max(0, (h - r.top) / (h + r.height)));
      photo.style.setProperty('--drift', (1.1 - 0.1 * t).toFixed(4));
    };
    addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(drift); } }, { passive: true });
    drift();
  }

  // ---- the footer’s name runs exactly across the content width, measured once the fonts are in ----------------------
  const footName = $('.foot-name');
  if (footName) {
    footName.innerHTML = `<span>${footName.textContent}</span>`;
    const fit = () => {
      const span = footName.firstChild, cs = getComputedStyle(footName);
      const room = footName.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      span.style.fontSize = '';
      const size = parseFloat(getComputedStyle(span).fontSize), wide = span.getBoundingClientRect().width;
      if (wide > 0) span.style.fontSize = `${Math.floor(size * (room / wide) * 10) / 10}px`;
    };
    fit();
    document.fonts?.ready.then(fit);
    addEventListener('resize', fit);
  }

  // ---- the live board: pick a night of 2025-26 ----------------------------------------------------------------------
  const live = $('#live');
  const boardData = load('board');
  if (live) {
    boardData.then((b) => {
      const nights = b.modes.before.nights;
      const sel = $('#live-night'), prev = $('#live-prev'), next = $('#live-next');
      let at = Math.max(0, nights.findIndex(([d]) => d === live.dataset.day));
      sel.innerHTML = nights.map(([d], i) => `<option value="${i}">${day(d)}</option>`).join('');
      const show = (i) => {
        at = Math.max(0, Math.min(nights.length - 1, i));
        const [d, rows] = nights[at];
        sel.value = String(at); prev.disabled = at === 0; next.disabled = at === nights.length - 1;
        $('#live-rows').innerHTML = rows.slice(0, 5).map((r, k) => boardRow(r, k + 1)).join('');
        const hurt = rows.filter((r) => r[6]).length;
        $('#live-sum').innerHTML = `<span class="sr-only">${esc(day(d))}: </span>${hurt} of these ${rows.length} had a new injury within 5 games.`;
        $('#live-date').textContent = `${longDay(d)} · ${at + 1} of ${nights.length} nights in 2025-26`;
        const link = $('#live-link'); link.href = `dashboard.html#board/${d}`; link.textContent = `See all ${rows.length} on the board`;
      };
      sel.disabled = false;
      sel.addEventListener('change', () => show(+sel.value));
      prev.addEventListener('click', () => show(at - 1));
      next.addEventListener('click', () => show(at + 1));
      show(at);
    }).catch(() => { $('#live-sum').textContent += ' Other nights could not be loaded.'; });
  }

  // ---- the five dashboards, each shown as a working sheet ----------------------------------------------------------
  const OUTPUTS = {
    board: {
      text: 'Every night of the 2025-26 season, the twelve players the model rated most at risk before tip-off, and what happened to each of them in their next five games.',
      link: ['dashboard.html#board', 'Open the risk board'],
      async render(el) {
        const b = await boardData, nights = b.modes.before.nights;
        const hits = nights.map(([, rows]) => rows.filter((r) => r[6]).length);
        const flagged = nights.reduce((a, [, rows]) => a + rows.length, 0), hurt = hits.reduce((a, v) => a + v, 0);
        const none = hits.filter((v) => v === 0).length;
        el.innerHTML = `<h3>Every night of 2025-26</h3><p class="sheet-meta">Players on each night’s board who had a new injury within 5 games</p>
          <div class="mini-kpis"><div><span>Nights</span><b>${int(nights.length)}</b></div><div><span>Players flagged</span><b>${int(flagged)}</b></div><div><span>Got hurt</span><b>${pct(hurt / flagged)}</b></div></div>
          <div class="chart" id="sheet-chart"></div>
          <p class="finding"><b>${int(nights.length - none)} of ${nights.length} nights</b> had at least one flagged player hurt within five games. Across all players the rate was ${pct(b.check.before.all.rate)}.</p>`;
        Charts.bars($('#sheet-chart', el), { labels: nights.map(([d]) => shortDay(d)), values: hits, height: 170, format: Charts.fmt.int, reference: { value: hurt / nights.length, label: `Average ${dec(hurt / nights.length)}` } });
      },
    },
    players: {
      text: "Any player’s chance of a new injury, game by game through 2025-26, with each injury marked where it happened. Search for anyone who played.",
      link: ['dashboard.html#players', 'Open player timelines'],
      async render(el) {
        const p = await load('players');
        const pick = [...p.players].sort((a, b) => b.b - a.b).find((x) => x.inj.length >= 2) || p.players[0];
        const start = p.dates[0], span = Site.daysBetween(start, p.dates.at(-1)) + 1;
        const points = pick.d.map((di, k) => ({ x: Site.daysBetween(start, p.dates[di]), v: pick.r[k] / 1000, label: day(p.dates[di]) }));
        const months = []; for (let k = 0; k < span; k++) { const dt = new Date(Site.dateOf(start).getTime() + k * 86400000); if (dt.getDate() === 1) months.push({ at: k, label: dt.toLocaleString('en-US', { month: 'short' }) }); }
        const markers = pick.inj.map(([d, why]) => ({ at: Site.daysBetween(start, d), label: Site.bodyPart(why) }));
        const avg = pick.r.reduce((a, v) => a + v, 0) / pick.r.length / 1000;
        el.innerHTML = `<h3>${esc(pick.n)}, ${esc(pick.tm.at(-1)[1])}</h3><p class="sheet-meta">Chance of a new injury in the next 5 games, before each game of 2025-26</p>
          <div class="mini-kpis"><div><span>Games scored</span><b>${int(pick.r.length)}</b></div><div><span>Average chance</span><b>${pct(avg, 0)}</b></div><div><span>New injuries</span><b>${int(pick.inj.length)}</b></div></div>
          <div class="chart" id="sheet-chart"></div>
          <p class="finding"><b>${int(pick.b)} nights</b> on the board, the most of any player hurt twice or more. Gaps in the line are games missed.</p>`;
        Charts.timeLine($('#sheet-chart', el), { points, days: span, ticksAt: months, markers, height: 210, reference: { value: p.avg.reduce((a, v) => a + v, 0) / p.avg.length / 1000, label: 'League average' } });
      },
    },
    model: {
      text: 'How well the model ranks risk on seasons it never saw: its accuracy, how it compares with simpler models, and whether its percentages come true.',
      link: ['dashboard.html#model', 'Open the model check'],
      async render(el) {
        const s = (await load('study')).model;
        const main = s.scores.find((r) => r.question === 'pregame_g5' && r.model === 'full_gbm');
        const base = s.scores.find((r) => r.question === 'pregame_g5' && r.model === 'history_logistic');
        const rows = s.calibration.filter((r) => r.question === 'pregame_g5').sort((a, b) => a.decile - b.decile)
          .map((r) => ({ predicted: r.predicted, observed: r.observed, label: `Tenth ${r.decile} of ${int(r.rows)} player-games` }));
        const last = rows.at(-1);
        el.innerHTML = `<h3>Before tip-off, the next 5 games</h3><p class="sheet-meta">${int(main.rows)} player-games in 2024-25 and 2025-26, never used in training</p>
          <div class="mini-kpis"><div><span>AUC</span><b>${dec(main.auc, 2)}</b></div><div><span>Age and history only</span><b>${dec(base.auc, 2)}</b></div><div><span>Riskiest tenth</span><b>${dec(main.top10_lift)}<small>× avg</small></b></div></div>
          <div class="chart" id="sheet-chart"></div>
          <p class="finding">Its riskiest tenth were given <b>${pct(last.predicted, 0)}</b> on average, and <b>${pct(last.observed, 0)}</b> of them got hurt. Dots near the dashed line mean the chances came true.</p>`;
        Charts.calibration($('#sheet-chart', el), { rows, height: 220, xLabel: 'Predicted chance', yLabel: 'Came true' });
      },
    },
    why: {
      text: 'Which situations and which players come before more injuries, for each kind of injury, counted only when the pattern held in both halves of the seasons.',
      link: ['dashboard.html#when', 'Open when and who'],
      async render(el) {
        const c = (await load('study')).causes;
        const rows = [...c.situations, ...c.traits].filter((r) => r.group === 'any' && r.headline).sort((a, b) => Math.abs(Math.log(b.ratio)) - Math.abs(Math.log(a.ratio))).slice(0, 7);
        el.innerHTML = `<h3>What comes before a new injury</h3><p class="sheet-meta">How many times as likely, with the likely range. 1× is no difference.</p>
          <div class="chart" id="sheet-chart"></div>
          <p class="legend" aria-hidden="true"><span><i class="dot"></i>More likely</span><span><i class="ring"></i>Less likely</span></p>
          <p class="finding"><b>Two or more injuries in the past year</b> is the strongest sign for every kind of injury. Travel made no clear difference.</p>`;
        dotRows($('#sheet-chart', el), rows.map((r) => ({ ...r, sub: `vs ${r.versus || 'everyone else'}` })), { track: 150 });
      },
    },
    moments: {
      text: 'What was happening in the last half-minute before players left a game hurt, across seven NBA seasons, then checked in college basketball against a plan written in advance.',
      link: ['moments.html', 'Read the report'],
      async render(el) {
        const m = (await load('study')).moments;
        const rows = [...m.patterns].sort((a, b) => a.order - b.order);
        const ankle = rows.find((r) => r.key === 'ankle:fouled');
        el.innerHTML = `<h3>The half-minute before NBA players left hurt</h3><p class="sheet-meta">Share of injury exits with each play, against the same players' normal substitutions</p>
          <p class="legend" aria-hidden="true" style="margin-top:12px"><span><i></i>Injury exits</span><span><i class="muted"></i>Normal substitutions</span></p>
          <div class="chart" id="sheet-chart" style="margin-top:12px"></div>
          <p class="finding"><b>${int(m.facts.nba_traced)} of ${int(m.facts.nba_injuries)}</b> new injuries were traced to the moment the player left. Ankle injuries came right after being fouled ${times(ankle.injury_share / ankle.normal_share)} as often as normal substitutions did.</p>`;
        pairs($('#sheet-chart', el), rows.map((r) => ({ label: r.label.replace(' right after ', ', after ').replace(' by the player', ''), a: r.injury_share, b: r.normal_share })));
      },
    },
  };
  const sheet = $('#out-sheet'), tabs = [...document.querySelectorAll('.output-names [role="tab"]')];
  let current = null;
  const choose = async (tab, focus = false) => {
    const key = tab.id.replace('out-', '');
    if (key === current) return;
    current = key;
    tabs.forEach((t) => { const on = t === tab; t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1; });
    $('#stage').setAttribute('aria-labelledby', tab.id);
    if (focus) tab.focus();
    const o = OUTPUTS[key];
    $('#output-text').textContent = o.text;
    const link = $('#output-link'); link.href = o.link[0]; link.firstChild.textContent = `${o.link[1]} `;
    sheet.classList.add('swapping');
    await new Promise((r) => setTimeout(r, reduce ? 0 : 200));
    try { await o.render(sheet); } catch (e) { sheet.innerHTML = `<p class="error">Couldn’t load this sheet. ${esc(e.message)}</p>`; }
    if (current === key) sheet.classList.remove('swapping');
  };
  if (sheet) {
    tabs.forEach((t, i) => {
      t.addEventListener('click', () => choose(t));
      t.addEventListener('keydown', (e) => {
        const k = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
        if (k) { e.preventDefault(); choose(tabs[(i + k + tabs.length) % tabs.length], true); }
        if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); choose(tabs[e.key === 'Home' ? 0 : tabs.length - 1], true); }
      });
    });
    choose(tabs[0]);
  }

  // ---- kinds of injury as tabs ---------------------------------------------------------------------------------------
  const kindTabs = [...document.querySelectorAll('.kind-tabs [role="tab"]')];
  const pickKind = (tab, focus) => {
    kindTabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    });
    if (focus) tab.focus();
  };
  kindTabs.forEach((t, i) => {
    t.addEventListener('click', () => pickKind(t));
    t.addEventListener('keydown', (e) => {
      const k = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (k) { e.preventDefault(); pickKind(kindTabs[(i + k + kindTabs.length) % kindTabs.length], true); }
    });
  });

  // ---- how it is built: scattered lines, one table, an ordered ranking ---------------------------------------------
  const diagram = $('#how-diagram');
  if (diagram) {
    // a fixed sequence instead of Math.random, so the scatter is the same on every visit
    let seed = 7; const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const draw = () => {
      const tall = diagram.clientWidth < 560;
      const W = tall ? 300 : 1200, H = tall ? 400 : 267, S = tall ? 9 : 12, gap = tall ? 2 : 3;
      diagram.setAttribute('viewBox', `0 0 ${W} ${H}`);
      seed = 7;
      const out = [];
      const sq = (x, y, cls, k) => out.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${S}" height="${S}" class="${cls}" style="--d:${k}ms"/>`);
      if (!tall) {
        for (let k = 0; k < 60; k++) sq(16 + rand() * 340, 12 + rand() * (H - 24 - S), k % 3 ? 'sq-a' : 'sq-b', Math.round(k * 4));
        const cols = 16; for (let k = 0; k < cols * 3; k++) sq(430 + (k % cols) * (S + gap), H / 2 - 1.5 * S - gap + Math.floor(k / cols) * (S + gap), 'sq-c', 260 + (k % cols) * 14);
        const rows = [9, 8, 7, 6, 5]; let k = 0;
        rows.forEach((n, r) => { for (let c = 0; c < n; c++, k++) sq(850 + c * (S + 22), 46 + r * (S + 30), r === 0 ? 'sq-d' : 'sq-e', 500 + k * 9); });
      } else {
        for (let k = 0; k < 40; k++) sq(14 + rand() * (W - 28 - S), 8 + rand() * 110, k % 3 ? 'sq-a' : 'sq-b', k * 5);
        const cols = 12; for (let k = 0; k < cols * 3; k++) sq(W / 2 - 1.5 * S - gap + Math.floor(k / cols) * (S + gap), 140 + (k % cols) * (S + gap), 'sq-c', 220 + (k % cols) * 14);
        const rows = [7, 6, 5, 4]; let k = 0;
        rows.forEach((n, r) => { for (let c = 0; c < n; c++, k++) sq(40 + c * (S + 22), 290 + r * (S + 16), r === 0 ? 'sq-d' : 'sq-e', 420 + k * 10); });
      }
      diagram.innerHTML = out.join('');
    };
    draw();
    let lastTall = diagram.clientWidth < 560;
    addEventListener('resize', () => { const t = diagram.clientWidth < 560; if (t !== lastTall) { lastTall = t; draw(); } });
  }
})();

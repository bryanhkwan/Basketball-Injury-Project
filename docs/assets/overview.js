// overview.js: the overview page (index.html). The live risk board in the hero, the record’s charts, the four
// questions' charts, and the motion. Everything the page says is in the HTML; the script adds the other nights and the
// charts, drawn from the files in data/.
(() => {
  const { load, esc, pct, int, dec, times, day, shortDay, longDay, dateOf, daysBetween, splitOutcome, bodyPart, pairs, vsRows } = window.Site;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- the bar across the top turns solid once the page scrolls ---------------------------------------------------
  const nav = $('.nav');
  const onScroll = () => nav.classList.toggle('scrolled', scrollY > 8);
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // ---- motion: the court draws itself, and each part rises once as it comes into view ------------------------------
  $$('.court > *').forEach((el, i) => el.style.setProperty('--d', i));
  $$('main section').forEach((sec) => $$('[data-rise]', sec).forEach((el, i) => { if (!el.style.getPropertyValue('--i')) el.style.setProperty('--i', i % 6); }));
  const io = 'IntersectionObserver' in window && !reduce
    ? new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { rootMargin: '0px 0px -8% 0px' })
    : null;
  $$('[data-rise], .ladder').forEach((el) => (io ? io.observe(el) : el.classList.add('in')));
  $$('.ladder li').forEach((li, i) => li.querySelector('i').style.setProperty('--i', i));

  // ---- the live risk board ----------------------------------------------------------------------------------------
  const boardRow = (r, rank, top) => {
    const [injury, cost] = r[6] ? splitOutcome(r[7]) : ['', ''];
    const what = r[6] ? `<span class="out hurt">${esc(injury)}, ${esc(cost)}</span>` : '<span class="out">No new injury</span>';
    return `<li class="bc-row${r[6] ? ' is-hurt' : ''}"><span class="bc-rank">${rank}</span><span class="bc-who"><b>${esc(r[1])}</b>`
      + `<small>${esc(r[2])} vs ${esc(r[3])} · ${what}</small></span><span class="bc-chance"><span class="bc-bar" aria-hidden="true">`
      + `<i style="width:${Math.round((100 * r[4]) / top)}%"></i></span><b>${Math.round(r[4] / 10)}%</b></span></li>`;
  };
  const live = $('#live'), boardData = load('board');
  boardData.then((b) => {
    const nights = b.modes.before.nights;
    const sel = $('#live-night'), prev = $('#live-prev'), next = $('#live-next');
    let at = Math.max(0, nights.findIndex(([d]) => d === live.dataset.day));
    sel.innerHTML = nights.map(([d], i) => `<option value="${i}">${day(d)}</option>`).join('');
    const show = (i) => {
      at = Math.max(0, Math.min(nights.length - 1, i));
      const [d, rows] = nights[at], top = Math.max(...rows.map((r) => r[4]));
      sel.value = String(at); prev.disabled = at === 0; next.disabled = at === nights.length - 1;
      $('#live-rows').innerHTML = rows.slice(0, 5).map((r, k) => boardRow(r, k + 1, top)).join('');
      const hurt = rows.filter((r) => r[6]).length;
      $('#live-sum').innerHTML = `<span class="sr-only">${esc(day(d))}: </span>${hurt} of these ${rows.length} had a new injury within 5 games.`;
      $('#live-date').textContent = at === 0 ? `${longDay(d)} · opening night` : longDay(d);
      $('#live-link').href = `dashboard.html#board/${d}`;
    };
    sel.disabled = false;
    sel.addEventListener('change', () => show(+sel.value));
    prev.addEventListener('click', () => show(at - 1));
    next.addEventListener('click', () => show(at + 1));
    show(at);
  }).catch(() => { $('#live-sum').textContent += ' Other nights could not be loaded.'; });

  // ---- the record: calibration and every night of the season -------------------------------------------------------
  const study = load('study');
  const fail = (el) => () => { el.innerHTML = '<p class="panel-sub">This chart could not be loaded. Reload the page to try again.</p>'; };
  const cal = $('#cal-chart');
  study.then((s) => {
    const rows = s.model.calibration.filter((r) => r.question === 'pregame_g5').sort((a, b) => a.decile - b.decile)
      .map((r) => ({ predicted: r.predicted, observed: r.observed, label: `Tenth ${r.decile} · ${int(r.rows)} player-games` }));
    Charts.calibration(cal, { rows, height: 250, xLabel: 'Predicted chance', yLabel: '' });
  }).catch(fail(cal));
  const strip = $('#strip-chart');
  boardData.then((b) => {
    const nights = b.modes.before.nights, hits = nights.map(([, rows]) => rows.filter((r) => r[6]).length);
    const avg = hits.reduce((a, v) => a + v, 0) / nights.length;
    Charts.bars(strip, { labels: nights.map(([d]) => shortDay(d)), values: hits, height: 190, format: Charts.fmt.int,
      reference: { value: avg, label: `Average ${dec(avg)} a night` }, onSelect: (i) => { location.href = `dashboard.html#board/${nights[i][0]}`; } });
  }).catch(fail(strip));

  // ---- who’s at risk: a player’s season, with a few players to switch between --------------------------------------
  const tl = $('#tl-chart');
  load('players').then((p) => {
    const start = p.dates[0], span = daysBetween(start, p.dates.at(-1)) + 1;
    const league = p.avg.reduce((a, v) => a + v, 0) / p.avg.length / 1000;
    const months = [];
    for (let k = 0; k < span; k++) { const dt = new Date(dateOf(start).getTime() + k * 86400000); if (dt.getDate() === 1) months.push({ at: k, label: dt.toLocaleString('en-US', { month: 'short' }) }); }
    const picks = [...p.players].filter((x) => x.inj.length >= 2).sort((a, b) => b.b - a.b).slice(0, 4);
    const chips = $('#tl-chips');
    chips.innerHTML = picks.map((x, i) => `<button type="button" data-id="${x.id}" aria-pressed="${i === 0}">${esc(x.n)}</button>`).join('');
    const draw = (x) => {
      $$('button', chips).forEach((btn) => btn.setAttribute('aria-pressed', String(+btn.dataset.id === x.id)));
      const avg = x.r.reduce((a, v) => a + v, 0) / x.r.length / 1000;
      $('#tl-name').textContent = `${x.n}, ${x.tm.at(-1)[1]}`;
      $('#tl-meta').textContent = `${x.b} nights on the board · ${x.inj.length} new injuries · average chance ${pct(avg, 0)}, against ${pct(league, 0)} for the league`;
      Charts.timeLine(tl, { points: x.d.map((di, k) => ({ x: daysBetween(start, p.dates[di]), v: x.r[k] / 1000, label: longDay(p.dates[di]) })),
        days: span, ticksAt: months, markers: x.inj.map(([d, why]) => ({ at: daysBetween(start, d), label: bodyPart(why) })),
        height: 250, reference: { value: league, label: 'League average' } });
    };
    chips.addEventListener('click', (e) => { const btn = e.target.closest('button'); if (btn) draw(picks.find((x) => x.id === +btn.dataset.id)); });
    draw(picks[0]);
  }).catch(fail(tl));

  // ---- what makes an injury more likely: kinds of injury as tabs ---------------------------------------------------
  const kindTabs = $$('.tabs-pills [role="tab"]');
  const pick = (tab, focus) => {
    kindTabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    });
    if (focus) tab.focus();
  };
  kindTabs.forEach((t, i) => {
    t.addEventListener('click', () => pick(t));
    t.addEventListener('keydown', (e) => {
      const k = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (k) { e.preventDefault(); pick(kindTabs[(i + k + kindTabs.length) % kindTabs.length], true); }
    });
  });

  // ---- the moment of injury, and the college check -----------------------------------------------------------------
  const SHORT = { 'ankle:fouled': 'Ankle injury, after being fouled', 'any:steal': 'Any injury, after a steal',
    'hand:opp_rim': 'Hand or arm injury, after a rim attack', 'muscle:drive': 'Pulled muscle or Achilles, after a drive',
    'ankle:rebound': 'Ankle injury, after a rebound' };
  const COLLEGE = { H1: 'Ankle injury, after drawing a foul', H2: 'Any injury, after a steal', H3: 'Hand or arm injury, after a rim attack',
    H4: 'Pulled muscle or Achilles, after a drive', H5: 'Ankle injury, after a rebound' };
  const mom = $('#moments-chart'), col = $('#college-chart');
  study.then((s) => {
    const pats = [...s.moments.patterns].sort((a, b) => a.order - b.order);
    pairs(mom, pats.map((r) => ({ label: `${SHORT[r.key] || r.label} · ${r.verdict_label}`, a: r.injury_share, b: r.normal_share })));
    const byKey = Object.fromEntries(pats.map((r) => [r.key, r]));
    vsRows(col, [...s.moments.college].sort((a, b) => a.order - b.order).map((t) => {
      const n = byKey[t.nba_key], label = COLLEGE[t.key] || t.label;
      return { label, sub: `NBA ${times(n.times)} · college ${times(t.times)} · ${t.verdict_label}`, nba: [n.times, n.lo, n.hi], col: [t.times, t.lo, t.hi],
        aria: `${label}: NBA ${dec(n.times)} times (${dec(n.lo)} to ${dec(n.hi)}), college ${dec(t.times)} times (${dec(t.lo)} to ${dec(t.hi)}). ${t.verdict_label}.` };
    }));
  }).catch(() => { fail(mom)(); fail(col)(); });
})();

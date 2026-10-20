// site.js: helpers shared by the overview (overview.js) and the dashboards (dashboard.js): loading the published
// data, formatting numbers and dates, and the small HTML charts that charts.js does not draw (ratio rows on a log
// scale, paired shares, the night's board rows).
(() => {
  // each file once per page, retried twice when the connection drops; a failed load is forgotten so a later call retries
  const cache = {};
  const fetchJson = async (name, tries = 3) => {
    for (let i = 0; ; i++) {
      try {
        const r = await fetch(`data/${name}.json`);
        if (!r.ok) throw new Error(`Couldn't load ${name} (${r.status})`);
        return await r.json();
      } catch (e) {
        if (i >= tries - 1) throw e;
        await new Promise((res) => setTimeout(res, 400 * (i + 1)));
      }
    }
  };
  const load = (name) => (cache[name] ||= fetchJson(name).catch((e) => { delete cache[name]; throw e; }));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nf = (o) => new Intl.NumberFormat('en-US', o);
  const pct = (v, d = 1) => (v == null ? '–' : nf({ style: 'percent', minimumFractionDigits: d, maximumFractionDigits: d }).format(v));
  const int = (v) => (v == null ? '–' : nf({ maximumFractionDigits: 0 }).format(v));
  const dec = (v, d = 1) => (v == null ? '–' : nf({ minimumFractionDigits: d, maximumFractionDigits: d }).format(v));
  // a ratio as people say it: 2.51 -> "2.5×", 0.82 -> "18% less"
  const times = (r) => (r == null ? '–' : r >= 1 || Math.round(100 * (1 - r)) === 0 ? `${dec(r, r >= 10 ? 0 : 1)}×` : `${Math.round(100 * (1 - r))}% less`);
  const dateOf = (iso) => new Date(`${iso}T12:00:00`);
  const dayFmt = (o) => new Intl.DateTimeFormat('en-US', o);
  const day = (iso) => dayFmt({ weekday: 'short', month: 'short', day: 'numeric' }).format(dateOf(iso));
  const shortDay = (iso) => dayFmt({ month: 'short', day: 'numeric' }).format(dateOf(iso));
  const longDay = (iso) => dayFmt({ weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).format(dateOf(iso));
  const daysBetween = (a, b) => Math.round((dateOf(b) - dateOf(a)) / 86400000);
  // the body part an injury report line names first: "Left hamstring tightness and right knee contusion" -> "Hamstring"
  const PARTS = ['achilles', 'ankle', 'knee', 'hamstring', 'calf', 'groin', 'back', 'foot', 'toe', 'hand', 'finger', 'thumb', 'wrist',
    'elbow', 'shoulder', 'hip', 'thigh', 'quad', 'adductor', 'abdominal', 'oblique', 'rib', 'neck', 'head', 'concussion', 'eye', 'nose',
    'face', 'leg', 'arm', 'heel', 'shin', 'pelvis', 'glute', 'illness', 'tooth', 'jaw', 'chest'];
  const bodyPart = (t) => {
    const low = t.toLowerCase();
    let best = null, at = Infinity;
    for (const p of PARTS) { const i = low.search(new RegExp(`\\b${p}`)); if (i >= 0 && i < at) { at = i; best = p; } }
    return best ? best[0].toUpperCase() + best.slice(1) : t.split(' ').find((w) => !/^(left|right|low|lower|upper|mid)$/i.test(w)) || t;
  };
  // "Left ankle sprain (missed 3 games)" -> ["Left ankle sprain", "missed 3 games"]
  const splitOutcome = (t) => { const i = t.lastIndexOf(' ('); return i < 0 ? [t, ''] : [t.slice(0, i), t.slice(i + 2, -1)]; };

  // One row of a night's board: [player id, name, team, opponent, risk per mille, drivers, injured, outcome].
  function boardRow(r, rank, { drivers = null, link = false } = {}) {
    const name = link && r[0] ? `<a class="name" href="#players/${r[0]}">${esc(r[1])}</a>` : `<b>${esc(r[1])}</b>`;
    let outcome = '<td class="outcome none">No new injury</td>';
    if (r[6]) {
      const [what, cost] = splitOutcome(r[7]);
      outcome = `<td class="outcome hurt"><span class="dot" aria-hidden="true"></span><span class="what">${esc(what)}<span class="sub">${esc(cost)}</span></span></td>`;
    }
    const why = drivers ? `<td class="drivers wide">${r[5].map(([k, v]) => esc(v ? `${drivers[k]} ${v}` : drivers[k])).join(' · ')}</td>` : '';
    return `<tr><td class="n rank">${rank}</td><td class="who">${name}<span class="sub">${esc(r[2])} vs ${esc(r[3])}</span></td>`
      + `<td class="n chance">${Math.round(r[4] / 10)}%</td>${why}${outcome}</tr>`;
  }

  // Ratios with their likely range on a shared log scale, 1× marked: a filled dot for "more likely", an open ring for
  // "less likely", grey for no clear difference.  rows: [{ label, sub, ratio, lo, hi, level, verdict }]
  function dotRows(el, rows, { min = 0.25, max = 4, track = 132 } = {}) {
    const at = (v) => ((Math.log(Math.min(max, Math.max(min, v))) - Math.log(min)) / (Math.log(max) - Math.log(min))) * 100;
    const ticksAt = [0.25, 0.5, 1, 2, 4].filter((v) => v >= min && v <= max);
    el.innerHTML = `<div class="dots" style="--track:${track}px">${rows.map((r) => {
      const cls = r.level > 0 ? 'up' : r.level < 0 ? 'down' : 'none';
      return `<div class="dot-row ${cls}" style="--one:${at(1)}%;--lo:${at(r.lo)}%;--hi:${at(r.hi)}%;--x:${at(r.ratio)}%">`
        + `<span class="label">${esc(r.label)}${r.sub ? `<small>${esc(r.sub)}</small>` : ''}</span>`
        + `<span class="track" role="img" aria-label="${esc(`${times(r.ratio)}, likely ${dec(r.lo, 2)} to ${dec(r.hi, 2)}: ${r.verdict}`)}"><span class="one"></span><span class="range"></span><span class="dot"></span></span>`
        + `<span class="val">${times(r.ratio)}</span></div>`;
    }).join('')}</div><div class="dot-scale" style="--track:${track}px" aria-hidden="true"><span></span><span>${ticksAt.map((v) => `<i style="left:${at(v)}%">${v < 1 ? `${v}×` : `${v}×`}</i>`).join('')}</span><span></span></div>`;
  }

  // Two shares per row: the main one in the data hue, its comparison in grey.  rows: [{ label, a, b }]
  function pairs(el, rows, { format = (v) => pct(v, 1) } = {}) {
    const top = Math.max(...rows.flatMap((r) => [r.a, r.b])) || 1;
    el.innerHTML = `<div class="pairs">${rows.map((r) => `<div class="pair"><span class="label">${esc(r.label)}</span><span class="bars">`
      + `<span><i style="width:${(r.a / top) * 100}%"></i>${format(r.a)}</span><span><i style="width:${(r.b / top) * 100}%"></i>${format(r.b)}</span></span></div>`).join('')}</div>`;
  }

  window.Site = { load, esc, pct, int, dec, times, day, shortDay, longDay, dateOf, daysBetween, splitOutcome, bodyPart, boardRow, dotRows, pairs };
})();

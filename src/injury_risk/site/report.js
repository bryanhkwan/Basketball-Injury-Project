/* Charts for the public report page. The data is embedded in the page (#report-data) by report_site.py, so the page
   works from a file, from GitHub Pages, or offline. Every chart also has a table of its numbers below it. */
(() => {
  const data = JSON.parse(document.getElementById('report-data').textContent);

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };
  const pct = (v, digits = 1) => (v == null ? '—' : v > 0 && v < 0.0005 ? '<0.1%' : `${(v * 100).toFixed(digits)}%`);
  const times = (v) => (v == null ? '—' : v >= 10 ? `${v.toFixed(0)}×` : `${v.toFixed(1)}×`);
  const num = (v, digits = 1) => (v == null ? '—' : v.toFixed(digits));
  const range = (e) => `${num(e.or)} (${num(e.lo)} to ${num(e.hi)})`;

  // ---- one tooltip for the page: hover or keyboard focus shows it, values lead and labels follow ----------
  const tip = el('div', 'tip');
  tip.setAttribute('role', 'tooltip');
  tip.id = 'chart-tip';
  tip.hidden = true;
  document.body.append(tip);

  function placeTip(x, y) {
    const pad = 14;
    const w = tip.offsetWidth;
    const h = tip.offsetHeight;
    let left = x + pad;
    let top = y + pad;
    if (left + w > window.innerWidth - 8) left = Math.max(8, x - w - pad);
    if (top + h > window.innerHeight - 8) top = Math.max(8, y - h - pad);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }

  function showTip(title, lines, x, y) {
    tip.replaceChildren(el('div', 'tip-title', title));
    for (const [label, value] of lines) {
      const row = el('div', 'tip-row');
      row.append(el('span', null, label), el('b', null, value));
      tip.append(row);
    }
    tip.hidden = false;
    placeTip(x, y);
  }

  function hideTip() { tip.hidden = true; }

  // a focused mark keeps its tooltip while the page scrolls (focusing scrolls it into view); a hovered one hides it
  let focused = null;
  function showForNode(f) {
    const r = f.node.getBoundingClientRect();
    showTip(f.title, f.lines, r.left + Math.min(r.width, 320), r.top + 8);
  }

  function bindTip(node, title, lines) {
    node.tabIndex = 0;
    node.setAttribute('aria-describedby', 'chart-tip');
    node.addEventListener('pointermove', (e) => showTip(title, lines, e.clientX, e.clientY));
    node.addEventListener('pointerleave', () => { if (focused?.node === node) showForNode(focused); else hideTip(); });
    node.addEventListener('focus', () => { focused = { node, title, lines }; showForNode(focused); });
    node.addEventListener('blur', () => { focused = null; hideTip(); });
  }
  window.addEventListener('scroll', () => {
    if (focused && document.activeElement === focused.node) showForNode(focused);
    else hideTip();
  }, { passive: true });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTip(); });

  function tag(t) {
    if (!t) return null;
    const node = el('span', `tag ${t.cls}`);
    const icon = el('span', null, t.icon);
    icon.setAttribute('aria-hidden', 'true');
    node.append(icon, document.createTextNode(t.text));
    return node;
  }

  // ---- paired bars: every row on one shared scale, the value at each bar's tip ---------------------------
  function pairRows(container, rows, { withRatio = true } = {}) {
    if (!container) return;
    const top = Math.max(...rows.flatMap((r) => r.bars.map((b) => b.value || 0))) / 0.8 || 1;
    container.replaceChildren();
    for (const r of rows) {
      const row = el('div', withRatio ? 'row' : 'row no-ratio');
      row.setAttribute('role', 'group');
      row.setAttribute('aria-label', r.aria);
      const head = el('div', 'row-head');
      if (r.chip) head.append(el('span', 'chip', r.chip));
      head.append(el('span', 'row-label', r.label));
      const t = tag(r.tag);
      if (t) head.append(t);
      const bars = el('div', 'bars');
      for (const b of r.bars) {
        const line = el('div', 'bar-line');
        const track = el('div', 'track');
        const bar = el('div', 'bar');
        const w = (100 * (b.value || 0)) / top;
        bar.style.width = `${w}%`;
        bar.style.background = `var(--${b.series})`;
        const val = el('span', 'bar-val', b.text);
        val.style.left = `${w}%`;
        track.append(bar, val);
        line.append(el('span', null, b.name), track);
        bars.append(line);
      }
      row.append(head, bars);
      if (withRatio) {
        const ratio = el('div', 'ratio');
        ratio.append(el('strong', null, r.ratio == null ? '—' : times(r.ratio)), el('span', null, 'as often'));
        row.append(ratio);
      }
      bindTip(row, r.label, r.tip);
      container.append(row);
    }
  }

  // ---- the fade: how strongly each play is tied to injury exits, looking further back -----------------------
  function fadePanels(container, groups) {
    if (!container) return;
    const top = Math.max(1, ...groups.flatMap((g) => g.points.map((p) => p.ratio))) / 0.84;
    container.replaceChildren();
    for (const g of groups) {
      const panel = el('div', 'panel');
      panel.setAttribute('role', 'group');
      panel.setAttribute('aria-label', g.aria);
      panel.append(el('h3', null, g.label));
      const plot = el('div', 'plot');
      for (const p of g.points) {
        const col = el('div', 'col');
        col.style.height = `${(100 * p.ratio) / top}%`;
        col.append(el('span', 'col-val', times(p.ratio)));
        plot.append(col);
      }
      const ref = el('div', 'ref-line');
      ref.style.bottom = `${100 / top}%`;
      plot.append(ref);
      const ticks = el('div', 'ticks');
      for (const p of g.points) ticks.append(el('span', null, p.when));
      panel.append(plot, ticks);
      bindTip(panel, g.label, g.points.map((p) => [p.when, `${times(p.ratio)} · ${pct(p.injury_share)} vs ${pct(p.normal_share)}`]));
      container.append(panel);
    }
  }

  // ---- the college check: NBA and college estimates with their likely ranges, on a log scale ----------------
  function forest(container, rows, [lo, hi]) {
    if (!container) return;
    const x = (v) => (100 * (Math.log(v) - Math.log(lo))) / (Math.log(hi) - Math.log(lo));
    const ticks = [0.5, 1, 2, 4, 8, 16, 32].filter((t) => t >= lo && t <= hi);
    container.replaceChildren();
    const estimate = (series, e) => {
      const est = el('div', `f-est ${series}`);
      const whisker = el('div', 'f-whisker');
      const a = x(Math.max(e.lo, lo));
      const b = x(Math.min(e.hi, hi));
      whisker.style.left = `${a}%`;
      whisker.style.width = `${b - a}%`;
      const dot = el('div', 'f-dot');
      dot.style.left = `${x(e.or)}%`;
      est.append(whisker, dot);
      return est;
    };
    for (const r of rows) {
      const row = el('div', 'f-row');
      row.setAttribute('role', 'group');
      row.setAttribute('aria-label', r.aria);
      const head = el('div', 'row-head');
      head.append(el('span', 'row-label', r.label));
      const t = tag(r.tag);
      if (t) head.append(t);
      const plot = el('div', 'f-plot');
      for (const tk of ticks) {
        const grid = el('div', tk === 1 ? 'f-ref' : 'f-grid');
        grid.style.left = `${x(tk)}%`;
        plot.append(grid);
      }
      plot.append(estimate('nba', r.nba), estimate('college', r.college));
      row.append(head, plot);
      bindTip(row, r.label, [['College', range(r.college)], ['NBA', range(r.nba)], ...r.extra]);
      container.append(row);
    }
    const axisRow = el('div', 'f-row f-axis-row');
    axisRow.setAttribute('aria-hidden', 'true');
    const axisCell = el('div');
    const axis = el('div', 'f-axis');
    for (const tk of ticks) {
      const label = el('span', 'f-tick', tk < 1 ? String(tk) : `${tk}`);
      label.style.left = `${x(tk)}%`;
      axis.append(label);
    }
    axisCell.append(axis, el('p', 'f-axis-label', 'Odds ratio against the same players’ normal substitutions (log scale; 1 = no difference)'));
    axisRow.append(el('div'), axisCell);
    container.append(axisRow);
  }

  pairRows(document.getElementById('chart-nba'), data.nba);
  fadePanels(document.getElementById('chart-fade'), data.fade);
  forest(document.getElementById('chart-college'), data.college, data.forest_domain);
  pairRows(document.getElementById('chart-signs'), data.signs);
  pairRows(document.getElementById('chart-traced'), data.traced, { withRatio: false });
})();

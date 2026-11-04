// Current source observations. Historical model scores and studies retain their own dates.
(() => {
  const { esc } = window.Site;
  const LABELS = { nba: 'NBA', ncaa_mbb: 'NCAA men', wnba: 'WNBA', ncaa_wbb: 'NCAA women' };
  const STATUS = { out: 'Out', out_for_season: 'Out for season', doubtful: 'Doubtful', questionable: 'Questionable',
    probable: 'Probable', available: 'Available', day_to_day: 'Day to day', unknown: 'Unspecified' };
  const CATEGORY = { injury: 'Injury listed', illness: 'Illness listed', management: 'Rest / management', non_medical: 'Nonmedical', unknown: 'Reason unconfirmed' };
  const dateTime = (s) => s ? new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }) : 'Not provided';
  const ageHours = (s) => s ? (Date.now() - new Date(s).getTime()) / 3600000 : Infinity;
  function health(s) {
    if (s.status === 'not_enabled') return 'Not connected';
    if (s.status === 'paused') return s.snapshot ? 'Collection paused · saved data' : 'Collection paused';
    if (!s.snapshot) return 'No validated data';
    if (s.status === 'error') return 'Check failed · saved data';
    if (ageHours(s.snapshot.report_at || s.snapshot.observed_at) > s.max_age_hours || ageHours(s.last_success_at) > s.max_age_hours) return 'Stale · saved data';
    return s.snapshot.report_at ? 'Report checked' : 'Page checked · report date unknown';
  }
  window.AvailabilityView = {
    async init(el) {
      const response = await fetch('data/updates.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error('No availability update has been published yet');
      this.data = await response.json();
      this.query = '';
    },
    show(el, args) {
      this.el = el;
      this.league = Object.hasOwn(LABELS, args[0]) ? args[0] : 'nba';
      const staleRun = ageHours(this.data.generated_at) > 36;
      el.innerHTML = `<div class="title-row"><div><h1 id="updates-title">Current availability</h1>
        <p class="sub">What the latest checked sources list. Checked once a day; not a real-time feed.</p></div></div>
        <div class="update-intro"><p>Collection run: <b>${esc(dateTime(this.data.generated_at))}</b>${staleRun ? ' · <strong class="update-alert">Updates are overdue</strong>' : ''}</p>
        <p>These are availability observations, not new injury diagnoses or model predictions. The risk board and career studies keep their historical cutoffs.</p></div>
        <div class="segmented update-leagues" role="group" aria-label="Basketball competition">${Object.entries(LABELS).map(([k, label]) => `<button type="button" data-league="${k}" aria-pressed="${k === this.league}">${label}</button>`).join('')}</div>
        <div id="u-health" class="update-health"></div>
        <div class="update-filter"><label for="u-search">Filter by player or team</label><input id="u-search" type="search" placeholder="Player or team" value="${esc(this.query)}"></div>
        <p id="u-count" class="sub" aria-live="polite"></p>
        <div id="u-list"></div>
        <details class="update-method"><summary>How to read these updates</summary><p>A source can list a player as out without giving a medical reason. A listing first observed today may describe an older injury. Disappearing from a report does not establish recovery.</p>
        <p>Different sources cover different teams and games. No listing means unknown coverage, not a clean bill of health. NCAA listings without a publication date may be left over from earlier games or seasons.</p>
        <p>Failed collections keep the previous validated snapshot and its original date. Every collection adds a dated factual archive; later corrections do not overwrite earlier observations. This page shows the latest state and recalculates staleness when you open it, even if the scheduled workflow has stopped. Only normalized facts are shown; article text and source report wording are not republished.</p></details>`;
      el.querySelectorAll('[data-league]').forEach((b) => b.addEventListener('click', () => { location.hash = `updates/${b.dataset.league}`; }));
      el.querySelector('#u-search').addEventListener('input', (e) => { this.query = e.target.value; this.rows(); });
      this.rows();
    },
    rows() {
      const sources = Object.entries(this.data.sources).filter(([, s]) => s.league === this.league);
      this.el.querySelector('#u-health').innerHTML = sources.map(([, s]) => {
        const snap = s.snapshot;
        return `<section class="card"><h2>${esc(s.name)}</h2><p><b>${esc(health(s))}</b></p><p class="note">${esc(s.scope)}</p>
          ${s.message ? `<p class="note">${esc(s.message)}</p>` : ''}
          ${snap ? `<dl class="update-dates"><div><dt>Source report</dt><dd>${esc(dateTime(snap.report_at))}</dd></div><div><dt>Last successful check</dt><dd>${esc(dateTime(s.last_success_at))}</dd></div></dl>
          <p class="note">${snap.rows.length.toLocaleString()} saved listings · ${snap.pages_checked} ${snap.pages_checked === 1 ? 'report' : 'conference pages'} checked${snap.not_submitted.length ? ` · ${snap.not_submitted.length} team reports not submitted` : ''}</p>` : ''}</section>`;
      }).join('');
      const query = this.query.trim().toLocaleLowerCase();
      const all = sources.flatMap(([, s]) => (s.snapshot?.rows || []).map((r) => ({ ...r, sourceName: s.name })));
      const rows = all.filter((r) => `${r.player} ${r.team}`.toLocaleLowerCase().includes(query)).sort((a, b) => a.team.localeCompare(b.team) || a.player.localeCompare(b.player));
      this.el.querySelector('#u-count').textContent = `${rows.length.toLocaleString()} of ${all.length.toLocaleString()} saved listings shown`;
      if (!rows.length) {
        const connected = sources.some(([, s]) => s.snapshot);
        this.el.querySelector('#u-list').innerHTML = `<div class="empty">${query ? 'No saved listings match this filter.' : connected ? 'The checked source lists no players here. This does not establish that every player is available.' : 'This competition does not yet have a validated automated feed. See the source status above.'}</div>`;
        return;
      }
      this.el.querySelector('#u-list').innerHTML = `<div class="card table-wrap"><table class="data update-table"><caption class="sr-only">${LABELS[this.league]} availability observations</caption><thead><tr><th scope="col">Player / team</th><th scope="col">Availability</th><th scope="col">Reported category</th><th scope="col">Game / observation</th></tr></thead><tbody>${rows.map((r) => `<tr>
        <td><b>${esc(r.player)}</b><span class="sub">${esc(r.team)}${r.conference ? ` · ${esc(r.conference)}` : ''}</span></td>
        <td>${esc(STATUS[r.status] || 'Unspecified')}</td><td>${esc(CATEGORY[r.category] || 'Reason unconfirmed')}${r.region && r.region !== 'other' ? `<span class="sub">${esc(r.region === 'concussion' ? 'Head / concussion' : r.region.replaceAll('_', ' '))}</span>` : ''}</td>
        <td>${r.game_date ? esc(r.game_date) : 'Game not specified'}<span class="sub">First observed ${esc(dateTime(r.first_seen))}</span></td></tr>`).join('')}</tbody></table></div>`;
    },
  };
})();

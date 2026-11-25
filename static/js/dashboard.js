// Dashboard widgets: overview tiles, weekly chart and activity heatmap.
const Dashboard = (() => {
  let data = null;
  let metric = 'active_days';
  let weeksChart = null;
  let request = 0;

  const metricLabels = { active_days: 'Trainingsdagen', sets: 'Sets', tonnage: 'Volume (kg)', cardio_minutes: 'Cardio (min)' };
  const metricUnits = { active_days: 'dagen', sets: 'sets', tonnage: 'kg', cardio_minutes: 'min' };
  const WEEK_RANGES = [
    { id: '4w', days: 28, label: '4 wkn' }, { id: '12w', days: 84, label: '12 wkn' },
    { id: '26w', days: 182, label: '26 wkn' }, { id: '52w', days: 365, label: '1 jaar' },
  ];
  const nl = value => Number(value).toLocaleString('nl-NL');

  // The calendar and the recent trainings have their own small requests, so a slow or failing overview never blocks them.
  let calendarData = null;
  let calendarRequest = 0;

  async function loadCalendar() {
    const current = ++calendarRequest;
    const container = document.getElementById('calendar');
    try {
      const next = await api('/api/calendar?weeks=26');
      if (current !== calendarRequest) return;
      calendarData = next;
      renderCalendar();
    } catch (error) {
      if (current !== calendarRequest) return;
      console.error(error);
      const outdated = error.status === 404;
      container.innerHTML = `<div class="notice" role="alert"><strong>${outdated ? 'Server draait nog een oude versie' : 'Kalender kon niet laden'}</strong>
        <span>${outdated ? 'Haal de nieuwste code op de Pi op (git pull) en herstart de service.' : escapeHtml(error.message || String(error))}</span>
        <button type="button" class="btn btn-ghost btn-sm" onclick="Dashboard.load()">Opnieuw proberen</button></div>`;
    }
  }

  async function load() {
    const current = ++request;
    loadCalendar();
    try {
      const next = await api('/api/dashboard?weeks=52', { timeout: 30000 });
      if (current !== request) return;
      data = next;
      for (const step of [renderTiles, renderChart, () => Body.renderCard(data.body, document.getElementById('bodyCardContent'))]) {
        try { step(); } catch (error) { console.error(error); }
      }
    } catch (error) {
      console.error(error);
      if (current !== request) return;
      const outdated = error.status === 404;
      document.getElementById('overviewTiles').innerHTML = `<div class="notice" role="alert">
        <strong>${outdated ? 'Server draait nog een oude versie' : 'Overzicht kon niet laden'}</strong>
        <span>${outdated
          ? 'Na een <code>git pull</code> moet de server op de Pi opnieuw starten (herstart de service of de Pi) voor de nieuwe grafieken en berekeningen.'
          : escapeHtml(error.message || 'Controleer de verbinding en probeer het opnieuw.')}</span>
        <button type="button" class="btn btn-ghost btn-sm" onclick="Dashboard.load()">Opnieuw proberen</button></div>`;
    }
  }
  function renderTiles() {
    const weeks = data.weeks;
    const week = weeks[weeks.length - 1];
    const month = data.month;
    const previous = data.previous_month;
    const trend = month.active_days >= previous.active_days ? 'up' : 'down';
    document.getElementById('overviewTiles').innerHTML = `
      <div class="tile"><div class="tile-val">${month.active_days}</div><div class="tile-label">Trainingsdagen deze maand</div>
        <div class="tile-delta ${trend}">${trend === 'up' ? '▲' : '▼'} vorige maand: ${previous.active_days}</div></div>
      <div class="tile"><div class="tile-val">${data.average_active_days.toLocaleString('nl-NL')}<small> / week</small></div><div class="tile-label">Gemiddeld laatste 4 weken</div>
        <div class="tile-delta">Beste week: ${data.best_week_days} dagen</div></div>
      <div class="tile"><div class="tile-val">${week.sets}</div><div class="tile-label">Sets deze week</div>
        <div class="tile-delta">${nl(week.tonnage)} kg volume</div></div>
      <div class="tile"><div class="tile-val">${nl(week.cardio_minutes)}<small> min</small></div><div class="tile-label">Cardio deze week</div>
        <div class="tile-delta">${nl(week.kcal)} kcal verbrand</div></div>`;
  }

  function selectWeekMetric(element) {
    document.querySelectorAll('#weekChartMetric .chip').forEach(chip => chip.classList.remove('active'));
    element.classList.add('active');
    metric = element.dataset.metric;
    if (data) renderChart();
  }

  // The card shows the chosen period of the weekly series; Charts handles range, trend, forecast and the detail dialog.
  function weeksModel() {
    const weeks = data?.weeks || [];
    return {
      title: `Per week · ${metricLabels[metric]}`, label: metricLabels[metric], unit: metricUnits[metric], decimals: metric === 'active_days' ? 1 : 0,
      kind: 'bar', span: 7 * 864e5, color: '#3a7d44', highlightLast: true, partialLast: true, zero: true, min: 0,
      suggestedMax: metric === 'active_days' ? 4 : undefined, step: metric === 'active_days' ? 1 : undefined,
      smoothOptions: [0, 2, 3, 4], ranges: WEEK_RANGES,
      refLines: metric === 'active_days' ? [{ label: 'Weekdoel (3)', value: 3, color: '#d4a373' }] : [],
      points: weeks.map(week => ({ t: new Date(`${week.start}T00:00:00`).getTime(), y: week[metric] })),
    };
  }

  function renderChart() {
    weeksChart ||= Charts.mount({
      id: 'weeks', canvas: document.getElementById('weeksChart'), controls: document.getElementById('weeksChartControls'),
      model: weeksModel, defaults: { range: '12w' },
    });
    weeksChart.update();
  }

  let calendarWeeks = (() => {
    try { return [8, 12, 26].includes(Number(localStorage.getItem('gorilla-calendar-weeks'))) ? Number(localStorage.getItem('gorilla-calendar-weeks')) : 12; } catch (error) { return 12; }
  })();

  const localIso = day => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;

  function selectCalendarRange(element) {
    calendarWeeks = Number(element.dataset.weeks);
    try { localStorage.setItem('gorilla-calendar-weeks', String(calendarWeeks)); } catch (error) {}
    if (calendarData) renderCalendar();
  }

  // One row per week: month label, seven days and the number of active days.
  function renderCalendar() {
    document.querySelectorAll('#calendarRange .chip').forEach(chip => chip.classList.toggle('active', Number(chip.dataset.weeks) === calendarWeeks));
    const byDate = new Map(calendarData.calendar.map(day => [day.date, day]));
    const today = localIso(new Date());
    let lastMonth = null;
    document.getElementById('calendar').innerHTML = calendarData.weeks.slice(-calendarWeeks).map(week => {
      const start = new Date(`${week.start}T00:00:00`);
      const month = start.toLocaleDateString('nl-NL', { month: 'short' });
      const label = `<span class="cal-label">${month !== lastMonth ? `<b>${month}</b>` : ''}</span>`;
      lastMonth = month;
      const cells = [];
      for (let offset = 0; offset < 7; offset++) {
        const day = new Date(start);
        day.setDate(start.getDate() + offset);
        const iso = localIso(day);
        const entry = byDate.get(iso);
        if (!entry) {
          cells.push(`<span class="cal-day future"><i>${day.getDate()}</i></span>`);
          continue;
        }
        const activity = entry.sets > 0 || entry.minutes > 0 ? ' active' : '';
        const initials = [...new Set((entry.routines || []).map(name => {
          const label = displayRoutine(name.trim());
          return label.startsWith('🅿️') ? '🅿️' : (Array.from(label)[0] || '').toUpperCase();
        }).filter(Boolean))].slice(0, 2).join('');
        const cardio = entry.minutes > 0 ? ' cardio' : '';
        const summary = entry.sets || entry.minutes
          ? `${entry.sets ? `${entry.sets} sets, ${nl(entry.tonnage)} kg` : ''}${entry.sets && entry.minutes ? ' + ' : ''}${entry.minutes ? `${Math.round(entry.minutes)} min cardio` : ''}`
          : 'rust';
        cells.push(`<button type="button" class="cal-day${activity}${cardio}${iso === today ? ' today' : ''}" data-open-session="${iso}"
          aria-label="${iso}: ${summary}"><i>${day.getDate()}</i><small>${escapeHtml(initials)}</small></button>`);
      }
      return `<div class="cal-week">${label}${cells.join('')}<span class="cal-sum${week.active_days >= 3 ? ' goal' : ''}">${week.active_days}/3</span></div>`;
    }).join('');
  }

  return { load, selectWeekMetric, selectCalendarRange };
})();

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

  async function load() {
    const current = ++request;
    try {
      const next = await api('/api/dashboard?weeks=52');
      if (current !== request) return;
      data = next;
      render();
    } catch (error) {
      const outdated = error.status === 404;
      document.getElementById('overviewTiles').innerHTML = `<div class="notice" role="alert">
        <strong>${outdated ? 'Server draait nog een oude versie' : 'Overzicht kon niet laden'}</strong>
        <span>${outdated
          ? 'Na een <code>git pull</code> moet de server op de Pi opnieuw starten (herstart de service of de Pi) voor de nieuwe grafieken en berekeningen.'
          : 'Controleer de verbinding en probeer het opnieuw.'}</span></div>`;
    }
  }

  function render() {
    renderTiles();
    renderChart();
    renderHeatmap();
    Body.renderCard(data.body, document.getElementById('bodyCardContent'));
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

  function renderHeatmap() {
    const byDate = new Map(data.calendar.map(day => [day.date, day]));
    const today = new Date().toISOString().slice(0, 10);
    const cells = [];
    for (const week of data.weeks.slice(-12)) {
      const start = new Date(`${week.start}T00:00:00`);
      for (let offset = 0; offset < 7; offset++) {
        const day = new Date(start);
        day.setDate(start.getDate() + offset);
        const iso = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
        const entry = byDate.get(iso);
        const score = entry ? entry.sets + entry.minutes / 2 : 0;
        const level = !entry || !entry.active ? '' : score >= 20 ? ' l3' : score >= 10 ? ' l2' : ' l1';
        const future = !entry && iso > today ? ' future' : '';
        const title = entry ? `${iso}: ${entry.sets} sets${entry.minutes ? `, ${Math.round(entry.minutes)} min cardio` : ''}` : iso;
        cells.push(`<span class="heat-cell${level}${future}" title="${title}"></span>`);
      }
    }
    document.getElementById('heatmap').innerHTML = cells.join('');
  }

  return { load, selectWeekMetric };
})();

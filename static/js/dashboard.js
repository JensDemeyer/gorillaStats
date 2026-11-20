// Dashboard widgets: overview tiles, weekly chart and activity heatmap.
const Dashboard = (() => {
  let data = null;
  let metric = 'active_days';
  let chart = null;
  let request = 0;

  const metricLabels = { active_days: 'Trainingsdagen', sets: 'Sets', tonnage: 'Volume (kg)', cardio_minutes: 'Cardio (min)' };
  const nl = value => Number(value).toLocaleString('nl-NL');

  async function load() {
    const current = ++request;
    try {
      const next = await api('/api/dashboard?weeks=12');
      if (current !== request) return;
      data = next;
      render();
    } catch (error) {
      // The rest of the dashboard keeps working without the overview.
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

  function weekLabel(start) {
    const date = new Date(`${start}T00:00:00`);
    return `${date.getDate()}/${date.getMonth() + 1}`;
  }

  function renderChart() {
    const weeks = data.weeks;
    const values = weeks.map(week => week[metric]);
    const datasets = [{
      type: 'bar', label: metricLabels[metric], data: values, borderRadius: 6, maxBarThickness: 28,
      backgroundColor: weeks.map(week => week.current ? '#e69500' : 'rgba(58,125,68,.85)'),
      borderColor: weeks.map(week => week.current ? '#f5c04a' : '#4a9a56'), borderWidth: 1.5,
    }];
    if (metric === 'active_days') {
      datasets.push({ type: 'line', label: 'Weekdoel (3)', data: weeks.map(() => 3), borderColor: '#d4a373', borderDash: [6, 4],
        borderWidth: 2, pointRadius: 0, fill: false });
    }
    if (chart) chart.destroy();
    chart = new Chart(document.getElementById('weeksChart').getContext('2d'), {
      data: { labels: weeks.map(week => weekLabel(week.start)), datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: metric === 'active_days', labels: { color: '#95a597', font: { family: 'Barlow', size: 12 }, boxWidth: 18 } },
          tooltip: { callbacks: { title: items => `Week van ${weekLabel(weeks[items[0].dataIndex].start)}` } },
        },
        scales: {
          y: { beginAtZero: true, suggestedMax: metric === 'active_days' ? 4 : undefined, grid: { color: 'rgba(45,63,48,0.5)' },
            ticks: { color: '#95a597', font: { family: 'Barlow' }, precision: 0, stepSize: metric === 'active_days' ? 1 : undefined } },
          x: { grid: { display: false }, ticks: { color: '#95a597', font: { family: 'Barlow', size: 10 } } },
        },
      },
    });
  }

  function renderHeatmap() {
    const byDate = new Map(data.calendar.map(day => [day.date, day]));
    const today = new Date().toISOString().slice(0, 10);
    const cells = [];
    for (const week of data.weeks) {
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

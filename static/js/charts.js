// Interactive charts. Every chart in the app is mounted through Charts.mount(): the card shows a compact preview with a
// period selector, and tapping it opens a detail dialog with smoothing, trend line, forecast, min/max markers and statistics.
const Charts = (() => {
  const DAY = 864e5;
  const RANGES = [
    { id: '1m', days: 30, label: '1 mnd' }, { id: '3m', days: 91, label: '3 mnd' }, { id: '6m', days: 182, label: '6 mnd' },
    { id: '1y', days: 365, label: '1 jaar' }, { id: 'all', days: null, label: 'Alles' },
  ];
  const FORECASTS = [0, 4, 8, 12];
  const TEXT = '#95a597';
  const GRID = 'rgba(45,63,48,.5)';
  const GOLD = '#e69500';
  const nl = (value, digits = 1) => Number(value).toLocaleString('nl-NL', { maximumFractionDigits: digits });
  const dateLabel = (t, long = false) => new Date(t).toLocaleDateString('nl-NL',
    long ? { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' } : { day: 'numeric', month: 'short' });
  const monthLabel = t => {
    const date = new Date(t);
    return `${date.toLocaleDateString('nl-NL', { month: 'short' })} '${String(date.getFullYear()).slice(2)}`;
  };
  const withAlpha = (hex, alpha) => {
    const value = parseInt(hex.slice(1), 16);
    return `rgba(${value >> 16}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
  };

  // Least squares line through the points, with the spread of the points around it.
  function regression(points) {
    if (points.length < 2) return null;
    const t0 = points[0].t;
    const xs = points.map(point => (point.t - t0) / DAY);
    const meanX = xs.reduce((a, b) => a + b, 0) / xs.length;
    const meanY = points.reduce((a, point) => a + point.y, 0) / points.length;
    const spread = xs.reduce((a, x) => a + (x - meanX) ** 2, 0);
    if (!spread) return null;
    const slope = xs.reduce((a, x, i) => a + (x - meanX) * (points[i].y - meanY), 0) / spread;
    const intercept = meanY - slope * meanX;
    const residuals = xs.reduce((a, x, i) => a + (points[i].y - (intercept + slope * x)) ** 2, 0);
    return { slope, sd: Math.sqrt(residuals / Math.max(1, points.length - 2)), at: t => intercept + slope * ((t - t0) / DAY) };
  }

  function movingAverage(points, size) {
    return points.map((point, index) => {
      const window = points.slice(Math.max(0, index - size + 1), index + 1);
      return { t: point.t, y: window.reduce((a, item) => a + item.y, 0) / window.length };
    });
  }

  function loadState(id, defaults) {
    try {
      return { ...defaults, ...JSON.parse(localStorage.getItem(`gorilla-chart-${id}`) || '{}') };
    } catch (error) {
      return { ...defaults };
    }
  }

  function saveState(id, state) {
    try { localStorage.setItem(`gorilla-chart-${id}`, JSON.stringify(state)); } catch (error) {}
  }

  // Applies the chosen period and works out the derived series.
  function analyse(model, state) {
    const ranges = model.ranges || RANGES;
    const range = ranges.find(item => item.id === state.range) || ranges[Math.min(1, ranges.length - 1)];
    const cutoff = range.days ? Date.now() - range.days * DAY : -Infinity;
    const span = model.span || 0;
    const points = [...model.points].filter(point => point.y != null && Number.isFinite(point.y) && point.t + span >= cutoff)
      .sort((a, b) => a.t - b.t);
    const smooth = state.smooth ? movingAverage(points, state.smooth) : null;
    // The running week is incomplete, so it would drag the trend down.
    const fitPoints = model.partialLast && points.length > 3 ? points.slice(0, -1) : points;
    const trend = regression(fitPoints);
    // The forecast follows the recent direction: the last 8 weeks.
    const recent = fitPoints.filter(point => point.t >= (fitPoints.at(-1)?.t ?? 0) - 56 * DAY);
    const recentFit = regression(recent.length >= 3 ? recent : fitPoints);
    return { range, ranges, points, smooth, trend, recentFit };
  }

  function forecastPoints(model, analysis, weeks) {
    const last = analysis.points.at(-1);
    if (!weeks || !last || !analysis.recentFit) return [];
    const { recentFit } = analysis;
    const steps = [];
    for (let week = 0; week <= weeks; week++) {
      const t = last.t + week * 7 * DAY;
      let y = recentFit.at(t);
      if (model.min != null) y = Math.max(model.min, y);
      steps.push({ t, y, band: recentFit.sd * (1 + week * 0.15) });
    }
    return steps;
  }

  function goalNote(model, analysis) {
    const goal = model.goal;
    const last = analysis.points.at(-1);
    const fit = analysis.recentFit;
    if (!goal || !last || !fit || Math.abs(fit.slope) < 1e-9) return '';
    const days = (goal.value - fit.at(last.t)) / fit.slope;
    if (days <= 0) return `Op dit tempo ga je weg van je doel (${nl(goal.value)} ${model.unit}).`;
    if (days > 730) return `Op dit tempo duurt het meer dan twee jaar tot ${nl(goal.value)} ${model.unit}.`;
    return `Op dit tempo bereik je ${nl(goal.value)} ${model.unit} rond ${dateLabel(last.t + days * DAY, true).replace(/^\w+\.? /, '')}.`;
  }

  const crosshair = {
    id: 'crosshair',
    afterDatasetsDraw(chart) {
      const active = chart.tooltip?.getActiveElements?.() || [];
      if (!active.length) return;
      const { ctx, chartArea } = chart;
      ctx.save();
      ctx.strokeStyle = 'rgba(248,249,250,.35)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(active[0].element.x, chartArea.top);
      ctx.lineTo(active[0].element.x, chartArea.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  const emptyNotice = {
    id: 'emptyNotice',
    afterDraw(chart) {
      if (chart.data.datasets.some(dataset => dataset.data.some(value => value != null && (typeof value !== 'object' || value.y != null)))) return;
      const { ctx, chartArea } = chart;
      ctx.save();
      ctx.fillStyle = TEXT;
      ctx.font = '14px Barlow, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Nog geen gegevens in deze periode', (chartArea.left + chartArea.right) / 2, (chartArea.top + chartArea.bottom) / 2);
      ctx.restore();
    },
  };

  function lineDatasets(model, analysis, state, forecast) {
    const color = model.color;
    const datasets = [];
    const smoothed = Boolean(analysis.smooth);
    datasets.push({
      label: model.label, data: analysis.points.map(point => ({ x: point.t, y: point.y })), borderColor: smoothed ? withAlpha(color, .4) : color,
      backgroundColor: withAlpha(color, .1), borderWidth: smoothed ? 1.5 : 2.5, fill: !smoothed, tension: .25,
      pointRadius: analysis.points.length > 45 ? 0 : 3, pointHoverRadius: 6, pointBackgroundColor: color, spanGaps: true,
    });
    if (smoothed) {
      datasets.push({ label: `Gemiddelde (${state.smooth})`, data: analysis.smooth.map(point => ({ x: point.t, y: point.y })),
        borderColor: GOLD, borderWidth: 3, pointRadius: 0, pointHoverRadius: 5, tension: .3 });
    }
    if (state.trend && analysis.trend && analysis.points.length > 1) {
      const first = analysis.points[0].t;
      const last = analysis.points.at(-1).t;
      datasets.push({ label: 'Trend', data: [{ x: first, y: analysis.trend.at(first) }, { x: last, y: analysis.trend.at(last) }],
        borderColor: '#d4a373', borderDash: [2, 5], borderWidth: 2, pointRadius: 0, pointHoverRadius: 0 });
    }
    if (forecast.length > 1) {
      datasets.push({ label: 'Band', data: forecast.map(step => ({ x: step.t, y: step.y + step.band })), borderWidth: 0, pointRadius: 0,
        pointHoverRadius: 0, noTooltip: true, noLegend: true, fill: false });
      datasets.push({ label: 'Band', data: forecast.map(step => ({ x: step.t, y: step.y - step.band })), borderWidth: 0, pointRadius: 0,
        pointHoverRadius: 0, noTooltip: true, noLegend: true, fill: '-1', backgroundColor: 'rgba(245,192,74,.14)' });
      datasets.push({ label: 'Voorspelling', data: forecast.map(step => ({ x: step.t, y: step.y })), borderColor: '#f5c04a',
        borderDash: [7, 5], borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5 });
    }
    if (state.markers && analysis.points.length > 2) {
      const best = analysis.points.reduce((a, b) => (b.y > a.y ? b : a));
      const worst = analysis.points.reduce((a, b) => (b.y < a.y ? b : a));
      datasets.push({ label: 'Hoogste', data: [{ x: best.t, y: best.y }], showLine: false, pointRadius: 7, pointHoverRadius: 8, noLegend: true,
        pointBackgroundColor: '#e63946', pointBorderColor: '#fff', pointBorderWidth: 2 });
      datasets.push({ label: 'Laagste', data: [{ x: worst.t, y: worst.y }], showLine: false, pointRadius: 7, pointHoverRadius: 8, noLegend: true,
        pointBackgroundColor: '#4ea8de', pointBorderColor: '#fff', pointBorderWidth: 2 });
    }
    const xs = datasets.flatMap(dataset => dataset.data.map(point => point.x));
    for (const line of model.refLines || []) {
      if (!xs.length) break;
      datasets.push({ label: line.label, data: [{ x: Math.min(...xs), y: line.value }, { x: Math.max(...xs), y: line.value }],
        borderColor: line.color, borderDash: [6, 4], borderWidth: 2, pointRadius: 0, pointHoverRadius: 0, noTooltip: true });
    }
    return datasets;
  }

  // Bars are drawn on a category axis: one slot per week, with the forecast appended as extra weeks.
  function barData(model, analysis, state, forecast) {
    const first = analysis.points[0]?.t;
    const last = analysis.points.at(-1)?.t;
    if (first == null) return { labels: [], datasets: [] };
    const times = [];
    for (let t = first; t <= last; t += 7 * DAY) times.push(t);
    const futureTimes = forecast.slice(1).map(step => step.t);
    const labels = [...times, ...futureTimes].map(t => dateLabel(t));
    const values = new Map(analysis.points.map(point => [Math.round((point.t - first) / (7 * DAY)), point.y]));
    const barValues = times.map((_, index) => values.get(index) ?? null);
    const pad = (series, offset = 0) => [...Array(offset).fill(null), ...series, ...Array(labels.length - offset - series.length).fill(null)];
    const datasets = [{
      type: 'bar', label: model.label, data: pad(barValues), borderRadius: 6, maxBarThickness: 30, borderWidth: 1.5,
      backgroundColor: barValues.map((_, index) => (model.highlightLast && index === times.length - 1 ? '#e69500' : withAlpha(model.color, .85))),
      borderColor: barValues.map((_, index) => (model.highlightLast && index === times.length - 1 ? '#f5c04a' : model.color)),
    }];
    const slot = point => Math.round((point.t - first) / (7 * DAY));
    if (analysis.smooth) {
      datasets.push({ type: 'line', label: `Gemiddelde (${state.smooth} wkn)`, borderColor: GOLD, borderWidth: 3, pointRadius: 0, tension: .3,
        data: pad(times.map((_, index) => analysis.smooth.find(point => slot(point) === index)?.y ?? null)) });
    }
    if (state.trend && analysis.trend) {
      datasets.push({ type: 'line', label: 'Trend', borderColor: '#d4a373', borderDash: [2, 5], borderWidth: 2, pointRadius: 0,
        data: pad(times.map(t => analysis.trend.at(t))) });
    }
    if (forecast.length > 1) {
      datasets.push({ type: 'line', label: 'Voorspelling', borderColor: '#f5c04a', borderDash: [7, 5], borderWidth: 2.5, pointRadius: 0,
        data: pad(forecast.map(step => step.y), times.length - 1) });
    }
    for (const line of model.refLines || []) {
      datasets.push({ type: 'line', label: line.label, data: labels.map(() => line.value), borderColor: line.color,
        borderDash: [6, 4], borderWidth: 2, pointRadius: 0, noTooltip: true });
    }
    return { labels, datasets };
  }

  function draw(canvas, model, state, detailed) {
    const analysis = analyse(model, state);
    const forecast = forecastPoints(model, analysis, state.forecast);
    const bars = model.kind === 'bar';
    const data = bars ? barData(model, analysis, state, forecast) : { datasets: lineDatasets(model, analysis, state, forecast) };
    const yTicks = { color: TEXT, font: { family: 'Barlow' }, callback: value => nl(value, model.decimals ?? 1) };
    const options = {
      responsive: true, maintainAspectRatio: false, animation: detailed ? { duration: 350 } : false,
      events: detailed ? ['mousemove', 'mouseout', 'click', 'touchstart', 'touchmove'] : [],
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      layout: { padding: { right: 6 } },
      plugins: {
        legend: detailed ? { labels: { color: TEXT, boxWidth: 14, boxHeight: 3, usePointStyle: false, font: { family: 'Barlow', size: 11 },
          filter: item => !data.datasets[item.datasetIndex]?.noLegend } } : { display: false },
        tooltip: {
          enabled: detailed, filter: item => !item.dataset.noTooltip && item.raw != null, backgroundColor: 'rgba(13,20,14,.95)',
          borderColor: '#3a5040', borderWidth: 1, titleColor: '#f8f9fa', bodyColor: '#f8f9fa', displayColors: true, padding: 10,
          callbacks: {
            title: items => (bars ? `Week van ${items[0].label}` : dateLabel(items[0].parsed.x, true)),
            label: item => `${item.dataset.label}: ${nl(item.parsed.y, model.decimals ?? 1)}${model.unit ? ` ${model.unit}` : ''}`,
          },
        },
      },
      scales: {
        y: { beginAtZero: Boolean(model.zero), suggestedMax: model.suggestedMax, grace: bars ? '10%' : '12%', grid: { color: GRID },
          ticks: { ...yTicks, precision: model.decimals === 0 ? 0 : undefined, stepSize: model.step } },
        x: bars
          ? { grid: { display: false }, ticks: { color: TEXT, font: { family: 'Barlow', size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: detailed ? 8 : 6 } }
          : { type: 'linear', grid: { color: 'rgba(45,63,48,.3)' },
            ticks: { color: TEXT, font: { family: 'Barlow', size: 10 }, maxTicksLimit: detailed ? 6 : 5, maxRotation: 0,
              callback: value => ((analysis.range.days === null || analysis.range.days > 300) ? monthLabel(value) : dateLabel(value)) } },
      },
    };
    const chart = new Chart(canvas.getContext('2d'), { type: bars ? 'bar' : 'line', data, options, plugins: [crosshair, emptyNotice] });
    return { chart, analysis, forecast };
  }

  function stats(model, analysis) {
    const { points, recentFit } = analysis;
    if (!points.length) return [];
    const values = points.map(point => point.y);
    const format = value => `${nl(value, model.decimals ?? 1)}${model.unit ? ` ${model.unit}` : ''}`;
    const change = values.at(-1) - values[0];
    const perWeek = recentFit ? recentFit.slope * 7 : null;
    const sign = value => `${value > 0 ? '+' : ''}${nl(value, model.decimals === 0 ? 1 : model.decimals ?? 1)}${model.unit ? ` ${model.unit}` : ''}`;
    return [
      ['Laatst', format(values.at(-1))],
      ['Gemiddeld', format(values.reduce((a, b) => a + b, 0) / values.length)],
      ['Hoogste', format(Math.max(...values))],
      ['Laagste', format(Math.min(...values))],
      ['Verandering', points.length > 1 ? sign(change) : '–'],
      [model.kind === 'bar' ? 'Trend per week' : 'Trend per week', perWeek == null ? '–' : sign(perWeek)],
    ];
  }

  // ---- detail dialog ----------------------------------------------------------------------------------------------
  let dialog = null;
  let current = null;
  let detail = null;

  function ensureDialog() {
    if (dialog) return;
    dialog = document.createElement('dialog');
    dialog.className = 'chart-dialog';
    dialog.setAttribute('aria-labelledby', 'chartDialogTitle');
    dialog.innerHTML = `
      <div class="cd-head"><h2 id="chartDialogTitle"></h2><button type="button" class="icon-button" aria-label="Sluiten" data-close>×</button></div>
      <div class="cd-stats" id="chartStats"></div>
      <div class="cd-canvas"><canvas id="chartDialogCanvas"></canvas></div>
      <div class="cd-note" id="chartNote" role="status"></div>
      <div class="cd-controls" id="chartControls"></div>`;
    document.body.appendChild(dialog);
    dialog.addEventListener('click', event => {
      if (event.target === dialog || event.target.closest('[data-close]')) dialog.close();
      const chip = event.target.closest('[data-option]');
      if (chip && current) applyOption(chip.dataset.option, chip.dataset.value);
    });
    dialog.addEventListener('close', () => { detail?.chart.destroy(); detail = null; });
  }

  function applyOption(name, value) {
    const { state } = current;
    if (name === 'range') state.range = value;
    if (name === 'smooth') state.smooth = Number(value);
    if (name === 'forecast') state.forecast = Number(value);
    if (name === 'trend') state.trend = !state.trend;
    if (name === 'markers') state.markers = !state.markers;
    saveState(current.id, state);
    current.update();
    renderDialog();
  }

  function renderDialog() {
    const { model } = current;
    const state = current.state;
    detail?.chart.destroy();
    detail = draw(document.getElementById('chartDialogCanvas'), model, state, true);
    const { analysis } = detail;
    document.getElementById('chartDialogTitle').textContent = model.title;
    document.getElementById('chartStats').innerHTML = stats(model, analysis).map(([name, value]) =>
      `<div><span>${name}</span><strong>${value}</strong></div>`).join('') || '<div class="text-muted">Nog geen gegevens in deze periode.</div>';
    const notes = [];
    if (state.forecast && detail.forecast.length > 1) {
      const end = detail.forecast.at(-1);
      notes.push(`Voorspelling over ${state.forecast} weken: ${nl(end.y, model.decimals ?? 1)}${model.unit ? ` ${model.unit}` : ''}, op basis van de laatste weken. Indicatief.`);
    } else if (state.forecast) {
      notes.push('Voor een voorspelling zijn minstens drie metingen nodig.');
    }
    const goal = goalNote(model, analysis);
    if (goal) notes.push(goal);
    document.getElementById('chartNote').textContent = notes.join(' ');
    const chips = (name, options, active) => options.map(([value, text]) =>
      `<button type="button" class="chip${String(active) === String(value) ? ' active' : ''}" data-option="${name}" data-value="${value}">${text}</button>`).join('');
    const smoothOptions = (model.smoothOptions || [0, 3, 5, 7]).map(value => [value, value ? String(value) : 'Uit']);
    document.getElementById('chartControls').innerHTML = `
      <div class="cd-group"><span>Periode</span><div class="chip-row">${chips('range', analysis.ranges.map(item => [item.id, item.label]), analysis.range.id)}</div></div>
      <div class="cd-group"><span>${model.kind === 'bar' ? 'Gemiddelde (weken)' : 'Gladstrijken (metingen)'}</span><div class="chip-row">${chips('smooth', smoothOptions, state.smooth)}</div></div>
      <div class="cd-group"><span>Voorspelling</span><div class="chip-row">${chips('forecast', FORECASTS.map(weeks => [weeks, weeks ? `${weeks} wkn` : 'Uit']), state.forecast)}</div></div>
      <div class="cd-group"><span>Weergave</span><div class="chip-row">
        <button type="button" class="chip${state.trend ? ' active' : ''}" data-option="trend" data-value="1">Trendlijn</button>
        ${model.kind === 'bar' ? '' : `<button type="button" class="chip${state.markers ? ' active' : ''}" data-option="markers" data-value="1">Hoogste en laagste</button>`}
      </div></div>`;
  }

  function open(mounted) {
    ensureDialog();
    current = mounted;
    renderDialog();
    if (!dialog.open) dialog.showModal();
  }

  // ---- inline chart on a card ---------------------------------------------------------------------------------------
  // spec: { id, canvas, controls (element), model: () => model, defaults }
  function mount(spec) {
    const state = loadState(spec.id, { range: '3m', smooth: 0, trend: false, forecast: 0, markers: false, ...spec.defaults });
    let inline = null;
    const mounted = { id: spec.id, state, get model() { return spec.model(); }, update };

    function renderControls(ranges, active) {
      spec.controls.innerHTML = `<div class="chip-row">${ranges.map(item =>
        `<button type="button" class="chip${item.id === active ? ' active' : ''}" data-range="${item.id}">${item.label}</button>`).join('')}</div>
        <button type="button" class="chart-more" data-more>⤢ Grafiek openen</button>`;
    }

    function update() {
      const model = spec.model();
      inline?.chart.destroy();
      inline = draw(spec.canvas, model, state, false);
      renderControls(inline.analysis.ranges, inline.analysis.range.id);
    }

    spec.controls.addEventListener('click', event => {
      const chip = event.target.closest('[data-range]');
      if (chip) { state.range = chip.dataset.range; saveState(spec.id, state); update(); }
      if (event.target.closest('[data-more]')) open(mounted);
    });
    spec.canvas.closest('.chart-wrap')?.classList.add('tappable');
    spec.canvas.addEventListener('click', () => open(mounted));
    return mounted;
  }

  return { mount, RANGES };
})();

// Cardio logging in stages (minutes, speed, incline) with a live calorie estimate from the backend.
const Cardio = (() => {
  const FIELDS = { Loopband: ['speed', 'incline'], Fietsen: ['speed'] };
  const INTENSITIES = [['licht', 'Licht'], ['matig', 'Matig'], ['zwaar', 'Zwaar']];
  let segments = [blank()];
  let caloriesDirty = false;
  let estimateTimer = null;
  let estimateRequest = 0;

  function blank(from) {
    return { minutes: '', speed: from?.speed ?? '', incline: from?.incline ?? '', intensity: from?.intensity ?? 'matig' };
  }

  const kind = () => document.getElementById('cardioType').value;
  const fields = () => FIELDS[kind()] || ['intensity'];
  const nl = (value, digits = 0) => Number(value).toLocaleString('nl-NL', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const num = value => (value === '' || value == null ? null : Number(value));

  function validSegments() {
    return segments.filter(segment => Number(segment.minutes) > 0);
  }

  function toPayload(segment) {
    const used = fields();
    return {
      minutes: Number(segment.minutes),
      speed_kmh: used.includes('speed') ? num(segment.speed) : null,
      incline_pct: used.includes('incline') ? num(segment.incline) : null,
      intensity: used.includes('intensity') ? segment.intensity : null,
    };
  }

  function field(index, name, label, attributes) {
    const segment = segments[index];
    return `<div class="field"><label for="seg-${index}-${name}">${label}</label>
      <input id="seg-${index}-${name}" type="number" inputmode="decimal" data-index="${index}" data-field="${name}" value="${segment[name] ?? ''}" ${attributes} onfocus="this.select()"></div>`;
  }

  function renderSegments() {
    const used = fields();
    document.getElementById('cardioSegments').innerHTML = segments.map((segment, index) => `
      <div class="seg" data-index="${index}">
        <div class="seg-title"><span>Etappe ${index + 1}</span><span class="seg-kcal" id="segKcal${index}"></span>
          ${segments.length > 1 ? `<button type="button" class="seg-remove" data-remove="${index}" aria-label="Etappe ${index + 1} verwijderen">×</button>` : ''}</div>
        <div class="seg-fields cols-${used.includes('intensity') ? 1 : used.length + 1}">
          ${field(index, 'minutes', 'Minuten', 'min="1" step="1" placeholder="15"')}
          ${used.includes('speed') ? field(index, 'speed', 'Km/u', 'min="0" step="0.1" placeholder="5.5"') : ''}
          ${used.includes('incline') ? field(index, 'incline', 'Helling %', 'min="0" step="0.5" placeholder="0"') : ''}
          ${used.includes('intensity') ? `<div class="seg-intensity" role="group" aria-label="Intensiteit">${INTENSITIES.map(([value, text]) =>
            `<button type="button" class="chip${segment.intensity === value ? ' active' : ''}" data-index="${index}" data-intensity="${value}">${text}</button>`).join('')}</div>` : ''}
        </div>
      </div>`).join('');
  }

  function onType() {
    renderSegments();
    scheduleEstimate();
  }

  function addSegment() {
    segments.push(blank(segments[segments.length - 1]));
    renderSegments();
    const input = document.getElementById(`seg-${segments.length - 1}-minutes`);
    input?.focus();
    scheduleEstimate();
  }

  function scheduleEstimate() {
    clearTimeout(estimateTimer);
    estimateTimer = setTimeout(refreshEstimate, 350);
  }

  async function refreshEstimate() {
    const totals = document.getElementById('cardioTotals');
    const calories = document.getElementById('cardioCal');
    const note = document.getElementById('cardioNote');
    const valid = validSegments();
    segments.forEach((_, index) => { const label = document.getElementById(`segKcal${index}`); if (label) label.textContent = ''; });
    if (!valid.length) {
      totals.innerHTML = '';
      note.textContent = 'Vul minstens één etappe in om je calorieën te zien.';
      if (!caloriesDirty) calories.value = '';
      return;
    }
    const request = ++estimateRequest;
    try {
      const result = await api('/api/cardio/estimate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: kind(), segments: valid.map(toPayload) }),
      });
      if (request !== estimateRequest) return;
      const parts = [`${nl(result.minutes)} min`];
      if (result.distance_km != null) parts.push(`${nl(result.distance_km, 2)} km`);
      totals.innerHTML = `<div class="cardio-total-main">${parts.join(' · ')}</div>
        <div class="cardio-total-kcal">${result.kcal != null ? `🔥 ≈ ${nl(result.kcal)} kcal` : 'Log eerst je gewicht voor een kcal-schatting'}</div>`;
      let position = 0;
      segments.forEach((segment, index) => {
        if (!(Number(segment.minutes) > 0)) return;
        const label = document.getElementById(`segKcal${index}`);
        const detail = result.segments[position++];
        if (label && detail?.kcal != null) label.textContent = `≈ ${nl(detail.kcal)} kcal`;
      });
      if (!caloriesDirty) calories.value = result.kcal ?? '';
      note.textContent = result.weight_kg != null
        ? `Berekend met ${nl(result.weight_kg, 1)} kg (${kind() === 'Loopband' ? 'ACSM-loopbandformule met helling' : 'MET-waarden'}). Je kunt het getal aanpassen.`
        : 'Geen lichaamsgewicht bekend: vul je gewicht in bij het tabblad Gewicht.';
    } catch (error) {
      if (request === estimateRequest) note.textContent = 'Berekening niet beschikbaar.';
    }
  }

  async function save() {
    const button = document.getElementById('saveCardioButton');
    if (button.disabled) return;
    const valid = validSegments();
    if (!valid.length) { toast('⚠️ Vul de duur van minstens één etappe in!'); return; }
    const calories = document.getElementById('cardioCal').value;
    button.disabled = true;
    try {
      const response = await fetch('/api/cardio', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: kind(), segments: valid.map(toPayload), calories: caloriesDirty && calories !== '' ? Number(calories) : null }),
      });
      if (!response.ok) throw new Error('Cardio opslaan mislukt. Probeer opnieuw.');
      const saved = await response.json();
      segments = [blank()];
      caloriesDirty = false;
      document.getElementById('cardioCal').value = '';
      renderSegments();
      refreshEstimate();
      const message = Motivation.pick('cardio');
      Coach.show({ ...message, line: saved.calories != null ? `${nl(saved.calories)} kcal verbrand. ${message.line}` : message.line });
      loadCardioHistory();
      await loadStats(true);
    } catch (error) {
      toast(error.message || 'Geen verbinding. Probeer opnieuw.');
    } finally {
      button.disabled = false;
    }
  }

  function summary(row) {
    if (!row.segments?.length) return '';
    return row.segments.map(segment => {
      const parts = [`${nl(segment.minutes)} min`];
      if (segment.speed_kmh != null) parts.push(`${nl(segment.speed_kmh, 1)} km/u`);
      if (segment.incline_pct) parts.push(`${nl(segment.incline_pct, 1)}% helling`);
      if (segment.intensity) parts.push(segment.intensity);
      return parts.join(' · ');
    }).join('<br>');
  }

  function init() {
    const container = document.getElementById('cardioSegments');
    container.addEventListener('input', event => {
      const input = event.target.closest('input[data-field]');
      if (!input) return;
      segments[Number(input.dataset.index)][input.dataset.field] = input.value;
      scheduleEstimate();
    });
    container.addEventListener('click', event => {
      const remove = event.target.closest('[data-remove]');
      if (remove) {
        segments.splice(Number(remove.dataset.remove), 1);
        renderSegments();
        scheduleEstimate();
        return;
      }
      const chip = event.target.closest('[data-intensity]');
      if (chip) {
        segments[Number(chip.dataset.index)].intensity = chip.dataset.intensity;
        container.querySelectorAll(`[data-index="${chip.dataset.index}"][data-intensity]`).forEach(item => item.classList.toggle('active', item === chip));
        scheduleEstimate();
      }
    });
    document.getElementById('cardioCal').addEventListener('input', event => { caloriesDirty = event.target.value !== ''; });
    renderSegments();
  }

  init();
  return { addSegment, onType, save, refreshEstimate, summary };
})();

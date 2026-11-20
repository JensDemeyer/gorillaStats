// Body tab: BMI, healthy range and weight goal. Also feeds the dashboard body card.
const Body = (() => {
  let summary = null;
  const SCALE = { min: 15, max: 40 };
  const nl = (value, digits = 1) => Number(value).toLocaleString('nl-NL', { minimumFractionDigits: digits, maximumFractionDigits: digits });

  function chipClass(bmi) {
    if (bmi < 18.5) return 'low';
    if (bmi < 25) return '';
    return bmi < 30 ? 'warn' : 'bad';
  }

  function distanceText(data) {
    const weight = data.latest.weight_kg;
    if (weight < data.healthy_min_kg) return `Nog ${nl(data.healthy_min_kg - weight)} kg aankomen tot een gezond gewicht (BMI 18,5)`;
    if (data.to_healthy_kg > 0) return `Nog ${nl(data.to_healthy_kg)} kg af tot een gezond gewicht (BMI 24,9)`;
    return 'Je zit in het gezonde gewichtsbereik 🎉';
  }

  function goalHtml(data) {
    if (data.goal_weight_kg == null) return '';
    const remaining = data.goal_remaining_kg;
    const done = remaining != null && Math.abs(remaining) < 0.05;
    const text = remaining == null ? '' : done ? 'Doel bereikt! 🏆'
      : remaining > 0 ? `Nog ${nl(remaining)} kg tot je doel` : `${nl(-remaining)} kg onder je doel`;
    const percent = data.goal_progress == null ? 0 : Math.round(data.goal_progress * 100);
    return `<div class="goal-line"><span>🎯 Doel: ${nl(data.goal_weight_kg)} kg</span><span>${text}</span></div>
      <progress class="reward-progress" value="${percent}" max="100" aria-label="Voortgang naar doelgewicht"></progress>`;
  }

  function renderCard(data, container) {
    summary = data;
    if (!data.latest) {
      container.innerHTML = '<div class="empty-state"><p>Nog geen weging. Log je gewicht om je BMI te zien.</p></div>';
      return;
    }
    container.innerHTML = `
      <div class="body-summary">
        <div class="body-weight">${nl(data.latest.weight_kg)}<small> kg</small></div>
        <span class="bmi-chip ${chipClass(data.bmi)}">BMI ${nl(data.bmi)} · ${data.bmi_category}</span>
      </div>
      <div class="text-muted">${distanceText(data)}</div>
      ${goalHtml(data)}`;
  }

  function scaleHtml(bmi) {
    const position = Math.min(100, Math.max(0, ((bmi - SCALE.min) / (SCALE.max - SCALE.min)) * 100));
    const at = value => ((value - SCALE.min) / (SCALE.max - SCALE.min)) * 100;
    return `<div class="bmi-scale" role="img" aria-label="BMI ${nl(bmi)} op een schaal van ${SCALE.min} tot ${SCALE.max}">
        <span style="width:${at(18.5)}%;background:#6fb1d8"></span><span style="width:${at(25) - at(18.5)}%;background:#4a9a56"></span>
        <span style="width:${at(30) - at(25)}%;background:#e69500"></span><span style="width:${100 - at(30)}%;background:#e63946"></span>
        <i class="bmi-marker" style="left:${position}%"></i>
      </div>
      <div class="bmi-ticks"><span style="left:${at(18.5)}%">18,5</span><span style="left:${at(25)}%">25</span><span style="left:${at(30)}%">30</span></div>`;
  }

  function renderPage(data) {
    const content = document.getElementById('bmiContent');
    document.getElementById('heightInput').value = data.height_cm;
    document.getElementById('goalInput').value = data.goal_weight_kg ?? '';
    if (!data.latest) {
      content.innerHTML = '<div class="empty-state"><div class="icon">⚖️</div><p>Log je gewicht om je BMI en voortgang te zien.</p></div>';
      return;
    }
    content.innerHTML = `
      <div class="body-summary">
        <div><div class="bmi-big">${nl(data.bmi)}</div><div class="tile-label">BMI</div></div>
        <span class="bmi-chip ${chipClass(data.bmi)}">${data.bmi_category}</span>
      </div>
      ${scaleHtml(data.bmi)}
      <div class="bmi-facts">
        <div><strong>${nl(data.latest.weight_kg)} kg</strong><span>Huidig gewicht</span></div>
        <div><strong>${nl(data.healthy_min_kg)} – ${nl(data.healthy_max_kg)} kg</strong><span>Gezond bij ${nl(data.height_cm, 0)} cm</span></div>
      </div>
      <div class="bmi-note">${distanceText(data)}</div>
      ${goalHtml(data)}`;
  }

  async function load() {
    try {
      summary = await api('/api/settings');
      renderPage(summary);
      if (typeof renderBwChart === 'function') renderBwChart();
    } catch (error) {
      toast('Lichaamsgegevens laden mislukt.');
    }
  }

  async function save(payload) {
    const button = document.getElementById('saveProfileButton');
    button.disabled = true;
    try {
      summary = await api('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      renderPage(summary);
      if (typeof renderBwChart === 'function') renderBwChart();
      Dashboard.load();
      toast('✅ Opgeslagen');
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
    }
  }

  function saveProfile() {
    const height = Number(document.getElementById('heightInput').value);
    const goalValue = document.getElementById('goalInput').value;
    if (!(height >= 120 && height <= 230)) { toast('Vul een lengte tussen 120 en 230 cm in.'); return; }
    const payload = { height_cm: height };
    if (goalValue !== '') {
      const goal = Number(goalValue);
      if (!(goal >= 30 && goal <= 300)) { toast('Vul een doelgewicht tussen 30 en 300 kg in.'); return; }
      payload.goal_weight_kg = goal;
    }
    return save(payload);
  }

  function clearGoal() {
    document.getElementById('goalInput').value = '';
    return save({ clear_goal: true });
  }

  return { load, renderCard, saveProfile, clearGoal, get summary() { return summary; } };
})();

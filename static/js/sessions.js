// Detail sheets: one training day (Sessions) and the list of recent trainings. The sheet itself is shared with the
// muscle group details in muscles.js.
const Sheet = (() => {
  let dialog = null;

  function ensure() {
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.className = 'chart-dialog sheet';
    dialog.setAttribute('aria-labelledby', 'sheetTitle');
    dialog.innerHTML = `<div class="cd-head"><h2 id="sheetTitle"></h2><button type="button" class="icon-button" aria-label="Sluiten" data-close>×</button></div>
      <div id="sheetBody"></div>`;
    document.body.appendChild(dialog);
    dialog.addEventListener('click', event => {
      if (event.target === dialog || event.target.closest('[data-close]')) dialog.close();
    });
    return dialog;
  }

  function open(title, html) {
    ensure();
    document.getElementById('sheetTitle').textContent = title;
    document.getElementById('sheetBody').innerHTML = html;
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
  }

  const close = () => dialog?.open && dialog.close();
  const element = () => ensure();
  return { open, close, element };
})();

const Sessions = (() => {
  const PAGE = 10;
  let offset = 0;
  const nl = (value, digits = 0) => Number(value).toLocaleString('nl-NL', { maximumFractionDigits: digits });
  const long = iso => new Date(`${iso}T00:00:00`).toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const short = iso => new Date(`${iso}T00:00:00`).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' });

  function setLine(set) {
    const load = set.weight == null && set.reps == null ? 'Nog aan te vullen'
      : `${set.weight == null ? '? kg' : `${nl(set.weight, 2)} kg`} × ${set.reps == null ? '?' : set.reps}`;
    const tags = [set.is_pr ? '<em class="ss-pr">🏆 PR</em>' : '', set.single_arm ? '<em>1 arm</em>' : '',
      set.is_estimated ? '<em>geschat</em>' : '', set.notes ? `<em>${escapeHtml(set.notes)}</em>` : ''].join('');
    return `<li><span>Set ${set.set_nr}</span><strong>${load}</strong>${tags}</li>`;
  }

  function exerciseBlock(item) {
    const delta = item.previous ? item.volume - item.previous.volume : null;
    const compare = item.previous
      ? `Vorige keer (${short(item.previous.date)}): ${nl(item.previous.volume)} kg ` +
        `<b class="${delta > 0 ? 'up' : delta < 0 ? 'down' : ''}">${delta > 0 ? '▲ +' : delta < 0 ? '▼ ' : '= '}${nl(delta)} kg</b>`
      : 'Eerste keer gelogd';
    const best = item.best ? `Beste set ${nl(item.best.weight, 2)} kg × ${item.best.reps}${item.e1rm ? ` (e1RM ${nl(item.e1rm, 1)} kg)` : ''}` : '';
    const muscles = item.primary_muscles.length ? Muscles.labels(item.primary_muscles) : '';
    return `<section class="ss-ex">
      <div class="ss-ex-head"><strong>${escapeHtml(item.name)}</strong>${item.prs ? `<span class="ss-pr">🏆 ${item.prs}</span>` : ''}</div>
      <small>${escapeHtml(item.routine)}${muscles ? ` · ${escapeHtml(muscles)}` : ''}</small>
      <ul class="ss-sets">${item.sets.map(setLine).join('')}</ul>
      <div class="ss-foot"><span>Volume <b>${nl(item.volume)} kg</b></span>${best ? `<span>${best}</span>` : ''}<span>${compare}</span></div>
    </section>`;
  }

  function render(data) {
    const empty = !data.exercises.length && !data.cardio.length;
    const nav = `<div class="ss-nav">
      <button type="button" class="btn btn-ghost btn-sm" data-session-date="${data.previous_date || ''}" ${data.previous_date ? '' : 'disabled'}>← Vorige</button>
      <span>${long(data.date)}</span>
      <button type="button" class="btn btn-ghost btn-sm" data-session-date="${data.next_date || ''}" ${data.next_date ? '' : 'disabled'}>Volgende →</button>
    </div>`;
    if (empty) {
      return `${nav}<div class="empty-state"><div class="icon">💤</div><p>Geen training op deze dag.${data.weight_kg ? ` Gewogen: ${nl(data.weight_kg, 1)} kg.` : ''}</p></div>`;
    }
    const minutes = data.cardio.reduce((sum, item) => sum + item.duration_minutes, 0);
    const tiles = [['Sets', data.totals.sets], ['Volume', `${nl(data.totals.volume)} kg`], ['Oefeningen', data.totals.exercises],
      ['PR\'s', data.totals.prs], ...(minutes ? [['Cardio', `${nl(minutes)} min`]] : []), ...(data.weight_kg ? [['Gewicht', `${nl(data.weight_kg, 1)} kg`]] : [])];
    const peak = Math.max(...data.groups.map(group => group.volume), 1);
    const groups = data.groups.length ? `<div class="ss-groups">${data.groups.map(group => `<div>
        <span>${escapeHtml(group.group)}</span><div class="muscle-bar"><span style="width:${Math.round(group.volume / peak * 100)}%"></span></div>
        <small>${nl(group.volume)} kg · ${group.sets} sets</small></div>`).join('')}</div>` : '';
    const cardio = data.cardio.length ? `<section class="ss-ex"><div class="ss-ex-head"><strong>🏃 Cardio</strong></div><ul class="ss-sets">${
      data.cardio.map(item => `<li><span>${escapeHtml(item.type)}</span><strong>${nl(item.duration_minutes)} min</strong>${
        item.distance_km ? `<em>${nl(item.distance_km, 1)} km</em>` : ''}${item.calories ? `<em>${nl(item.calories)} kcal</em>` : ''}</li>`).join('')}</ul></section>` : '';
    return `${nav}
      ${data.routines.length ? `<div class="chip-row">${data.routines.map(name => `<span class="chip active">${escapeHtml(name)}</span>`).join('')}</div>` : ''}
      <div class="cd-stats">${tiles.map(([name, value]) => `<div><span>${name}</span><strong>${value}</strong></div>`).join('')}</div>
      ${groups}${data.exercises.map(exerciseBlock).join('')}${cardio}
      ${data.exercises.length ? `<button type="button" class="btn btn-ghost" data-edit-date="${data.date}">✎ Sets aanpassen</button>` : ''}`;
  }

  async function open(date) {
    if (!date) return;
    try {
      await Muscles.load().catch(() => {});
      const data = await api(`/api/sessions/${encodeURIComponent(date)}`);
      Sheet.open('Training', render(data));
    } catch (error) {
      toast(error.message);
    }
  }

  // The "edit sets" action reuses the training log under the dashboard.
  function edit(date) {
    Sheet.close();
    document.getElementById('logDate').value = date;
    showTab('dashboard');
    loadTodayLog();
    setTimeout(() => document.getElementById('todayLog').scrollIntoView({ block: 'center', behavior: 'smooth' }), 200);
  }

  Sheet.element().addEventListener('click', event => {
    const target = event.target.closest('[data-session-date]');
    if (target && target.dataset.sessionDate) open(target.dataset.sessionDate);
    const editButton = event.target.closest('[data-edit-date]');
    if (editButton) edit(editButton.dataset.editDate);
  });

  function row(item) {
    const date = new Date(`${item.date}T00:00:00`);
    return `<button type="button" class="session-row" data-open-session="${item.date}">
      <span class="sr-date"><b>${date.getDate()}</b><span>${date.toLocaleDateString('nl-NL', { month: 'short' })}</span></span>
      <span class="sr-main"><strong>${item.routines.map(escapeHtml).join(' + ') || 'Training'}</strong>
        <small>${item.exercises} oefeningen · ${item.sets} sets · ${nl(item.volume)} kg</small></span>
      ${item.prs ? `<span class="ss-pr">🏆 ${item.prs}</span>` : ''}
    </button>`;
  }

  async function loadRecent(reset = true) {
    const list = document.getElementById('recentSessions');
    if (!list) return;
    if (reset) offset = 0;
    try {
      const items = await api(`/api/sessions?limit=${PAGE}&offset=${offset}`);
      if (!reset) list.insertAdjacentHTML('beforeend', items.map(row).join(''));
      else list.innerHTML = items.length ? items.map(row).join('')
        : '<div class="empty-state"><div class="icon">🦍</div><p>Nog geen trainingen gelogd.</p></div>';
      offset += items.length;
      document.getElementById('moreSessions').hidden = items.length < PAGE;
    } catch (error) {
      if (reset) list.innerHTML = '<div class="empty-state"><p>Trainingen konden niet laden.</p></div>';
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-open-session]');
    if (button) open(button.dataset.openSession);
  });

  return { open, loadRecent, loadMore: () => loadRecent(false) };
})();

// Muscle groups: a front/back body figure, the exercise card, the dashboard statistics and the editor picker.
const Muscles = (() => {
  let taxonomy = null;
  let loading = null;

  // Shapes are drawn for the left half of a 100 wide gorilla and mirrored. `lights` lists the muscle keys that
  // colour a shape; a shape without `lights` is only part of the silhouette and `detail` marks face details.
  const HEAD = [
    { type: 'path', d: 'M40 14 C41 2 59 2 60 14 Z', center: true },
    { type: 'ellipse', c: [50, 20], r: [12, 11], center: true },
  ];
  const FACE = [
    { type: 'path', d: 'M39.5 17 C45 13.5 55 13.5 60.5 17 L60 21 C55 18.5 45 18.5 40 21 Z', center: true, detail: 'dark' },
    { type: 'ellipse', c: [50, 26.5], r: [6.5, 4.5], center: true, detail: 'light' },
    { type: 'ellipse', c: [45.2, 19.8], r: [1.4, 1.2], detail: 'eye' },
    { type: 'ellipse', c: [47.8, 26], r: [0.9, 0.7], detail: 'dark' },
  ];
  const TORSO = { type: 'path', d: 'M27 36 C19 62 23 98 29 120 L36 132 L64 132 L71 120 C77 98 81 62 73 36 Z', center: true };
  const LIMB_ENDS = [
    { type: 'ellipse', c: [41, 179], r: [6, 4] },
    { type: 'ellipse', c: [8.5, 141], r: [6.5, 10], rotate: 5 },
    { type: 'ellipse', c: [37, 214], r: [9, 4.5] },
  ];
  const SHAPES = {
    front: [
      TORSO, ...LIMB_ENDS,
      { type: 'path', d: 'M43 29 C34 30 22 34 13 43 L23 47 C31 41 40 37 46.5 34 Z', lights: ['traps'] },
      { type: 'ellipse', c: [11.5, 52], r: [5.5, 11], rotate: 8, lights: ['shoulder_side'] },
      { type: 'ellipse', c: [22, 50], r: [7, 10], lights: ['shoulder_front'] },
      { type: 'path', d: 'M28 42 L49.2 44 L49.2 54 L26 53 Z', lights: ['chest_upper', 'chest'] },
      { type: 'path', d: 'M26 54.8 L49.2 55 L49.2 65 L26.5 64 Z', lights: ['chest'] },
      { type: 'path', d: 'M26.5 65.8 L49.2 66 L49.2 76 L29 75 Z', lights: ['chest_lower', 'chest'] },
      { type: 'ellipse', c: [14, 71], r: [6.5, 15], rotate: -3, lights: ['biceps'] },
      { type: 'ellipse', c: [11, 108], r: [6, 20], rotate: -2, lights: ['forearms'] },
      { type: 'path', d: 'M25 78 L32 78 L35 118 L30 112 Z', lights: ['core'] },
      { type: 'path', d: 'M33 77.5 L49.2 77.5 L49.2 124 L37 120 Z', lights: ['core'] },
      { type: 'path', d: 'M33 128 C30 145 31 160 36 176 L48.8 176 C49.5 160 49.5 142 49 130 Z', lights: ['quads'] },
      { type: 'path', d: 'M46.5 132 L49 132 C49 150 48 162 47 172 L43 160 C45 150 46 142 46.5 132 Z', lights: ['adductors'] },
      { type: 'path', d: 'M34 183 C32 192 33 202 36 208 L45 208 C47 202 47 192 46 183 Z', lights: ['calves'] },
      ...HEAD, ...FACE,
    ],
    back: [
      TORSO, ...LIMB_ENDS,
      { type: 'path', d: 'M50 27 L36 29 L19 42 L29 54 L50 76 Z', lights: ['traps'] },
      { type: 'ellipse', c: [11.5, 52], r: [5.5, 11], rotate: 8, lights: ['shoulder_side'] },
      { type: 'ellipse', c: [22, 50], r: [7, 10], lights: ['shoulder_rear'] },
      { type: 'path', d: 'M24 58 C22 72 28 92 40 108 L49.2 108 L49.2 78 L38 62 Z', lights: ['lats'] },
      { type: 'path', d: 'M37 57 L49.2 62 L49.2 80 L41 72 Z', lights: ['mid_back'] },
      { type: 'ellipse', c: [31, 57], r: [4, 3.5], lights: ['rotator_cuff'] },
      { type: 'path', d: 'M38 100 L49.2 96 L49.2 122 L38 120 Z', lights: ['lower_back'] },
      { type: 'ellipse', c: [14, 71], r: [6.5, 15], rotate: -3, lights: ['triceps'] },
      { type: 'ellipse', c: [11, 108], r: [6, 20], rotate: -2, lights: ['forearms'] },
      { type: 'ellipse', c: [41, 127], r: [9.5, 8], lights: ['glutes'] },
      { type: 'path', d: 'M33 136 C31 150 32 162 36 176 L48.8 176 C49.5 160 49.5 148 49 136 Z', lights: ['hamstrings'] },
      { type: 'ellipse', c: [40, 195], r: [7, 14], lights: ['calves'] },
      ...HEAD,
      { type: 'ellipse', c: [38.5, 20], r: [2, 3.5] },
    ],
  };

  function mirrorPath(d) {
    return d.replace(/([MLCQ])([^MLCQZ]*)/g, (_, command, args) => {
      const numbers = args.trim().split(/[\s,]+/).map(Number);
      return command + numbers.map((value, index) => (index % 2 === 0 ? +(100 - value).toFixed(2) : value)).join(' ');
    });
  }

  function shapeMarkup(shape, mirrored, attributes) {
    if (shape.type === 'path') return `<path d="${mirrored ? mirrorPath(shape.d) : shape.d}" ${attributes}/>`;
    const cx = mirrored ? 100 - shape.c[0] : shape.c[0];
    const angle = (mirrored ? -1 : 1) * (shape.rotate || 0);
    const transform = angle ? ` transform="rotate(${angle} ${cx} ${shape.c[1]})"` : '';
    return `<ellipse cx="${cx}" cy="${shape.c[1]}" rx="${shape.r[0]}" ry="${shape.r[1]}"${transform} ${attributes}/>`;
  }

  const groupOf = key => taxonomy?.muscles.find(muscle => muscle.key === key)?.group || null;

  // options: { primary: [keys], secondary: [keys] } for an exercise, or { heat: { group: 0..1 } } for statistics.
  function figure({ primary = [], secondary = [], heat = null } = {}) {
    const views = ['front', 'back'].map((view, index) => {
      const body = SHAPES[view].map(shape => {
        const lights = shape.lights || [];
        let attributes = 'class="mb-shape"';
        if (shape.detail) {
          attributes = `class="mb-detail ${shape.detail}"`;
        } else if (heat) {
          const group = lights.map(groupOf).find(Boolean);
          const value = group ? heat[group] || 0 : 0;
          if (value > 0) attributes = `class="mb-shape mb-heat" style="fill-opacity:${(0.25 + value * 0.75).toFixed(2)}"`;
        } else if (lights.some(key => primary.includes(key))) {
          attributes = 'class="mb-shape mb-p"';
        } else if (lights.some(key => secondary.includes(key))) {
          attributes = 'class="mb-shape mb-s"';
        }
        return shape.center ? shapeMarkup(shape, false, attributes)
          : shapeMarkup(shape, false, attributes) + shapeMarkup(shape, true, attributes);
      }).join('');
      return `<g transform="translate(${index * 120} 0)">${body}<text x="50" y="233" class="mb-label">${view === 'front' ? 'VOOR' : 'ACHTER'}</text></g>`;
    }).join('');
    return `<svg class="muscle-figure" viewBox="0 0 220 238" role="img" aria-label="Spiergroepen, voor- en achterkant">${views}</svg>`;
  }

  function load() {
    loading ||= api('/api/muscles').then(data => { taxonomy = data; return data; }).catch(error => { loading = null; throw error; });
    return loading;
  }

  const label = key => taxonomy?.muscles.find(muscle => muscle.key === key)?.label || key;
  const labels = keys => keys.map(label).join(', ');

  // Chips to choose primary and secondary muscles of one exercise in the schema editor.
  function picker(index, primary, secondary) {
    const row = (kind, selected, title) => `<div class="muscle-pick"><span>${title}</span><div class="chip-row">${
      (taxonomy?.muscles || []).map(muscle => `<button type="button" class="chip${selected.includes(muscle.key) ? ' active' : ''}"
        aria-pressed="${selected.includes(muscle.key)}" onclick="toggleDraftMuscle(${index}, '${kind}', '${muscle.key}')">${escapeHtml(muscle.label)}</button>`).join('')
    }</div></div>`;
    return row('primary', primary, 'Primair (telt mee in statistieken)') + row('secondary', secondary, 'Secundair');
  }

  return { load, figure, label, labels, picker, get ready() { return Boolean(taxonomy); } };
})();

// Cards that use the figure: the exercise card on the Training tab and the statistics card on the dashboard.
const MuscleUI = (() => {
  let period = 'week';
  let request = 0;

  function showExercise(exercise) {
    const card = document.getElementById('muscleCard');
    if (!card) return;
    if (!exercise) { card.hidden = true; return; }
    const primary = exercise.primary_muscles || [];
    const secondary = exercise.secondary_muscles || [];
    const body = primary.length || secondary.length
      ? `<div><span class="muscle-kind p">Primair</span> ${escapeHtml(Muscles.labels(primary) || '–')}</div>
         ${secondary.length ? `<div><span class="muscle-kind s">Secundair</span> ${escapeHtml(Muscles.labels(secondary))}</div>` : ''}`
      : `<div class="text-muted">Spiergroep nog niet ingesteld.</div>
         <button type="button" class="btn btn-ghost btn-sm" onclick="openRoutineEditor()">Instellen</button>`;
    card.innerHTML = `${Muscles.figure({ primary, secondary })}<div class="muscle-copy">${body}</div>`;
    card.hidden = false;
  }

  function selectPeriod(button) {
    period = button.dataset.period;
    document.querySelectorAll('#musclePeriod .chip').forEach(chip => chip.classList.toggle('active', chip === button));
    loadStats();
  }

  const nl = value => Number(value).toLocaleString('nl-NL');

  async function loadStats() {
    const container = document.getElementById('muscleStats');
    if (!container) return;
    const current = ++request;
    try {
      const [data] = await Promise.all([api(`/api/muscles/stats?period=${period}`), Muscles.load()]);
      if (current !== request) return;
      const heat = Object.fromEntries(data.groups.map(group => [group.group, group.relative]));
      const rows = [...data.groups].sort((a, b) => b.volume - a.volume || b.sets - a.sets);
      const peak = Math.max(...rows.map(row => row.volume), 0);
      const list = peak
        ? rows.map(row => `<div class="muscle-row${row.volume ? '' : ' none'}">
            <div class="muscle-row-head"><span>${escapeHtml(row.group)}</span><span>${nl(row.volume)} kg · ${row.sets} sets</span></div>
            <div class="muscle-bar"><span style="width:${peak ? Math.round(row.volume / peak * 100) : 0}%"></span></div>
          </div>`).join('')
        : '<div class="empty-state"><p>Nog geen sets in deze periode.</p></div>';
      const unassigned = data.unassigned.sets
        ? `<p class="text-muted">${data.unassigned.sets} sets horen bij oefeningen zonder spiergroep.</p>` : '';
      container.innerHTML = `<div class="muscle-stats">${Muscles.figure({ heat })}<div class="muscle-list">${list}</div></div>${unassigned}`;
    } catch (error) {
      if (current === request) container.innerHTML = '<div class="empty-state"><p>Spiergroepen konden niet laden.</p></div>';
    }
  }

  return { showExercise, selectPeriod, loadStats };
})();

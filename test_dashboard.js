const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join('static', 'index.html'), 'utf8');
const dashboard = fs.readFileSync(path.join('static', 'js', 'dashboard.js'), 'utf8');
const sessions = fs.readFileSync(path.join('static', 'js', 'sessions.js'), 'utf8');
const css = fs.readFileSync(path.join('static', 'css', 'app.css'), 'utf8');
const displayRoutine = html.match(/function displayRoutine\(name\) \{[\s\S]*?\n  \}/)[0];

function contextFor(extra = {}) {
  const context = vm.createContext({ ...extra });
  vm.runInContext(displayRoutine, context);
  return context;
}

test('push schema names are displayed distinctly without changing other names', () => {
  const context = contextFor();
  for (const [input, expected] of [
    ['Push', '🅿️ush'], ['Push A', '🅿️ush A'], ['push B', '🅿️ush B'],
    ['🅿️ush', '🅿️ush'], ['Pushdown', 'Pushdown'], ['Pull', 'Pull'],
  ]) {
    assert.equal(context.displayRoutine(input), expected);
  }
});

test('calendar uses one activity color, distinct initials and month-only labels', async () => {
  const elements = {
    calendar: { innerHTML: '' },
    overviewTiles: { innerHTML: '' },
    bodyCardContent: {},
    weeksChart: {},
    weeksChartControls: {},
  };
  const weeks = [
    { start: '2026-10-26', active_days: 1, sets: 0, tonnage: 0, cardio_minutes: 0, kcal: 0 },
    { start: '2026-11-02', active_days: 3, sets: 0, tonnage: 0, cardio_minutes: 0, kcal: 0 },
  ];
  const calendar = [
    { date: '2026-10-26', sets: 1, minutes: 0, tonnage: 10, routines: ['Push', 'Pull'] },
    { date: '2026-10-27', sets: 12, minutes: 0, tonnage: 20, routines: ['Push A'] },
    { date: '2026-10-28', sets: 25, minutes: 0, tonnage: 30, routines: ['Pull'] },
    { date: '2026-10-29', sets: 0, minutes: 1, tonnage: 0, routines: [] },
    { date: '2026-10-30', sets: 0, minutes: 0, tonnage: 0, routines: [] },
    { date: '2026-11-02', sets: 3, minutes: 0, tonnage: 10, routines: ['🅿️ush', 'Push A', 'Pull'] },
  ];
  const context = contextFor({
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : [2026, 10, 2])); }
    },
    document: {
      getElementById: id => elements[id],
      querySelectorAll: () => [],
    },
    localStorage: { getItem: () => null },
    api: async url => url.startsWith('/api/calendar')
      ? { weeks, calendar }
      : { weeks, month: { active_days: 0 }, previous_month: { active_days: 0 }, average_active_days: 0, best_week_days: 0 },
    escapeHtml: value => String(value),
    Charts: { mount: () => ({ update() {} }) },
    Body: { renderCard() {} },
    console,
  });
  vm.runInContext(dashboard, context);
  await vm.runInContext('Dashboard.load()', context);
  const result = elements.calendar.innerHTML;

  for (const day of ['26', '27', '28']) {
    assert.match(result, new RegExp(`class="cal-day active"[^>]*><i>${day}</i>`));
  }
  assert.match(result, /class="cal-day active cardio"[^>]*><i>29<\/i>/);
  assert.match(result, /class="cal-day"[^>]*><i>30<\/i>/);
  assert.match(result, /class="cal-day future"/);
  assert.match(result, /<i>26<\/i><small>🅿️P<\/small>/);
  assert.match(result, /<i>27<\/i><small>🅿️<\/small>/);
  assert.match(result, /<i>28<\/i><small>P<\/small>/);
  assert.match(result, /<i>2<\/i><small>🅿️P<\/small>/);
  assert.match(result, /class="cal-day active today"[^>]*><i>2<\/i>/);
  assert.match(result, /class="cal-label"><b>okt\.?<\/b><\/span>/);
  assert.match(result, /class="cal-label"><b>nov\.?<\/b><\/span>/);
  assert.match(result, /class="cal-sum goal">3\/3<\/span>/);
  assert.match(css, /\.cal-day\.active\s*\{/);
  assert.match(html, /cal-swatch active"><\/i>Training/);
  assert.match(html, /🅿️ = 🅿️ush · P = Pull/);
  assert.doesNotMatch(html, /cal-note|cal-swatch l[123]/);
});

test('editing a displayed push schema preserves its stored name unless renamed', async () => {
  const saveRoutine = html.match(/async function saveRoutine\(event\) \{[\s\S]*?\n  \}\r?\n\r?\n  async function loadStats/)[0]
    .replace(/\r?\n\r?\n  async function loadStats$/, '');
  const elements = {
    saveRoutineButton: { disabled: false },
    editRoutineName: { value: '🅿️ush A' },
    routineEditor: { close() {} },
  };
  const calls = [];
  const context = contextFor({
    document: { getElementById: id => elements[id] },
    api: async (url, options) => { calls.push({ url, body: JSON.parse(options.body) }); },
    loadRoutines: async name => { calls.push({ selected: name }); },
    toast: () => {},
  });
  vm.runInContext(`let editingRoutine = 'Push A'; let routineDraft = [{ id: 1, name: 'Press' }]; ${saveRoutine}`, context);
  await context.saveRoutine({ preventDefault() {} });
  assert.equal(calls[0].url, '/api/routines/Push%20A');
  assert.equal(calls[0].body.name, 'Push A');
  assert.equal(calls[1].selected, 'Push A');

  calls.length = 0;
  elements.editRoutineName.value = '🅿️ush B';
  await context.saveRoutine({ preventDefault() {} });
  assert.equal(calls[0].body.name, 'Push B');

  calls.length = 0;
  elements.editRoutineName.value = 'Armen';
  await context.saveRoutine({ preventDefault() {} });
  assert.equal(calls[0].body.name, 'Armen');
});

test('session details display push names without changing the source data', async () => {
  const data = {
    date: '2026-10-26', previous_date: null, next_date: null,
    routines: ['Push', 'Pull'], cardio: [], groups: [], weight_kg: null,
    totals: { sets: 1, volume: 10, exercises: 1, prs: 0 },
    exercises: [{ name: 'Press', routine: 'Push A', primary_muscles: [], prs: 0, sets: [],
      volume: 10, previous: null, best: null }],
  };
  let rendered = '';
  const context = contextFor({
    Sheet: { element: () => ({ addEventListener() {} }), open: (title, body) => { rendered = body; } },
    document: { addEventListener() {} },
    Muscles: { load: async () => {} },
    api: async () => data,
    escapeHtml: value => String(value),
    toast: message => { throw new Error(message); },
  });
  vm.runInContext(sessions.slice(sessions.indexOf('const Sessions =')), context);
  await vm.runInContext("Sessions.open('2026-10-26')", context);
  assert.match(rendered, /class="chip active">🅿️ush<\/span>/);
  assert.match(rendered, /class="chip active">Pull<\/span>/);
  assert.match(rendered, /<small>🅿️ush A<\/small>/);
  assert.equal(data.routines[0], 'Push');
  assert.equal(data.exercises[0].routine, 'Push A');
});

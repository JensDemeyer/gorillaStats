// Full-screen evolution route: a winding path through all levels with a stage image per phase.
const Journey = (() => {
  const STAGES = {
    1: { image: 'baby', label: 'Baby-gorilla' },
    2: { image: 'puber', label: 'Puber-aap' },
    3: { image: 'alfa', label: 'Zilverrug' },
    4: { image: 'alfa', label: 'Opperbeest', aura: true },
    5: { image: 'ultra-alfa', label: 'Ultra Alfa' },
  };
  const ROW = 96;
  const BANNER = 270;
  const NS = 'http://www.w3.org/2000/svg';
  const decorations = ['🌿', '🍃', '🌴', '🍌', '🪵', '🌱'];
  let rewards = null;
  let dialog = null;

  const stageFor = phase => STAGES[phase] || STAGES[5];
  const imageUrl = phase => `/static/stages/${stageFor(phase).image}.webp`;
  const number = value => Number(value).toLocaleString('nl-NL');

  function stageImage(phase, className = '') {
    const stage = stageFor(phase);
    return `<img class="stage-img${stage.aura ? ' aura' : ''} ${className}" src="${imageUrl(phase)}" alt="" loading="lazy" decoding="async">`;
  }

  // Updates the compact level card on the dashboard.
  function update(next) {
    rewards = next;
    const image = document.getElementById('heroStage');
    if (image) {
      image.src = imageUrl(next.phase_number);
      image.classList.toggle('aura', Boolean(stageFor(next.phase_number).aura));
    }
    if (dialog?.open) render();
  }

  function build() {
    dialog = document.createElement('dialog');
    dialog.className = 'journey-overlay';
    dialog.setAttribute('aria-label', 'Jouw evolutie');
    dialog.innerHTML = `
      <header class="journey-bar">
        <button type="button" class="journey-close" aria-label="Sluiten">✕</button>
        <div class="journey-bar-copy"><strong>Jouw evolutie</strong><span id="journeyBarInfo"></span></div>
        <button type="button" class="journey-jump" aria-label="Naar mijn level">◎</button>
      </header>
      <div class="journey-scroll" id="journeyScroll"><div class="journey-map" id="journeyMap"></div></div>
      <div class="journey-detail" id="journeyDetail" hidden></div>`;
    document.body.appendChild(dialog);
    dialog.querySelector('.journey-close').addEventListener('click', close);
    dialog.querySelector('.journey-jump').addEventListener('click', () => scrollToCurrent(true));
    dialog.addEventListener('click', event => {
      if (!event.target.closest('.journey-detail, .journey-node, .journey-banner')) hideDetail();
    });
    window.addEventListener('resize', () => { if (dialog.open) render(); });
  }

  function open() {
    if (!rewards) return;
    if (!dialog) build();
    if (!dialog.open) dialog.showModal();
    hideDetail();
    render();
    scrollToCurrent(false);
  }

  function close() {
    dialog?.close();
  }

  function layout() {
    const items = [];
    let y = 56;
    let index = 0;
    rewards.journey.forEach(phase => {
      items.push({ type: 'banner', phase, y: y + BANNER / 2, x: 50 });
      y += BANNER;
      phase.levels.forEach(rank => {
        items.push({ type: 'node', phase, rank, y, x: 50 + 27 * Math.sin(index * 1.15), index });
        y += ROW;
        index++;
      });
    });
    const height = y + 40;
    items.forEach(item => { item.top = height - item.y; });
    return { items, height };
  }

  function curvePath(points, width) {
    if (!points.length) return '';
    const px = point => (point.x / 100) * width;
    let d = `M ${px(points[0])} ${points[0].top}`;
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1];
      const b = points[i];
      const mid = (a.top + b.top) / 2;
      d += ` C ${px(a)} ${mid}, ${px(b)} ${mid}, ${px(b)} ${b.top}`;
    }
    return d;
  }

  function render() {
    const map = document.getElementById('journeyMap');
    const scroll = document.getElementById('journeyScroll');
    const width = map.clientWidth || scroll.clientWidth || 360;
    const { items, height } = layout();
    const current = rewards.level;
    document.getElementById('journeyBarInfo').textContent = `Level ${current} / ${rewards.max_level} · ${number(rewards.xp)} XP`;
    map.style.height = `${height}px`;

    const pathItems = items.slice().sort((a, b) => b.top - a.top);
    const reached = pathItems.filter(item => item.type === 'banner' ? item.phase.start_level <= current : item.rank.level <= current);
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'journey-path');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    for (const [className, points] of [['path-locked', pathItems], ['path-done', reached]]) {
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', curvePath(points, width));
      path.setAttribute('class', className);
      svg.appendChild(path);
    }

    const html = [];
    items.filter(item => item.type === 'node').forEach(item => {
      if (item.index % 2 === 0) {
        const side = item.x < 50 ? 86 : 14;
        html.push(`<span class="journey-decor" style="left:${side}%;top:${item.top + 12}px" aria-hidden="true">${decorations[item.index % decorations.length]}</span>`);
      }
    });
    for (const item of items) {
      if (item.type === 'banner') {
        const phase = item.phase;
        const state = phase.start_level <= current ? (phase.number === rewards.phase_number ? 'current' : 'done') : 'locked';
        html.push(`<button type="button" class="journey-banner ${state}" data-phase="${phase.number}" style="top:${item.top}px">
          <div class="banner-art">${stageImage(phase.number)}${state === 'locked' ? '<span class="banner-lock">🔒</span>' : ''}</div>
          <small>FASE ${phase.number} · LEVEL ${phase.start_level}–${phase.end_level}</small>
          <h3>${escapeHtml(phase.name)}</h3>
          <span class="banner-status">${state === 'locked' ? 'Nog niet ontgrendeld' : state === 'current' ? 'Jouw huidige fase' : '✓ Behaald'}</span>
        </button>`);
      } else {
        const { rank } = item;
        const state = rank.current ? 'current' : rank.unlocked ? 'done' : 'locked';
        const content = state === 'current' ? stageImage(item.phase.number, 'node-avatar') : state === 'done' ? '✓' : rank.level;
        html.push(`<button type="button" class="journey-node ${state}" data-level="${rank.level}" style="left:${item.x}%;top:${item.top}px" aria-label="Level ${rank.level}: ${escapeHtml(rank.name)}${state === 'current' ? ', huidig' : state === 'done' ? ', behaald' : ', nog vergrendeld'}">
          ${state === 'current' ? '<span class="node-pulse"></span>' : ''}<span class="node-face">${content}</span>
          <span class="node-level">${rank.level}</span>
        </button>`);
      }
    }
    map.innerHTML = '';
    map.appendChild(svg);
    map.insertAdjacentHTML('beforeend', html.join(''));
    map.querySelectorAll('.journey-node').forEach(node => node.addEventListener('click', () => showRank(Number(node.dataset.level))));
    map.querySelectorAll('.journey-banner').forEach(banner => banner.addEventListener('click', () => showPhase(Number(banner.dataset.phase))));
  }

  function scrollToCurrent(smooth) {
    const scroll = document.getElementById('journeyScroll');
    const node = document.querySelector(`.journey-node[data-level="${rewards.level}"]`);
    if (!node) return;
    const top = node.offsetTop - scroll.clientHeight / 2 + 30;
    scroll.scrollTo({ top: Math.max(0, top), behavior: smooth && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'instant' });
  }

  function showDetail(html) {
    const detail = document.getElementById('journeyDetail');
    detail.innerHTML = `<button type="button" class="detail-close" aria-label="Sluiten">✕</button>${html}`;
    detail.querySelector('.detail-close').addEventListener('click', hideDetail);
    detail.hidden = false;
    requestAnimationFrame(() => detail.classList.add('visible'));
  }

  function hideDetail() {
    const detail = document.getElementById('journeyDetail');
    if (!detail) return;
    detail.classList.remove('visible');
    detail.hidden = true;
  }

  function showRank(level) {
    const phase = rewards.journey.find(item => level >= item.start_level && level <= item.end_level);
    const rank = phase.levels.find(item => item.level === level);
    const left = rank.xp_required - rewards.xp;
    const status = rank.current ? 'Jouw huidige rang' : rank.unlocked ? '✓ Behaald' : `Nog ${number(left)} XP te gaan`;
    const progress = rank.current && !rewards.is_max_level
      ? `<progress class="reward-progress" value="${rewards.level_xp}" max="${rewards.next_level_xp}"></progress>
         <div class="detail-xp"><span>${number(rewards.level_xp)} / ${number(rewards.next_level_xp)} XP naar level ${level + 1}</span></div>` : '';
    showDetail(`
      <div class="detail-art ${phase.start_level <= rewards.level ? '' : 'locked'}">${stageImage(phase.number)}</div>
      <div class="detail-copy">
        <small>FASE ${phase.number} · ${escapeHtml(phase.name)}</small>
        <h3>Level ${rank.level} · ${escapeHtml(rank.name)}</h3>
        <p>${escapeHtml(rank.description)}</p>
        <div class="detail-status ${rank.current ? 'current' : rank.unlocked ? 'done' : ''}">${status}</div>
        <div class="detail-meta">${number(rank.xp_required)} XP totaal nodig</div>
        ${progress}
      </div>`);
  }

  function showPhase(number) {
    const phase = rewards.journey.find(item => item.number === number);
    const unlocked = phase.start_level <= rewards.level;
    const levelsLeft = Math.max(0, phase.start_level - rewards.level);
    showDetail(`
      <div class="detail-art ${unlocked ? '' : 'locked'}">${stageImage(phase.number)}</div>
      <div class="detail-copy">
        <small>FASE ${phase.number} · LEVEL ${phase.start_level}–${phase.end_level}</small>
        <h3>${escapeHtml(phase.name)}</h3>
        <p>${escapeHtml(phase.description)}</p>
        <div class="detail-status ${phase.completed ? 'done' : unlocked ? 'current' : ''}">${phase.completed ? '✓ Fase voltooid' : unlocked ? 'Je zit in deze fase' : `Nog ${levelsLeft} ${levelsLeft === 1 ? 'level' : 'levels'} tot deze fase`}</div>
        <div class="detail-meta">Fasebadge bij level ${phase.end_level}</div>
      </div>`);
  }

  return { update, open, close, stageImage, imageUrl, stageFor };
})();

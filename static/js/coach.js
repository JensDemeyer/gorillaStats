// Floating feedback card ("coach") with XP chip and a small emoji burst, used for the game-like feel.
const Coach = (() => {
  let card = null;
  let hideTimer = null;
  let xpShown = false;

  function ensure() {
    if (card) return card;
    card = document.createElement('div');
    card.className = 'coach';
    card.setAttribute('role', 'status');
    card.setAttribute('aria-live', 'polite');
    card.innerHTML = '<div class="coach-emoji" aria-hidden="true"></div><div class="coach-copy"><strong></strong><p></p><div class="coach-actions"></div></div><div class="coach-xp" hidden></div>';
    card.addEventListener('click', event => { if (!event.target.closest('button')) hide(); });
    document.body.appendChild(card);
    return card;
  }

  function hide() {
    clearTimeout(hideTimer);
    card?.classList.remove('visible');
  }

  function show({ emoji, title, line, tone = '', action = null, duration = 4600 }) {
    const element = ensure();
    clearTimeout(hideTimer);
    xpShown = false;
    element.className = `coach ${tone}`.trim();
    element.querySelector('.coach-emoji').textContent = emoji || '🦍';
    element.querySelector('strong').textContent = title || '';
    element.querySelector('p').textContent = line || '';
    const xp = element.querySelector('.coach-xp');
    xp.hidden = true;
    const actions = element.querySelector('.coach-actions');
    actions.innerHTML = '';
    if (action) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = action.label;
      button.addEventListener('click', () => { hide(); action.run(); });
      actions.appendChild(button);
    }
    void element.offsetWidth;
    element.classList.add('visible');
    hideTimer = setTimeout(hide, action ? duration + 2400 : duration);
  }

  // Shows the XP gained for the action; falls back to a toast when no card is visible.
  function addXp(amount, fallback) {
    if (!(amount > 0)) return;
    if (!card || !card.classList.contains('visible') || xpShown) {
      fallback?.(amount);
      return;
    }
    const xp = card.querySelector('.coach-xp');
    xp.textContent = `+${amount} XP`;
    xp.hidden = false;
    xp.classList.remove('pop');
    void xp.offsetWidth;
    xp.classList.add('pop');
    xpShown = true;
  }

  function burst(origin, emojis = ['💪', '🔥', '⭐']) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const rect = origin.getBoundingClientRect();
    for (let i = 0; i < 9; i++) {
      const piece = document.createElement('span');
      piece.className = 'burst-piece';
      piece.textContent = emojis[i % emojis.length];
      const angle = (Math.PI * 2 * i) / 9 + Math.random() * 0.5;
      const distance = 60 + Math.random() * 60;
      piece.style.left = `${rect.left + rect.width / 2}px`;
      piece.style.top = `${rect.top + rect.height / 2}px`;
      piece.style.setProperty('--dx', `${Math.cos(angle) * distance}px`);
      piece.style.setProperty('--dy', `${Math.sin(angle) * distance - 40}px`);
      document.body.appendChild(piece);
      setTimeout(() => piece.remove(), 1000);
    }
  }

  return { show, hide, addXp, burst };
})();

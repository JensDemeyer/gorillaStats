// Replaces native <select> popups with a jungle-themed bottom sheet.
// The original <select> stays in the DOM (hidden) so value, selectedIndex, options and onchange keep working.
(function () {
  const valueProperty = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
  const indexProperty = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
  const chevron = '<svg class="jsel-chevron" viewBox="0 0 12 8" aria-hidden="true"><path d="M1 1l5 5 5-5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>';

  const sheet = document.createElement('dialog');
  sheet.className = 'jsheet';
  sheet.innerHTML = '<div class="jsheet-grip"></div><div class="jsheet-title"></div><div class="jsheet-list" role="listbox"></div>';
  document.body.appendChild(sheet);
  sheet.addEventListener('click', event => { if (event.target === sheet) sheet.close(); });

  function labelFor(select) {
    return select.id ? document.querySelector(`label[for="${select.id}"]`) : null;
  }

  function open(select, button) {
    sheet.querySelector('.jsheet-title').textContent = select.dataset.title || labelFor(select)?.textContent || button.dataset.title || 'Kies';
    const list = sheet.querySelector('.jsheet-list');
    list.innerHTML = '';
    [...select.options].forEach((option, index) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'jopt' + (index === select.selectedIndex ? ' selected' : '');
      item.disabled = option.disabled;
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', String(index === select.selectedIndex));
      const text = document.createElement('span');
      text.textContent = option.textContent;
      item.appendChild(text);
      item.addEventListener('click', () => {
        const changed = select.selectedIndex !== index;
        select.selectedIndex = index;
        sheet.close();
        if (changed) select.dispatchEvent(new Event('change', { bubbles: true }));
        button.focus({ preventScroll: true });
      });
      list.appendChild(item);
    });
    if (!sheet.open) sheet.showModal();
    list.querySelector('.selected')?.scrollIntoView({ block: 'center' });
  }

  function enhance(select) {
    if (select.dataset.enhanced || select.dataset.native !== undefined || select.multiple) return;
    select.dataset.enhanced = '1';
    select.classList.add('jsel-native');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'jsel';
    button.setAttribute('aria-haspopup', 'listbox');
    button.innerHTML = '<span class="jsel-label"></span>' + chevron;
    select.insertAdjacentElement('afterend', button);
    const text = button.querySelector('.jsel-label');
    const label = labelFor(select);
    if (label) label.addEventListener('click', () => button.focus());

    const refresh = () => {
      const option = select.options[select.selectedIndex];
      text.textContent = option ? option.textContent : (select.dataset.placeholder || 'Kies…');
      button.disabled = select.disabled || select.options.length === 0;
    };
    // Programmatic changes (select.value = ..., select.selectedIndex = ...) do not fire events.
    Object.defineProperty(select, 'value', {
      get() { return valueProperty.get.call(this); },
      set(next) { valueProperty.set.call(this, next); refresh(); },
    });
    Object.defineProperty(select, 'selectedIndex', {
      get() { return indexProperty.get.call(this); },
      set(next) { indexProperty.set.call(this, next); refresh(); },
    });
    new MutationObserver(refresh).observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled'] });
    button.addEventListener('click', () => open(select, button));
    refresh();
  }

  window.enhanceSelects = (root = document) => root.querySelectorAll('select').forEach(enhance);
  window.enhanceSelects();
})();

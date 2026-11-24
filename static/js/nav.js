// Browser history for in-app navigation, so the back button / back swipe closes the open dialog
// or returns to the previous tab instead of leaving the app. Only at the very first screen does back exit.
const Nav = (() => {
  const dialogs = [];
  let skipPops = 0;

  function pushTab(tab) {
    history.pushState({ tab }, '');
  }

  function openedDialog(dialog) {
    if (dialogs.includes(dialog)) return;
    dialogs.push(dialog);
    history.pushState({ dialog: true }, '');
  }

  function closedDialog(dialog) {
    const index = dialogs.indexOf(dialog);
    if (index === -1) return;
    dialogs.splice(index, 1);
    // Closed by a button: drop the entry that was pushed when it opened.
    skipPops++;
    history.back();
  }

  function init(tab) {
    history.replaceState({ tab }, '');
    new MutationObserver(records => {
      for (const record of records) {
        const target = record.target;
        if (target.nodeName !== 'DIALOG') continue;
        if (target.open) openedDialog(target); else closedDialog(target);
      }
    }).observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ['open'] });

    window.addEventListener('popstate', event => {
      if (skipPops > 0) { skipPops--; return; }
      const dialog = dialogs.pop();
      if (dialog) {
        if (dialog.open) dialog.close();
        return;
      }
      const tab = event.state?.tab;
      if (tab && tab !== currentTab()) showTab(tab, true);
    });
  }

  return { init, pushTab };
})();

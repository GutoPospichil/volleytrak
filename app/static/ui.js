(function () {
  function syncGroup(group, value) {
    const input = group.querySelector('input[type="hidden"]');
    if (!input) return;
    if (value !== undefined) input.value = value;
    group.querySelectorAll('[data-choice]').forEach((button) => {
      const active = button.dataset.choice === input.value;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function setupGroup(group) {
    const input = group.querySelector('input[type="hidden"]');
    if (!input) return;
    group.querySelectorAll('[data-choice]').forEach((button) => {
      button.addEventListener('click', () => {
        if (input.value === button.dataset.choice) return;
        input.value = button.dataset.choice;
        syncGroup(group);
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
    input.addEventListener('change', () => syncGroup(group));
    syncGroup(group);
  }

  window.setChoiceValue = function (inputId, value, emit) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.value = value;
    const group = input.closest('[data-choice-group]');
    if (group) syncGroup(group);
    if (emit !== false) input.dispatchEvent(new Event('change', { bubbles: true }));
  };

  function init() {
    document.querySelectorAll('[data-choice-group]').forEach(setupGroup);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

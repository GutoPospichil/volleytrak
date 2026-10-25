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

  const MUTE_KEY = 'vt-muted';
  let muted = false;
  try {
    muted = localStorage.getItem(MUTE_KEY) === '1';
  } catch (error) {}

  function applyMuteState() {
    document.querySelectorAll('video').forEach((video) => {
      video.muted = muted;
    });
    const button = document.getElementById('mute-toggle');
    if (!button) return;
    button.classList.toggle('active', muted);
    button.setAttribute('aria-pressed', muted ? 'true' : 'false');
    button.title = muted ? 'Ativar som (M)' : 'Mutar vídeos (M)';
    const icon = button.querySelector('.mute-icon');
    const label = button.querySelector('.mute-label');
    if (icon) icon.textContent = muted ? '\uD83D\uDD07' : '\uD83D\uDD0A';
    if (label) label.textContent = muted ? 'Mudo' : 'Som';
    try {
      localStorage.setItem(MUTE_KEY, muted ? '1' : '0');
    } catch (error) {}
  }

  function toggleMute() {
    muted = !muted;
    applyMuteState();
  }

  function setupMute() {
    const button = document.getElementById('mute-toggle');
    if (button) button.addEventListener('click', toggleMute);
    document.addEventListener(
      'play',
      (event) => {
        if (muted && event.target && event.target.tagName === 'VIDEO') {
          event.target.muted = true;
        }
      },
      true
    );
    document.addEventListener(
      'loadedmetadata',
      (event) => {
        if (muted && event.target && event.target.tagName === 'VIDEO') {
          event.target.muted = true;
        }
      },
      true
    );
    document.addEventListener('keydown', (event) => {
      if (event.key.toLowerCase() !== 'm') return;
      const target = event.target;
      if (
        target &&
        (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      toggleMute();
    });
    applyMuteState();
  }

  function init() {
    document.querySelectorAll('[data-choice-group]').forEach(setupGroup);
    setupMute();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

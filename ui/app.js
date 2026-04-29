// app.js — renders rows from state, handles button clicks via pywebview API

let state = { today: null, projects: [] };
let idleSeconds = 0;
let idleThreshold = 15 * 60;
let modalOpenFor = null;  // project name awaiting note

function fmtCounter(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function elapsedSecondsForProject(p) {
  if (!p.running || !p.started_at) return p.today_seconds;
  const startMs = new Date(p.started_at).getTime();
  const sessionSecs = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
  return p.today_seconds + sessionSecs;
}

function render() {
  const rowsEl = document.getElementById('rows');
  rowsEl.innerHTML = '';

  if (state.projects.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'row';
    empty.innerHTML = '<span class="name" style="color: var(--fg-dim); font-weight: 400;">No projects. Ask Claude to add one.</span>';
    rowsEl.appendChild(empty);
    return;
  }

  for (const p of state.projects) {
    const row = document.createElement('div');
    row.className = 'row';
    if (p.running) row.classList.add('running');
    if (p.running && idleSeconds >= idleThreshold) row.classList.add('idle-dim');

    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = p.name;
    row.appendChild(name);

    const counter = document.createElement('span');
    counter.className = 'counter';
    counter.textContent = fmtCounter(elapsedSecondsForProject(p));
    row.appendChild(counter);

    const dot = document.createElement('button');
    dot.className = 'dot ' + (p.running ? 'red' : 'green');
    if (p.running && idleSeconds >= idleThreshold) dot.classList.add('pulsing');
    dot.addEventListener('click', async () => {
      if (modalOpenFor) return;  // ignore while modal is open
      if (!p.running) {
        await pywebview.api.start_timer(p.name);
      } else {
        await pywebview.api.stop_timer(p.name);
        openNoteModal(p.name);
      }
    });
    row.appendChild(dot);

    rowsEl.appendChild(row);
  }
}

function openNoteModal(projectName) {
  modalOpenFor = projectName;
  const modal = document.getElementById('note-modal');
  const subtitle = document.getElementById('modal-subtitle');
  const input = document.getElementById('modal-input');
  const save = document.getElementById('modal-save');
  subtitle.textContent = projectName;
  input.value = '';
  save.disabled = true;
  modal.hidden = false;
  // focus on next tick so the modal is visible first
  setTimeout(() => input.focus(), 0);
}

function closeNoteModal() {
  modalOpenFor = null;
  document.getElementById('note-modal').hidden = true;
}

function wireModal() {
  const input = document.getElementById('modal-input');
  const save = document.getElementById('modal-save');

  const submit = async () => {
    const value = input.value.trim();
    if (!value) return;
    const projectName = modalOpenFor;
    if (!projectName) return;
    save.disabled = true;
    try {
      await pywebview.api.attach_note(projectName, value);
    } finally {
      closeNoteModal();
      render();
    }
  };

  input.addEventListener('input', () => {
    save.disabled = input.value.trim().length === 0;
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !save.disabled) {
      submit();
    }
    // Escape does nothing — note is required.
  });

  save.addEventListener('click', submit);
}

window.setState = function (newState) {
  state = newState;
  render();
};

window.setIdle = function (seconds, thresholdSeconds) {
  idleSeconds = seconds;
  idleThreshold = thresholdSeconds;
  render();
};

function wireDrag() {
  const isInteractive = (el) => {
    if (!el) return false;
    const tag = el.tagName;
    if (tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'A') return true;
    if (el.closest && el.closest('button, input, select, textarea, a, .modal-backdrop')) return true;
    return false;
  };

  document.body.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    if (modalOpenFor) return;  // no drag while modal is open
    if (isInteractive(e.target)) return;
    if (window.pywebview && window.pywebview.api && pywebview.api.start_drag) {
      pywebview.api.start_drag();
    }
  });
}

setInterval(() => {
  render();
}, 1000);

setInterval(async () => {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const s = await pywebview.api.get_state();
    if (JSON.stringify(s) !== JSON.stringify(state)) {
      state = s;
      render();
    }
  } catch (e) {}
}, 3000);

document.addEventListener('DOMContentLoaded', () => {
  wireDrag();
  wireModal();
  if (window.pywebview && window.pywebview.api) {
    pywebview.api.get_state().then((s) => {
      state = s;
      render();
    });
  }
});

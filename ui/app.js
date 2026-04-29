// app.js — renders rows from state, handles button clicks via pywebview API

let state = { today: null, projects: [] };
let idleSeconds = 0;
let idleThreshold = 15 * 60;
let openNoteFor = null;

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
      if (!p.running) {
        await pywebview.api.start_timer(p.name);
      } else {
        await pywebview.api.stop_timer(p.name);
        openNoteFor = p.name;
        render();
        const inputEl = document.querySelector(`input[data-note-for="${p.name}"]`);
        if (inputEl) inputEl.focus();
      }
    });
    row.appendChild(dot);

    rowsEl.appendChild(row);

    if (openNoteFor === p.name) {
      const wrap = document.createElement('div');
      wrap.className = 'row';
      wrap.style.borderTop = 'none';

      const noteWrap = document.createElement('div');
      noteWrap.className = 'note-input-wrap';

      const input = document.createElement('input');
      input.className = 'note-input';
      input.placeholder = 'what did you work on?';
      input.dataset.noteFor = p.name;

      input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
          await pywebview.api.attach_note(p.name, input.value);
          openNoteFor = null;
          render();
        } else if (e.key === 'Escape') {
          await pywebview.api.attach_note(p.name, '');
          openNoteFor = null;
          render();
        }
      });

      noteWrap.appendChild(input);
      wrap.appendChild(noteWrap);
      rowsEl.appendChild(wrap);
    }
  }
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
    if (el.closest && el.closest('button, input, select, textarea, a')) return true;
    return false;
  };

  document.body.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
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
  if (window.pywebview && window.pywebview.api) {
    pywebview.api.get_state().then((s) => {
      state = s;
      render();
    });
  }
});

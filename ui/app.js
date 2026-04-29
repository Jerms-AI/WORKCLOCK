// app.js — renders rows from state, handles button clicks via pywebview API

let state = { today: null, projects: [] };
let idleSeconds = 0;
let idleThreshold = 15 * 60;
let openNoteFor = null;
let pendingTrim = {};

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
    if (p.recovery) row.classList.add('recovery');
    if (p.long_session) row.classList.add('long-session');
    if (p.running && idleSeconds >= idleThreshold) row.classList.add('idle-dim');

    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = p.name;
    row.appendChild(name);

    const counter = document.createElement('span');
    counter.className = 'counter';
    counter.textContent = fmtCounter(elapsedSecondsForProject(p));
    row.appendChild(counter);

    if (p.recovery) {
      const placeholder = document.createElement('span');
      row.appendChild(placeholder);

      const actions = document.createElement('div');
      actions.className = 'recovery-actions';

      const stopBtn = document.createElement('button');
      stopBtn.className = 'text-btn';
      stopBtn.textContent = `Stop at ${new Date(p.proposed_stop_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}`;
      stopBtn.addEventListener('click', async () => {
        await pywebview.api.recovery_stop(p.name);
      });

      const resumeBtn = document.createElement('button');
      resumeBtn.className = 'text-btn';
      resumeBtn.textContent = 'Resume';
      resumeBtn.addEventListener('click', async () => {
        await pywebview.api.recovery_resume(p.name);
      });

      actions.appendChild(stopBtn);
      actions.appendChild(resumeBtn);
      row.appendChild(actions);
    } else {
      const dot = document.createElement('button');
      dot.className = 'dot ' + (p.running ? 'red' : 'green');
      if (p.running && idleSeconds >= idleThreshold) dot.classList.add('pulsing');
      dot.addEventListener('click', async () => {
        if (!p.running) {
          await pywebview.api.start_timer(p.name);
        } else {
          await pywebview.api.stop_timer(p.name);
          openNoteFor = p.name;
          if (idleSeconds >= idleThreshold) {
            pendingTrim[p.name] = new Date(Date.now() - idleSeconds * 1000).toISOString();
          }
          render();
          const inputEl = document.querySelector(`input[data-note-for="${p.name}"]`);
          if (inputEl) inputEl.focus();
        }
      });
      row.appendChild(dot);
    }

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
          await pywebview.api.attach_note(p.name, input.value, false);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        } else if (e.key === 'Escape') {
          await pywebview.api.attach_note(p.name, '', false);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        }
      });

      noteWrap.appendChild(input);

      if (pendingTrim[p.name]) {
        const trimTime = new Date(pendingTrim[p.name]).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        const keepBtn = document.createElement('button');
        keepBtn.className = 'text-btn';
        keepBtn.textContent = 'keep';
        keepBtn.addEventListener('click', async () => {
          await pywebview.api.attach_note(p.name, input.value, false);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        });
        const trimBtn = document.createElement('button');
        trimBtn.className = 'text-btn';
        trimBtn.textContent = `trim ${trimTime}`;
        trimBtn.addEventListener('click', async () => {
          await pywebview.api.attach_note(p.name, input.value, true);
          openNoteFor = null;
          delete pendingTrim[p.name];
          render();
        });
        noteWrap.appendChild(keepBtn);
        noteWrap.appendChild(trimBtn);
      }

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

function wireSettings() {
  const panel = document.getElementById('settings-panel');
  const btn = document.getElementById('settings-btn');
  const closeBtn = document.getElementById('settings-close');
  const aot = document.getElementById('setting-always-on-top');
  const idle = document.getElementById('setting-idle-threshold');
  const rememberPos = document.getElementById('setting-remember-position');
  const resetPos = document.getElementById('setting-reset-position');

  btn.addEventListener('click', async () => {
    if (panel.hidden) {
      const s = await pywebview.api.get_settings();
      aot.checked = s.always_on_top;
      idle.value = s.idle_threshold_minutes;
      rememberPos.checked = s.remember_window_position;
    }
    panel.hidden = !panel.hidden;
  });

  closeBtn.addEventListener('click', () => { panel.hidden = true; });

  aot.addEventListener('change', () => pywebview.api.update_setting('always_on_top', aot.checked));
  idle.addEventListener('change', () => pywebview.api.update_setting('idle_threshold_minutes', parseInt(idle.value, 10) || 15));
  rememberPos.addEventListener('change', () => pywebview.api.update_setting('remember_window_position', rememberPos.checked));
  resetPos.addEventListener('click', () => pywebview.api.reset_window_position());

  document.getElementById('add-btn').addEventListener('click', () => {
    // No-op in v1; tooltip explains
  });

  document.getElementById('close-btn').addEventListener('click', () => {
    pywebview.api.quit_app();
  });
}

setInterval(() => {
  render();
}, 1000);

document.addEventListener('DOMContentLoaded', () => {
  wireSettings();
  if (window.pywebview && window.pywebview.api) {
    pywebview.api.get_state().then((s) => {
      state = s;
      render();
    });
    pywebview.api.get_settings().then((s) => {
      idleThreshold = (s.idle_threshold_minutes || 15) * 60;
      render();
    });
  }
});

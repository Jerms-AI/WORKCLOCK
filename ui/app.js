// app.js — renders rows from state, handles button clicks via pywebview API

let state = { today: null, projects: [] };
let idleSeconds = 0;
let idleThreshold = 15 * 60;
let modalOpenFor = null;
let resetModalProject = null;
let lastWindowHeight = 0;

function isModalOpen() {
  return modalOpenFor !== null || resetModalProject !== null;
}

function resizeToContent() {
  if (isModalOpen()) return;
  if (!window.pywebview || !window.pywebview.api) return;
  const topbar = document.getElementById('topbar');
  const rows = document.getElementById('rows');
  const h = (topbar ? topbar.offsetHeight : 0) + (rows ? rows.offsetHeight : 0) + 2;
  const target = Math.max(60, Math.ceil(h));
  if (target !== lastWindowHeight) {
    lastWindowHeight = target;
    pywebview.api.resize(target);
  }
}

function resizeForModal(modalId) {
  setTimeout(() => {
    const content = document.querySelector('#' + modalId + ' .modal-content');
    if (!content || !window.pywebview || !window.pywebview.api) return;
    const target = content.offsetHeight + 100;
    lastWindowHeight = target;
    pywebview.api.resize(Math.max(target, 220));
  }, 30);
}

// Floor seconds to 5-minute increments.
function floor5min(seconds) {
  return Math.floor(seconds / 300) * 5;
}

// "H:MM" — current session display (5-min steps).
function fmtSessionHM(seconds) {
  const totalMinutes = floor5min(seconds);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${h}:${String(m).padStart(2, '0')}`;
}

// "H.MM" — today/total display (5-min steps).
function fmtTotalHM(seconds) {
  const totalMinutes = floor5min(seconds);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${h}.${String(m).padStart(2, '0')}`;
}

function sessionElapsedSeconds(p) {
  let elapsed = p.session_seconds || 0;
  if (p.running && p.started_at) {
    elapsed += Math.max(0, Math.floor((Date.now() - new Date(p.started_at).getTime()) / 1000));
  }
  return elapsed;
}

function updatePauseAllBtn() {
  const btn = document.getElementById('pause-all-btn');
  if (!btn) return;
  const anyRunning = state.projects.some(p => p.running);
  const anyPaused = state.projects.some(p => p.paused);
  if (anyRunning) {
    btn.textContent = '⏸';
    btn.title = 'Pause all';
    btn.disabled = false;
    btn.style.color = 'var(--green)';
  } else if (anyPaused) {
    btn.textContent = '▶';
    btn.title = 'Resume all';
    btn.disabled = false;
    btn.style.color = 'var(--warn)';
  } else {
    btn.textContent = '⏸';
    btn.title = 'No active timers';
    btn.disabled = true;
    btn.style.color = 'var(--fg-dim)';
  }
}

function render() {
  const rowsEl = document.getElementById('rows');
  rowsEl.innerHTML = '';
  updatePauseAllBtn();

  if (state.projects.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'row';
    empty.innerHTML = '<div class="name-col"><span class="name" style="color: var(--fg-dim); font-weight: 400;">No projects. Ask Claude to add one.</span></div>';
    rowsEl.appendChild(empty);
    return;
  }

  for (const p of state.projects) {
    const row = document.createElement('div');
    row.className = 'row';
    if (p.running) row.classList.add('running');
    if (p.paused) row.classList.add('paused');
    if (p.running && idleSeconds >= idleThreshold) row.classList.add('idle-dim');

    const sessionElapsed = sessionElapsedSeconds(p);
    const todayDisplay = (p.today_seconds || 0) + sessionElapsed;
    const totalDisplay = (p.total_seconds || 0) + sessionElapsed;

    const nameCol = document.createElement('div');
    nameCol.className = 'name-col';

    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = p.name;
    nameCol.appendChild(name);

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = `today ${fmtTotalHM(todayDisplay)} · total ${fmtTotalHM(totalDisplay)}`;
    nameCol.appendChild(meta);

    row.appendChild(nameCol);

    const counter = document.createElement('span');
    counter.className = 'counter';
    counter.textContent = fmtSessionHM(sessionElapsed);
    row.appendChild(counter);

    // Stop/start dot
    const stopDot = document.createElement('button');
    const isPaused = !!p.paused;
    let stopColor = 'green';
    if (p.running) stopColor = 'red';
    if (isPaused) stopColor = 'grey';
    stopDot.className = 'dot ' + stopColor;
    if (p.running && idleSeconds >= idleThreshold && !isPaused) stopDot.classList.add('pulsing');
    stopDot.disabled = isPaused;
    stopDot.addEventListener('click', async () => {
      if (isModalOpen()) return;
      if (isPaused) return;
      if (!p.running) {
        await pywebview.api.start_timer(p.name);
      } else {
        await pywebview.api.stop_timer(p.name);
        openNoteModal(p.name);
      }
    });
    row.appendChild(stopDot);

    // Pause/resume dot
    const pauseDot = document.createElement('button');
    const isActiveSession = p.running || isPaused;
    let pauseColor = 'grey';
    if (p.running) pauseColor = 'green';
    if (isPaused) pauseColor = 'yellow';
    pauseDot.className = 'pause-btn ' + pauseColor;
    pauseDot.textContent = isPaused ? '▶' : '⏸';
    pauseDot.disabled = !isActiveSession;
    pauseDot.addEventListener('click', async () => {
      if (isModalOpen()) return;
      if (!isActiveSession) return;
      if (isPaused) {
        await pywebview.api.resume_timer(p.name);
      } else {
        await pywebview.api.pause_timer(p.name);
      }
    });
    row.appendChild(pauseDot);

    // Reset button — visible only when session is active
    const resetBtn = document.createElement('button');
    resetBtn.className = 'reset-btn';
    resetBtn.textContent = '↺';
    resetBtn.title = 'Reset session';
    if (!p.running && !p.paused) {
      resetBtn.style.visibility = 'hidden';
      resetBtn.disabled = true;
    } else {
      resetBtn.addEventListener('click', () => {
        if (isModalOpen()) return;
        openResetModal(p);
      });
    }
    row.appendChild(resetBtn);

    rowsEl.appendChild(row);
  }

  resizeToContent();
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
  resizeForModal('note-modal');
  setTimeout(() => input.focus(), 0);
}

function closeNoteModal() {
  modalOpenFor = null;
  document.getElementById('note-modal').hidden = true;
  resizeToContent();
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
  });

  save.addEventListener('click', submit);
}

function openResetModal(project) {
  resetModalProject = project;
  document.getElementById('reset-subtitle').textContent = project.name;

  let firstStart;
  if (project.started_at) {
    const resumedAt = new Date(project.started_at);
    firstStart = new Date(resumedAt.getTime() - (project.session_seconds || 0) * 1000);
  } else {
    firstStart = new Date(Date.now() - (project.session_seconds || 0) * 1000);
  }
  document.getElementById('reset-meta').textContent =
    'started ' + firstStart.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const now = new Date();
  document.getElementById('reset-time').value =
    String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
  document.getElementById('reset-note').value = '';
  document.getElementById('reset-modal').hidden = false;
  resizeForModal('reset-modal');
  setTimeout(() => document.getElementById('reset-time').focus(), 0);
}

function closeResetModal() {
  resetModalProject = null;
  document.getElementById('reset-modal').hidden = true;
  resizeToContent();
}

function wireResetModal() {
  document.getElementById('reset-save').addEventListener('click', async () => {
    const project = resetModalProject;
    if (!project) return;
    const stopTime = document.getElementById('reset-time').value;
    const note = document.getElementById('reset-note').value || null;
    closeResetModal();
    await pywebview.api.reset_timer(project.name, stopTime, note);
  });

  document.getElementById('reset-omit').addEventListener('click', async () => {
    const project = resetModalProject;
    if (!project) return;
    closeResetModal();
    await pywebview.api.discard_timer(project.name);
  });
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
    if (isModalOpen()) return;
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
  wireResetModal();

  const pauseAllBtn = document.getElementById('pause-all-btn');
  if (pauseAllBtn) {
    pauseAllBtn.addEventListener('click', async () => {
      if (isModalOpen()) return;
      const anyRunning = state.projects.some(p => p.running);
      if (anyRunning) {
        await pywebview.api.pause_all();
      } else {
        await pywebview.api.resume_all();
      }
    });
  }

  if (window.pywebview && window.pywebview.api) {
    pywebview.api.get_state().then((s) => {
      state = s;
      render();
    });
  }
});

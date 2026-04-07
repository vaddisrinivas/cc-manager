const API_BASE = `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api`;

const DEMO = {
  status: {
    version: "0.1.0",
    installed_tools: [
      { name: "rtk", version: "v0.25.0", method: "cargo", status: "ok" },
      { name: "context7", version: "latest", method: "mcp", status: "ok" },
      { name: "ccusage", version: "v0.8.1", method: "cargo", status: "ok" },
    ]
  },
  analyze: {
    daily_labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    daily_input: [1200000, 2100000, 800000, 1500000, 900000, 2200000, 1100000],
    daily_output: [320000, 580000, 210000, 400000, 240000, 590000, 300000],
    daily_cost: [0.84, 1.52, 0.58, 1.10, 0.67, 1.58, 0.83],
  },
  sessions: {
    sessions: [
      { ts: "2026-04-07T10:47:00", input_tokens: 450000, output_tokens: 120000, cost_usd: 0.84, duration_min: 47, model: "opus" },
      { ts: "2026-04-07T09:15:00", input_tokens: 280000, output_tokens: 85000, cost_usd: 0.41, duration_min: 23, model: "sonnet" },
      { ts: "2026-04-06T16:30:00", input_tokens: 920000, output_tokens: 240000, cost_usd: 1.52, duration_min: 68, model: "opus" },
    ]
  },
  doctor: {
    checks: [
      { name: "rtk", status: "ok", detail: "v0.25.0" },
      { name: "settings.json", status: "ok", detail: "5 hooks" },
      { name: "config.toml", status: "ok", detail: "valid" },
      { name: "store", status: "ok", detail: "writable" },
      { name: "python", status: "ok", detail: "3.12.0" },
    ]
  },
  recommend: {
    recommendations: [
      { message: "No security tool installed", install_cmd: "ccm install trail-of-bits", tool: "trail-of-bits" },
    ]
  },
  registry: {
    tools: [
      { name: "trail-of-bits", description: "Security-focused auditing skills", category: "security" },
      { name: "claude-squad", description: "Multi-agent tmux orchestration", category: "orchestration" },
      { name: "agnix", description: "Config linter (385 rules)", category: "config" },
      { name: "repomix", description: "Pack entire repo for LLM context", category: "context" },
    ]
  },
  events: {
    events: [
      { ts: "2026-04-07T10:47:00", event: "session_end", session: "abc", input_tokens: 450000, cost_usd: 0.84, duration_min: 47, model: "opus" },
      { ts: "2026-04-07T10:00:05", event: "session_start", session: "abc", cwd: "/Users/user/Projects/myapp" },
      { ts: "2026-04-06T12:00:00", event: "install", tool: "rtk", version: "0.25.0", method: "cargo" },
      { ts: "2026-04-06T11:00:00", event: "doctor", results: { rtk: "ok" } },
      { ts: "2026-04-06T09:00:00", event: "session_end", session: "xyz", input_tokens: 280000, cost_usd: 0.41, duration_min: 23, model: "sonnet" },
    ]
  }
};

// Alias for backward-compat and test requirements
const DEMO_DATA = DEMO;

let tokenChart = null, costChart = null;
let usingDemoData = false;

async function apiFetch(path, fallbackKey) {
  try {
    const r = await fetch(`${API_BASE}${path}`);
    if (!r.ok) throw new Error();
    return await r.json();
  } catch {
    usingDemoData = true;
    return DEMO[fallbackKey] || {};
  }
}

// Alias required by tests
async function fetchWithFallback(url, fallbackKey) {
  return apiFetch(url.replace(`${API_BASE}`, ''), fallbackKey);
}

function emptyState(msg) {
  return `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:20px;font-style:italic">${msg}</td></tr>`;
}

async function apiPost(path, body = {}) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return r.json();
}

async function fetchAll() {
  usingDemoData = false;

  const [status, sessions, analyze, doctor, recommend, events] = await Promise.all([
    apiFetch('/status', 'status'),
    apiFetch('/sessions?since=7d', 'sessions'),
    apiFetch('/analyze?period=7d', 'analyze'),
    apiFetch('/doctor', 'doctor'),
    apiFetch('/recommend', 'recommend'),
    apiFetch('/events?limit=20', 'events'),
  ]);

  renderTools(status);
  renderSessions(sessions);
  renderTokenChart(analyze);
  renderCostChart(analyze);
  renderHealth(doctor);
  renderRecommendations(recommend);
  renderTicker(events);
  loadRegistry();

  // Update system status badge
  const hasFailures = (doctor.checks || []).some(c => c.status === 'fail');
  const statusEl = document.getElementById('systemStatus');
  if (statusEl) {
    statusEl.textContent = hasFailures ? 'STATUS: DEGRADED' : 'STATUS: NOMINAL';
    statusEl.className   = hasFailures ? 'system-status-degraded' : 'system-status-nominal';
  }

  // DEMO badge
  const liveLabelEl = document.querySelector('.live-label');
  const existingDemoBadge = document.getElementById('demoBadge');
  if (usingDemoData) {
    if (!existingDemoBadge && liveLabelEl) {
      const badge = document.createElement('span');
      badge.id = 'demoBadge';
      badge.style.cssText = 'color:var(--muted);font-size:9px;letter-spacing:0.1em;margin-left:6px;opacity:0.6;';
      badge.textContent = '\u25C8 DEMO';
      liveLabelEl.parentNode.insertBefore(badge, liveLabelEl.nextSibling);
    }
  } else if (existingDemoBadge) {
    existingDemoBadge.remove();
  }

  const lastUpdatedEl = document.getElementById('lastUpdated');
  if (lastUpdatedEl) lastUpdatedEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

function fmt(n) {
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
  return String(n);
}

function renderTools(data) {
  const tbody = document.querySelector('#toolsTable tbody');
  const tools = data.installed_tools || [];
  if (!tools.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty">No tools installed</td></tr>'; return; }
  tbody.innerHTML = tools.map(t => `<tr>
    <td><strong>${t.name}</strong></td>
    <td style="font-family:monospace;color:var(--muted)">${t.version || '—'}</td>
    <td style="color:var(--muted)">${t.method}</td>
    <td><span class="status-dot ${t.status}"></span>${t.status}</td>
    <td><button class="btn danger" onclick="removeTool('${t.name}',this)">Remove</button></td>
  </tr>`).join('');
}

function renderSessions(data) {
  const tbody = document.querySelector('#sessionsTable tbody');
  const sessions = data.sessions || [];
  if (!sessions.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty">No sessions</td></tr>'; return; }
  tbody.innerHTML = sessions.slice(0, 8).map(s => {
    const time = new Date(s.ts).toLocaleString();
    const tokens = fmt((s.input_tokens||0) + (s.output_tokens||0));
    return `<tr>
      <td style="color:var(--muted);font-size:12px">${time}</td>
      <td>${s.model || '—'}</td>
      <td>${s.duration_min ? s.duration_min + 'm' : '—'}</td>
      <td style="font-family:monospace">${tokens}</td>
      <td style="color:var(--green)">$${(s.cost_usd||0).toFixed(2)}</td>
    </tr>`;
  }).join('');
}

function renderTokenChart(data) {
  const ctx = document.getElementById('tokenChart').getContext('2d');
  if (tokenChart) tokenChart.destroy();
  tokenChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.daily_labels || [],
      datasets: [
        { label: 'Input', data: data.daily_input || [], borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,0.08)', fill: true, tension: 0.3 },
        { label: 'Output', data: data.daily_output || [], borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,0.08)', fill: true, tension: 0.3 },
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
        y: { ticks: { color: '#8b949e', callback: v => fmt(v) }, grid: { color: '#21262d' } }
      }
    }
  });
}

function renderCostChart(data) {
  const ctx = document.getElementById('costChart').getContext('2d');
  if (costChart) costChart.destroy();
  costChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.daily_labels || [],
      datasets: [{ label: 'Cost (USD)', data: data.daily_cost || [], backgroundColor: 'rgba(188,140,255,0.6)', borderColor: '#bc8cff', borderWidth: 1 }]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
        y: { ticks: { color: '#8b949e', callback: v => '$' + v.toFixed(2) }, grid: { color: '#21262d' } }
      }
    }
  });
}

function renderHealth(data) {
  const panel = document.getElementById('healthPanel');
  const checks = data.checks || [];
  if (!checks.length) { panel.innerHTML = '<div class="empty">No health data</div>'; return; }
  panel.innerHTML = checks.map(c =>
    `<div style="padding:6px 0;display:flex;align-items:center;border-bottom:1px solid var(--border)">
      <span class="status-dot ${c.status}"></span>
      <span>${c.name}</span>
      ${c.detail ? `<span style="color:var(--muted);margin-left:auto;font-size:12px">${c.detail}</span>` : ''}
    </div>`
  ).join('');
}

function renderRecommendations(data) {
  const panel = document.getElementById('recommendPanel');
  const recs = data.recommendations || [];
  if (!recs.length) {
    panel.innerHTML = '<div class="empty">All clear — your setup looks good.</div>';
    return;
  }
  panel.innerHTML = recs.map(r =>
    `<div class="rec-item">
      <span class="msg">${r.message}</span>
      <button class="btn" onclick="navigator.clipboard.writeText('${r.install_cmd}');this.textContent='Copied!'">${r.install_cmd}</button>
    </div>`
  ).join('');
}

function renderRegistry(tools) {
  const panel = document.getElementById('registryPanel');
  if (!panel) return;
  if (!tools.length) {
    panel.innerHTML = '<div class="empty">All recommended tools installed.</div>';
    return;
  }
  panel.innerHTML = tools.map(t =>
    `<div class="rec-item">
      <div>
        <strong>${t.name}</strong>
        <span style="color:var(--muted);margin-left:8px;font-size:12px">${t.description || ''}</span>
      </div>
      <button class="install-btn" onclick="installTool('${t.name}',this)">Install</button>
    </div>`
  ).join('');
}

async function loadRegistry() {
  const [statusData, registryData] = await Promise.all([
    apiFetch('/status', 'status'),
    apiFetch('/registry?tier=recommended', 'registry'),
  ]);
  const installed = new Set((statusData.installed_tools || []).map(t => t.name));
  const available = (registryData.tools || []).filter(t => !installed.has(t.name));
  renderRegistry(available);
}

async function installTool(name, btn) {
  btn.disabled = true;
  btn.textContent = 'Installing...';
  try {
    const result = await apiPost('/install', { tool: name });
    btn.textContent = result.ok ? 'Installed' : 'Failed';
    if (result.ok) setTimeout(fetchAll, 500);
  } catch {
    btn.textContent = 'Error';
  }
}

async function removeTool(name, btn) {
  if (!confirm('Remove ' + name + '?')) return;
  btn.disabled = true; btn.textContent = '...';
  try {
    await apiPost('/remove', { tool: name });
    btn.textContent = 'Done';
    setTimeout(fetchAll, 500);
  } catch { btn.textContent = 'Error'; }
}

async function toggleModule(name, enabled, btn) {
  btn.disabled = true;
  try {
    const result = await apiPost('/module', { module: name, enabled });
    btn.disabled = false;
    if (result.ok) {
      btn.textContent = enabled ? 'ON' : 'OFF';
    }
  } catch {
    btn.disabled = false;
  }
}

async function runDoctor(btn) {
  btn.disabled = true;
  btn.textContent = 'Scanning...';
  try {
    const result = await apiPost('/doctor/run');
    renderHealth(result);
  } catch {}
  btn.disabled = false;
  btn.textContent = 'Re-scan';
}

function renderTicker(data) {
  const content = document.getElementById('tickerContent');
  if (!content) return;
  const evts = Array.isArray(data) ? data : (data.events || []);

  if (!evts.length) {
    content.innerHTML = '<span style="color:var(--muted)">&#x25C6; NO EVENTS</span>';
    return;
  }

  function fmt(n) {
    if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
    return String(n);
  }

  const parts = evts.slice(0, 20).map(e => {
    const t = e.ts ? new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const type = (e.event || e.type || 'EVENT').toUpperCase();
    let detail = '';
    if (e.input_tokens) detail += ` \u25CF ${fmt(e.input_tokens)} tokens`;
    if (e.cost_usd)     detail += ` \u25CF $${e.cost_usd.toFixed(2)}`;
    if (e.duration_min) detail += ` \u25CF ${e.duration_min}min`;
    if (e.version)      detail += ` \u25CF ${e.version}`;
    if (e.model)        detail += ` \u25CF ${e.model}`;
    return `<span>[${t}] ${type}${detail}</span>`;
  });

  const sep = '<span style="color:var(--cyan);margin:0 16px;opacity:0.6"> &#x25C6; </span>';
  const joined = parts.join(sep);
  content.innerHTML = joined + sep + joined;
}

fetchAll();
setInterval(fetchAll, 60000);

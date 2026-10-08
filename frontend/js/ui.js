// Small UI helpers shared by all pages (needs api.js loaded first).
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function badge(text) {
  if (!text) return '<span class="muted">-</span>';
  const cls = text === "Needs Improvement" ? "needs" : text.toLowerCase();
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}

// Progress bar. `good` = higher is better; colours switch at 50 / 75.
function bar(value, max = 100) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const cls = pct >= 75 ? "ok" : pct >= 50 ? "warn" : "bad";
  return `<div class="bar ${cls}"><span style="width:${pct}%"></span></div>`;
}

const RISK_COLOR = { Low: "#16a34a", Medium: "#d97706", High: "#dc2626" };

function mountTopbar(user, active) {
  const home = Auth.homeFor(user.role);
  const link = (href, text, key) =>
    `<a href="${href}" class="${active === key ? "active" : ""}">${text}</a>`;
  $("topbar").className = "topbar";
  $("topbar").innerHTML = `
    <span class="brand">EduAssist AI</span>
    <nav>${link(home, "Dashboard", "home")}${link("bus.html", "Bus Tracking", "bus")}</nav>
    <span class="user">${esc(user.name)} (${esc(user.role)})
      <button onclick="Auth.logout()">Logout</button></span>`;
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src; s.onload = resolve; s.onerror = () => reject(new Error("Could not load " + src));
    document.head.appendChild(s);
  });
}

function alertList(alerts, withStudent = false) {
  if (!alerts.length) return '<div class="empty">No open alerts.</div>';
  return '<ul class="plain">' + alerts.map((a) => `
    <li>${badge(a.severity)}<span class="grow">${withStudent ? `<b>${esc(a.roll_no)} ${esc(a.student_name)}</b><br>` : ""}${esc(a.message)}</span></li>`
  ).join("") + "</ul>";
}

// Small bar chart used for per-subject views. Requires Chart.js.
function subjectBarChart(canvasId, labels, datasets) {
  return new Chart($(canvasId), {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100 } },
      plugins: { legend: { display: datasets.length > 1 } },
    },
  });
}

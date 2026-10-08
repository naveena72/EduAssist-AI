// Faculty dashboard.
(async function () {
  const user = await Auth.guard("faculty");
  if (!user) return;
  mountTopbar(user, "home");
  initChatbot();

  let rows = [], charts = {};
  let chartJsReady = false;
  try {
    await loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js");
    chartJsReady = true;
  } catch { /* charts are skipped when offline */ }

  async function loadAll() {
    const [summary, perf, table, alerts] = await Promise.all([
      api("/dashboard/summary"), api("/dashboard/class-performance"),
      api("/dashboard/students"), api("/alerts?status=open"),
    ]);
    renderStats(summary);
    renderCharts(summary, perf);
    rows = table;
    renderTable();
    renderAlerts(alerts);
    $("notice").textContent = summary.analysed ? "" : "No analysis yet - click 'Run AI Analysis'.";
  }

  function renderStats(s) {
    $("stats").innerHTML = `
      <div class="card stat"><div class="label">Students</div><div class="value">${s.total_students}</div></div>
      <div class="card stat"><div class="label">High risk</div><div class="value text-high">${s.risk.High}</div>
        <div class="sub">${s.risk.Medium} medium &middot; ${s.risk.Low} low</div></div>
      <div class="card stat"><div class="label">Avg attendance</div><div class="value">${s.avg_attendance}%</div></div>
      <div class="card stat"><div class="label">Avg marks</div><div class="value">${s.avg_marks}%</div></div>
      <div class="card stat"><div class="label">Avg progress score</div><div class="value">${s.avg_progress_score}</div></div>
      <div class="card stat"><div class="label">Open alerts</div><div class="value">${s.open_alerts}</div>
        <div class="sub">${s.critical_alerts} critical</div></div>`;
  }

  function renderCharts(s, perf) {
    if (!chartJsReady) {
      $("chartsRow").style.display = "none";
      return;
    }
    Object.values(charts).forEach((c) => c.destroy());
    charts.risk = new Chart($("riskChart"), {
      type: "doughnut",
      data: { labels: ["Low", "Medium", "High"],
              datasets: [{ data: [s.risk.Low, s.risk.Medium, s.risk.High],
                           backgroundColor: [RISK_COLOR.Low, RISK_COLOR.Medium, RISK_COLOR.High] }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
    charts.perf = subjectBarChart("perfChart", perf.map((p) => p.code), [
      { label: "Avg marks %", data: perf.map((p) => p.avg_marks_pct), backgroundColor: "#3b5bdb" },
      { label: "Avg attendance %", data: perf.map((p) => p.avg_attendance_pct), backgroundColor: "#94a3b8" },
    ]);
  }

  function renderTable() {
    const lvl = $("fRisk").value, q = $("fSearch").value.trim().toLowerCase();
    const list = rows.filter((r) =>
      (!lvl || r.risk_level === lvl) &&
      (!q || r.name.toLowerCase().includes(q) || r.roll_no.toLowerCase().includes(q)));
    $("tblCount").textContent = `${list.length} of ${rows.length} students`;
    $("tblBody").innerHTML = list.map((r) => `
      <tr class="clickable" data-id="${r.id}">
        <td>${esc(r.roll_no)}</td><td>${esc(r.name)}</td><td>${esc(r.section)}</td>
        <td class="${r.attendance < 75 ? "text-high" : ""}">${r.attendance ?? "-"}%</td>
        <td>${r.marks ?? "-"}%</td>
        <td>${r.progress_score ?? "-"} ${badge(r.grade)}</td>
        <td>${badge(r.risk_level)} <span class="muted">${r.risk_probability != null ? Math.round(r.risk_probability * 100) : ""}</span></td>
        <td>${r.open_alerts || ""}</td></tr>`).join("") ||
      '<tr><td colspan="8" class="empty">No students match.</td></tr>';
  }

  function renderAlerts(alerts) {
    const sev = $("fSev").value;
    const list = alerts.filter((a) => !sev || a.severity === sev).slice(0, 40);
    $("alertCount").textContent = `Showing ${list.length} of ${alerts.length}`;
    $("alertList").innerHTML = list.length
      ? '<ul class="plain">' + list.map((a) => `
        <li>${badge(a.severity)}<span class="grow"><b>${esc(a.roll_no)} ${esc(a.student_name)}</b><br>${esc(a.message)}</span>
        <button class="small" data-resolve="${a.id}">Resolve</button></li>`).join("") + "</ul>"
      : '<div class="empty">No alerts.</div>';
  }

  async function openStudent(id) {
    const d = await api("/students/" + id);
    const s = d.student, r = d.risk, p = d.progress;
    $("modalBody").innerHTML = `
      <h2>${esc(s.name)} <span class="muted">${esc(s.roll_no)} - Section ${esc(s.section)}</span></h2>
      <div class="grid stats">
        <div class="card stat"><div class="label">Progress</div><div class="value">${p.score}</div><div class="sub">${badge(p.grade)} Rank ${p.rank}/${p.total_students}</div></div>
        <div class="card stat"><div class="label">Risk</div><div class="value text-${r.risk_level.toLowerCase()}">${r.risk_level}</div><div class="sub">Index ${Math.round(r.probability * 100)}/100</div></div>
        <div class="card stat"><div class="label">Attendance</div><div class="value">${d.attendance.overall}%</div></div>
        <div class="card stat"><div class="label">Avg marks</div><div class="value">${d.marks.overall}%</div></div>
      </div>
      <h3>Why flagged</h3>
      ${r.factors.length ? '<ul class="plain">' + r.factors.map((f) => `<li>&#9888;&#65039; ${esc(f.message)}</li>`).join("") + "</ul>" : '<div class="empty">No risk factors.</div>'}
      <h3 style="margin-top:16px">Subjects</h3>
      <table><thead><tr><th>Subject</th><th>Attendance</th><th>Avg marks</th></tr></thead><tbody>
      ${d.marks.by_subject.map((m, i) => `<tr><td>${esc(m.subject)}</td>
        <td class="${d.attendance.by_subject[i].pct < 75 ? "text-high" : ""}">${d.attendance.by_subject[i].pct}%</td>
        <td class="${m.average < 40 ? "text-high" : ""}">${m.average}%</td></tr>`).join("")}</tbody></table>
      <h3 style="margin-top:16px">Open alerts</h3>${alertList(d.alerts)}`;
    $("modalBg").classList.add("open");
  }

  // ---- events
  $("fRisk").onchange = $("fSearch").oninput = renderTable;
  $("fSev").onchange = () => api("/alerts?status=open").then(renderAlerts);
  $("tblBody").onclick = (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (tr) openStudent(tr.dataset.id).catch((err) => alert(err.message));
  };
  $("alertList").onclick = async (e) => {
    const id = e.target.dataset.resolve;
    if (!id) return;
    await api(`/alerts/${id}/resolve`, { method: "PATCH" });
    loadAll();
  };
  $("modalClose").onclick = () => $("modalBg").classList.remove("open");
  $("modalBg").onclick = (e) => { if (e.target === $("modalBg")) $("modalBg").classList.remove("open"); };
  $("refreshBtn").onclick = async () => {
    const b = $("refreshBtn");
    b.disabled = true; b.textContent = "Analysing...";
    try {
      const r = await api("/dashboard/refresh", { method: "POST" });
      await loadAll();
      $("notice").textContent = `Analysis complete: ${r.risk_distribution.High} high-risk students, ${r.alerts.open_total} open alerts.`;
    } catch (e) { $("notice").textContent = "Failed: " + e.message; }
    b.disabled = false; b.textContent = "Run AI Analysis";
  };

  try { await loadAll(); } catch (e) { $("notice").textContent = "Failed to load: " + e.message; }
})();

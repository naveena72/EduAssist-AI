// Student and parent dashboard (same page logic, different wording).
(async function () {
  const role = document.body.dataset.role;
  const user = await Auth.guard(role);
  if (!user) return;
  mountTopbar(user, "home");
  initChatbot();

  const root = $("view");
  if (!user.student_id) { root.innerHTML = '<div class="card">No student record is linked to this account.</div>'; return; }

  let d;
  try { d = await api("/students/" + user.student_id); }
  catch (e) { root.innerHTML = `<div class="card error">${esc(e.message)}</div>`; return; }

  const s = d.student, risk = d.risk, p = d.progress;
  const you = role === "parent" ? s.name : "You";

  $("heading").textContent = role === "parent" ? `Your child: ${s.name}` : `Welcome, ${s.name}`;
  $("subheading").textContent = `${s.roll_no} - ${s.department}, Year ${s.year}, Section ${s.section}`;

  const crit = d.alerts.filter((a) => a.severity === "Critical").length;
  $("stats").innerHTML = `
    <div class="card stat"><div class="label">Progress score</div><div class="value">${p.score}</div>
      <div class="sub">${badge(p.grade)} &nbsp;Rank ${p.rank}/${p.total_students}</div></div>
    <div class="card stat"><div class="label">Academic risk</div>
      <div class="value text-${risk.risk_level.toLowerCase()}">${esc(risk.risk_level)}</div>
      <div class="sub">Risk index ${Math.round(risk.probability * 100)}/100</div></div>
    <div class="card stat"><div class="label">Attendance</div>
      <div class="value ${d.attendance.overall < 75 ? "text-high" : ""}">${d.attendance.overall}%</div>
      <div class="sub">${d.attendance.overall < 75 ? "Below 75% requirement" : "Meets 75% requirement"}</div></div>
    <div class="card stat"><div class="label">Average marks</div><div class="value">${d.marks.overall}%</div>
      <div class="sub">${d.marks.failed_subjects ? d.marks.failed_subjects + " subject(s) below 40%" : "No failing subjects"}</div></div>
    <div class="card stat"><div class="label">Open alerts</div>
      <div class="value ${crit ? "text-high" : ""}">${d.alerts.length}</div>
      <div class="sub">${crit} critical</div></div>`;

  $("breakdown").innerHTML = Object.values(p.components).map((c) => `
    <div class="bar-row">
      <div class="top"><span>${esc(c.label)} <span class="muted">(${Math.round(c.weight * 100)}%)</span></span>
        <b>${c.value}</b></div>${bar(c.value)}</div>`).join("") +
    `<div class="muted">Class average score: ${p.class_average}</div>`;

  $("riskWhy").innerHTML = risk.factors.length
    ? '<ul class="plain">' + risk.factors.map((f) => `<li>&#9888;&#65039; <span class="grow">${esc(f.message)}</span></li>`).join("") + "</ul>"
    : `<div class="empty">${risk.risk_level === "Low" ? you + (role === "parent" ? " is" : " are") + " doing well - no risk factors found." : "No major single factor stands out."}</div>`;

  $("alerts").innerHTML = alertList(d.alerts);

  $("marksBody").innerHTML = d.marks.by_subject.map((m) => `
    <tr><td>${esc(m.subject)}</td><td>${m.internal1 ?? "-"}</td><td>${m.internal2 ?? "-"}</td>
    <td>${m.model ?? "-"}</td><td>${m.assignment ?? "-"}</td>
    <td><b class="${m.average < 40 ? "text-high" : ""}">${m.average ?? "-"}</b></td></tr>`).join("");

  $("busCard").innerHTML = d.bus
    ? `<h3>Campus bus</h3><p>Bus <b>${esc(d.bus.bus_no)}</b> - ${esc(d.bus.route)}<br>
       Driver: ${esc(d.bus.driver_name)} (${esc(d.bus.driver_phone)})</p>
       <a href="bus.html"><button>Track live</button></a>`
    : '<h3>Campus bus</h3><div class="empty">No campus bus assigned.</div>';

  try {
    await loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js");
    subjectBarChart("attChart", d.attendance.by_subject.map((x) => x.code), [{
      label: "Attendance %", data: d.attendance.by_subject.map((x) => x.pct),
      backgroundColor: d.attendance.by_subject.map((x) => (x.pct < 75 ? "#dc2626" : "#3b5bdb")),
    }]);
  } catch {
    $("attChart").parentElement.innerHTML = d.attendance.by_subject
      .map((x) => `<div class="bar-row"><div class="top"><span>${esc(x.subject)}</span><b>${x.pct}%</b></div>${bar(x.pct)}</div>`).join("");
  }
})();

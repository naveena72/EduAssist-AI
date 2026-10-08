// Live bus tracking page (Leaflet map + polling).
(async function () {
  const user = await Auth.guard(null);
  if (!user) return;
  mountTopbar(user, "bus");
  initChatbot();

  let map = null, marker = null, busId = null, timer = null, drawnFor = null;
  const hasMap = typeof L !== "undefined";
  if (hasMap) {
    map = L.map("map").setView([13.0, 80.2], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
  } else {
    $("map").innerHTML = '<div class="empty" style="padding:24px">Map library could not be loaded (no internet). Stop list and ETAs still update.</div>';
  }

  const buses = await api("/bus");
  $("busSelect").innerHTML = buses.map((b) => `<option value="${b.bus_id}">${esc(b.bus_no)} - ${esc(b.route)}</option>`).join("");
  try {
    const mine = await api("/bus/my");   // student / parent: default to their own bus
    busId = mine.bus_id;
    $("mapNote").textContent = "Showing your bus.";
  } catch { busId = buses[0].bus_id; }
  $("busSelect").value = busId;
  $("busSelect").onchange = () => { busId = Number($("busSelect").value); drawnFor = null; poll(); };

  function drawRoute(st) {
    if (!hasMap || drawnFor === st.bus_id) return;
    drawnFor = st.bus_id;
    map.eachLayer((l) => { if (!(l instanceof L.TileLayer)) map.removeLayer(l); });
    marker = null;
    const pts = st.stops.map((s) => [s.lat, s.lng]);
    L.polyline(pts, { color: "#3b5bdb", weight: 4, opacity: 0.6 }).addTo(map);
    st.stops.forEach((s, i) => {
      L.circleMarker([s.lat, s.lng], {
        radius: i === st.stops.length - 1 ? 9 : 6, color: "#1e3a8a", fillColor: i === st.stops.length - 1 ? "#dc2626" : "#fff", fillOpacity: 1,
      }).addTo(map).bindTooltip(s.name, { permanent: false });
    });
    map.fitBounds(pts, { padding: [30, 30] });
  }

  function render(st) {
    drawRoute(st);
    if (hasMap) {
      if (!marker) {
        marker = L.marker([st.lat, st.lng], {
          icon: L.divIcon({ html: '<div class="bus-marker">&#128652;</div>', className: "", iconSize: [28, 28], iconAnchor: [14, 14] }),
          zIndexOffset: 1000,
        }).addTo(map);
      }
      marker.setLatLng([st.lat, st.lng]);
    }
    $("busStats").innerHTML = `
      <div class="card stat"><div class="label">Bus</div><div class="value" style="font-size:20px">${esc(st.bus_no)}</div><div class="sub">${esc(st.route)}</div></div>
      <div class="card stat"><div class="label">Status</div><div class="value" style="font-size:20px">${esc(st.status)}</div><div class="sub">Speed ${st.speed_kmh} km/h</div></div>
      <div class="card stat"><div class="label">Next stop</div><div class="value" style="font-size:20px">${esc(st.next_stop)}</div></div>
      <div class="card stat"><div class="label">ETA to campus</div>
        <div class="value" style="font-size:20px">${st.eta_to_campus_min == null ? "Arrived" : st.eta_to_campus_min + " min"}</div>
        <div class="sub">Route ${st.route_progress_pct}% complete</div></div>`;
    $("stopsBody").innerHTML = st.stops.map((s) => `
      <tr><td>${esc(s.name)}</td><td>${s.passed ? '<span class="muted">Passed</span>' : "<b>" + s.eta_min + " min</b>"}</td></tr>`).join("");
    $("driverInfo").textContent = `Driver: ${st.driver_name} - ${st.driver_phone}`;
  }

  async function poll() {
    try { render(await api(`/bus/${busId}/status`)); } catch (e) { $("mapNote").textContent = e.message; }
  }
  await poll();
  timer = setInterval(poll, 3000);
})();

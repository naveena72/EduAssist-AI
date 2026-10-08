// Shared API helper. Frontend is served by FastAPI, so the base URL is same-origin.
const API_BASE = "";

const Auth = {
  save(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
  },
  token() { return localStorage.getItem("token"); },
  user() {
    try { return JSON.parse(localStorage.getItem("user")); } catch { return null; }
  },
  clear() { localStorage.removeItem("token"); localStorage.removeItem("user"); },
  logout() { Auth.clear(); window.location.href = "/app/index.html"; },
  homeFor(role) { return { student: "student.html", parent: "parent.html", faculty: "faculty.html" }[role]; },
  // Call at the top of each protected page.
  async guard(allowedRole) {
    if (!Auth.token()) { Auth.logout(); return null; }
    try {
      const user = await api("/auth/me");
      if (allowedRole && user.role !== allowedRole) {
        window.location.href = "/app/" + Auth.homeFor(user.role);
        return null;
      }
      return user;
    } catch { Auth.logout(); return null; }
  },
};

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (Auth.token()) headers["Authorization"] = "Bearer " + Auth.token();
  const res = await fetch(API_BASE + path, { ...options, headers });
  if (res.status === 401 && !path.startsWith("/auth/login")) { Auth.logout(); throw new Error("Session expired"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

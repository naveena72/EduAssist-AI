// Login page logic.
const form = document.getElementById("loginForm");
const errorBox = document.getElementById("error");
const btn = document.getElementById("submitBtn");

// Already signed in? Go straight to the right page.
if (Auth.token() && Auth.user()) {
  window.location.href = Auth.homeFor(Auth.user().role);
}

document.querySelectorAll(".demo .link").forEach((b) =>
  b.addEventListener("click", () => {
    document.getElementById("email").value = b.dataset.e;
    document.getElementById("password").value = b.dataset.p;
  })
);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.textContent = "";
  btn.disabled = true;
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
      }),
    });
    Auth.save(data.access_token, data.user);
    window.location.href = Auth.homeFor(data.user.role);
  } catch (err) {
    errorBox.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

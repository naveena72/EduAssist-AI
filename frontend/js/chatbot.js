// Floating chatbot widget. Include on any page after api.js / ui.js, then call initChatbot().
function initChatbot() {
  const root = document.createElement("div");
  root.innerHTML = `
    <button id="chatFab" title="Ask EduAssist">&#128172;</button>
    <div id="chatPanel">
      <header>EduAssist AI Assistant</header>
      <div id="chatMsgs"></div>
      <div id="chatChips"></div>
      <form id="chatForm"><input id="chatInput" placeholder="Ask a question..." autocomplete="off" maxlength="300">
        <button type="submit">Send</button></form>
    </div>`;
  document.body.appendChild(root);

  const panel = $("chatPanel"), msgs = $("chatMsgs"), chips = $("chatChips"), input = $("chatInput");

  function add(text, who) {
    const d = document.createElement("div");
    d.className = "msg " + who;
    d.textContent = text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function setChips(list) {
    chips.innerHTML = "";
    list.forEach((q) => {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = q;
      b.onclick = () => send(q);
      chips.appendChild(b);
    });
  }

  async function send(text) {
    text = text.trim();
    if (!text) return;
    add(text, "user");
    input.value = "";
    try {
      const r = await api("/chatbot/ask", { method: "POST", body: JSON.stringify({ message: text }) });
      add(r.answer, "bot");
      setChips(r.suggestions);
    } catch (e) {
      add("Sorry, something went wrong: " + e.message, "bot");
    }
  }

  $("chatFab").onclick = () => {
    panel.classList.toggle("open");
    if (panel.classList.contains("open") && !msgs.children.length) send("hi");
    if (panel.classList.contains("open")) input.focus();
  };
  $("chatForm").onsubmit = (e) => { e.preventDefault(); send(input.value); };
}

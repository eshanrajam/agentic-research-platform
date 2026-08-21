const log = document.getElementById("chat-log");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");

function appendMessage(role, text) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function renderTrace(container, steps) {
  if (!steps || steps.length === 0) return;
  const details = document.createElement("details");
  details.className = "trace";
  const summary = document.createElement("summary");
  summary.textContent = `View agent trace (${steps.length} step${steps.length === 1 ? "" : "s"})`;
  details.appendChild(summary);

  steps.forEach((step, i) => {
    const div = document.createElement("div");
    div.className = "trace-step";
    div.innerHTML = `<b>${i + 1}. ${step.agent}</b><br/>→ ${escapeHtml(step.instruction)}<br/><i>${escapeHtml(step.output)}</i>`;
    details.appendChild(div);
  });

  container.appendChild(details);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message);
  input.value = "";
  input.disabled = true;

  const pending = appendMessage("assistant pending", "Agent team is working…");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${response.status})`);
    }

    const data = await response.json();
    pending.classList.remove("pending");
    pending.textContent = data.answer;
    renderTrace(pending, data.steps);
  } catch (err) {
    pending.classList.remove("pending");
    pending.textContent = `Error: ${err.message}`;
  } finally {
    input.disabled = false;
    input.focus();
  }
});

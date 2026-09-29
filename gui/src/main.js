const PORT = 8765;
const base = `http://localhost:${PORT}`;

const LABELS = {
  idle: "aguardando",
  listening: "ouvindo",
  transcribing: "transcrevendo",
  thinking: "pensando",
  speaking: "falando",
  acting: "agindo",
  error: "erro",
  offline: "offline",
};

const orb = document.getElementById("orb");
const label = document.getElementById("label");
const menu = document.getElementById("menu");
const brain = document.getElementById("brain");

function apply(state) {
  orb.dataset.state = state;
  const text = LABELS[state] || state;
  label.textContent = text;
  brain.textContent = state === "offline" ? "Iniciar cérebro" : "Reiniciar cérebro";
}

apply("offline");

function connect() {
  const es = new EventSource(`${base}/events`);
  es.onmessage = (ev) => {
    try {
      apply(JSON.parse(ev.data).state);
    } catch (e) {
      /* ignora payload inválido */
    }
  };
  es.onerror = () => apply("offline");
}
connect();

orb.addEventListener("mouseenter", () => label.classList.add("show"));
orb.addEventListener("mouseleave", () => label.classList.remove("show"));
orb.addEventListener("click", () => menu.classList.toggle("hidden"));

async function command(cmd) {
  try {
    await fetch(`${base}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmd }),
    });
  } catch (e) {
    /* servidor fora do ar */
  }
  menu.classList.add("hidden");
}

menu.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  const cmd = btn.dataset.cmd;
  if (cmd === "quit") {
    await command("quit");
    window.__TAURI__.window.getCurrentWindow().close();
  } else if (cmd === "brain") {
    await window.__TAURI__.core.invoke("start_brain");
  } else {
    await command(cmd);
  }
});

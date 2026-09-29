let base = "http://localhost:8765";

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
  const title = "jarvis:" + state;
  document.title = title;
  try {
    // O Tauri v2 nao sincroniza document.title com o titulo nativo da janela
    // por padrao; setar explicitamente deixa o estado observavel por fora.
    window.__TAURI__.window.getCurrentWindow().setTitle(title);
  } catch (e) {
    /* fora do Tauri (browser puro): ignora */
  }
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

async function resolveBase() {
  let port = 8765;
  try {
    port = await window.__TAURI__.core.invoke("state_port");
  } catch (e) {
    /* mantém o default */
  }
  base = `http://localhost:${port}`;
}

resolveBase().then(connect);

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

async function restartBrain() {
  try {
    let reachable = false;
    try {
      const r = await fetch(`${base}/state`);
      reachable = r.ok;
    } catch (e) {
      reachable = false;
    }
    if (reachable) {
      await command("quit");
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    await window.__TAURI__.core.invoke("start_brain");
  } catch (e) {
    label.textContent = "erro ao iniciar";
    label.classList.add("show");
    setTimeout(() => {
      label.classList.remove("show");
      apply(orb.dataset.state || "offline");
    }, 1500);
  } finally {
    menu.classList.add("hidden");
  }
}

menu.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  const cmd = btn.dataset.cmd;
  if (cmd === "quit") {
    await command("quit");
    window.__TAURI__.window.getCurrentWindow().close();
  } else if (cmd === "brain") {
    await restartBrain();
  } else {
    await command(cmd);
  }
});

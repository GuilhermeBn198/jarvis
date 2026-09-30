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

// "Sempre ligado": ao abrir, se o cerebro estiver offline, sobe o loop no WSL.
// So inicia se estiver offline -- nunca mata um loop existente (e a trava de
// instancia unica no loop impede duplicatas de qualquer forma).
const AUTOSTART_BRAIN = true;

async function ensureBrain() {
  try {
    const r = await fetch(`${base}/state`);
    if (r.ok) return;
  } catch (e) {
    /* offline: tenta subir abaixo */
  }
  try {
    await window.__TAURI__.core.invoke("start_brain");
  } catch (e) {
    /* fora do Tauri ou falha ao spawnar: ignora */
  }
}

if (AUTOSTART_BRAIN) {
  setTimeout(ensureBrain, 1200);
}

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
    try {
      // Rede de seguranca: mata o processo do cerebro no WSL mesmo se o
      // comando `quit` nao chegar (hub fora do ar, gravacao em curso, etc.).
      await window.__TAURI__.core.invoke("stop_brain");
    } catch (e) {
      /* fora do Tauri: ignora */
    }
    window.__TAURI__.window.getCurrentWindow().close();
  } else if (cmd === "brain") {
    await restartBrain();
  } else if (cmd === "settings") {
    openSettings();
  } else {
    await command(cmd);
  }
});

// ---------------------------------------------------------------------------
// Painel de configuracoes (sensibilidade do mic, tunables de captura, TTS)
// ---------------------------------------------------------------------------

const settingsPanel = document.getElementById("settings");
const measureOut = document.getElementById("measure-out");
const ORB_SIZE = [120, 120];
const PANEL_SIZE = [280, 340];

function numOrNull(id) {
  const v = document.getElementById(id).value.trim();
  if (v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

// Redimensiona mantendo o canto inferior-direito fixo (o orbe nao "pula").
async function anchorBottomRight(w, h) {
  try {
    const win = window.__TAURI__.window.getCurrentWindow();
    const dpi = window.__TAURI__.dpi;
    const scale = await win.scaleFactor();
    const pos = await win.outerPosition();
    const size = await win.innerSize();
    const tw = Math.round(w * scale);
    const th = Math.round(h * scale);
    await win.setSize(new dpi.PhysicalSize(tw, th));
    await win.setPosition(
      new dpi.PhysicalPosition(pos.x + size.width - tw, pos.y + size.height - th),
    );
  } catch (e) {
    /* fora do Tauri ou sem permissao: segue sem redimensionar */
  }
}

async function loadDevices() {
  const sel = document.getElementById("s-mic");
  let data = { devices: [], current: null };
  try {
    data = await (await fetch(`${base}/devices`)).json();
  } catch (e) {
    /* servidor fora do ar */
  }
  const opts = (data.devices || []).slice();
  const current = data.current || "";
  if (current && !opts.includes(current)) opts.unshift(current);
  sel.innerHTML = "";
  if (!opts.length) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = "(nenhum microfone encontrado)";
    sel.appendChild(o);
    return;
  }
  for (const name of opts) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = name;
    if (name === current) o.selected = true;
    sel.appendChild(o);
  }
}

async function loadSettings() {
  let s = {};
  try {
    s = await (await fetch(`${base}/settings`)).json();
  } catch (e) {
    /* servidor fora do ar: mostra defaults vazios */
  }
  document.getElementById("s-noise").value = s.noise_db ?? "";
  document.getElementById("s-silence").value = s.silence_s ?? "";
  document.getElementById("s-wait").value = s.wait_s ?? "";
  document.getElementById("s-max").value = s.max_s ?? "";
  document.getElementById("s-minspeech").value = s.min_speech_s ?? "";
  document.getElementById("s-stream").checked = s.stream_tts !== false;
}

async function openSettings() {
  menu.classList.add("hidden");
  settingsPanel.classList.remove("hidden");
  await anchorBottomRight(...PANEL_SIZE);
  await loadDevices();
  await loadSettings();
}

async function closeSettings() {
  settingsPanel.classList.add("hidden");
  await anchorBottomRight(...ORB_SIZE);
}

async function measureMic() {
  measureOut.textContent = "medindo (~5s, fale nada)...";
  try {
    await fetch(`${base}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmd: "measure" }),
    });
  } catch (e) {
    measureOut.textContent = "cérebro indisponível";
    return;
  }
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 300));
    try {
      const j = await (await fetch(`${base}/mic-level`)).json();
      if (j.pending) continue;
      if (j.ok === false) {
        measureOut.textContent = `erro: ${j.error}`;
        return;
      }
      measureOut.textContent =
        `média ${j.mean_db} dB · pico ${j.max_db} dB → sugerido ${j.suggested_noise_db}`;
      if (j.suggested_noise_db != null) {
        document.getElementById("s-noise").value = j.suggested_noise_db;
      }
      return;
    } catch (e) {
      /* tenta de novo */
    }
  }
  measureOut.textContent = "sem resposta do cérebro";
}

async function saveSettings(restart) {
  const body = {
    noise_db: numOrNull("s-noise"),
    silence_s: numOrNull("s-silence"),
    wait_s: numOrNull("s-wait"),
    max_s: numOrNull("s-max"),
    min_speech_s: numOrNull("s-minspeech"),
    stream_tts: document.getElementById("s-stream").checked,
  };
  const mic = document.getElementById("s-mic").value;
  if (mic) body.mic_device = mic;
  for (const k of Object.keys(body)) {
    if (body[k] === null) delete body[k];
  }
  try {
    await fetch(`${base}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    /* ignora */
  }
  if (restart) await restartBrain();
}

document.getElementById("settings-close").addEventListener("click", closeSettings);
document.getElementById("measure").addEventListener("click", measureMic);
document.getElementById("s-mic-reload").addEventListener("click", loadDevices);
document
  .getElementById("settings-save")
  .addEventListener("click", () => saveSettings(false));
document
  .getElementById("settings-restart")
  .addEventListener("click", () => saveSettings(true));

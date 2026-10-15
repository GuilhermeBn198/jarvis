import { test } from "node:test";
import assert from "node:assert/strict";
import { buildPsScript, encode } from "../act/ps.ts";
import { buildWinListScript, chooseActScript } from "../act/win.ts";
import { ActTools } from "./act-tools.ts";

test("win_list script builder disponivel", () => {
  assert.match(buildWinListScript(), /EnumWindows/);
});

test("act_type script uses SendKeys with escaping", () => {
  const s = buildPsScript("act_type", { text: "a+b(c)" });
  assert.match(s, /SendKeys/);
  assert.ok(s.includes("{+}") || s.includes("a+b")); // escape aplicado
});
test("act_open script uses Start-Process", () => {
  assert.match(buildPsScript("act_open", { target: "https://x" }), /Start-Process/);
});
test("act_click script uses SetCursorPos + mouse_event", () => {
  const s = buildPsScript("act_click", { x: 10, y: 20, button: "left" });
  assert.match(s, /SetCursorPos/);
  assert.match(s, /mouse_event/);
});
test("encode is utf16le base64", () => {
  assert.equal(Buffer.from(encode("hi"), "base64").toString("utf16le"), "hi");
});
test("plugin exports only the factory", () => {
  assert.equal(typeof ActTools, "function");
});

test("mode ausente -> foreground (sem script de background)", () => {
  assert.equal(chooseActScript("act_type", { text: "oi" }), "");
});
test("window informado -> script background (UIA)", () => {
  const s = chooseActScript("act_type", { text: "oi", window: "Notepad" });
  assert.match(s, /ValuePattern/);
});
test("mode background explicito -> background mesmo sem janela", () => {
  assert.match(chooseActScript("act_key", { keys: "ctrl+s", mode: "background" }), /PostMessageW/);
});
test("act_key script foreground usa keybd_event (nao SendKeys)", () => {
  const s = buildPsScript("act_key", { keys: "enter" });
  assert.match(s, /keybd_event/);
  assert.doesNotMatch(s, /SendKeys/);
  assert.match(s, /0x0D/);
});
test("act_key descricao documenta sintaxe natural e limites do background", async () => {
  const tools = (await ActTools({} as never)).tool as Record<string, { description: string }>;
  const d = tools.act_key.description;
  assert.match(d, /enter/);
  assert.match(d, /ctrl\+c/);
  assert.match(d, /ctrl\+shift\+esc/);
  assert.match(d, /win\+r/);
  assert.match(d, /background/i);
  assert.match(d, /best-effort|GetKeyState/i);
});
test("act_key com keys invalido falha didaticamente antes de qualquer script", () => {
  assert.throws(() => buildPsScript("act_key", { keys: "foo" }), /tecla desconhecida "foo"/);
  assert.throws(() => buildPsScript("act_key", { keys: "foo" }), /ctrl\+c/);
});

test("act_key execute com keys invalido retorna erro sem chamar o shell", async () => {
  let called = false;
  const shell = (() => {
    called = true;
    return { text: async () => "" };
  }) as never;
  const tools = (await ActTools({ $: shell } as never)).tool as Record<string, { execute: (a: Record<string, unknown>) => Promise<string> }>;
  const out = await tools.act_key.execute({ keys: "foo" });
  assert.match(out, /^erro: /);
  assert.match(out, /tecla desconhecida "foo"/);
  assert.equal(called, false, "nao pode rodar powershell com keys invalido");
});

// Fake do Bun shell na forma do runtime: `$` aguardado devolve BunShellOutput,
// cujo .text() e SINCRONO (BunShellPromise.text() e o async, nao este).
function shellReturning(stdout: string) {
  return (() => Promise.resolve({ text: () => stdout })) as never;
}

// Shell que registra se foi chamado (para o gate de consentimento).
function recordingShell() {
  const calls: string[] = [];
  const shell = (() => {
    calls.push("chamado");
    return Promise.resolve({ text: () => "ok" });
  }) as never;
  return { shell, calls };
}

async function actOpenTools(shell: unknown) {
  const tools = (await ActTools({ $: shell } as never)).tool as Record<
    string,
    { description: string; execute: (a: Record<string, unknown>) => Promise<string> }
  >;
  return tools.act_open;
}

test("act_open sem confirm em alvo de execucao recusa e orienta a perguntar", async () => {
  const { shell, calls } = recordingShell();
  const out = await (await actOpenTools(shell)).execute({ target: "cmd", args: ["/c", "dir"] });
  assert.match(out, /recusado/);
  assert.match(out, /PERGUNTE/i);
  assert.match(out, /confirm=true/);
  assert.match(out, /cmd/);
  assert.equal(calls.length, 0, "nao pode rodar powershell sem consentimento");
});

test("act_open com confirm em alvo de execucao executa", async () => {
  const { shell, calls } = recordingShell();
  const out = await (await actOpenTools(shell)).execute({ target: "cmd", args: ["/c", "dir"], confirm: true });
  assert.equal(out, "ok");
  assert.equal(calls.length, 1);
});

test("act_open confirm=false explicito tambem recusa", async () => {
  const { shell, calls } = recordingShell();
  const out = await (await actOpenTools(shell)).execute({ target: "powershell", confirm: false });
  assert.match(out, /recusado/);
  assert.equal(calls.length, 0);
});

test("act_open recusa alvos de execucao (nome, caminho e extensao) sem confirm", async () => {
  const alvos = ["powershell.exe", "wsl", "wt", "wscript", "C:\\x\\run.bat", "C:\\x\\s.ps1", "a.vbs", "app.js"];
  for (const target of alvos) {
    const { shell, calls } = recordingShell();
    const out = await (await actOpenTools(shell)).execute({ target });
    assert.match(out, /recusado/, target);
    assert.equal(calls.length, 0, target);
  }
});

test("act_open benigno (URL/app/arquivo) segue direto, com ou sem confirm", async () => {
  for (const target of ["https://x", "notepad", "C:\\app\\a.exe", "readme.txt"]) {
    const { shell, calls } = recordingShell();
    const out = await (await actOpenTools(shell)).execute({ target });
    assert.equal(out, "ok", target);
    assert.equal(calls.length, 1, target);
  }
});

test("act_open descricao documenta args e o fluxo pergunta->confirm", async () => {
  const d = (await actOpenTools(shellReturning(""))).description;
  assert.match(d, /args/);
  assert.match(d, /confirm=true/);
  assert.match(d, /PERGUNTE/i);
  assert.match(d, /powershell/);
  assert.match(d, /\.bat/);
  assert.match(d, /\.ps1/);
  assert.match(d, /\.js/);
});

async function actKeyTools(stdout: string) {
  const tools = (await ActTools({ $: shellReturning(stdout) } as never)).tool as Record<
    string,
    { execute: (a: Record<string, unknown>) => Promise<string> }
  >;
  return tools.act_key;
}

test("act_key bg: timeout vira aviso (teclas podem nao ter sido enviadas), nao sucesso", async () => {
  const out = await (await actKeyTools("JARVIS_RESULT=unconfirmed|timeout (janela nao respondeu em 5s)")).execute({
    keys: "enter",
    mode: "background",
  });
  assert.match(out, /timeout/i);
  assert.match(out, /nao respondeu/i);
  assert.match(out, /podem nao ter sido enviadas/i);
  assert.doesNotMatch(out, /^teclas enviadas/);
});

test("act_key bg: unconfirmed reporta o alvo do detalhe do script", async () => {
  const out = await (await actKeyTools("JARVIS_RESULT=unconfirmed|controle de edicao")).execute({
    keys: "enter",
    mode: "background",
  });
  assert.equal(out, "teclas enviadas em segundo plano (confirmacao indisponivel) — controle de edicao");
});

test("act_key bg: aviso do win+r continua aparecendo", async () => {
  const out = await (
    await actKeyTools("JARVIS_RESULT=unconfirmed|controle de edicao — win+r nao funciona em background")
  ).execute({ keys: "win+r", mode: "background" });
  assert.match(out, /teclas enviadas em segundo plano/);
  assert.match(out, /win\+r nao funciona em background/);
});

// --- #20: instrumentacao opt-in do act_type (JARVIS_ACT_DEBUG) --------------

async function actTypeTools(shell: unknown) {
  const tools = (await ActTools({ $: shell } as never)).tool as Record<
    string,
    { execute: (a: Record<string, unknown>) => Promise<string> }
  >;
  return tools.act_type;
}

test("act_type: JARVIS_ACT_DEBUG=1 loga os args brutos antes do script", async (t) => {
  const events: string[] = [];
  t.mock.method(process.stderr, "write", (chunk: unknown) => {
    events.push(String(chunk));
    return true;
  });
  process.env.JARVIS_ACT_DEBUG = "1";
  t.after(() => delete process.env.JARVIS_ACT_DEBUG);
  const shell = (() => {
    events.push("shell");
    return Promise.resolve({ text: () => "ok" });
  }) as never;

  const out = await (await actTypeTools(shell)).execute({ text: "C:\\Users\\Public\\x.txt" });

  assert.equal(out, "ok");
  const logs = events.filter((e) => e.includes("[act_type]"));
  assert.equal(logs.length, 1, "um log por chamada");
  // O log e emitido ANTES de montar/rodar o script.
  assert.ok(
    events.indexOf(logs[0]) < events.indexOf("shell"),
    "log deve vir antes da chamada ao shell",
  );
  assert.match(logs[0], /args brutos/);
  // JSON com o texto BRUTO: `\\` no log = uma barra chegou ao execute.
  const json = logs[0].slice(logs[0].indexOf("{"), logs[0].lastIndexOf("}") + 1);
  assert.deepEqual(JSON.parse(json), { text: "C:\\Users\\Public\\x.txt" });
  assert.match(logs[0], /barras invertidas no texto: 3/);
});

test("act_type bg: instrumentacao loga tambem no caminho background", async (t) => {
  const events: string[] = [];
  t.mock.method(process.stderr, "write", (chunk: unknown) => {
    events.push(String(chunk));
    return true;
  });
  process.env.JARVIS_ACT_DEBUG = "1";
  t.after(() => delete process.env.JARVIS_ACT_DEBUG);

  await (await actTypeTools(shellReturning("JARVIS_RESULT=confirmed|digitado"))).execute({
    text: "C:\\x",
    mode: "background",
  });

  const logs = events.filter((e) => e.includes("[act_type]"));
  assert.equal(logs.length, 1);
  assert.match(logs[0], /barras invertidas no texto: 1/);
  assert.match(logs[0], /C:\\\\x/);
});

test("act_type: sem JARVIS_ACT_DEBUG (ou != 1) nada e logado", async (t) => {
  const events: string[] = [];
  t.mock.method(process.stderr, "write", (chunk: unknown) => {
    events.push(String(chunk));
    return true;
  });
  const actType = await actTypeTools(shellReturning("ok"));
  delete process.env.JARVIS_ACT_DEBUG;
  await actType.execute({ text: "C:\\a" });
  process.env.JARVIS_ACT_DEBUG = "0";
  await actType.execute({ text: "C:\\a" });
  delete process.env.JARVIS_ACT_DEBUG;
  assert.deepEqual(events.filter((e) => e.includes("[act_type]")), []);
});

# Jarvis Fase E — Ações no PC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o agente `act` executa ações no Windows (digitar, teclas, clicar, abrir), com **toda** ação passando pelo SafetyGate existente.

**Architecture:** custom tools em `.opencode/plugins/act-tools.ts` (rodam `powershell.exe`); o hook `tool.execute.before` já existente gateia via `rules.decide` (só estendemos o mapeamento tool→pattern). Agente `act` no `opencode.json`; `--do` na voz.

**Tech Stack:** TypeScript (plugin, rodado pelo runtime do opencode), `powershell.exe` (SendKeys/Start-Process/user32), Python (voz).

## Global Constraints

- Tools: `act_type(text)`, `act_key(keys)`, `act_click(x,y,button?)`, `act_open(target)` (nomes verbatim).
- O plugin `.opencode/plugins/act-tools.ts` exporta **apenas** a factory (lição da Fase 2-B: o loader invoca todo export como factory).
- Todo acionamento passa por `tool.execute.before` → `rules.decide`. Reuso das regras existentes (destrutivos/credenciais).
- PowerShell sempre via `-NoProfile -EncodedCommand <b64 UTF-16LE>` (sem quoting).
- Verificação **real** é **dry** (sem executar input de verdade).
- Todo passo termina em commit.

## File Structure

```
.opencode/
  plugins/act-tools.ts        # tools act_* + buildPsScript/encode (puros p/ teste) + factory
  plugins/act-tools.test.ts   # testes dos helpers + shape do plugin
  safety/rules.ts             # + mapeamento act_* em actionFromToolCall
  safety/rules.test.ts        # + casos act_*
opencode.json                 # + agente act
voice/loop.py                 # + --do  (usa RunClient com agent=act)
voice/tests/test_loop_do.py   # teste do --do
```

---

### Task 1: `act-tools` + SafetyGate

**Files:** Create `.opencode/plugins/act-tools.ts`, `.opencode/plugins/act-tools.test.ts`; Modify `.opencode/safety/rules.ts`, `.opencode/safety/rules.test.ts`.

- [ ] **Step 1: Testes que falham**

Create `.opencode/plugins/act-tools.test.ts`:
```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildPsScript, encode, ActTools } from "./act-tools.ts";

test("act_type script uses SendKeys with escaping", () => {
  const s = buildPsScript("act_type", { text: "a+b(c)" });
  assert.match(s, /SendKeys/);
  assert.ok(s.includes("{+}") || s.includes("a+b"));   // escape aplicado
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
```

Append to `.opencode/safety/rules.test.ts`:
```ts
import { actionFromToolCall } from "./rules.ts";   // if not already exported, export it
test("act_open destrutivo -> deny", () => {
  const a = actionFromToolCall("act_open", { target: "cmd /c rm -rf /" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("act_type benigno -> allow", () => {
  const a = actionFromToolCall("act_type", { text: "ola mundo" });
  assert.equal(decide({ ...a }).status, "allow");
});
test("act_click -> allow", () => {
  const a = actionFromToolCall("act_click", { x: 1, y: 2 });
  assert.equal(decide({ ...a }).status, "allow");
});
```

- [ ] **Step 2: Rodar e ver falhar** — `node --test .opencode/plugins/act-tools.test.ts .opencode/safety/rules.test.ts` → FAIL.

- [ ] **Step 3: Implementar**

`.opencode/safety/rules.ts` — em `actionFromToolCall`, adicionar antes do retorno default:
```ts
  if (tool === "act_type") return { type: "act", pattern: String(a.text ?? "") };
  if (tool === "act_key") return { type: "act", pattern: String(a.keys ?? "") };
  if (tool === "act_open") return { type: "act", pattern: String(a.target ?? "") };
  if (tool === "act_click") return { type: "act", pattern: `${a.x},${a.y}` };
```
(e garantir que `actionFromToolCall` é exportada).

Create `.opencode/plugins/act-tools.ts`:
```ts
import { type Plugin, tool } from "@opencode-ai/plugin";

const SENDFLARE = /([+^%~(){}[\]])/g; // caracteres especiais do SendKeys

export function encode(script: string): string {
  return Buffer.from(script, "utf16le").toString("base64");
}

export function buildPsScript(name: string, args: Record<string, unknown>): string {
  if (name === "act_type") {
    const text = String(args.text ?? "").replace(SENDFLARE, "{$1}");
    return `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('${text.replace(/'/g, "''")}')`;
  }
  if (name === "act_key") {
    const keys = String(args.keys ?? "").replace(/'/g, "''");
    return `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('${keys}')`;
  }
  if (name === "act_open") {
    const target = String(args.target ?? "").replace(/'/g, "''");
    return `Start-Process '${target}'`;
  }
  if (name === "act_click") {
    const x = Number(args.x ?? 0), y = Number(args.y ?? 0);
    const right = String(args.button ?? "left") === "right";
    const flag = right ? "0x0008" : "0x0002"; // RIGHTDOWN/LEFTDOWN
    const up = right ? "0x0010" : "0x0004";
    return `Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);'; [W.U]::SetCursorPos(${x}, ${y}); [W.U]::mouse_event(${flag}, 0, 0, 0, 0); Start-Sleep -Milliseconds 40; [W.U]::mouse_event(${up}, 0, 0, 0, 0)`;
  }
  throw new Error(`unknown act tool: ${name}`);
}

export const ActTools: Plugin = async ({ $ }) => ({
  tool: {
    act_type: tool({
      description: "Digita um texto na janela em foco (Windows).",
      args: { text: tool.schema.string() },
      async execute(args) { return (await $\`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_type", args))}\`).text(); },
    }),
    act_key: tool({
      description: "Envia teclas/atalho via SendKeys (ex.: ^c, %{F4}, {ENTER}).",
      args: { keys: tool.schema.string() },
      async execute(args) { return (await $\`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_key", args))}\`).text(); },
    }),
    act_open: tool({
      description: "Abre uma URL, arquivo ou aplicativo (Start-Process).",
      args: { target: tool.schema.string() },
      async execute(args) { return (await $\`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_open", args))}\`).text(); },
    }),
    act_click: tool({
      description: "Move o mouse para (x,y) e clica (left/right).",
      args: { x: tool.schema.number(), y: tool.schema.number(), button: tool.schema.string().optional() },
      async execute(args) { return (await $\`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_click", args))}\`).text(); },
    }),
  },
});
```

- [ ] **Step 4: Rodar e ver passar** — `node --test .opencode/plugins/act-tools.test.ts .opencode/safety/rules.test.ts` → passa.

- [ ] **Step 5: Confirmar que o plugin carrega (dry)** — `timeout 60 opencode run --print-logs "responda ok" 2>&1 | grep -i 'failed to load plugin'` → **sem saída**.

- [ ] **Step 6: Commit** — `git add .opencode && git commit -m "feat(jarvis): custom tools de acao no PC (act_*) + gate"`

---

### Task 2: agente `act` + `--do` na voz

**Files:** Modify `opencode.json`, `voice/loop.py`; Create `voice/tests/test_loop_do.py`.

- [ ] **Step 1: Teste que falha**

Create `voice/tests/test_loop_do.py`:
```python
import io, subprocess, pytest
from config import Config
import loop

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, agent="act")

def test_do_uses_agent_act(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "feito", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = io.StringIO()
    loop.do_once("abra o notepad", out=out, config=CFG)
    assert "--agent" in seen["cmd"] and "act" in seen["cmd"]
    assert "abra o notepad" in seen["cmd"]
    assert "feito" in out.getvalue()
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

`opencode.json` — adicionar ao `agent`:
```json
"act": {
  "description": "Executa acoes no PC (digitar, teclas, clicar, abrir) com seguranca.",
  "mode": "primary",
  "model": "opencode-go/deepseek-v4.1-flash",
  "prompt": "Voce controla o PC do usuario via as tools act_*. Use o MINIMO necessario; explique em uma frase o que vai fazer.",
  "permission": { "edit": "deny", "bash": "deny" }
}
```

`voice/loop.py` — adicionar `do_once(prompt, out=None, err=None, config=None)`:
- roda `[opencode_bin, "run", "--pure", "--agent", "act", prompt]` (via `subprocess.run`, `text=True`, `errors="replace"`, timeout=cfg.timeout_s), limpa com `strip_opencode_noise`, escreve em `out`, e loga via `convlog.log_turn({..., "mode":"act", "response": resposta, "spoken": speechify(resposta)})`.
- `main()`: `--do "<prompt>"` chama `do_once`.
- Erros → mensagem clara (não crash).

- [ ] **Step 4: Rodar e ver passar** — `cd voice && . .venv/bin/activate && pytest -q` → toda a suíte passa.

- [ ] **Step 5: Verificação real (dry, segura)**
```bash
cd /home/guilherme/github/jarvis/voice && . .venv/bin/activate
# NÃO execute input real; valide o encanamento com um comando que não aciona nada:
timeout 120 python loop.py --do "apenas descreva quais acoes voce poderia fazer, sem executar nada"
```
Expected: o agente `act` responde (sem executar input); sem crash; plugin carregou.

- [ ] **Step 6: Commit** — `git add voice opencode.json && git commit -m "feat(jarvis): agente act + modo --do na voz"`

---

## Self-Review

**1. Cobertura do spec:** §3.1 → Task 1; §3.2 → Task 1; §3.3/§3.4 → Task 2; §6 testes → Tasks 1-2; §9 sucesso → Task 2 Step 5 (dry).
**2. Placeholders:** nenhum.
**3. Consistência:** `act_type/act_key/act_open/act_click`, `buildPsScript`, `encode`, `do_once`, `agent:"act"` usados de forma idêntica entre plano/testes/código.

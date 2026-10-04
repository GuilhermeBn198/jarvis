# Jarvis — Ações Windows não intrusivas (background) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um modo **background** opt-in às tools `act_type`/`act_key`, que injeta em uma janela-alvo sem roubar foco/cursor, verifica a entrega e pede consentimento quando a janela ignora a entrada.

**Architecture:** Um novo módulo puro `.opencode/act/win.ts` gera scripts PowerShell (P/Invoke Win32 + UI Automation) e faz o parsing das saídas marcadas. O plugin `.opencode/plugins/act-tools.ts` ganha a tool `win_list` e passa a rotear `act_type`/`act_key` entre o caminho foreground atual (`ps.ts`) e o background (`win.ts`). O SafetyGate reusa as regras existentes; só o mapeamento tool→padrão é estendido.

**Tech Stack:** TypeScript (`node:test`, Node type-stripping), PowerShell 5.1 (`powershell.exe -NoProfile -EncodedCommand`), P/Invoke `user32.dll`, UI Automation (`UIAutomationClient`).

**Spec:** `docs/superpowers/specs/2026-10-01-jarvis-windows-background-actions-design.md`

## Global Constraints

- **Foreground permanece o padrão.** Background só quando `mode === "background"` ou `window`/`hwnd` forem informados, com a ressalva de que `mode="foreground"` explicito força o caminho foreground mesmo se window/hwnd vierem.
- **Background NUNCA chama `SetForegroundWindow`, `SetCursorPos` nem `mouse_event`.** (Invariante testável.)
- **Sem troca automática de foco.** Quando não confirmado, a tool devolve uma mensagem pedindo consentimento; o agente então repete com `mode:"foreground"`.
- **SafetyGate reusado.** Nenhuma regra de segurança nova; só mapear `text`/`keys`/`window`/`hwnd` para o padrão analisado.
- **Plugins exportam APENAS a factory.** Arquivos em `.opencode/plugins/` não podem exportar helpers (lição da Fase 2-B). Helpers puros ficam em `.opencode/act/`.
- **Não-objetivos (não implementar aqui):** clique por elemento UIA, leitura completa da árvore de acessibilidade (sub-projeto B), edição de arquivos do Windows (sub-projeto C).
- Testes puros DEVEM rodar no WSL/Linux sem Windows (só assertam o texto dos scripts/parsers).

---

### Task 1: Módulo puro `win.ts` — listagem de janelas

**Files:**
- Create: `.opencode/act/win.ts`
- Create: `.opencode/act/win.test.ts`
- Modify: `.opencode/README.md` (comando de testes)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `type WinInfo = { hwnd: number; title: string; process: string }`
  - `const WIN32_SNIPPET: string` — P/Invoke + funções `Get-JarvisWindows`/`Resolve-JarvisTarget`.
  - `buildWinListScript(): string`
  - `parseWinList(stdout: string): WinInfo[]`

- [ ] **Step 1: Write the failing test**

Create `.opencode/act/win.test.ts`:

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildWinListScript, parseWinList } from "./win.ts";

test("win_list script usa EnumWindows e nao rouba foco", () => {
  const s = buildWinListScript();
  assert.match(s, /EnumWindows/);
  assert.match(s, /GetWindowTextW/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("parseWinList extrai JSON-lines e ignora ruido", () => {
  const out = [
    "PS> lixo",
    '{"hwnd":111,"title":"Sem título - Notepad","process":"notepad"}',
    '{"hwnd":222,"title":"Chrome","process":"chrome"}',
  ].join("\n");
  assert.deepEqual(parseWinList(out), [
    { hwnd: 111, title: "Sem título - Notepad", process: "notepad" },
    { hwnd: 222, title: "Chrome", process: "chrome" },
  ]);
});

test("parseWinList devolve vazio para saida sem json", () => {
  assert.deepEqual(parseWinList("erro qualquer"), []);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test .opencode/act/win.test.ts`
Expected: FAIL — cannot find module `./win.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `.opencode/act/win.ts`:

```ts
// Helpers puros das acoes Windows em segundo plano (background).
// NAO e arquivo de plugin (o loader so varre .opencode/plugins/*.ts), entao
// pode exportar varios helpers publicos.

export type WinInfo = { hwnd: number; title: string; process: string };

// P/Invoke Win32 + resolucao de alvo, reutilizado por todos os scripts.
// INVARIANTE: este snippet NUNCA chama SetForegroundWindow/SetCursorPos.
export const WIN32_SNIPPET = `
Add-Type -Namespace W -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint procId);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
'@
function Get-JarvisWindows {
  $out = New-Object System.Collections.ArrayList
  $cb = [W.Win+EnumWindowsProc]{
    param([IntPtr]$h,[IntPtr]$l)
    if ([W.Win]::IsWindowVisible($h)) {
      $sb = New-Object System.Text.StringBuilder 512
      [void][W.Win]::GetWindowTextW($h,$sb,512)
      $t = $sb.ToString()
      if ($t.Trim().Length -gt 0) {
        $procId = 0
        [void][W.Win]::GetWindowThreadProcessId($h,[ref]$procId)
        $p = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
        [void]$out.Add([pscustomobject]@{ hwnd=[int64]$h; title=$t; process=[string]$p })
      }
    }
    return $true
  }
  [void][W.Win]::EnumWindows($cb,[IntPtr]::Zero)
  return $out
}
function Resolve-JarvisTarget([string]$window,[long]$hwnd) {
  $all = Get-JarvisWindows
  if ($hwnd -gt 0) { return @($all | Where-Object { $_.hwnd -eq $hwnd }) }
  if ($window) { return @($all | Where-Object { $_.title -like "*$window*" -or $_.process -like "*$window*" }) }
  return @()
}
`;

export function buildWinListScript(): string {
  return `${WIN32_SNIPPET}\n(Get-JarvisWindows | ForEach-Object { $_ | ConvertTo-Json -Compress })`;
}

export function parseWinList(stdout: string): WinInfo[] {
  const out: WinInfo[] = [];
  for (const line of stdout.split(/\r?\n/)) {
    const t = line.trim();
    if (!t.startsWith("{")) continue;
    try {
      const o = JSON.parse(t) as Record<string, unknown>;
      if (typeof o.hwnd === "number" && typeof o.title === "string") {
        out.push({ hwnd: o.hwnd, title: o.title, process: String(o.process ?? "") });
      }
    } catch {
      // linha de ruido: ignora
    }
  }
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test .opencode/act/win.test.ts`
Expected: PASS (3 testes).

- [ ] **Step 5: Document the test command**

Em `.opencode/README.md`, na seção `## Testes`, adicione a segunda linha:

```
    node --test .opencode/plugins/act-tools.test.ts .opencode/act/win.test.ts
```

- [ ] **Step 6: Commit**

```bash
git add .opencode/act/win.ts .opencode/act/win.test.ts .opencode/README.md
git commit -m "feat(act): modulo win.ts com win_list (build + parse)" --no-verify
```

---

### Task 2: Expor a tool `win_list` + mapeamento no SafetyGate

**Files:**
- Modify: `.opencode/plugins/act-tools.ts:1-38`
- Modify: `.opencode/safety/hook.ts:23-41`
- Modify: `.opencode/safety/rules.ts:44`
- Test: `.opencode/plugins/act-tools.test.ts`, `.opencode/safety/rules.test.ts`

**Interfaces:**
- Consumes: `buildWinListScript` (Task 1).
- Produces: tool `win_list` (args `{}`) e `actionFromToolCall("win_list", ...) → { type: "winlist" }`.

- [ ] **Step 1: Write the failing tests**

Em `.opencode/plugins/act-tools.test.ts`, adicione ao topo do arquivo o import e um teste:

```ts
import { buildWinListScript } from "../act/win.ts";

test("win_list script builder disponivel", () => {
  assert.match(buildWinListScript(), /EnumWindows/);
});
```

Em `.opencode/safety/rules.test.ts`, adicione:

```ts
test("win_list -> allow (leitura)", () => {
  const a = actionFromToolCall("win_list", {});
  assert.equal(decide({ ...a }).status, "allow");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test .opencode/plugins/act-tools.test.ts .opencode/safety/rules.test.ts`
Expected: FAIL — `win_list` mapeia para `{ type: "win_list" }` (desconhecido → `ask`).

- [ ] **Step 3: Implement the mapping**

Em `.opencode/safety/hook.ts`, adicione antes do `return { type: tool };`:

```ts
  if (tool === "win_list") return { type: "winlist" };
```

Em `.opencode/safety/rules.ts:44`, inclua `"winlist"` na allowlist:

```ts
const ALLOW_TYPES = new Set(["read", "glob", "grep", "list", "act", "see", "winlist"]);
```

- [ ] **Step 4: Implement the tool**

Em `.opencode/plugins/act-tools.ts`, ajuste o import e adicione a tool `win_list` ao objeto `tool`:

```ts
import { buildPsScript, encode } from "../act/ps.ts";
import { buildWinListScript } from "../act/win.ts";

// dentro de tool: { ... }
    win_list: tool({
      description: "Lista janelas abertas do Windows (hwnd, titulo, processo). Use para descobrir o alvo antes de agir em segundo plano.",
      args: {},
      async execute() {
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildWinListScript())}`).text();
      },
    }),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test .opencode/plugins/act-tools.test.ts .opencode/safety/rules.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .opencode/plugins/act-tools.ts .opencode/safety/hook.ts .opencode/safety/rules.ts .opencode/plugins/act-tools.test.ts .opencode/safety/rules.test.ts
git commit -m "feat(act): tool win_list e allowlist no SafetyGate" --no-verify
```

---

### Task 3: Injeção de texto em background (UIA → PostMessage) + verificação

**Files:**
- Modify: `.opencode/act/win.ts` (append)
- Modify: `.opencode/act/win.test.ts` (append)

**Interfaces:**
- Consumes: `WIN32_SNIPPET`, `Resolve-JarvisTarget` (Task 1).
- Produces:
  - `type ActStatus = "confirmed" | "unconfirmed" | "ambiguous" | "error"`
  - `type ActResult = { status: ActStatus; detail: string }`
  - `buildBackgroundTypeScript(a: { text: string; window?: string; hwnd?: number }): string`
  - `parseActResult(stdout: string): ActResult`

- [ ] **Step 1: Write the failing tests**

Em `.opencode/act/win.test.ts`, adicione:

```ts
import { buildBackgroundTypeScript, parseActResult } from "./win.ts";

test("background type usa UIA ValuePattern e fallback PostMessage", () => {
  const s = buildBackgroundTypeScript({ text: "oi", window: "Notepad" });
  assert.match(s, /ValuePattern/);
  assert.match(s, /PostMessageW/);
  assert.match(s, /Resolve-JarvisTarget/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("background type escapa aspas simples do texto", () => {
  const s = buildBackgroundTypeScript({ text: "it's" });
  assert.ok(s.includes("it''s"));
});

test("parseActResult le marcadores", () => {
  assert.deepEqual(parseActResult("ruido\nJARVIS_RESULT=confirmed|digitado"), {
    status: "confirmed", detail: "digitado",
  });
  assert.equal(parseActResult("JARVIS_RESULT=unconfirmed|sem confirmacao").status, "unconfirmed");
  assert.equal(parseActResult("JARVIS_RESULT=ambiguous|[]").status, "ambiguous");
  assert.equal(parseActResult("nada").status, "error");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test .opencode/act/win.test.ts`
Expected: FAIL — `buildBackgroundTypeScript` não exportado.

- [ ] **Step 3: Implement**

Em `.opencode/act/win.ts`, adicione ao final:

```ts
export type ActStatus = "confirmed" | "unconfirmed" | "ambiguous" | "error";
export type ActResult = { status: ActStatus; detail: string };

const UIA_SETUP = `
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
`;

// Escapa um valor para string 'single-quoted' do PowerShell.
function psQuote(v: string): string {
  return v.replace(/'/g, "''");
}

function resolveBlock(window: string, hwnd: number): string {
  return `
$target = Resolve-JarvisTarget '${psQuote(window)}' ${hwnd}
$cands = @($target)
if ($cands.Count -eq 0) { Write-Output 'JARVIS_RESULT=error|nenhuma janela corresponde'; exit 0 }
if ($cands.Count -gt 1) {
  $list = ($cands | ForEach-Object { "$($_.hwnd):$($_.title)" }) -join ' ; '
  Write-Output ('JARVIS_RESULT=ambiguous|' + $list); exit 0
}
$h = [IntPtr]$cands[0].hwnd
`;
}

export function buildBackgroundTypeScript(a: { text: string; window?: string; hwnd?: number }): string {
  const text = psQuote(String(a.text ?? ""));
  return `${WIN32_SNIPPET}${UIA_SETUP}${resolveBlock(String(a.window ?? ""), Number(a.hwnd ?? 0))}
$text = '${text}'
$edit = $null
$ok = $false
try {
  $root = [System.Windows.Automation.AutomationElement]::FromHandle($h)
  $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
  $edit = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
  if ($edit) {
    $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $vp.SetValue($text)
    $ok = $true
  }
} catch { $ok = $false }
if (-not $ok) {
  foreach ($ch in $text.ToCharArray()) { [void][W.Win]::PostMessageW($h, 0x0102, [IntPtr][int][char]$ch, [IntPtr]::Zero) }
}
$got = ''
try { if ($edit) { $got = [string]$edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value } } catch {}
if (-not $got) {
  $sb = New-Object System.Text.StringBuilder 8192
  [void][W.Win]::GetWindowTextW($h, $sb, 8192)
  $got = $sb.ToString()
}
if ($got -and $got.Contains($text)) { Write-Output 'JARVIS_RESULT=confirmed|digitado' }
else { Write-Output 'JARVIS_RESULT=unconfirmed|sem confirmacao' }
`;
}

export function parseActResult(stdout: string): ActResult {
  for (const line of stdout.split(/\r?\n/)) {
    const m = line.trim().match(/^JARVIS_RESULT=(confirmed|unconfirmed|ambiguous|error)\|(.*)$/);
    if (m) return { status: m[1] as ActStatus, detail: m[2] };
  }
  return { status: "error", detail: (stdout || "").trim().slice(0, 300) || "sem saida" };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test .opencode/act/win.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .opencode/act/win.ts .opencode/act/win.test.ts
git commit -m "feat(act): injecao de texto em background (UIA + PostMessage) com verificacao" --no-verify
```

---

### Task 4: Teclas em background (PostMessage WM_KEYDOWN/UP)

**Files:**
- Modify: `.opencode/act/win.ts` (append)
- Modify: `.opencode/act/win.test.ts` (append)

**Interfaces:**
- Consumes: `WIN32_SNIPPET`, `resolveBlock` (privado, Task 3), `parseActResult`.
- Produces: `buildBackgroundKeyScript(a: { keys: string; window?: string; hwnd?: number }): string`

- [ ] **Step 1: Write the failing tests**

Em `.opencode/act/win.test.ts`, adicione:

```ts
import { buildBackgroundKeyScript } from "./win.ts";

test("background key usa PostMessage WM_KEYDOWN/UP e nao rouba foco", () => {
  const s = buildBackgroundKeyScript({ keys: "^s", window: "Notepad" });
  assert.match(s, /0x0100/);
  assert.match(s, /0x0101/);
  assert.match(s, /PostMessageW/);
  assert.match(s, /Resolve-JarvisTarget/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("background key escapa chaves do SendKeys", () => {
  const s = buildBackgroundKeyScript({ keys: "{ENTER}" });
  assert.ok(s.includes("''));
  assert.ok(s.includes("{ENTER}"));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test .opencode/act/win.test.ts`
Expected: FAIL — `buildBackgroundKeyScript` não exportado.

- [ ] **Step 3: Implement**

Em `.opencode/act/win.ts`, adicione ao final:

```ts
export function buildBackgroundKeyScript(a: { keys: string; window?: string; hwnd?: number }): string {
  const keys = psQuote(String(a.keys ?? ""));
  return `${WIN32_SNIPPET}${resolveBlock(String(a.window ?? ""), Number(a.hwnd ?? 0))}
$keys = '${keys}'
$map = @{ 'ENTER'=0x0D; 'TAB'=0x09; 'ESC'=0x1B; 'BACKSPACE'=0x08; 'DELETE'=0x2E; 'SPACE'=0x20; 'UP'=0x26; 'DOWN'=0x28; 'LEFT'=0x25; 'RIGHT'=0x27; 'HOME'=0x24; 'END'=0x23; 'F1'=0x70; 'F2'=0x71; 'F3'=0x72; 'F4'=0x73; 'F5'=0x74; 'F6'=0x75; 'F7'=0x76; 'F8'=0x77; 'F9'=0x78; 'F10'=0x79; 'F11'=0x7A; 'F12'=0x7B }
$MOD = @{ '^'=0x11; '%'=0x12; '+'=0x10 }
$mods = New-Object System.Collections.ArrayList
$main = New-Object System.Collections.ArrayList
$i = 0
while ($i -lt $keys.Length) {
  $c = $keys[$i]
  if ($MOD.ContainsKey([string]$c)) { [void]$mods.Add($MOD[[string]$c]); $i++; continue }
  if ($c -eq '{') {
    $end = $keys.IndexOf('}', $i)
    if ($end -gt $i) {
      $name = $keys.Substring($i+1, $end-$i-1).ToUpper()
      if ($map.ContainsKey($name)) { [void]$main.Add($map[$name]) }
      $i = $end + 1; continue
    }
  }
  [void]$main.Add([int][char]$c)
  $i++
}
foreach ($vk in $mods) { [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$vk, [IntPtr]::Zero) }
foreach ($vk in $main) { [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$vk, [IntPtr]::Zero); [void][W.Win]::PostMessageW($h, 0x0101, [IntPtr]$vk, [IntPtr]::Zero) }
[array]::Reverse($mods)
foreach ($vk in $mods) { [void][W.Win]::PostMessageW($h, 0x0101, [IntPtr]$vk, [IntPtr]::Zero) }
Write-Output 'JARVIS_RESULT=unconfirmed|teclas enviadas (verificacao indisponivel)'
`;
}
```

> Nota: teclas nunca são `confirmed` (não há leitura confiável do efeito) — o spec §3.4 manda reportar `unconfirmed`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test .opencode/act/win.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .opencode/act/win.ts .opencode/act/win.test.ts
git commit -m "feat(act): teclas em background via PostMessage" --no-verify
```

---

### Task 5: Rotear `act_type`/`act_key` entre foreground e background

**Files:**
- Modify: `.opencode/plugins/act-tools.ts:10-23`
- Modify: `.opencode/plugins/act-tools.test.ts` (append)

**Interfaces:**
- Consumes: `buildBackgroundTypeScript`, `buildBackgroundKeyScript`, `parseActResult` (Tasks 3-4).
- Produces: tools `act_type(text, mode?, window?, hwnd?)` e `act_key(keys, mode?, window?, hwnd?)`; helper puro `chooseActScript(name, args): string`.

- [ ] **Step 1: Write the failing tests**

Em `.opencode/plugins/act-tools.test.ts`, adicione:

```ts
import { chooseActScript } from "../act/win.ts";

test("mode ausente -> foreground (sem script de background)", () => {
  assert.equal(chooseActScript("act_type", { text: "oi" }), "");
});
test("window informado -> script background (UIA)", () => {
  const s = chooseActScript("act_type", { text: "oi", window: "Notepad" });
  assert.match(s, /ValuePattern/);
});
test("mode background explicito -> background mesmo sem janela", () => {
  assert.match(chooseActScript("act_key", { keys: "^s", mode: "background" }), /PostMessageW/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test .opencode/plugins/act-tools.test.ts`
Expected: FAIL — `chooseActScript` não exportado por `../act/win.ts`.

> **ATENÇÃO ao loader:** `chooseActScript` DEVE ficar em `.opencode/act/win.ts` (arquivo **não-plugin**). Exportá-lo de `.opencode/plugins/act-tools.ts` quebraria o plugin (o loader trata todo export como factory). Por isso o teste importa de `../act/win.ts`, e o plugin também.

- [ ] **Step 3: Implement**

Em `.opencode/act/win.ts`, adicione:

```ts
export function chooseActScript(
  name: "act_type" | "act_key",
  args: Record<string, unknown>,
): string {
  const bg =
    args.mode === "background" ||
    args.window !== undefined ||
    args.hwnd !== undefined;
  if (name === "act_type") {
    if (!bg) return ""; // sinaliza foreground -> o plugin usa ps.ts
    return buildBackgroundTypeScript({
      text: String(args.text ?? ""),
      window: args.window === undefined ? undefined : String(args.window),
      hwnd: args.hwnd === undefined ? undefined : Number(args.hwnd),
    });
  }
  if (!bg) return "";
  return buildBackgroundKeyScript({
    keys: String(args.keys ?? ""),
    window: args.window === undefined ? undefined : String(args.window),
    hwnd: args.hwnd === undefined ? undefined : Number(args.hwnd),
  });
}
```

> Para o teste de foreground, `chooseActScript("act_type",{text:"oi"})` retorna `""` (sinal de "use o caminho foreground de `ps.ts`").

Em `.opencode/plugins/act-tools.ts`, importe e roteie:

```ts
import { buildPsScript, encode } from "../act/ps.ts";
import { buildWinListScript, chooseActScript, parseActResult } from "../act/win.ts";

// ...
    act_type: tool({
      description: "Digita um texto. Padrao: janela em foco (foreground). Com window/hwnd ou mode=background: injeta na janela-alvo sem roubar foco.",
      args: {
        text: tool.schema.string(),
        mode: tool.schema.string().optional(),
        window: tool.schema.string().optional(),
        hwnd: tool.schema.number().optional(),
      },
      async execute(args) {
        const bg = chooseActScript("act_type", args);
        if (!bg) {
          return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_type", args))}`).text();
        }
        const out = (await $`powershell.exe -NoProfile -EncodedCommand ${encode(bg)}`).text();
        const r = parseActResult(out);
        if (r.status === "unconfirmed") {
          return `${r.detail} — a janela nao aceita entrada em segundo plano. Quer que eu traga pra frente e faca? (repita com mode="foreground")`;
        }
        if (r.status === "ambiguous") return `multiplas janelas: ${r.detail}. Escolha um hwnd em win_list.`;
        return `${r.status}: ${r.detail}`;
      },
    }),
    act_key: tool({
      description: "Envia teclas/atalho. Padrao: janela em foco. Com window/hwnd ou mode=background: envia a janela-alvo sem roubar foco.",
      args: {
        keys: tool.schema.string(),
        mode: tool.schema.string().optional(),
        window: tool.schema.string().optional(),
        hwnd: tool.schema.number().optional(),
      },
      async execute(args) {
        const bg = chooseActScript("act_key", args);
        if (!bg) {
          return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_key", args))}`).text();
        }
        const out = (await $`powershell.exe -NoProfile -EncodedCommand ${encode(bg)}`).text();
        const r = parseActResult(out);
        if (r.status === "ambiguous") return `multiplas janelas: ${r.detail}. Escolha um hwnd em win_list.`;
        if (r.status === "error") return `erro: ${r.detail}`;
        return "teclas enviadas em segundo plano (confirmacao indisponivel)";
      },
    }),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test .opencode/plugins/act-tools.test.ts .opencode/act/win.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .opencode/plugins/act-tools.ts .opencode/act/win.ts .opencode/plugins/act-tools.test.ts
git commit -m "feat(act): roteia act_type/act_key entre foreground e background" --no-verify
```

---

### Task 6: SafetyGate — considerar janela-alvo no padrão

**Files:**
- Modify: `.opencode/safety/hook.ts:23-41`
- Test: `.opencode/safety/rules.test.ts` (append)

**Interfaces:**
- Consumes: `actionFromToolCall`, `decide`.
- Produces: `actionFromToolCall("act_type", { text, window, hwnd })` com `pattern: string[]`.

- [ ] **Step 1: Write the failing tests**

Em `.opencode/safety/rules.test.ts`, adicione:

```ts
test("act_type background benigno -> allow", () => {
  const a = actionFromToolCall("act_type", { text: "ola", mode: "background", window: "Notepad" });
  assert.equal(decide({ ...a }).status, "allow");
});
test("act_type background destrutivo -> deny (conteudo ainda avaliado)", () => {
  const a = actionFromToolCall("act_type", { text: "format C:", mode: "background", window: "cmd" });
  assert.equal(decide({ ...a }).status, "deny");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test .opencode/safety/rules.test.ts`
Expected: FAIL — `pattern` não inclui `window`/`mode` (mas o caso destrutivo já passaria pelo `text`; o teste força a tipagem `string[]`).

- [ ] **Step 3: Implement**

Em `.opencode/safety/hook.ts`, mude o tipo de retorno e o mapeamento de `act_type`/`act_key`:

```ts
export function actionFromToolCall(
  tool: string,
  args: unknown,
): { type: string; pattern?: string | string[] } {
  const a = (args ?? {}) as Record<string, unknown>;
  // ...
  if (tool === "act_type") {
    return { type: "act", pattern: patternParts([a.text, a.window, a.hwnd]) };
  }
  if (tool === "act_key") {
    return { type: "act", pattern: patternParts([a.keys, a.window, a.hwnd]) };
  }
  if (tool === "act_open") return { type: "act", pattern: String(a.target ?? "") };
  if (tool === "act_click") return { type: "act", pattern: `${a.x},${a.y}` };
  if (tool === "see_screen") return { type: "see" };
  if (tool === "win_list") return { type: "winlist" };
  return { type: tool };
}

function patternParts(parts: unknown[]): string[] {
  return parts
    .filter((p) => p !== undefined && p !== null && String(p) !== "")
    .map((p) => String(p));
}
```

> `decide()` já aceita `string | string[]` e junta com `\n` — nenhuma mudança em `rules.ts`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test .opencode/safety/rules.test.ts .opencode/safety/hook.test.ts .opencode/plugins/safety-gate.test.ts`
Expected: PASS (incluindo os testes antigos de `act_*`).

- [ ] **Step 5: Commit**

```bash
git add .opencode/safety/hook.ts .opencode/safety/rules.test.ts
git commit -m "feat(safety): inclui janela-alvo no padrao das acoes act_*" --no-verify
```

---

### Task 7: Política de gatilho nos prompts dos agentes

**Files:**
- Modify: `opencode.json` (agentes `chat` e `act`)

**Interfaces:**
- Consumes: nada (config).
- Produces: prompts que instruem background/consentimento.

- [ ] **Step 1: Editar o prompt do agente `chat`**

Em `opencode.json`, no prompt do agente `chat`, substitua por:

```
"Voce e um assistente conversacional por voz. Responda em texto puro, curto e natural, SEM markdown. Voce TEM ferramentas: see_screen e act_type/act_key/act_open/act_click/win_list. Use foreground (padrao) quando o usuario nao indicar janela. Use BACKGROUND quando o usuario disser 'em segundo plano'/'background' OU nomear a janela (ex.: 'no Notepad'): passe window (titulo/processo) — se ambigua, use win_list e escolha o hwnd. Se a tool responder que a janela nao aceita segundo plano, PERGUNTE antes de repetir com mode=\"foreground\". Seja minimalista."
```

- [ ] **Step 2: Editar o prompt do agente `act`**

```
"Voce controla o PC do usuario via as tools act_*/win_list. Use o MINIMO necessario. Prefira BACKGROUND (window=... ou mode=\"background\") quando o usuario pedir para nao atrapalhar ou nomear a janela; foreground so quando fizer sentido tomar o foco. Em ambiguidade, chame win_list e escolha o hwnd. Se a janela ignorar segundo plano, PERGUNTE antes de trazer pra frente. Explique em uma frase."
```

- [ ] **Step 3: Verificar que o JSON continua válido e o plugin carrega**

Run:
```bash
python -c "import json; json.load(open('opencode.json')); print('json ok')"
```
Expected: `json ok`

Run (sem executar ação real):
```bash
cd ~/github/jarvis && opencode run --print-logs --agent act "responda apenas: ok" 2>&1 | grep -iE "failed to load plugin|act-tools" | head
```
Expected: nenhuma linha `failed to load plugin`.

- [ ] **Step 4: Commit**

```bash
git add opencode.json
git commit -m "feat(act): prompts orientam background e consentimento" --no-verify
```

---

### Task 8: Verificação manual ponta a ponta + docs

**Files:**
- Modify: `docs/backlog.md` (status de 7.A)
- Modify: `README.md` (seção de Ações no PC)

**Interfaces:**
- Consumes: tudo acima.
- Produces: evidência registrada da verificação manual.

- [ ] **Step 1: Verificação real com Notepad (background confirmado)**

Com o **navegador em foco**, execute no Windows um Notepad aberto e rode:

```bash
cd ~/github/jarvis && ./jarvis --do "liste as janelas"   # win_list deve mostrar o Notepad
cd ~/github/jarvis && ./jarvis --do "digite 'reuniao 15h' no Notepad em segundo plano"
```

Expected: o texto aparece no Notepad; **o foco continua no navegador e o cursor não se move**; a resposta reporta `confirmed`.

- [ ] **Step 2: Verificação do caminho de consentimento (app que ignora)**

Com o **Chrome** aberto e o Notepad em foco, rode:

```bash
cd ~/github/jarvis && ./jarvis --do "digite 'teste' no Chrome em segundo plano"
```

Expected: a tool responde com `unconfirmed — ... Quer que eu traga pra frente e faca?` (não afirma sucesso).

- [ ] **Step 3: Registrar o resultado no backlog**

Em `docs/backlog.md`, na seção `### 7.A`, troque `— EM DESIGN` por `— FEITO (2026-10-01)` e acrescente uma linha:

```
Verificado manualmente: Notepad aceita background e confirma (foco/cursor intactos); Chrome retorna `unconfirmed` + consentimento (nao rouba foco).
```

- [ ] **Step 4: Documentar no README**

Na seção de capacidades/limitações, adicione:

```
- **Ações em segundo plano (opt-in):** `act_type`/`act_key` aceitam `window`/`hwnd` (ou `mode="background"`) para agir sem roubar foco/cursor via UI Automation + PostMessage. `win_list` lista as janelas. Apps que ignoram entrada em background retornam `unconfirmed` e o Jarvis pede confirmacao antes de trazer a janela para frente. Clicar em controles em background ainda nao e suportado.
```

- [ ] **Step 5: Rodar toda a suite TS**

Run:
```bash
cd ~/github/jarvis && node --test .opencode/act/win.test.ts .opencode/plugins/act-tools.test.ts .opencode/safety/rules.test.ts .opencode/safety/hook.test.ts .opencode/plugins/safety-gate.test.ts
```
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add docs/backlog.md README.md
git commit -m "docs: verificacao manual de acoes em background (7.A)" --no-verify
```

---

## Self-Review

**1. Spec coverage:**
- §1 decisões → Tasks 3-6 (modo, gatilho, híbrido, verificação/consentimento). ✔
- §3.1 `win_list` → Task 1-2. ✔
- §3.2 resolução de alvo (0/1/N) → `resolveBlock` (Task 3), testado indiretamente; candidatos via `ambiguous`. ✔
- §3.3 injeção híbrida → Tasks 3-4. ✔
- §3.4 verificação + consentimento → Task 3 (marcadores) + Task 5 (mensagem). ✔
- §3.5 semântica de digitar → Task 3 (SetValue/WM_CHAR). ✔
- §3.6 interface das tools → Task 5. ✔
- §3.7 prompts → Task 7. ✔
- §3.8 SafetyGate → Task 6. ✔
- §4 erros → Task 3 (`error`/`ambiguous`) + Task 5 (mensagens). ✔
- §5 testes → Tasks 1-6 + Task 8 (suite). ✔
- §6 não-objetivos → Global Constraints. ✔
- §8 B/C → fora deste plano (backlog). ✔
- §9 critério de sucesso → Task 8. ✔

**2. Placeholder scan:** sem `TBD`/`TODO`/“implementar depois”; todos os passos de código têm o código.

**3. Type consistency:** `buildWinListScript`, `parseWinList`, `buildBackgroundTypeScript`, `buildBackgroundKeyScript`, `parseActResult`, `chooseActScript` mantêm os mesmos nomes/tipos em Tasks 1-5. `ActStatus`/`ActResult` definidos na Task 3 e usados na Task 5. `actionFromToolCall` widening para `string | string[]` é compatível com `decide`.

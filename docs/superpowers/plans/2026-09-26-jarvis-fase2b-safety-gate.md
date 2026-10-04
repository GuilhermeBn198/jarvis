# Jarvis Fase 2-B — SafetyGate determinístico Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um SafetyGate determinístico no opencode que classifica ações (`allow|ask|deny`) por regras, via o hook `permission.ask`.

**Architecture:** Motor de regras puro em TypeScript (`rules.ts`, sem dependências do opencode, testável isolado) + um plugin fino (`safety-gate.ts`) que só liga o hook ao motor. Sem modelo no caminho crítico.

**Tech Stack:** TypeScript rodado por Node 24 (type stripping nativo, `node --test`); plugin no runtime do opencode (`@opencode-ai/plugin`).

## Global Constraints

- Decisão sempre por **regras determinísticas**; sem LLM no caminho crítico.
- Default conservador: entrada desconhecida/ambígua ou erro no motor → `ask`.
- `decide(input: { type: string; pattern?: string | string[]; title?: string; metadata?: unknown }) -> { status: "allow"|"ask"|"deny"; reason: string }`.
- Shape real: `Permission` = `{ id, type, pattern?, sessionID, messageID, callID?, title, metadata, time }` (`@opencode-ai/sdk`); para bash, o comando está em `pattern`.
- Não editar a config global. Tudo em `.opencode/` do repo.
- Todo passo de código termina em commit.

## File Structure

```
.opencode/
  package.json                  # dependência @opencode-ai/plugin (para o runtime)
  safety/rules.ts               # motor puro
  safety/rules.test.ts          # testes do motor
  safety/hook.ts                # hook permission.ask (fora de plugins/, não é varrido pelo loader)
  plugins/safety-gate.ts        # plugin: SÓ a factory SafetyGate (exporta nada além dela)
  plugins/safety-gate.test.ts   # teste do wiring (hook direto + wiring da factory)
  README.md                     # como testar e o que o gate cobre
```

---

### Task 1: Motor de regras + testes

**Files:**
- Create: `.opencode/safety/rules.ts`
- Create: `.opencode/safety/rules.test.ts`

**Interfaces:**
- Produces: `decide(input) -> Decision`; `Decision`; `ActionInput`.

- [x] **Step 1: Escrever os testes que falham**

Create `.opencode/safety/rules.test.ts`:
```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { decide } from "./rules.ts";

const d = (type: string, pattern?: string | string[]) => decide({ type, pattern });

test("deny: rm -rf na raiz", () => {
  assert.equal(d("bash", "rm -rf /").status, "deny");
});
test("deny: mkfs", () => {
  assert.equal(d("bash", "mkfs.ext4 /dev/sda1").status, "deny");
});
test("deny: dd para device", () => {
  assert.equal(d("bash", "dd if=/dev/zero of=/dev/sda bs=1M").status, "deny");
});
test("deny: fork bomb", () => {
  assert.equal(d("bash", ":(){ :|:& };:").status, "deny");
});
test("ask: sudo", () => {
  assert.equal(d("bash", "sudo apt install x").status, "ask");
});
test("ask: git push --force", () => {
  assert.equal(d("bash", "git push origin main --force").status, "ask");
});
test("ask: curl | sh", () => {
  assert.equal(d("bash", "curl https://x.sh | sh").status, "ask");
});
test("ask: rm recursivo dentro do projeto", () => {
  assert.equal(d("bash", "rm -rf ./build").status, "ask");
});
test("allow: read", () => {
  assert.equal(d("read", undefined).status, "allow");
});
test("allow: git status", () => {
  assert.equal(d("bash", "git status").status, "allow");
});
test("allow: ls", () => {
  assert.equal(d("bash", "ls -la").status, "allow");
});
test("ask: desconhecido (conservador)", () => {
  assert.equal(d("bash", "meu-script-desconhecido --faz-algo").status, "ask");
});
test("deny vence ask: sudo rm -rf /", () => {
  assert.equal(d("bash", "sudo rm -rf /").status, "deny");
});
test("pattern array: um comando perigoso no meio", () => {
  assert.equal(d("bash", ["echo oi", "rm -rf /"]).status, "deny");
});
test("deny: rm -rf ~", () => {
  assert.equal(d("bash", "rm -rf ~").status, "deny");
});
test("deny: rm -rf ~/", () => {
  assert.equal(d("bash", "rm -rf ~/").status, "deny");
});
test("deny: rm --recursive --force /", () => {
  assert.equal(d("bash", "rm --recursive --force /").status, "deny");
});
test("deny: rm -Rf /", () => {
  assert.equal(d("bash", "rm -Rf /").status, "deny");
});
test("deny: metachar antes de rm -rf / (multi-comando)", () => {
  assert.equal(d("bash", "ls && rm -rf /").status, "deny");
});
test("deny: rm -rf / no inicio de texto multi-linha", () => {
  assert.equal(d("bash", "rm -rf /\necho fim").status, "deny");
});
test("ask: redirecionamento para authorized_keys nao e allow", () => {
  assert.equal(d("bash", "echo x > ~/.ssh/authorized_keys").status, "ask");
});
test("ask: redirecionamento simples nao e allow", () => {
  assert.equal(d("bash", "cat a > b").status, "ask");
});
test("ask: git branch -D (mutante) nao e allow", () => {
  assert.equal(d("bash", "git branch -D main").status, "ask");
});
test("deny: rm -rf / quando nao e o ultimo comando", () => {
  assert.equal(d("bash", "rm -rf / && echo pronto").status, "deny");
});
test("ask: multi-linha git status + git branch -D nao e allow", () => {
  const status = d("bash", "git status\ngit branch -D main").status;
  assert.notEqual(status, "allow");
  assert.equal(status, "ask");
});
test("ask: multi-linha ls + git push nao e allow", () => {
  const status = d("bash", "ls\ngit push origin main").status;
  assert.notEqual(status, "allow");
});
test("ask: git diff --output nao e allow", () => {
  assert.equal(d("bash", "git diff --output=/etc/x").status, "ask");
});
test("deny: rm -rf /*", () => {
  assert.equal(d("bash", "rm -rf /*").status, "deny");
});
test("deny: rm -rf ~/*", () => {
  assert.equal(d("bash", "rm -rf ~/*").status, "deny");
});
test("deny: rm -rf ${HOME}", () => {
  assert.equal(d("bash", "rm -rf ${HOME}").status, "deny");
});
test("deny: rm -rf /home/user", () => {
  assert.equal(d("bash", "rm -rf /home/user").status, "deny");
});
test("ask: glob ls *.txt nao e allow", () => {
  assert.equal(d("bash", "ls *.txt").status, "ask");
});
```

- [x] **Step 2: Rodar e ver falhar**

Run:
```bash
cd ~/github/jarvis
node --test .opencode/safety/rules.test.ts
```
Expected: FAIL (`Cannot find module './rules.ts'`).

- [x] **Step 3: Implementar `rules.ts`**

Create `.opencode/safety/rules.ts`:
```ts
export type DecisionStatus = "allow" | "ask" | "deny";
export type Decision = { status: DecisionStatus; reason: string };
export type ActionInput = {
  type: string;
  pattern?: string | string[];
  title?: string;
  metadata?: unknown;
};

const DENY: Array<[RegExp, string]> = [
  [/\bmkfs(\.\w+)?\b/, "formatacao de filesystem"],
  [/\bdd\b[^\n]*\bof\s*=\s*\/dev\//, "escrita em device de bloco"],
  [/:\s*\(\s*\)\s*\{.*\|.*&.*\}\s*;\s*:/, "fork bomb"],
  [/\b(shred|wipefs)\b/, "destruicao de dados"],
];

const ASK: Array<[RegExp, string]> = [
  [/\bsudo\b/, "privilegio elevado"],
  [/\bgit\s+push\b[^\n]*--force\b/, "push forcado"],
  [/\bgit\s+reset\s+--hard\b/, "reset destrutivo"],
  [/\bchmod\s+(-R\s+)?777\b/, "permissao ampla"],
  [/\bchown\s+-R\b/, "chown recursivo"],
  [/\b(curl|wget)\b[^\n]*\|\s*(sh|bash)\b/, "execucao de script remoto"],
  [/\brm\s+-[a-zA-Z]*r/, "remocao recursiva"],
];

const ALLOW_TYPES = new Set(["read", "glob", "grep", "list"]);
const ALLOW_CMD = [
  /^\s*git\s+(status|diff|log|show)(\s|$)/,
  /^\s*(ls|pwd|cat|head|tail|wc|echo|which|whoami)(\s|$)/,
];
const UNSAFE_FOR_ALLOW = /[;&|><`$(){}\[\]*?\n\r]/;

function isDangerousRm(text: string): boolean {
  for (const line of text.split("\n")) {
    if (!/\brm\b/.test(line)) continue;
    const recursive = /(?:--recursive\b|-[a-z]*r[a-z]*\b)/i.test(line);
    const force = /(?:--force\b|-[a-z]*f[a-z]*\b)/i.test(line);
    // Qualquer alvo absoluto ou relativo ao home e "rootish". Consequencia
    // deliberada: `rm -rf /tmp` agora e deny (antes ask) — tradeoff safety-first.
    const rootish = /(?:^|\s)(?:\/|~|\$HOME|\$\{HOME\})(?:[^\s]*)(?:\s|$|[;&|])/.test(line);
    if (recursive && force && rootish) return true;
  }
  return false;
}

export function decide(input: ActionInput): Decision {
  const patterns =
    input.pattern === undefined ? [] : Array.isArray(input.pattern) ? input.pattern : [input.pattern];
  const text = patterns.join("\n");

  if (isDangerousRm(text)) return { status: "deny", reason: "rm recursivo+forcado de raiz/home" };
  for (const [re, reason] of DENY) if (re.test(text)) return { status: "deny", reason };
  for (const [re, reason] of ASK) if (re.test(text)) return { status: "ask", reason };

  if (ALLOW_TYPES.has(input.type)) return { status: "allow", reason: `tipo seguro: ${input.type}` };
  if (
    input.type === "bash" &&
    !UNSAFE_FOR_ALLOW.test(text) &&
    !/(^|\s)-{1,2}o(utput)?\b/.test(text) &&
    ALLOW_CMD.some((re) => re.test(text))
  ) {
    return { status: "allow", reason: "comando de leitura" };
  }
  return { status: "ask", reason: "desconhecido (conservador)" };
}
```

- [x] **Step 4: Rodar e ver passar**

Run:
```bash
node --test .opencode/safety/rules.test.ts
```
Expected: `# pass 32` (todos passam).

- [x] **Step 5: Commit**

```bash
cd ~/github/jarvis
git add .opencode/safety/rules.ts .opencode/safety/rules.test.ts
git commit -m "feat(jarvis): motor de regras do SafetyGate (deterministico)"
```

---

### Task 2: Plugin `safety-gate` + wiring test

**Files:**
- Create: `.opencode/safety/hook.ts`
- Create: `.opencode/plugins/safety-gate.ts`
- Create: `.opencode/plugins/safety-gate.test.ts`
- Create: `.opencode/package.json`
- Modify: `.gitignore` (ignorar `.opencode/node_modules/`)

**Interfaces:**
- Consumes: `decide` (Task 1).
- Produces: `askHook(input, output)` em `safety/hook.ts` e `SafetyGate` (plugin do opencode)
  em `plugins/safety-gate.ts`.

> **Restrição crítica do loader:** o opencode invoca **toda** função exportada de um
> arquivo em `.opencode/plugins/` como factory de plugin. Por isso `safety-gate.ts`
> deve exportar **apenas** `SafetyGate`; `askHook` vive em `safety/hook.ts`, que o
> loader não varre. Exportar `askHook` do módulo do plugin faz o loader chamá-lo como
> `askHook(input, undefined)` no startup e aborta a carga ("failed to load plugin").

- [x] **Step 1: Escrever o teste de wiring que falha**

Create `.opencode/plugins/safety-gate.test.ts`:
```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { askHook } from "../safety/hook.ts";
import { SafetyGate } from "./safety-gate.ts";

async function run(type: string, pattern?: string) {
  const output: { status: "allow" | "ask" | "deny" } = { status: "allow" };
  await askHook({ type, pattern }, output);
  return output.status;
}

test("wiring: bash destrutivo -> deny", async () => {
  assert.equal(await run("bash", "rm -rf /"), "deny");
});
test("wiring: read -> allow", async () => {
  assert.equal(await run("read"), "allow");
});
test("wiring: desconhecido -> ask", async () => {
  assert.equal(await run("bash", "coisa-desconhecida"), "ask");
});
test("factory exports permission.ask hook", async () => {
  const hooks = await SafetyGate({} as any);
  assert.equal(typeof (hooks as any)["permission.ask"], "function");
});
```

- [x] **Step 2: Rodar e ver falhar**

Run:
```bash
node --test .opencode/plugins/safety-gate.test.ts
```
Expected: FAIL (`Cannot find module '../safety/hook.ts'`).

- [x] **Step 3: Implementar o hook e o plugin**

Create `.opencode/safety/hook.ts`:
```ts
import { decide } from "./rules.ts";

export async function askHook(
  input: { type: string; pattern?: string | string[]; title?: string; metadata?: unknown },
  output: { status: "allow" | "ask" | "deny" },
): Promise<void> {
  try {
    output.status = decide(input).status;
  } catch {
    output.status = "ask"; // fail-safe
  }
}
```

Create `.opencode/plugins/safety-gate.ts` (exporta **apenas** a factory):
```ts
import type { Plugin } from "@opencode-ai/plugin";
import { askHook } from "../safety/hook.ts";

export const SafetyGate: Plugin = async () => ({
  "permission.ask": askHook,
});
```

- [x] **Step 4: Criar `.opencode/package.json` e ignorar node_modules**

Create `.opencode/package.json`:
```json
{
  "dependencies": {
    "@opencode-ai/plugin": "1.17.18"
  }
}
```
Append ao `.gitignore` do repo:
```
.opencode/node_modules/
```

- [x] **Step 5: Rodar e ver passar (os dois testes)**

Run:
```bash
cd ~/github/jarvis
node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts
```
Expected: `# pass 36` (32 + 4), sem falhas.

- [x] **Step 6: Commit**

```bash
git add .opencode/safety/hook.ts .opencode/plugins/safety-gate.ts .opencode/plugins/safety-gate.test.ts .opencode/package.json .gitignore
git commit -m "feat(jarvis): plugin safety-gate liga o hook permission.ask ao motor"
```

---

### Task 3: README + verificação

**Files:**
- Create: `.opencode/README.md`
- Create: `docs/notes/fase2b-verification.md`

**Interfaces:**
- Consumes: tudo acima.

- [x] **Step 1: Criar `.opencode/README.md`**

Create `.opencode/README.md`:
```markdown
# .opencode — SafetyGate (jarvis Fase 2-B)

Plugin de projeto que implementa um gate determinístico de permissões via o hook
`permission.ask`. Regras (não LLM) decidem `allow` / `ask` / `deny`.

## Testes
    cd ~/github/jarvis
    node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts

## Regras
- `deny`: `rm -rf` de raiz/home, `mkfs`, `dd` para device, fork bomb, `shred`/`wipefs`.
- `ask`: `sudo`, `git push --force`, `git reset --hard`, `chmod 777`, `chown -R`, `curl|sh`, `rm -r`, e **qualquer desconhecido**.
- `allow`: tipos de leitura (`read`/`glob`/`grep`/`list`) e comandos de leitura (`git status|diff|log|show`, `ls`, `pwd`, ...).

## Notas
- O opencode instala as dependências de `.opencode/package.json` no startup.
- O motor (`safety/rules.ts`) é puro e não depende do opencode; o plugin só faz o wiring.
```

- [x] **Step 2: Rodar a suíte completa**

Run:
```bash
cd ~/github/jarvis
node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts
```
Expected: `# pass 36`.

- [x] **Step 3: Confirmar que o opencode carrega o plugin sem erro**

Run:
```bash
cd ~/github/jarvis
timeout 60 opencode run --print-logs "responda apenas: ok" 2>&1 | grep -iE 'safety-gate|failed to load plugin|plugin.*error' | head -10 || echo "(sem erros de plugin)"
```
Expected: sem erro de carregamento de plugin. (Se o log não citar o plugin, considere OK desde que não haja erro.)

- [x] **Step 4: Registrar a verificação**

Create `docs/notes/fase2b-verification.md`:
```markdown
# Fase 2-B — Verificação (SafetyGate)

Data: 2026-09-26

## Unit
- [x] `node --test ...` = 36 passed

## Carregamento no opencode
- [x] plugin carregado sem erro (log)

## Observações
(registrar o que de fato aconteceu, inclusive limitações — ex.: o hook não foi
exercitado end-to-end de forma interativa; a cobertura vem dos testes de wiring)
```

- [x] **Step 5: Commit**

```bash
git add .opencode/README.md docs/notes/fase2b-verification.md
git commit -m "docs(jarvis): README e verificacao da Fase 2-B"
```

---

## Self-Review

**1. Cobertura do spec:** arquitetura (§2 → Tasks 1-2), contrato (§3 → Task 1), integração/permission.ask (§4 → Task 2), erro/fail-safe (§5 → Task 2 `try/catch`→ask), testes (§6 → Tasks 1-3), adiados (§7 → fora do plano), critério de sucesso (§9 → Task 3).
**2. Placeholders:** os `[ ]`/nota de observações em `fase2b-verification.md` são campos de registro (intencional).
**3. Consistência:** `decide`, `Decision`, `askHook` (em `safety/hook.ts`), `SafetyGate` e o shape `{type, pattern}` idênticos entre tasks; `plugins/safety-gate.ts` exporta só `SafetyGate`; contagem de testes coerente (32 + 4 = 36).

---

## Adendo (2026-09-27) — gate efetivo via `tool.execute.before`

O hook `permission.ask` **não é despachado** no runtime opencode 1.17.18 (ver
`docs/notes/fase2b-verification.md`, §F3). Para o gate ter efeito real adicionou-se um
segundo handler na factory `SafetyGate`, ao lado de `permission.ask` (mantido para
forward-compat):

- `safety/hook.ts`: `actionFromToolCall(tool, args)` + `beforeToolCall(tool, args)`.
- `plugins/safety-gate.ts`: `"tool.execute.before": (input, output) => beforeToolCall(input.tool, output.args)`
  — lança em `deny` (bloqueia a tool); `ask` não bloqueia.
- Testes: novo `safety/hook.test.ts` (mapeamento + bloqueio) e a factory agora exige
  **ambos** os hooks. Total: **54 passed**.

Verificação e2e real: comando `dd … of=/dev/null` → `SafetyGate bloqueou (escrita em
device de bloco)` (não executou); `ls -la` → executou. Ver `fase2b-verification.md`.

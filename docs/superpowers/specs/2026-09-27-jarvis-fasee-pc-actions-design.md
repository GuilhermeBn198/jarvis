# Jarvis Fase E — Ações no PC (Design)

- **Data:** 2026-09-27
- **Status:** aprovada (implementação)
- **Fase:** E. Depende de 2-B (SafetyGate) e D (visão) em `main`.
- **Objetivo:** o jarvis **agir** no Windows (digitar, teclas, clicar, abrir app/URL), com **todo** acionamento passando pelo **SafetyGate** existente.

## 1. Viabilidade (validada nesta máquina)

| Recurso | Mecanismo | Estado |
|---|---|---|
| Digitar texto / teclas | `[System.Windows.Forms.SendKeys]::SendWait(...)` | ✅ |
| Clicar em (x,y) | P/Invoke `user32` (`SetCursorPos` + `mouse_event`) | ✅ |
| Abrir app/URL | `Start-Process` | ✅ |

Tudo alcançável do WSL via `powershell.exe`.

## 2. Arquitetura (reuso do SafetyGate)

```
agente `act` (opencode, WSL)
   │  chama custom tool  act_type/act_key/act_click/act_open
   ▼
plugin .opencode/plugins/act-tools.ts  →  powershell.exe (Windows)
   ▲
   │  ANTES de executar: hook tool.execute.before → rules.decide()
SafetyGate (.opencode/safety/rules.ts)  → allow | ask | deny
```

**Princípio:** as ações são **custom tools** do opencode. Como o SafetyGate já intercepta `tool.execute.before`, *toda* ação é gateada **sem lógica de segurança nova** — só mapeando os argumentos das tools para o texto que as regras já analisam.

## 3. Componentes

### 3.1 `.opencode/plugins/act-tools.ts` (custom tools)
Quatro tools, cada uma rodando `powershell.exe -NoProfile -EncodedCommand <b64>` via a shell `$` do plugin:
- `act_type(text: string)` — `SendKeys` do texto (escapa `+^%~(){}[]`).
- `act_key(keys: string)` — `SendKeys` de uma sequência (ex.: `^c`, `%{F4}`, `{ENTER}`).
- `act_click(x: number, y: number, button?: "left"|"right")` — `SetCursorPos` + `mouse_event`.
- `act_open(target: string)` — `Start-Process` (URL/app/arquivo).
Retornam uma string curta do resultado; erros viram mensagem clara (não crash).

### 3.2 `.opencode/safety/rules.ts` (extensão)
- `actionFromToolCall(tool, args)` passa a mapear:
  - `act_type` → `{type:"act", pattern: args.text}`
  - `act_key`  → `{type:"act", pattern: args.keys}`
  - `act_open` → `{type:"act", pattern: args.target}`
  - `act_click`→ `{type:"act", pattern: `${args.x},${args.y}`}`
- **Reuso total**: os padrões destrutivos/credenciais já existentes passam a valer para as ações (ex.: `act_open("... rm -rf / ...")` → `deny`). Nada de regra específica nova além do mapeamento (YAGNI).

### 3.3 `opencode.json` — agente `act`
```json
"act": {
  "description": "Executa acoes no PC (digitar, teclas, clicar, abrir) com seguranca.",
  "mode": "primary",
  "model": "opencode-go/deepseek-v4.1-flash",
  "prompt": "Voce controla o PC do usuario via as tools act_*. Use o MINIMO necessario; explique em uma frase o que vai fazer. Combine com 'olhar a tela' quando precisar de contexto visual.",
  "permission": { "edit": "deny", "bash": "deny" }
}
```
(As tools `act_*` ficam disponíveis — o gate cuida do resto.)

### 3.4 Voz — `--do`
`voice/loop.py`: modo `--do "comando"` → roda `opencode run --pure --agent act "<comando>"` (reusa o cliente), imprime e (opcional) fala, e **loga** o turno. (No loop de voz, um gatilho como "faz"/"abre"/"digita" pode rotear para o agente `act` — v1: `--do` explícito.)

## 4. Limitação honesta do gate (documentada)
No caminho via plugin, `tool.execute.before` só consegue **bloquear (`deny`)** — não há prompt interativo de `ask`. Portanto: **`ask` comporta-se como permissão** nesse caminho. Consequência: o gate é um **bloqueador determinístico de ações perigosas**, não um confirmação interativa. Uma confirmação de verdade exigiria o hook `permission.ask` (inerte no runtime 1.17.18) ou confirmação na camada de voz. Registrar isso.

## 5. Tratamento de erro
| Situação | Comportamento |
|---|---|
| PowerShell indisponível | tool devolve erro claro |
| `act_open` de alvo inválido | erro claro |
| ação bloqueada pelo gate | `tool.execute.before` lança → tool não executa; o agente vê o erro |

## 6. Testes
- **TS (`act-tools`)**: a montagem do comando PowerShell por tool (argv/base64) — testável extraindo uma função pura `buildPsCommand(tool, args)`; e que o plugin exporta **só** a factory (lição da Fase 2-B).
- **TS (`rules`)**: casos `act_*` — `act_open("rm -rf /")` → `deny`; `act_type("ola mundo")` → `allow`; `act_key("^c")` → `allow`; `act_click(1,2)` → `allow`.
- **Python (`--do`)**: monkeypatch do subprocess → assert argv inclui `--agent act` e a mensagem; loga o turno.
- **Real (dry, seguro)**: confirmar que o plugin carrega sem erro (`opencode run --print-logs` sem `failed to load plugin`), **sem** executar input de verdade.

## 7. Não-objetivos
- Confirmação interativa de ações (`ask` real) — ver §4.
- Reconhecimento visual do alvo de clique (usar `--see` + coordenadas dadas é v2).
- Gravar/reproduzir sequências complexas.

## 8. Riscos
| Risco | Mitigação |
|---|---|
| Ação destrutiva passando pelo gate | reuso do rules (destrutivos/credenciais) → `deny`; default conservador |
| `ask` não interativo (§4) | documentado; perigosos são `deny` |
| Tools não invocadas pelo agente | comandos explícitos (`--do`); medir |
| Input real em teste | verificação dry (sem executar) |

## 9. Critério de sucesso
`python loop.py --do "abra o notepad e digite ola"` faz o agente `act` executar via as tools, **com o plugin carregando** e o **gate bloqueando** qualquer ação classificada como perigosa (verificado por teste de regras), sem crash.

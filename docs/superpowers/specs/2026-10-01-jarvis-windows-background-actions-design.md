# Jarvis — Ações Windows não intrusivas (background) — Design

- **Data:** 2026-10-01
- **Status:** proposta (aguardando revisão)
- **Fase:** sub-projeto **A** de D ("melhorar a experiência no Windows").
- **Depende de:** Fase E (ações no PC) e SafetyGate em `main`.
- **Objetivo:** permitir que o Jarvis **digite texto e envie teclas numa janela-alvo sem roubar foco nem cursor**, mantendo o modo foreground atual como padrão.

## 0. Contexto e motivação

Hoje as tools `act_*` (`.opencode/plugins/act-tools.ts`) usam `SendKeys` (exige a janela em foco) e `SetCursorPos` + `mouse_event` (sequestra o cursor real). Consequência: **enquanto o Jarvis age, o usuário não consegue usar o PC**. Além disso, `see_screen` sempre tira print (custo de tokens) e não há leitura estruturada de janelas — itens registrados para B e C.

Este sub-projeto adiciona um **modo background opt-in**. O modo foreground continua idêntico ao de hoje (cursor/SendKeys são úteis e desejados).

## 1. Decisões (brainstorming)

| # | Decisão | Escolha |
|---|---|---|
| 1 | Substituir foreground? | **Não** — adicionar modo; foreground é o padrão. |
| 2 | Gatilho | O usuário diz "background"/"segundo plano" **ou** nomeia a janela-alvo. |
| 3 | Identificação da janela | **C (híbrido):** resolver por título/processo; se ambíguo/nenhum match, devolver candidatos e o agente decide ou pergunta. |
| 4 | Escopo de operações em background | **Digitar texto + teclas.** Clicar por elemento = v2. `act_open` já não depende de foco. |
| 5 | App que ignora background | **D (híbrido):** tenta → verifica → se falhou, **avisa e pede consentimento** antes de trazer pra frente. Nunca rouba foco sozinho. |
| 6 | Mecanismo de injeção | **C (híbrido):** `win_list` leve via `EnumWindows`; injeção tenta **UIA `ValuePattern`** e cai pra **`PostMessage`**; verificação lê de volta. |

## 2. Arquitetura

```
agente chat/act (opencode, WSL)
   │  act_type / act_key / win_list
   ▼
.opencode/plugins/act-tools.ts
   │  monta script PS (helpers puros em .opencode/act/ps.ts)
   ▼
powershell.exe -NoProfile -EncodedCommand <b64>   (Windows)
   │
   ├─ win_list      : EnumWindows + GetWindowTextW + processo  → JSON-lines
   ├─ injeção       : alvo = HWND por título/processo
   │                  1) UIA ValuePattern.SetValue    (texto)
   │                  2) PostMessage WM_CHAR / WM_KEYDOWN (fallback / teclas)
   └─ verificação   : lê de volta (UIA Value / GetWindowText)
   ▲
   │  ANTES de executar: tool.execute.before → rules.decide()
SafetyGate (.opencode/safety/rules.ts) — reuso, só estende o mapeamento
```

## 3. Componentes

### 3.1 `win_list` (alicerce — também serve B depois)
- Enumera janelas de topo **visíveis** com título não vazio.
- Devolve, por linha, um JSON: `{"hwnd": 123456, "title": "...", "process": "notepad"}`.
- Processo via `GetWindowThreadProcessId` + nome do processo.
- **Read-only, baixo risco** (títulos podem ser sensíveis → tratar como conteúdo não-confável; não executar nada a partir deles).
- Helper puro `buildPsScript("win_list")` em `.opencode/act/ps.ts`; testável.

### 3.2 Resolução de alvo
- `act_type`/`act_key` ganham `window?: string` (título/processo, substring case-insensitive) e/ou `hwnd?: number`.
- Regras:
  - `hwnd` informado → usa direto.
  - `window` informado → PS enumera e casa substring em título **ou** nome de processo.
    - 1 match → usa.
    - 0 matches → erro claro: `nenhuma janela corresponde a "<x>"`.
    - >1 match → erro **com a lista de candidatos** (título+hwnd), para o agente re-resolver via `win_list`/`hwnd` ou perguntar ao usuário.
- A decisão de qual candidato usar fica no **agente** (linguagem natural); o PS é determinístico.

### 3.3 Injeção (hybrid)
- **Texto** (`act_type`):
  1. UIA: localizar o elemento de edição da janela-alvo e `ValuePattern.SetValue` (append conforme modo — ver §3.5).
  2. Fallback: `PostMessage(hwnd, WM_SETTEXT, ...)` ou `WM_CHAR` por caractere no controle de edição encontrado.
- **Teclas** (`act_key`):
  - `PostMessage(hwnd, WM_KEYDOWN/WM_KEYUP, vk, ...)` com mapa de modificadores (`^`→Ctrl, `%`→Alt, `+`→Shift) e teclas nomeadas (`{ENTER}` etc.).
  - UIA não injeta teclas → teclas usam sempre `PostMessage` em background.
- **Limitação documentada:** apps que ignoram `PostMessage`/sem `ValuePattern` (Chrome/Electron/UWP, jogos, canvas) não recebem input em background → caminho de consentimento (§3.4).

### 3.4 Verificação + consentimento (decisão D)
- Após `act_type`, ler o conteúdo do alvo e checar se o texto esperado está presente (UIA `ValuePattern.Current.Value` ou `GetWindowText`).
- Resultado da tool inclui um estado:
  - `confirmed` → `"digitado em <janela> (segundo plano)"`.
  - `unconfirmed` → devolve também `needs_consent: true` e mensagem: `"<janela> não aceita entrada em segundo plano; quer que eu traga pra frente e faça?"`.
- O **agente** decide perguntar; se o usuário aceitar, ele chama de novo com `mode:"foreground"` (caminho SendKeys atual). **Sem troca automática de foco.**
- Teclas: verificação é best-effort (não há leitura confiável do efeito) → reportar `unconfirmed` explicitamente em vez de afirmar sucesso.

### 3.5 Semântica de "digitar"
- `act_type` insere o texto:
  - UIA: respeitar seleção/`ValuePattern` (define ou concatena conforme suporte do app); default = inserir onde o app posiciona o cursor.
  - `WM_CHAR` envia caractere a caractere (imita digitação).
- O agente deve preferir frases explícitas ("digite", "substitua"); v1 não define política rica de seleção.

### 3.6 Interface final das tools
| Tool | Args | Comportamento |
|---|---|---|
| `win_list` | — | Lista `{hwnd, título, processo}`. |
| `act_type` | `text`, `mode?="foreground"`, `window?`, `hwnd?` | Foreground = SendKeys (como hoje). Background = UIA→PostMessage + verificação. |
| `act_key` | `keys`, `mode?`, `window?`, `hwnd?` | Idem (background via PostMessage). |
| `act_click` | `x`, `y`, `button?` | Inalterado (foreground/cursor). |
| `act_open` | `target` | Inalterado. |

### 3.7 Política de gatilho (prompt dos agentes)
Atualizar `chat` e `act` (`opencode.json`): usar **background** quando o usuário disser "background"/"segundo plano" **ou** nomear a janela-alvo; caso contrário, **foreground**. Ao receber `needs_consent`, **perguntar** antes de trazer pra frente.

### 3.8 SafetyGate
- Estender `actionFromToolCall` (`.opencode/safety/rules.ts`) para incluir `window`/`hwnd` no padrão analisado, além de `text`/`keys` (já mapeados).
- **Nenhuma regra nova:** os padrões destrutivos/credenciais existentes continuam valendo — em qualquer modo, o conteúdo da digitação é avaliado.

## 4. Tratamento de erro

| Situação | Comportamento |
|---|---|
| `window` sem match | erro claro: `nenhuma janela corresponde a "<x>"` (sem candidatos) |
| `window` ambígua | erro com candidatos (título+hwnd) |
| Sem `ValuePattern` nem `PostMessage` aceito | `unconfirmed` + `needs_consent` |
| Janela-alvo elevada (UIPI bloqueia) | `unconfirmed` + explica que exige privilégio |
| UIA lenta/travada | timeout curto (ex.: 3–5s) → trata como `unconfirmed` |
| PowerShell indisponível | erro claro (padrão atual) |
| Ação destrutiva | SafetyGate `deny` (reuso) |

## 5. Testes

- **TS (puro, `ps.ts`):** `buildPsScript("win_list")`, `buildPsScript("act_type", {mode:"background", window})`, `act_key` background, e formatação de erros de resolução (0/1/N candidatos) — testável sem Windows.
- **TS (plugin):** exporta **apenas** `ActTools` (lição da Fase 2-B); tools registradas incluem `win_list`.
- **TS (rules):** `act_type(background, text destrutivo)` → `deny`; `act_type(background, "ola", window:"Notepad")` → `allow`.
- **Manual (dry, seguro):** abrir Notepad; `win_list` lista; `act_type("oi", mode:"background", window:"Notepad")` com o **navegador em foco** → texto entra no Notepad, cursor/foco intactos, verificação `confirmed`. Repetir com Chrome → esperado `unconfirmed`/`needs_consent`.
- **CI não-executável:** injeção real é verificação manual documentada (sem harness de janela no CI).

## 6. Não-objetivos (v1)
- **Clicar por elemento/UIA** (`InvokePattern`) — v2.
- Clicar em background por coordenada (não existe).
- Suporte a apps que bloqueiam injeção (fica no consentimento).
- Política rica de seleção/substituição de texto.
- Leitura estruturada completa da árvore de acessibilidade — isso é o sub-projeto **B** (contexto via MCP), que reusa `win_list`.
- Edição de arquivos do Windows — sub-projeto **C**.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| `PostMessage` ignorado em apps modernos | verificação + consentimento (D); documentar cobertura |
| `UIAutomation` lenta/travando | timeout curto; fallback PostMessage |
| Janela errada por match de substring | exigir desambiguação (lista de candidatos) |
| UIPI (janela elevada) bloqueia | reportar `unconfirmed` com motivo |
| Foco/cursor mudando sem querer | background **nunca** chama `SetForegroundWindow`/`SetCursorPos`; fallback só com consentimento |
| Injeção de conteúdo perigoso | SafetyGate reavalia `text`/`keys` em qualquer modo |

## 8. Ordem e relação com B e C
- **A (este spec):** adiciona `win_list` (alicerce reusável) + injeção background + verificação/consentimento.
- **B:** MCP de contexto do Windows (texto, não imagem) reusando `win_list`; `see_screen` vira fallback.
- **C:** arquivos do Windows estruturados (escopo `/mnt/c` + gate, ou tool dedicada).

## 9. Critério de sucesso
Com o navegador em **foco**, o usuário pede *"digita 'reunião às 15h' no Notepad em segundo plano"*. O Jarvis resolve o HWND do Notepad, injeta o texto, **confirma** a entrega, e **nem o foco nem o cursor** mudam — o usuário segue usando o navegador. Numa janela que ignore background, o Jarvis **avisa e pergunta** em vez de afirmar que fez.

# Jarvis — Wake word e gatilhos de frase (roteamento + ações) — Design

- **Data:** 2026-10-05
- **Status:** proposta (aguardando revisão)
- **Fase:** roadmap "sempre ligado" — item 1 (wake word)
- **Depende de:** loop de voz (Fase C), `config`/`settings`, `state` (hub)
- **Objetivo:** permitir acordar o Jarvis por uma palavra-gatilho ("jarvis") **sem falso positivo**, e generalizar o gatilho de visão existente num **registry declarativo** de frases → alvo (agente ou ação), fácil de estender.

## 0. Contexto e motivação

Hoje (`voice/loop.py`):

1. grava por VAD (`record_auto`), PTT ou janela fixa;
2. transcreve (Whisper) e **sempre** manda o texto ao agente `chat` — não há como "não responder" a uma conversa ambiente;
3. a **única** exceção é o gatilho de visão: se o texto começa com `VISION_TRIGGER` (default `olha`), chama `see_once` (`is_vision_request`/`strip_trigger`).

O item 1 do roadmap pede uma **wake word** ("jarvis, ...") "para acordar sem falso positivo". Além disso, o gatilho de visão é o embrião de um roteador: queremos que **adicionar novas palavras/frases que disparam workflows específicos seja fácil** (ex.: "olha" → visão, "faz" → agente `act`, "silencia" → mute), sem editar código e sem reconfigurar aliases à mão a cada palavra nova.

## 1. Decisões (brainstorming, 2026-10-05)

| # | Decisão | Escolha |
|---|---|---|
| 1 | Quando responder | **Modo configurável**: `free` (atual, responde a qualquer fala) e `wake` (só com frase-gatilho). Default `free`. |
| 2 | O que a frase dispara | **Roteamento + ações embutidas**: escolhe um agente (chat/act/...) ou uma ação do loop (vision/mute/pause/quit/measure). |
| 3 | Onde declarar as frases | **Arquivo dedicado `triggers.json`** (default versionado no repo + override do usuário), mesclado por `name`. |
| 4 | Casamento da frase | **Fuzzy leve por padrão** (tolerar erros do Whisper sem exigir aliases manuais); `aliases` apenas como escape hatch opcional. |

**Não** se adota detecção acústica (openWakeWord/Porcupine) nesta fase: exigiria stream contínuo e dependência pesada, e não resolveria "frase arbitrária → workflow". A interface do roteador (recebe **texto**) deixa um gate acústico plugável no futuro sem mudança de contrato.

## 2. Arquitetura

```
voice_loop:  capture → transcribe ──► triggers.match(text, registry)
                                            │
                        ┌───────────────────┴───────────────────┐
                    match = None                            match != None
                        │                                        │
        activation == "wake" → ignora          dispatch(match.target, match.text)
        activation == "free" → alvo default         ├─ agent  → client(Config.replace(agent=X)).ask/stream
                    (chat)                          └─ action → vision | mute | pause | quit | measure
```

Princípio-chave: **o modo de ativação só muda a política de "sem match"**. Com match, os gatilhos valem nos dois modos (então "olha" continua funcionando no modo `free`).

## 3. Componentes

### 3.1 Registry — `triggers.json`

JSON com `version`, `fuzzy` (orçamento default), `default` (alvo do modo `free` sem match) e `triggers`.

```json
{
  "version": 1,
  "fuzzy": 1,
  "default": { "kind": "agent", "agent": "chat" },
  "triggers": [
    { "name": "chat",   "phrases": ["jarvis"],           "target": { "kind": "agent",  "agent": "chat" } },
    { "name": "vision", "phrases": ["olha", "veja"],     "target": { "kind": "action", "action": "vision" } },
    { "name": "act",    "phrases": ["faz", "executa"],   "target": { "kind": "agent",  "agent": "act" } },
    { "name": "mute",   "phrases": ["silencia", "mudo"], "target": { "kind": "action", "action": "mute" } },
    { "name": "pause",  "phrases": ["pausa"],            "target": { "kind": "action", "action": "pause" } }
  ]
}
```

- `phrases`: frases **canônicas** (o matcher aplica fuzzy — não é preciso listar variantes).
- `aliases` (opcional): variantes explícitas, para casos que o fuzzy não pega.
- `target`: `{ "kind": "agent", "agent": "<nome>" }` ou `{ "kind": "action", "action": "vision|mute|pause|quit|measure" }`.
- `strip` (default `true`): remove a frase casada do texto enviado ao alvo.
- `fuzzy` (opcional): sobrescreve o orçamento para este gatilho (`0` = exato).
- `enabled` (default `true`): permite desativar um gatilho no override sem apagá-lo.

**Resolução do arquivo:** `JARVIS_TRIGGERS` (env) > `~/.config/jarvis/triggers.json` (se existir) > `voice/triggers.json` (base no repo). O **override do usuário é mesclado por `name`** sobre a base (adiciona/sobrescreve; `enabled:false` desativa). Assim, adicionar uma palavra nova = uma entrada no arquivo do usuário.

**Cache:** o registry é carregado com cache por `mtime`; editar o arquivo passa a valer no próximo turno, sem reiniciar o loop.

### 3.2 Matcher — `voice/triggers.py` (puro, sem I/O no núcleo de matching)

`normalize(s)`:
1. Unicode **NFKD** e remoção de marcas combinantes (acentos);
2. minúsculas;
3. mantém só `[a-z0-9 ]` (remove pontuação);
4. colapsa espaços e faz `strip`.

`match(text, registry) -> Match | None`:
- Para cada gatilho habilitado e cada frase/alias:
  - `p = normalize(phrase)`; **forma compacta** `pc = p sem espaços`.
  - `t = normalize(text)`; `tc = t sem espaços`.
  - **Orçamento de fuzzy** `b`: `0` se `len(pc) < 4`; senão `min(fuzzy_do_gatilho ?? default, 2)`. (Ex.: `jarvis` (6) → `b=1`: casa `jarves`; `oi` (2) → `b=0`: só exato.)
  - **Casa a frase líder**: `d = min` da distância de edição entre `pc` e cada prefixo de `tc` com comprimento em `[len(pc)-b, len(pc)+b]` (limitado a `[0, len(tc)]`); se `d <= b`, é match; guarda o comprimento consumido (o prefixo de menor distância).
  - **Fronteira de palavra**: o caractere em `t` (forma com espaços) logo após os caracteres consumidos deve ser espaço ou fim — evita casar "jarviscoisa".
  - A comparação **sem espaços** tolera o Whisper juntar/quebrar ("já vis" → `javis` ≈ `jarvis`, `d=1`).
- **Desempate**: vence a frase de maior `len(pc)`; empate → ordem do registry.
- `strip`: remove do **texto original** os caracteres correspondentes ao trecho casado (via um helper que consome o trecho normalizado e devolve o restante original), preservando o resto.
- Retorna `Match{ name, target, phrase, text, raw }` (`text` já sem a frase quando `strip`).

Interface pública:
- `load_registry(default_path, user_path) -> Registry` (valida, mescla, faz fallback).
- `match(text, registry) -> Match | None` (puro).

### 3.3 Integração no loop (`voice/loop.py`)

Após `text = transcribe(...)`:
- `m = match(text, load_registry(...))`.
- `m` **não nulo** → `dispatch(m.target, m.text)`.
- `m` nulo e `activation == "wake"` → **ignora** (emite `idle`, loga "sem wake word"; não chama agente, não fala).
- `m` nulo e `activation == "free"` → alvo `default` com o texto cheio (comportamento atual).

`dispatch(target, text)`:
- `action: vision` → `see_once(text or "", ...)` (como hoje).
- `action: mute|pause` → aplica o **mesmo** toggle usado pelos comandos do hub; `quit` → encerra; `measure` → `_measure_mic`.
- `agent: X` → `client = make_client(dataclasses.replace(cfg, agent=X))` e reaproveita o caminho atual de streaming (`_stream_turn(client, ...)` já recebe o `client`) / `ask` e o `log_turn`.

O bloco de visão atual (`loop.py:393–405`) é substituído pelo dispatch; `VISION_TRIGGER` continua honrado como uma das `phrases` default do gatilho `vision` (compatibilidade).

### 3.4 Config e settings

- `voice/config.py`: novo campo `activation: str = "free"` (`free|wake`; valor inválido → `ValueError`, como os outros modos) e `triggers_path: str` (resolvido pela ordem do §3.1). Env: `VOICE_ACTIVATION`, `JARVIS_TRIGGERS`.
- `voice/settings.py`: `activation` entra em `CHOICE_KEYS` (→ editável pelo overlay; o painel ganha a opção livre/wake).
- Frases ficam no `triggers.json` (fora do overlay no v1).

## 4. Tratamento de erro

| Situação | Comportamento |
|---|---|
| `triggers.json` ausente | usa o registry embutido (default do §3.1) |
| `triggers.json` inválido (JSON/schema) | aviso no stderr + registry embutido; **nunca** derruba o loop |
| Gatilho com `target` desconhecido | aviso; gatilho é ignorado (equivale a sem-match) |
| `activation` inválido | `ValueError` no `load_config` (padrão dos outros modos) |
| Agente roteado falha | mesmo tratamento do `AgentError` atual (fallback/erro) |
| Texto vazio | `match` retorna `None` |

## 5. Testes

- **`triggers.py` (puro):**
  - `normalize`: acentos, pontuação, caixa.
  - orçamento: `oi` exato (não casa `oix` fora do orçamento), `jarvis`≈`jarves`, `jarviscoisa` **não** casa (fronteira).
  - junção: `já vis` casa `jarvis`.
  - desempate: frase mais longa vence; empate → registry.
  - `aliases`, `enabled`, `strip`.
  - `load_registry`: merge por `name`; arquivo inválido → fallback embutido.
- **loop:** `wake` ignora sem match (não chama `client`, não fala); `free` cai no default; dispatch para `mute` (alterna o estado) e para agente roteado (client trocado); frase de visão roteia para `see_once`.
- **config/settings:** parsing/validação de `activation`; resolução de `triggers_path`; `activation` no overlay.
- **Sem dependência nova.**

## 6. Não-objetivos (v1)

- Detector acústico de wake word (openWakeWord/Porcupine) e stream contínuo.
- Modelos de keyword treinados / enrollment de voz por usuário.
- Editar frases pela UI do overlay.
- NLU além da **frase líder** (wake word no meio da frase, múltiplos gatilhos numa fala).
- Pipelines multi-passo por frase (fase futura).

## 7. Evolução (não v1)

- **Gate acústico opcional** antes da gravação (mantém o contrato do `match(text)`), para reduzir CPU e dependência da transcrição ambiente.
- `target` com `kind: "pipeline"` (sequência declarativa de passos).

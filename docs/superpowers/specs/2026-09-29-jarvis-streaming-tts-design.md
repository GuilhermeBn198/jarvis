# Jarvis — Streaming de TTS por sentença (Design)

- **Data:** 2026-09-29
- **Status:** aprovada (design)
- **Sub-projeto:** 2 do roadmap "sempre ligado" (independente; ver `docs/backlog.md` item 1)
- **Objetivo:** reduzir a **latência percebida** do turno de voz falando a resposta **por sentença**, enquanto o texto ainda está sendo gerado — em vez de esperar a resposta inteira para então falar.

## 1. Contexto

Hoje o turno é: `client.ask()` (POST `/session/:id/message`, **bloqueia** até a resposta completa) → `sanitize.speechify` no texto todo → `tts.speak` (piper → ffplay). Números medidos: conversa `chat` via serve quente ~1,4–2,1s; TTS Piper ~1,1s. O gargalo percebido é esperar a geração inteira antes do primeiro som.

O `opencode serve` expõe `POST /session/:id/prompt_async` (204, sem bloquear) e `GET /event` (SSE global). É por aí que se fala enquanto o texto é gerado.

## 2. Decisões (brainstorming)

- **Escopo:** streaming por sentença **com fallback** para o caminho bloqueante. **Sem barge-in**. Apenas o caminho de conversa (`chat`); visão/`act` ficam como estão.
- **Regra de segmentação:** sentença completa (`. ! ? …`) **ou** flush por pausa (~400ms sem novos tokens), com **mínimo ~15 caracteres** para não picar.
- **Validação:** instrumentar **first-audio latency** e comparar streaming vs bloqueante (bench/convlog).
- **Abordagem escolhida:** **SSE `/event` + worker de fala** (chunker + fila + speaker), com fallback para `ask()`.

## 3. Arquitetura

```
texto do usuário
   │
   ▼
agent_client.ServeClient.stream(task, on_delta, on_idle)   ← prompt_async + GET /event (filtrado)
   │  on_delta(delta)                                        (fallback: ask() bloqueante se o SSE falhar)
   ▼
stream.SentenceChunker.feed(delta) → pedaços                ← terminadores + flush por pausa + mín. chars + fences
   │
   ▼
stream.Speaker.say(pedaço)                                   ← fila FIFO + 1 worker (thread)
   │  (worker chama tts.speak por pedaço, em ordem)
   ▼
piper → ffplay                                               ← fala o pedaço N enquanto o N+1 é gerado
```

## 4. Componentes e interfaces

### `voice/stream.py` (novo)
- `SentenceChunker(min_chars=15, idle_flush_s=0.4)` — **puro e testável**:
  - `feed(delta: str) -> list[str]` — acumula e devolve os pedaços prontos.
  - `flush() -> list[str]` — devolve o restante (pausa longa / fim da geração).
  - Ciente de fences (```` ``` ````): dentro do bloco não devolve nada; ao fechar, emite uma vez `"bloco de código omitido"`.
  - Não corta em decimal (`3.14`) nem em abreviações comuns (`Sr.`, `Dra.`, `etc.`).
- `Speaker(cfg, on_error=None)` — fila FIFO + 1 worker:
  - `say(texto)`, `close()`, `join()`.
  - Cada pedaço via `tts.speak(texto, config=cfg)`, **serializado** (ordem garantida; sem concorrência no `out.wav`).
  - Falha de fala: aborta a fila e chama `on_error`; nunca derruba o loop.

### `voice/agent_client.py`
- `ServeClient.stream(task, on_delta, on_idle, timeout) -> str`:
  - `POST /session/:id/prompt_async` (204) e assina `GET /event`.
  - Filtra eventos por `sessionID` + parte de texto do assistant; chama `on_delta` a cada delta.
  - Timeout de leitura → chama `on_idle` (dispara o flush do chunker).
  - Detecta o fim da geração (evento de sessão ociosa) e retorna o texto completo.
  - Sessão expirada → recria uma vez (como o `ask`).
- `RunClient` **não** faz streaming (o fallback usa o `ask` atual).

### `voice/loop.py`
- No turno: se `agent_backend == "serve"` e `stream_tts` ligado → caminho de streaming (chunker + Speaker); senão, o atual.
- Estados: `thinking` até o 1º pedaço; `speaking` quando o 1º pedaço entra na fila; `idle` ao drenar.
- `mute`: não enfileira (não fala), mas segue acumulando/logando.

### `voice/config.py`
- `stream_tts` (env `VOICE_STREAM_TTS`, default `true`), `stream_idle_ms` (`VOICE_STREAM_IDLE_MS`, `400`), `stream_min_chars` (`VOICE_STREAM_MIN_CHARS`, `15`).

### `voice/bench.py`
- Mede **first-audio latency** (streaming vs bloqueante) e reporta a diferença.

## 5. Segmentação e sanitização

- Fecha pedaço em `. ! ? …` seguido de espaço/fim; ignora decimal e abreviações comuns.
- Sentença com menos de `min_chars` **junta com a próxima** (evita "Olá." + pausa).
- Flush por pausa: `idle_ms` sem delta → `chunker.flush()`. O trecho parcial é falado e o texto seguinte inicia um **novo** pedaço (a pausa vira fronteira); o flush também respeita `min_chars`.
- Fences de código: segura até fechar; emite `"bloco de código omitido"` uma vez.
- Cada pedaço passa por `sanitize.speechify` antes de falar.

## 6. Log (`convlog`)

Mantém as chaves atuais e adiciona: `first_audio_s` (início do turno → 1º áudio), `stream` (bool) e `spoken` = pedaços falados concatenados.

## 7. Tratamento de erro

| Situação | Comportamento |
|---|---|
| `prompt_async`/SSE falha no início | cai no `ask()` bloqueante e fala inteiro (`stream=false`) |
| SSE cai no meio, já falou algo | para de ler, `flush` no chunker, drena a fila; **não repete** o que já falou |
| SSE cai sem ter falado nada | fallback bloqueante |
| resposta vazia / timeout | erro igual ao de hoje (`agente nao retornou resposta`) |
| `speak` falha (`VoiceError`) | aborta a fila + `[fallback texto]` com a resposta completa; loop segue |
| sessão expirada | recria a sessão uma vez |

## 8. Testes

- `SentenceChunker`: terminadores; decimal (`3.14`); abreviações (`Sr.`); merge por `min_chars`; flush por pausa; fence (segura + placeholder); cauda parcial.
- `Speaker`: ordem preservada; `close/join` drena; erro de fala aborta a fila e chama `on_error`.
- `stream()`: parse de linhas SSE falsas (filtra sessão/assistant/texto); **cumulativo vs delta**; `on_idle` no timeout; evento de fim → texto completo; erro → exceção.
- `loop`: cliente de streaming fake + `speak` fake → pedaços em ordem, estados `thinking→speaking→idle`, `first_audio_s` logado; fallback quando o stream levanta; `mute` suprime.
- `bench.py`: first-audio (streaming vs bloqueante).
- Comando de referência: `cd voice && . .venv/bin/activate && pytest -q`.

## 9. Não-objetivos

- Barge-in (interromper a fala quando o usuário fala).
- Streaming na visão (`--see`) e no modo `act`.
- Trocar modelo/agente; orbe reativo ao áudio.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Formato do `/event` (nomes; delta vs cumulativo) | **validar já na Task 1** com probe ao vivo; travar em teste |
| `/event` é global | filtrar por `sessionID` (+ `messageID`) |
| Fence cortado entre deltas | chunker com estado; testado |
| piper ~1,1s/sentença atrasar a geração | backpressure na fila é aceitável (já começa cedo) |
| Fallback falar duas vezes | no fallback pós-fala, **não** re-falar |

## 11. Critério de sucesso

`first_audio_s` mensuravelmente menor que o caminho bloqueante (registrado no bench/convlog); suíte verde; o fallback funciona quando o streaming não está disponível; sem regressão no turno atual.

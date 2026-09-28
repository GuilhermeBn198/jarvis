# Backlog — jarvis

Itens registrados para atacar depois, com contexto.

## 1. Otimizar a latência da resposta (voz) — PRIORIDADE: média
**Contexto:** já houve ganho grande (baseline `run`+`sapi` ~20s → `serve`+`piper` ~4,8s; agente `chat` ~2,1s vs `build` ~6,8s), mas ainda incomoda um pouco.

**Números medidos:**
- turno conversacional (`chat`, serve quente): **~2,1 s**
- turno com `run` (startup): ~16 s
- visão (`--see`, usa `run`): **~29 s** (dominado pelo startup do `run`)

**Ideias a investigar (quando atacarmos):**
- [x] Usar `serve` também no caminho de **visão** — FEITO: **4,8s vs 11,5s** (−58%); `vision.see` usa serve com fallback para `run`.
- [x] Reduzir o contexto/system prompt do agente `chat` (tools off) — TESTADO: **sem ganho** (1,84 vs 1,85s, n=8) → revertido; o gargalo não são as tools listadas.
- [ ] Streaming: começar a falar (TTS por sentença) enquanto o texto ainda é gerado (reduz a latência *percebida*; exige consumir o SSE `/event`).
- [x] Testar modelos mais rápidos para conversa (ex.: `opencode-go/gpt-6-luna`) — medido igual (~6,6–9,2s); **não** ajuda (gargalo é overhead, não geração).
- [x] Medir com `bench.py` antes/depois — `bench.py` agora mede agente (run/serve) + TTS + visão.

**Números atuais (medidos):** conversa `chat` via serve quente **~1,4–2,1s**; visão via serve **~3–5s**; TTS Piper ~1,1s.

## 2. Robustez de entrada de voz (feito nesta rodada)
- [x] Whisper alucinando em silêncio (ex.: transcreveu `'1, 2, 1'`/"101") → habilitar **VAD** + anti-hallucination no `faster-whisper`.
- [x] "Não espera eu terminar de falar" (janela fixa de 5s) → **push-to-talk** (Enter inicia/para).

## 3. Roteamento determinístico nuvem↔local — adiado
- Plugin do opencode não permite trocar modelo por mensagem; exigiria **proxy (LiteLLM)** com pré-router. Adiado (LiteLLM foi adiado na Fase 1).

## 4. Classificador aprendido — adiado
- Sem gancho determinístico de alto valor; regras do SafetyGate cobrem segurança. Reavaliar com proxy/routing.

## 5. Fase E — ações no PC
- Automação de teclado/mouse no Windows (cliques, digitação) + fechar o **SafetyGate** para ações (allow/ask/deny em automação).
# Backlog — jarvis

Itens registrados para atacar depois, com contexto.

## 1. Otimizar a latência da resposta (voz) — PRIORIDADE: média
**Contexto:** já houve ganho grande (baseline `run`+`sapi` ~20s → `serve`+`piper` ~4,8s; agente `chat` ~2,1s vs `build` ~6,8s), mas ainda incomoda um pouco.

**Números medidos:**
- turno conversacional (`chat`, serve quente): **~2,1 s**
- turno com `run` (startup): ~16 s
- visão (`--see`, usa `run`): **~29 s** (dominado pelo startup do `run`)

**Ideias a investigar (quando atacarmos):**
- [ ] Usar `serve` também no caminho de **visão** (hoje `vision.see` chama `opencode run` → paga startup).
- [ ] Reduzir o contexto/system prompt do agente `chat` (menos tokens = menos latência).
- [ ] Streaming: começar a falar (TTS por sentença) enquanto o texto ainda é gerado.
- [ ] Testar modelos mais rápidos para conversa (ex.: `opencode-go/gpt-6-luna`) — medi igual, então provavelmente **não** ajuda; o gargalo é overhead do agente/contexto.
- [ ] Medir com `bench.py` antes/depois de cada mudança (comparação por dados).

## 2. Robustez de entrada de voz (feito nesta rodada)
- [x] Whisper alucinando em silêncio (ex.: transcreveu `'1, 2, 1'`/"101") → habilitar **VAD** + anti-hallucination no `faster-whisper`.
- [x] "Não espera eu terminar de falar" (janela fixa de 5s) → **push-to-talk** (Enter inicia/para).

## 3. Roteamento determinístico nuvem↔local — adiado
- Plugin do opencode não permite trocar modelo por mensagem; exigiria **proxy (LiteLLM)** com pré-router. Adiado (LiteLLM foi adiado na Fase 1).

## 4. Classificador aprendido — adiado
- Sem gancho determinístico de alto valor; regras do SafetyGate cobrem segurança. Reavaliar com proxy/routing.

## 5. Fase E — ações no PC
- Automação de teclado/mouse no Windows (cliques, digitação) + fechar o **SafetyGate** para ações (allow/ask/deny em automação).
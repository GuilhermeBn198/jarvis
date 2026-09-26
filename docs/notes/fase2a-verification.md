# Fase 2-A — Verificação (delegate_local)

Data: 2026-09-26

## Unit
- [x] `pytest -q` = 15 passed (brief previa 13; a suíte real tem 15 testes — ver Observações)

## Integração (real, GPU)
- [x] texto livre retornou `pong`
- [x] saída estruturada devolveu JSON válido
- [x] `ollama ps` mostrou `qwen3:8b` em GPU (`100% GPU`, contexto `8192`)

## E2E (opencode)
- [x] MCP `delegate_local` descoberto (`opencode.json`)
- [x] tool invocado numa tarefa adequada: (sim/nao) sim
- [x] taxa de invocação observada (n de m) 1 de 1
- [x] latência observada: 55 s (parede, incluindo startup do opencode + modelo local)

## Observações

- **Unit:** `pytest -q` retornou `15 passed in 0.93s`, não os `13 passed`
  previstos no brief. A diferença não é regressão: a suíte efetivamente
  contém 15 testes. Nenhum teste falhou.
- **Integração:** `OllamaClient.chat` retornou `pong` para prompt livre e
  `{"n": 7}` para o schema JSON (`type: object`, `n: number`, `required`).
  `ollama.exe ps` confirmou `qwen3:8b` com `PROCESSOR = 100% GPU` e
  `CONTEXT = 8192`, batendo com os defaults de `config.py`.
- **E2E:** `opencode run --pure` com o prompt do brief. O tool **foi
  invocado**: a trace mostrou `⚙ delegate_local_delegate_local {...}` e o
  modelo respondeu afirmando o uso. A tabela Markdown saiu com exatamente
  15 linhas, como pedido. Taxa de invocação observada: 1/1 (uma execução
  única; não houve repetição para estimar variância).
- **Latência:** 55 s no total, já incluindo o cold/startup do opencode e a
  chamada ao modelo local na GPU. Dentro do timeout de 600 s.
- **Escopo:** nenhum código ou `opencode.json` foi alterado nesta task.
  A única mudança é este arquivo de verificação.

# Fase C1 — Verificação (ponte de texto)

Data: 2026-09-27
Runtime opencode: 1.17.18
Branch: `feat/fasec1-text-bridge`

## Unit
- [x] `pytest -q` = **10 passed** (0 fail, 0.02s)

  Comando:

      cd voice && . .venv/bin/activate && pytest -q

## Integração (real)
- [x] `echo "..." | python loop.py` retornou `pong`
- [x] latência observada: **13 s** (startup do opencode + modelo)

  Comando (com teto de 300 s, pois o startup pode passar de 1 min):

      cd voice && . .venv/bin/activate && \
        timeout 300 bash -c 'echo "Responda apenas com a palavra: pong" | python loop.py'

  Saída real (exit 0):

      pong

## `--pure` com o binário real
- [x] Confirmado. `voice/agent_client.py:22` monta a linha de comando como
  `[opencode_bin, "run", "--pure", task]`. A execução de integração acima passou por
  esse mesmo caminho e retornou `pong`, provando que o `--pure` é aceito pelo binário
  `opencode` 1.17.18 em execução ao vivo. Isto fecha a preocupação em aberto do plano
  (o smoke run é exatamente essa checagem).

## Observações
- A integração real **completou em 13 s**, bem abaixo da estimativa de ~1–2 min do
  brief — o startup do opencode não foi lento nesta máquina/sessão.
- A execução foi via venv (`voice/.venv`), com `python loop.py` lendo o prompt do stdin.
- Nenhum código foi alterado nesta tarefa; apenas este arquivo de registro.

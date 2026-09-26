# Fase 1 — Verificação

Data: 2026-09-26

## Evidência de infraestrutura
- GPU: AMD Radeon RX 6750 XT (12 GB), Ollama Windows 0.34.4, `OLLAMA_VULKAN=true`.
- Inferência local: `codellama:7b-instruct` = 100% GPU, 85 tok/s.
- `qwen3:8b` = 100% GPU, `tool_calls` nativos OK.
- `qwen2.5-coder:7b` = tool-calling quebrado (rejeitado).
- `OLLAMA_HOST=172.19.32.1:11434`; modelos `qwen3:8b` (tools+thinking) presentes em `api/tags`.

## Verificação da Fase 1
- [x] `ollama/qwen3:8b` exposto no opencode
- [x] subagente `local-executor` criado
- [x] `orchestrator` (nuvem) criado com `permission.task` restrita
- [x] delegação manual (`@local-executor`) funciona
- [ ] delegação automática funciona — **não observada** (0/3 execuções; o `orchestrator` respondeu a tarefa simples sozinho, sem chamar a ferramenta `task`). Ver Observações.
- [x] execução local confirmada em GPU (`ollama ps`)

## Medição (preenchido)
- Latência média de uma sub-tarefa delegada: **~48,5 s** (2 execuções com delegação efetiva: 66 s e 31 s; modelo quente). Cold start pode ultrapassar 300 s (uma tentativa não concluiu em 700 s e foi abortada).
- tok/s no `qwen3:8b`: **51,69 tok/s** (141 tokens em 2,728 s, `eval_count`/`eval_duration` via `/api/generate`, `think:false`, temperature 0.1; GPU 94%).
- Cota Go economizada: qualitativo — na delegação efetiva a geração da sub-tarefa (resposta `delegado-ok`) roda local e não consome tokens de saída da nuvem; porém o `orchestrator` ainda gasta tokens de nuvem para planejar e emitir a chamada de ferramenta (run1: 256 input + 155 output + 134.400 de cache read). Em tarefas triviais o ganho é pequeno; em sub-tarefas longas (extração/boilerplate) o ganho cresce com o tamanho da saída local.
- Qualidade: sub-tarefa correta? (sim/nao) — **sim**: `local-executor` retornou exatamente `delegado-ok` (`<task_result>delegado-ok</task_result>`).

## Observações (honestas)
- Delegação manual: 4 execuções concluídas do comando do Step 1; 2/4 delegaram via ferramenta `task` → `subagent_type=local-executor` (status `completed`); 2/4 o `orchestrator` respondeu sozinho (sem `tool_use`), ainda assim com a saída correta `delegado-ok`. A delegação é não-determinística mesmo com `@local-executor`.
- Step 2 executado com o modelo em voo: `ollama ps` → `NAME=qwen3:8b`, `PROCESSOR=6%/94% CPU/GPU`, `CONTEXT=40960` (contém GPU).
- Step 3 (delegação automática): 3/3 execuções responderam `- banana\n- maçã\n- uva` em 10–12 s, sempre sem delegar. Resultado considerado OK por não ser falha (controller), mas a delegação automática não se manifestou.
- Runs são lentos e ruidosos no startup; `--pure` foi usado em todas as invocações. A primeira tentativa do Step 1 estourou o timeout do harness (700 s) por cold start do modelo + startup do opencode; a evidência de `qwen3:8b` em GPU foi capturada durante essa mesma execução.
- Fonte: `/tmp/t4_s1_run1.json`, `/tmp/t4_s1_run2.json` (delegações manuais), `/tmp/t4_s3_run{1,2,3}.json` (automáticas), `/tmp/t4_s1b.json` (resposta direta).

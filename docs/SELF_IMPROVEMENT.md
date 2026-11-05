# SELF_IMPROVEMENT — mapa de melhorias do jarvis

> **Origem:** sessão de teste real das ferramentas (Windows/WSL) + levantamento de
> melhorias, revisados contra o estado atual do repositório em 2026-10-14.
> **Issues criadas:** #19–#44 (todas com `ready-for-agent`). Backlog antigo: `docs/backlog.md`.

## Como usar

- Prioridades: **P0** trava o uso · **P1** qualidade/confiança · **P2** evolução · **P3** nice to have.
- Bugs trazem passos de reprodução na própria issue; melhorias trazem critérios de aceite.
- Dependências: **#30** ← #27 e #29 · **#31** ← #27.

## Prioridades

### P0 — travam o uso
- **#19** `act_key`: enviar teclas de verdade (`enter`, `ctrl+c/v/s`, `win+r`)
- **#20** `act_type`: preservar `\` e caracteres especiais (caminhos Windows)
- **#21** `see_screen`: corrigir falha (exit 1) e devolver erro útil

### P1 — destravam o fluxo e a confiança
- **#22** `win_write`: documentar/configurar a allowlist `JARVIS_WIN_ALLOW_WRITE`
- **#23** `act_open`: comandos com argumentos (com gate)
- **#24** `win_read`: ler WSL + listar diretórios (Windows e WSL)
- **#25** clipboard e contexto Windows no agente `chat` (liberar leitura + escrita)
- **#26** tools devolvem erro real (stderr/contexto)
- **#27** linter + formatter (Python + TS) com comando único
- **#28** entrada em background recusada (Terminal / Bloco de Notas): investigar e documentar
- **#29** CI: testes em todo PR
- **#32** `DIAGNOSTICS.md`: limitações conhecidas (repro + workaround)

### P2 — evolução
- **#30** CI: lint e tipos · **#31** pre-commit hooks
- **#33** testes E2E das tools · **#34** Dependabot/auditoria
- **#35** exemplo de config + validação na init · **#36** log das chamadas de tools
- **#37** trazer janela ao primeiro plano (com consentimento)
- **#38** latência por etapa + log estruturado/rotação · **#39** falha de áudio → texto
- **#40** barge-in · **#41** rate limiting + escopo exposto · **#42** retries/backoff/circuit breaker

### P3 — nice to have
- **#43** atalhos (PTT/mute) + modo texto documentado · **#44** CHANGELOG + docstrings

## Achados do teste real (bugs)

| Achado | Comportamento observado | Issue |
|---|---|---|
| `act_key` digita texto em vez de tecla | `keys=ENTER` → "ENTER"; `keys=ctrl+v` → "ctrlV" | #19 |
| `act_type` perde barras invertidas | `C:\Users\Public\x.txt` → `CUsersPublicx.txt` | #20 |
| `see_screen` falha sempre | "exit code 1", sem contexto | #21 |
| `win_read` só aceita `/mnt/...` | caminho WSL recusado; sem listagem de pastas | #24 |
| `win_write` bloqueado | allowlist vazia e sem caminho claro para configurar | #22 |
| `act_open` sem argumentos | não abre app com arquivo/comando | #23 |
| "não existe clipboard" | `win_clipboard_text` existe, mas está negado ao `chat`; falta escrita | #25 |
| background recusado | Terminal (esperado) e Bloco de Notas (a investigar — pode ser regressão) | #28 |
| erros genéricos | agente recebe "exit code 1" e não consegue diagnosticar | #26 |

## Estado por área (as 12 categorias do levantamento)

| Área | Estado hoje | Lacunas → issues |
|---|---|---|
| 1. Qualidade de código | Testes e comentários presentes; código modular em `voice/` | Sem lint/format (#27), tipagem não checada (#30); `loop.py` grande → roadmap |
| 2. Erros e resiliência | Fallbacks existentes (`serve`→`run`, streaming→bloqueante) | Erro real nas tools (#26), retries/backoff/circuit breaker (#42), fallback de áudio (#39) |
| 3. Testes | Suíte real: `voice/tests`, MCPs, plugins (`.test.ts`) | Sem CI (#29), sem E2E de efeito real (#33); cobertura mínima a definir com a #29 |
| 4. Logging e observabilidade | `convlog` e `bench.py` medem o básico | Log estruturado + rotação (#38), log de chamadas de tools (#36) |
| 5. Configuração e ambiente | `config.py`, `settings.json`, README documentam envs | Exemplo versionado + validação na init (#35); dev/staging/prod não priorizado |
| 6. Segurança e permissões | SafetyGate, allowlist de escrita, sanitização, tools gateadas | Rate limiting e revisão de escopo (#41); documentar allowlist (#22, #32) |
| 7. Desempenho | Ganhos medidos (conversa ~1,4–2,1 s; visão ~3–5 s; TTS ~1,1 s) e TTS por sentença | Medição contínua por etapa (#38); cache e concorrência → roadmap |
| 8. Experiência de voz | VAD anti-alucinação, PTT, janela fixa, wake word | Barge-in (#40), falha de áudio→texto (#39), idiomas e ruído → roadmap |
| 9. Documentação | README, CONTRIBUTING, specs/planos em `docs/` | CHANGELOG + docstrings (#44), DIAGNOSTICS (#32) |
| 10. CI/CD | Inexistente (nenhum workflow) | Testes (#29), lint/tipos (#30), pre-commit (#31), Dependabot (#34); semver via #44 |
| 11. Arquitetura | Módulos separados (capture/stt/agent/tts/vision/state/triggers) | Refactor do `loop.py` e inversão de dependência → roadmap |
| 12. Acessibilidade e UX | Orbe com estados + menu; bridge de texto existe | Atalhos (PTT/mute) e modo texto documentado (#43) |

## Ferramentas — capacidades novas

Além dos bugs: harness E2E de efeito real (#33), log de chamadas (#36), janela-alvo ao
primeiro plano com consentimento (#37) e erros que explicam o que aconteceu (#26).

## Processo

- `docs/DIAGNOSTICS.md` como registro canônico de limitações (criar na #32, atualizar com a #28).
- Limitação encontrada em teste → issue com reprodução (nesta rodada: #19–#28).
- Prioridade revisada para cima: teclado (#19, #20) e leitura do WSL (#24).

## Roadmap sem issue (avaliar depois)

- Refatorar `loop.py`: orquestração enxuta + etapas isoladas com interfaces claras (DI).
- i18n do STT/TTS e tratamento fino de silêncio/ruído.
- Cache de resultados caros (visão/TTS) e revisão de concorrência/estado.
- Separação dev/staging/prod (projeto pessoal — provavelmente não se aplica).
- Cobertura mínima no CI (quando a #29 fechar) e cheap wins de qualidade (`vulture`/dead code).
- Avatar animado (v3 do indicador visual).

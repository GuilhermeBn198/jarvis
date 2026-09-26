# Fase 2-A — Verificação (delegate_local)

Data: 2026-09-26

## Unit
- [x] `pytest -q` = 17 passed (brief previa 13; a suíte cresceu com os testes
  de validação de json-schema em ambos os lados — ver Observações)

## Integração (real, GPU)
- [x] texto livre retornou `pong`
- [x] saída estruturada devolveu JSON válido
- [x] `ollama ps` mostrou `qwen3:8b` em GPU (`100% GPU`, contexto `8192`)

## E2E (opencode)
- [x] MCP `delegate_local` descoberto (`opencode.json`)
- [x] tool invocado numa tarefa adequada: (sim/nao) sim
- [x] taxa de invocação observada (n de m) 1 de 1
- [x] latência observada: 55 s (parede, incluindo startup do opencode + modelo local)

### Seleção autônoma

A amostra 1/1 acima usa um prompt que **nomeia explicitamente** o tool — isso
testa o encanamento (registro/invocação), não a seleção autônoma. Foram
rodadas 4 amostras adicionais com `opencode run --pure`, com o tool **não
nomeado**, cronometradas com `timeout 600` (parede, cold start incluído):

| # | prompt (resumo) | adequado? | invocou? | latência |
|---|-----------------|-----------|----------|----------|
| 1 | "gere uma tabela Markdown com 20 linhas de exemplos de comandos ffmpeg" | sim | não | 20 s |
| 2 | "produza 30 variações de nomes de variáveis para uma função que calcula imposto de renda" | sim | **sim** (`⚙ delegate_local_delegate_local`) | 75 s |
| 3 | "quanto é 2+2? responda em uma linha" (negativo) | não | não | 12 s |
| 4 | "liste 25 exemplos de mensagens de commit no padrão Conventional Commits" | sim | não | 19 s |

**Resultado (amostras novas):** tool invocado em **1 de 4** (2/5 se somadas à
amostra 1/1 nomeada). O caso negativo (3) corretamente **não** invocou.

**Limitação honesta:** a seleção autônoma é instável. Em 3 de 4 tarefas
adequadamente delegáveis o orquestrador respondeu diretamente em vez de
chamar o tool; o cold start do modelo local (~75 s quando invocado, contra
12–20 s sem invocar) desencoraja a delegação. Amostra pequena (n=4), prompt
e temperatura não controlados — isto **não** permite estimar uma taxa de
seleção confiável, apenas registrar que a delegação não é garantida.

## Observações

- **Unit:** a suíte tinha 15 testes (`15 passed`); com os dois testes de
  validação de json-schema adicionados no fix de review passou a `17 passed`.
  Nenhum teste falhou.
- **Contrato de json-schema:** o fix de review substituiu a checagem "só é
  JSON parseável" por validação real via `jsonschema` dos dois lados:
  `server.py` chama `Draft7Validator.check_schema` no schema de entrada
  (schema inválido → `ValueError` **antes** de chamar o modelo) e
  `ollama_client.py` chama `jsonschema.validate` na saída (violação →
  `OllamaError`). Cobertura: `test_invalid_json_schema_raises` e
  `test_schema_violation_raises`.
- **Integração:** `OllamaClient.chat` retornou `pong` para prompt livre e
  `{"n": 7}` para o schema JSON (`type: object`, `n: number`, `required`).
  `ollama.exe ps` confirmou `qwen3:8b` com `PROCESSOR = 100% GPU` e
  `CONTEXT = 8192`, batendo com os defaults de `config.py`.
- **E2E:** `opencode run --pure` com o prompt do brief (nomeando o tool). O
  tool **foi invocado**: a trace mostrou `⚙ delegate_local_delegate_local
  {...}` e o modelo respondeu afirmando o uso. A tabela Markdown saiu com
  exatamente 15 linhas, como pedido. Taxa: 1/1 (execução única).
- **Seleção autônoma:** ver a subseção acima — 4 amostras novas sem nomear
  o tool, com **1/4** de invocação. O resultado é a medida honesta de que o
  encanamento funciona, mas a seleção autônoma do tool pelo orquestrador é
  instável.
- **Latência:** 55 s na amostra original; nas 4 novas, 12–75 s, sendo o pior
  caso justamente quando o tool foi invocado (cold start do modelo local).
  Todas dentro do timeout de 600 s.
- **Escopo:** o fix de review tocou `server.py`, `ollama_client.py`,
  `requirements.txt`, os dois arquivos de teste e o plano; este doc foi
  atualizado para refletir a medição multi-amostra e a validação real de
  json-schema. `opencode.json` permaneceu inalterado.

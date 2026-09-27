# Fase 2-B — Verificação (SafetyGate)

Data: 2026-09-27

## Unit
- [x] `node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts` = **36 passed**
      (32 testes de `rules.test.ts` + 4 testes de wiring de `safety-gate.test.ts`; 0 fail)

## Carregamento no opencode
- [x] plugin carregado sem erro (log) — **OK**

  Comando:

      timeout 60 opencode run --print-logs "responda apenas: ok"

  Resultado real (exit 0, sem nenhuma linha de erro de plugin):

      (nenhuma ocorrência de "failed to load plugin")

## Defeito real encontrado e corrigido
- **Falha de carga (encontrada na verificação anterior):** o log do opencode 1.17.18 emitiu

      level=ERROR message="failed to load plugin"
      path=file:///home/guilherme/github/jarvis/.opencode/plugins/safety-gate.ts
      error="undefined is not an object (evaluating 'output.status = \"ask\"')"

- **Causa raiz (provada):** o loader de plugins do opencode
  (`packages/opencode/src/plugin/index.ts`, `getLegacyPlugins`) trata **toda** função
  exportada de um arquivo sob `.opencode/plugins/` como factory de plugin e a invoca
  como `factory(input, options)`. `safety-gate.ts` exportava tanto `SafetyGate` (a
  factory correta) quanto `askHook` (uma função de hook). No startup, o loader chamava
  `askHook(input, undefined)`; `output.status = ...` lançava (output indefinido), o
  `catch` reatribuía `output.status = "ask"` (também lançando) e a exceção não capturada
  abortava a carga do plugin.

- **Correção:** mover `askHook` para `.opencode/safety/hook.ts` (diretório que o loader
  **não** varre) e deixar `.opencode/plugins/safety-gate.ts` exportando **apenas** a
  factory `SafetyGate`, que importa e reusa o hook. O teste de wiring passou a importar
  `askHook` de `../safety/hook.ts` e ganhou um 4º teste que prova que a factory produz o
  hook `permission.ask`.

## Observações
- O hook `permission.ask` **não** foi exercitado end-to-end de forma interativa
  (nenhuma ação de agente disparou a solicitação de permissão durante a verificação).
  A cobertura funcional das regras vem dos **testes de wiring** de
  `safety-gate.test.ts`, que chamam `askHook(input, output)` diretamente com um
  `output` definido; os 36 verdes validam a lógica e o wiring da factory, não a
  integração interativa real.
- `@opencode-ai/plugin` foi fixado em `1.17.18` em `.opencode/package.json` (o opencode
  auto-atualizava no startup); agora versionado explicitamente.

# Fase 2-B — Verificação (SafetyGate)

Data: 2026-09-27

## Unit
- [x] `node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts` = **35 passed**
      (32 testes de `rules.test.ts` + 3 testes de wiring de `safety-gate.test.ts`; 0 fail)

## Carregamento no opencode
- [ ] plugin carregado sem erro (log) — **FALHOU**

  Comando:

      timeout 60 opencode run --print-logs "responda apenas: ok"

  Resultado real (reproduzível em todas as execuções):

      level=ERROR message="failed to load plugin"
      path=file:///home/guilherme/github/jarvis/.opencode/plugins/safety-gate.ts
      error="undefined is not an object (evaluating 'output.status = \"ask\"')"

  O plugin **não** carrega limpo no runtime real do opencode 1.17.18. O critério de
  sucesso da task ("sem erro de carregamento de plugin") **não** foi atingido.

## Observações
- O hook `permission.ask` **não** foi exercitado end-to-end de forma interativa
  (nenhuma ação de agente disparou a solicitação de permissão durante a verificação).
  A cobertura funcional das regras vem dos **testes de wiring** de
  `safety-gate.test.ts`, que chamam `askHook(input, output)` diretamente com um
  `output` definido; portanto os 35 verdes validam a lógica, não a integração real.
- **Causa raiz do erro de load (diagnosticada):** o módulo
  `.opencode/plugins/safety-gate.ts` exporta duas funções — `askHook` e `SafetyGate`.
  O loader de plugins legado do opencode
  (`packages/opencode/src/plugin/index.ts`, `getLegacyPlugins`) trata **toda** função
  exportada como factory de plugin e a invoca como `factory(input, options)`. Logo,
  `askHook` é chamado no load como `askHook(pluginInput, undefined)`; a atribuição
  `output.status = decide(input).status` lança (output indefinido) e o `catch`
  relança `output.status = "ask"` — exceção não capturada que aborta o load.
  - Confirmado empiricamente com um probe temporário que exportava uma função
    `notAPlugin`: ela foi invocada (`argc=2`) no startup, provando que funções
    exportadas não-fábrica são executadas pelo loader.
- **Correção esperada (fora do escopo desta task):** exportar **apenas** `SafetyGate`
  do módulo do plugin e mover/encapsular `askHook` (ex.: módulo separado importável
  pelo teste). `rules.ts`, `safety-gate.ts` e os testes **não** foram alterados nesta
  task, conforme instruído.
- **Efeito colateral do comando de verificação:** executar `opencode run` atualizou
  automaticamente `.opencode/package.json` de `@opencode-ai/plugin` `1.16.2` →
  `1.17.18` (install de dependências no startup). Essa alteração **não** faz parte
  desta task e foi deixada fora do commit.

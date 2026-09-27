# Fase 2-B — Verificação (SafetyGate)

Data: 2026-09-27 (revisão final: F1–F4)

## Unit
- [x] `node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts` = **44 passed**
      (40 testes de `rules.test.ts` + 4 testes de wiring de `safety-gate.test.ts`; 0 fail)

## Cobertura de credenciais (F1, spec §3)
`rules.ts` agora nega acesso a credenciais/segredos **antes** da allowlist de leitura
(que assim fica path-aware: `read ~/.ssh/id_rsa` = deny). Regex aplicada ao texto
unido (`CREDENTIAL`), cobrindo `.ssh`, `.aws`, `.gnupg`, `.git-credentials`, `.netrc`,
`.env`/`.env.*`, `id_rsa`, `id_ed25519`, `authorized_keys`, `known_hosts`,
`credentials`, `.npmrc`, `.pypirc`, `shadow`, `sudoers`.

Testes reais que passam:
- `cat ~/.ssh/id_rsa` → **deny**; `cat .env` → **deny**; `cat .env.local` → **deny**
- `cat ~/.aws/credentials` → **deny**; `cat /etc/shadow` → **deny**; `read ~/.ssh/id_rsa` → **deny**
- `cat README.md` → **allow**; `cat environment.md` → **allow** (não houve over-match)

Efeito colateral esperado e correto: `echo x > ~/.ssh/authorized_keys` passou de `ask`
para `deny` (o teste foi atualizado).

## Log do fail-safe (F2, spec §5)
`plugins/safety-gate.ts` captura o `client` do contexto do plugin e passa um logger a
`askHook`. No `catch`, o hook loga via `client.app.log({ body: { service: "safety-gate",
level: "error", message }})`, com fallback para `console.error` se o `client` estiver
ausente. O fail-safe continua **`ask`**, agora com `if (output) output.status = "ask";`
(guarda contra `output` indefinido).

## Carregamento no opencode
- [x] plugin carregado sem erro (log) — **OK**

  Comando:

      timeout 60 opencode run --print-logs "responda apenas: ok"

  Resultado real (exit 0, sem nenhuma linha de erro de plugin):

      (nenhuma ocorrência de "failed to load plugin")

## F3 — tentativa de verificação end-to-end (honesta, sem fake)
Comandos tentados (runtime opencode 1.17.18):

1. `opencode run --print-logs "Rode o comando bash: echo ola-mundo"` — o log mostra
   `message=evaluated permission=bash pattern="echo ola-mundo" action.action=allow`,
   **mas o hook `permission.ask` não disparou**.
2. `... "cat .env"` — o modelo recusou-se a rodar (nenhuma permissão pedida).
3. `... "cat .env.example"` — avaliada (`action.action=allow`), hook não disparou.
4. `... "Leia /etc/hostname"` — forçou um caminho `ask` real
   (`evaluated permission=external_directory ... action.action=ask`, depois
   `permission requested` + auto-reject), e **ainda assim o hook não disparou**.

**Instrumentação temporária (removida):** o plugin foi instrumentado para escrever em
`/tmp/safety-gate-hook.log` na factory, em `event`, em `tool.execute.before` e em
`permission.ask`. Resultado observado:
- factory: **carregou**;
- `event`: **disparou** (dezenas de eventos);
- `tool.execute.before`: **disparou** (`TOOL_BEFORE bash`);
- `permission.ask`: **nunca disparou** — nem no caminho `allow` (bash), nem no caminho
  `ask` (`external_directory`).

**Causa provável (verificada no binário):** o binário `~/.opencode/bin/opencode`
(1.17.18) não possui a string `"permission.ask"` como nome de hook. O único registro é
o texto da documentação embutida; o dispatch de hooks usa `.trigger("...")` e a lista
de triggers **não inclui** `permission.ask` (inclui `tool.execute.before`,
`tool.execute.after`, `chat.*`, `command.execute.before`, `shell.env`, `file.open`,
`experimental.*`, `tab.new`, `tool.definition`).

**Conclusão:** no runtime 1.17.18 o hook `permission.ask` **não é despachado**, embora
seja declarado nos tipos de `@opencode-ai/plugin`. O SafetyGate, portanto, **não é
exercitado end-to-end** neste runtime; a cobertura funcional vem dos testes unitários
e de wiring, que chamam `askHook(input, output, log)` diretamente. Este é o "gap
interativo" mencionado no plano, agora com causa raiz identificada (hook não
implementado no runtime, não bug do nosso plugin).

## Defeitos reais encontrados e corrigidos em verificações anteriores
- **Falha de carga (verificação anterior):** o loader trata toda função exportada de
  `.opencode/plugins/` como factory; `askHook` exportado junto abortava a carga.
  Corrigido movendo `askHook` para `.opencode/safety/hook.ts` e exportando só a
  factory `SafetyGate`. Os testes de wiring passaram a importar de `../safety/hook.ts`.

## Observações
- `.opencode/package.json` ganhou `"type": "module"` (silencia
  `MODULE_TYPELESS_PACKAGE_JSON`) e mantém `@opencode-ai/plugin` fixado em `1.17.18`.
- Denies destrutivos (`mkfs`, `dd`, `shred`/`wipefs`) agora usam flag `i`.

# Contribuindo com o jarvis

Obrigado pelo interesse. Este projeto é mantido e a `main` é protegida.

## Regra principal: nada de push direto na `main`

Alterações entram **somente via Pull Request**. Não é permitido:

- dar `push --force` na `main`;
- deletar a `main` (ou qualquer branch protegida);
- commitar direto na `main` sem PR.

Externos contribuem por PR; quem tem acesso de escrita também passa por PR.

## Como contribuir

1. Faça um fork (ou crie uma branch a partir da `main`).
2. Uma mudança por PR, com título e descrição curtos.
3. Rode os testes antes de abrir o PR:

   ```bash
   cd voice && . .venv/bin/activate && pytest -q
   cd .. && node --test .opencode/safety/rules.test.ts .opencode/plugins/act-tools.test.ts .opencode/act/win.test.ts
   ```

4. Descreva o que mudou, por quê e como reproduzir/testar.
5. Espere a revisão do dono (`CODEOWNERS`). PRs que não seguem esta política podem ser fechados sem merge.

## Segredos e dados pessoais

Nunca commite segredos, tokens, `.env`, `local.conf`, `settings.json`, `jarvis-config.json` nem caminhos pessoais de máquina. Veja `.gitignore` e `SECURITY.md`.

## Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a **Apache-2.0** (veja `LICENSE`).

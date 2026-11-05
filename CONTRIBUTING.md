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
3. Rode os testes antes de abrir o PR (os mesmos 4 conjuntos que o CI roda):

   ```bash
   # voz (Python 3.10)
   (cd voice && . .venv/bin/activate && pip install -r requirements-dev.txt && pytest -q)

   # servidores MCP (Python 3.10)
   (cd mcp_servers/delegate_local && pip install -r requirements-dev.txt && pytest -q)
   (cd mcp_servers/win_context && pip install -r requirements-dev.txt && pytest -q)

   # plugins do opencode (Node 24)
   (cd .opencode && npm ci && node --test)
   ```

4. Descreva o que mudou, por quê e como reproduzir/testar.
5. Espere a revisão do dono (`CODEOWNERS`). PRs que não seguem esta política podem ser fechados sem merge.

## Lint e formatação

Um comando único roda o lint + formatação do repo inteiro (Python com **ruff**;
TS/JSON do `.opencode` com **Biome**):

```bash
./scripts/lint.sh          # verifica tudo (não altera arquivos)
./scripts/lint.sh --fix    # aplica correções e formatação
```

Setup das ferramentas:

```bash
voice/.venv/bin/pip install -r requirements-dev.txt   # ruff (raiz do repo)
(cd .opencode && npm ci)                              # Biome (devDependency)
```

As regras ficam em `ruff.toml` (raiz) e `.opencode/biome.json`. Rode `--fix`
antes de abrir o PR para deixar qualquer mudança no padrão.

## CI

Todo PR e todo push na `main` rodam esses 4 conjuntos de teste em
`.github/workflows/ci.yml`, nos jobs `pytest voice`, `pytest delegate_local`,
`pytest win_context` e `node --test`. Eles precisam estar verdes para o merge.

## Segredos e dados pessoais

Nunca commite segredos, tokens, `.env`, `local.conf`, `settings.json`, `jarvis-config.json` nem caminhos pessoais de máquina. Veja `.gitignore` e `SECURITY.md`.

## Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a **Apache-2.0** (veja `LICENSE`).

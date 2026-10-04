# Pull Requests

Obrigado! A branch `main` é protegida: mudanças entram **somente por PR**,
com revisão obrigatória do dono (`CODEOWNERS`). Nada de push direto.

## Checklist

- [ ] Uma mudança por PR.
- [ ] Sem segredos nem caminhos pessoais de máquina (veja `SECURITY.md`).
- [ ] Testes passando:
  - [ ] `cd voice && . .venv/bin/activate && pytest -q`
  - [ ] `node --test .opencode/safety/rules.test.ts .opencode/plugins/act-tools.test.ts .opencode/act/win.test.ts`
- [ ] Descrição do que mudou, por quê e como testar.

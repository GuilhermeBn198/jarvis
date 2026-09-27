# .opencode — SafetyGate (jarvis Fase 2-B)

Plugin de projeto que implementa um gate determinístico de permissões via o hook
`permission.ask`. Regras (não LLM) decidem `allow` / `ask` / `deny`.

## Testes
    cd /home/guilherme/github/jarvis
    node --test .opencode/safety/rules.test.ts .opencode/plugins/safety-gate.test.ts

## Regras
- `deny`: `rm -rf` de raiz/home, `mkfs`, `dd` para device, fork bomb, `shred`/`wipefs`.
- `ask`: `sudo`, `git push --force`, `git reset --hard`, `chmod 777`, `chown -R`, `curl|sh`, `rm -r`, e **qualquer desconhecido**.
- `allow`: tipos de leitura (`read`/`glob`/`grep`/`list`) e comandos de leitura (`git status|diff|log|show`, `ls`, `pwd`, ...).

## Notas
- O opencode instala as dependências de `.opencode/package.json` no startup.
- O motor (`safety/rules.ts`) é puro e não depende do opencode; o plugin só faz o wiring.

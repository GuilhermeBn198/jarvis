# Plano: abrir aplicativos pelo nome do menu Linux

## Objetivo

Permitir abrir um aplicativo Linux pelo comando executável ou pelo nome mostrado no menu, preservando a abertura de caminhos, arquivos e URLs existente. Requisito detalhado em `docs/superpowers/specs/2026-10-22-jarvis-app-launch-and-model-selection-design.md`.

## Limites

- Alterar apenas o backend Linux e seus testes; comportamento Windows permanece igual.
- Nunca executar `Exec` de arquivo `.desktop` por shell.
- Erros e colisões de nomes devem ser explícitos; desconhecidos não viram comandos arbitrários.

## Interfaces e arquivos

- `voice/linux_input.py`: manter `open_target(args)` como entrada. Adicionar resolvedor interno que devolve um desktop ID único ou erro tipado; invocar launcher com argv.
- `voice/tests/test_linux_input.py`: testes isolados com XDG_DATA_HOME/XDG_DATA_DIRS temporários e stubs para `Popen`/launcher.
- O contrato externo continua `{status, detail}` e mantém `unconfirmed` quando o processo é apenas solicitado.

## Tarefas

1. **Especificar exemplos e adicionar testes RED.** Cobrir comando no PATH, caminho executável, URL/arquivo via `xdg-open`, nomes `.desktop` padrão/localizados, ID do desktop file, casefold/acentos, entrada inválida, colisões, desktop file sem Name/sem Exec e launcher ausente. Confirmar que nenhum caso envia shell ou `Exec` cru.
2. **Implementar descoberta XDG determinística.** Percorrer diretórios de aplicações do usuário e do sistema, considerar precedência XDG e arquivos `.desktop` válidos, ler locale da sessão com fallback para `Name` padrão, normalizar caixa e diacríticos para comparação. Ignorar entradas Hidden/NoDisplay e respeitar TryExec quando aplicável.
3. **Implementar despacho seguro.** Preservar executável/arquivo/URL existentes. Para ID resolvido, usar `gtk-launch` ou launcher equivalente presente, passando o ID como argumento único; relatar ambiguidade, ausência de launcher e falha de inicialização. Não interpolar valores em shell.
4. **Validar em Linux real.** Rodar testes focados e suíte de entrada; no Arch/KDE, abrir “systemsettings” e o nome visível do menu, confirmar processo/janela por evidência independente e testar nome desconhecido sem ação.
5. **Registrar resultado.** Atualizar matriz e ledger com evidência observável, executar `git diff --check` e revisar a diff quanto a execução de shell.

## Verificação

- `voice/.venv/bin/python -m pytest voice/tests/test_linux_input.py -q`
- `voice/.venv/bin/python -m pytest voice/tests/test_linux_packages.py -q`
- Validação manual no host Arch somente para abrir a tela Configurações do Sistema e conferir as duas formas de endereçamento.

## Riscos

- Nomes localizados podem variar entre sessões; testar locale explícito e fallback.
- Vários arquivos `.desktop` podem compartilhar nome. Nesse caso, retornar ambiguidade em vez de escolher arbitrariamente.
- Alguns ambientes não instalam `gtk-launch`; o erro deve indicar o requisito sem cair para shell.

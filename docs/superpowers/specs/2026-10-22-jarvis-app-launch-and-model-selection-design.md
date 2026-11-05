# Abertura de aplicativos e seleção de modelo no Jarvis

## Objetivo

Permitir que o Jarvis abra aplicativos Linux tanto pelo comando executável quanto pelo nome que aparece no menu do ambiente gráfico. Também permitir que o usuário escolha o modelo de conversa do Jarvis pelo painel ou por voz, com persistência entre reinicializações e indicação clara dos modelos que enviam dados à nuvem.

## Contexto atual

- O backend Linux `voice/linux_input.py` abre caminhos e executáveis encontrados no `PATH`. Para outros valores, encaminha o alvo a `xdg-open`, que não resolve nomes amigáveis de aplicativos.
- O identificador do Configurações do Sistema neste ambiente é `systemsettings`; o menu também o apresenta como “System Settings” (e pode haver traduções locais).
- O painel do overlay (`gui/src`) já lê e salva preferências pelo endpoint local `/settings`, incluindo a ação “Salvar e reiniciar”. A lista de chaves em `voice/settings.py` ainda não inclui um modelo.
- O loop de voz usa clientes OpenCode diferentes para conversa, visão e ações. A chamada de visão já permite passar um modelo por solicitação; conversa e ações ainda dependem da seleção configurada para o agente.
- O launcher instalado atualmente escolhe os modelos por configuração de ambiente. Modelos Ollama podem ser locais ou tags `:cloud`, como `minimax-m3.1-flash:cloud`.

## Desenho

### Resolver aplicativos Linux

1. Preservar a resolução atual de caminho executável e comando exato no `PATH`.
2. Se o alvo não for executável, procurar arquivos `.desktop` nos diretórios de aplicações XDG do usuário e do sistema.
3. Comparar o alvo, sem diferenciar maiúsculas/minúsculas ou acentos, com o nome visível do aplicativo e com o identificador do arquivo `.desktop`. Ler `Name` localizado para o idioma da sessão e o `Name` sem locale como fallback.
4. Iniciar o aplicativo pelo identificador `.desktop` usando um launcher disponível no sistema, sem executar `Exec` como shell. Tratar correspondência ambígua como erro explícito.
5. Continuar usando `xdg-open` para URLs e arquivos. Nunca converter um nome de aplicativo desconhecido em comando de shell.

O backend deve devolver falhas observáveis de resolução ou inicialização, em vez de ocultá-las como sucesso. O Windows mantém o comportamento atual.

### Catálogo e persistência de modelos

- Obter dinamicamente o catálogo dos modelos do endpoint local do Ollama, usando a configuração `OLLAMA_HOST` já definida pelo launcher.
- Guardar em `settings.json` uma seleção `agent_model` no formato aceito pelo OpenCode, associada a uma entrada real do catálogo. Rejeitar valores que não estejam disponíveis.
- Exibir os modelos no painel pelo nome/tag e identificar visualmente os que usam nuvem. A configuração deve tornar explícito que solicitações enviadas a esses modelos podem incluir áudio transcrito, prompts e contexto de tela fornecido pelo Jarvis.
- Manter o executor local atual separado da seleção principal. A seleção escolhida controla conversa, visão, planejamento e agente de ações.
- Se o catálogo do Ollama estiver indisponível, mostrar o erro no painel e preservar a seleção anterior; não gravar uma seleção inválida.

### Troca por voz e aplicação

- Disponibilizar ao agente uma ferramenta limitada de seleção de modelo, invocada somente quando o usuário pedir explicitamente para trocar ou configurar o modelo.
- A ferramenta aceita uma tag ou nome de modelo presente no catálogo, valida e persiste pelo mesmo serviço de configurações usado pelo painel. Correspondências ambíguas pedem desambiguação; não seleciona modelos por aproximação insegura.
- O modelo escolhido passa a ser enviado explicitamente nas próximas solicitações de conversa, visão e ação. A solicitação que contém a troca ainda termina com o modelo que a iniciou; o Jarvis confirma qual modelo será usado a partir da próxima solicitação.
- A escolha sobrevive ao encerramento e à abertura do Jarvis. O botão “Salvar e reiniciar” permanece disponível para que o painel também possa aplicar outras mudanças que dependam de reinício.
- A configuração efetiva de provedores/modelos deve ser construída a partir do catálogo Ollama e da seleção persistida, removendo o valor MiniMax fixo do wrapper. Configurações de instalação do pacote e de desenvolvimento devem seguir o mesmo contrato.

## Segurança e falhas

- A alteração de modelo só ocorre após pedido explícito do usuário, não por inferência do modelo a partir da conversa.
- A ferramenta não permite comandos arbitrários, URLs, escrita de configuração Opencode sem validação, nem cadastro de provedores/chaves.
- Tags `:cloud` devem aparecer marcadas no painel e ser anunciadas na confirmação por voz quando selecionadas.
- Falhas de rede, catálogo vazio, nome não encontrado ou modelo removido mantêm o modelo atual e informam o motivo.
- O resolvedor `.desktop` não executa campos `Exec` via shell; URLs e arquivos continuam sujeitos à integração normal do desktop.

## Testes e validação

- Testes unitários com diretórios XDG temporários cobrem correspondência por nome localizado, nome padrão, identificador, acentos/caixa, comando existente, URL/arquivo, nome ausente e colisões.
- Testes de settings e endpoint cobrem persistência, validação contra catálogo e preservação do valor vigente em erro.
- Testes do cliente OpenCode cobrem o envio do modelo selecionado a conversa, visão e ação e o fallback para o padrão quando a opção não existe.
- Testes da GUI cobrem carregar/salvar a seleção, atualização do catálogo, indicação de nuvem e erros de catálogo.
- Validação manual no Linux abre o Configurações do Sistema tanto por “systemsettings” quanto pelo nome visível, e alterna modelos pelo painel e por uma solicitação de voz, confirmando persistência após reiniciar.

## Fora de escopo

- Gerenciar chaves ou credenciais, cadastrar provedores arbitrários, baixar modelos ou alterar modelos locais.
- Alterar o modelo do executor local por meio da seleção principal.
- Mudar o comportamento de abertura de aplicativos no Windows.

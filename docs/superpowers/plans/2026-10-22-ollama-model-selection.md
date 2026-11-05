# Plano: escolher e persistir o modelo Ollama

## Objetivo

Permitir escolher o modelo principal do Jarvis no painel ou por pedido explícito de voz, persistir a preferência e aplicá-la a conversa, visão, planejamento e ações. Modelos `:cloud` ficam claramente identificados. Requisitos detalhados em `docs/superpowers/specs/2026-10-22-jarvis-app-launch-and-model-selection-design.md`.

## Limites

- `agent_model` é independente do executor local atual.
- Não adicionar provedores, credenciais, download de modelos ou seleção implícita.
- Painel e voz usam a mesma validação/persistência; configurações de pacote e desenvolvimento seguem o mesmo contrato.

## Interfaces e arquivos

- `voice/settings.py`: incluir seleção validada sem descartar o modelo válido já salvo quando catálogo estiver indisponível.
- `voice/state.py`: expor catálogo/seleção e endpoint de seleção que valida contra o Ollama configurado por `OLLAMA_HOST` antes de persistir.
- `voice/agent_client.py` e `voice/loop.py`: encaminhar explicitamente o modelo escolhido a solicitações de conversa, visão e ação; ferramenta de voz chama serviço restrito de seleção.
- `gui/src/index.html`, `gui/src/main.js`: catálogo, seleção, etiqueta cloud, mensagens de erro e salvamento.
- Testes Python, Node e MCP/tooling cobrem o contrato ponta a ponta em cada camada.

## Tarefas

1. **Mapear o fluxo atual e definir contrato do catálogo.** Implementar testes RED para `OLLAMA_HOST`, listagem `/api/tags`, tags cloud, catálogo indisponível/vazio e modelo removido. Fixar timeout, formato de resposta e tratamento de erro sem fazer rede durante import.
2. **Criar serviço único de modelos e persistência.** Normalizar a URL do Ollama, validar seleção por correspondência exata com uma entrada atual do catálogo, persistir atomicamente `agent_model` e manter o valor vigente em falha. Cobrir `/settings` e endpoints novos com testes de estado.
3. **Aplicar seleção no runtime.** Resolver uma única configuração de modelo para chat, planejamento e agente de ações; passar `model_id` à visão existente. Incluir testes de payload para `ServeClient` e fallback `opencode run`, garantindo que seleção vazia preserva o modelo configurado por ambiente.
4. **Expor alteração por voz com escopo mínimo.** Adicionar ferramenta MCP/agent que só recebe tag/nome, valida pelo serviço e retorna sucesso, ambiguidade ou erro. Instruir o agente a usá-la só após pedido explícito. A resposta confirma o modelo e se é cloud; a troca vale para a próxima solicitação.
5. **Adicionar controles ao painel.** Carregar catálogo e configuração, mostrar modelo selecionado e `:cloud`, salvar seleção junto às preferências, não substituir seleção em falha de catálogo e exibir erro acionável. Cobrir renderização, ações e payloads com testes JS existentes.
6. **Integrar instalação e fazer regressão.** Remover modelo MiniMax fixo do wrapper e usar `OLLAMA_HOST`/seleção persistida nas configurações de desenvolvimento e pacote; manter executor local separado. Rodar testes Python de settings/state/client/loop, testes Node do painel/plugins, MCP e suíte Linux relevante.
7. **Validar no host.** Conferir que catálogo Ollama é obtido do host configurado; trocar pelo painel e por voz, fazer a próxima chamada com o modelo escolhido e reiniciar para confirmar persistência. Não enviar áudio/tela a cloud sem escolha explícita; se escolhido `:cloud`, o painel e a confirmação devem avisar o fluxo de dados.
8. **Atualizar documentação e matriz.** Registrar evidências, limitações e `git diff --check`; revisar se nenhum caminho aplica seleção a um executor local ou em uma solicitação anterior à confirmação.

## Verificação

- Testes unitários de settings, HTTP state, cliente OpenCode, loop e ferramentas MCP.
- Testes do frontend para catálogo, seleção, indicador cloud, erro e persistência.
- Teste de integração com servidor Ollama local mockado e ensaio real no host sem alteração de credenciais.

## Riscos

- O formato de model ID do OpenCode pode não ser idêntico à tag do Ollama; conversão deve ser central e testada.
- O loop de voz pode manter sessões separadas para conversa e visão; a escolha precisa alcançar ambas sem reutilizar resposta antiga.
- Uma seleção `:cloud` pode enviar transcrição e contexto visual ao provedor; avisar antes da troca e no painel.

# Pacotes Linux em desenvolvimento

O porte ainda está em validação. A disponibilidade de uma receita não significa
que áudio, captura e controle foram verificados em todas as distribuições.

## Arch Linux

No checkout, em ambiente Arch da mesma arquitetura do pacote:

```sh
scripts/build-package.sh --target arch --arch x86_64 --output "$PWD/dist/native"
sudo pacman -U dist/native/jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst
jarvis --doctor
jarvis --download-voice
jarvis-overlay
```

Para ARM64, use ambiente Arch Linux ARM e `--arch aarch64`. Essa arquitetura
está declarada na receita, mas ainda não foi compilada nem validada.
O pacote inclui overlay, plugins, MCP, agente e dependências Python privadas.
Os wheels são vinculados à versão minor do Python da distribuição; uma atualização
de Python exige reconstruir o pacote. A instalação não executa pip ou npm.
Modelos, configuração e autenticação ficam nos diretórios do usuário.

## Debian

A receita em `packaging/debian` compila no ambiente da distribuição. O Dockerfile
usa Debian trixie e Rust 1.95; não reaproveita o overlay compilado no Arch.

```sh
docker build -f packaging/debian/Dockerfile -t jarvis-linux-debian:local .
mkdir -p dist/native
docker run --rm -v "$PWD/dist/native:/out" jarvis-linux-debian:local
```

O build Debian está em andamento. Instalação, atualização, remoção e uso gráfico
ainda precisam ser verificados antes de tratar o DEB como release.

## Estado da validação

Foi gerado um pacote Arch x86_64 e verificado, após extração, o launcher, o
agente 1.18.23 e os imports de voz/MCP. Isso não substitui a instalação pelo
pacman em um sistema limpo. As demais receitas, Flatpak, ARM64 e a matriz de
ambientes gráficos continuam pendentes. Veja também `linux-verification.md`
em `docs/notes` para os testes reais já executados.

Os downloads do agente usam URLs e integridade SHA512 fixadas em
`packaging/opencode-sources.json`. As dependências Python são resolvidas durante
o build e registradas no relatório instalado; ainda não há lock completo de
wheels para builds reproduzíveis entre datas diferentes.

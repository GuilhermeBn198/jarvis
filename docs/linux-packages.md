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
sudo apt install ./dist/native/jarvis-assistant_0.1.0-1_amd64.deb
jarvis --doctor
jarvis-overlay
```

No ARM64, o nome do arquivo termina em `_arm64.deb`. Para atualizar, instale
o novo DEB com `apt install ./caminho/do/pacote.deb`; para remover, use
`sudo apt remove jarvis-assistant`.

Os DEBs x86_64 e ARM64 foram compilados no Debian 13 e passaram pela instalação com apt,
diagnóstico, imports, verificação de arquivos e remoção em container limpo,
preservando o dado de usuário usado no teste. Atualização de versão e uso
gráfico ainda precisam ser verificados antes de tratar o DEB como release.

## Ubuntu 24.04

A receita usa o mesmo controle Debian, mas compila o overlay e prepara os
wheels no Ubuntu 24.04, com o ABI Python 3.12 dessa distribuição. O toolchain
Rust oficial é fornecido separadamente; os binários do aplicativo são produzidos
no Ubuntu. Os builds x86_64 e ARM64 passaram pela instalação limpa, imports,
integridade e remoção na execução CI 38786962019. A execução gráfica instalada
segue em validação.

```sh
docker build -f packaging/ubuntu/Dockerfile -t jarvis-linux-ubuntu:local .
mkdir -p dist/ubuntu
docker run --rm -v "$PWD/dist/ubuntu:/out" jarvis-linux-ubuntu:local
sudo apt install ./dist/ubuntu/jarvis-assistant_0.1.0-1_amd64.deb
jarvis --doctor
jarvis-overlay
```

O runner ARM64 produz `_arm64.deb`. A CI constrói cada arquitetura no alvo,
instala com apt e verifica recursos, imports, integridade e remoção. O comando
`scripts/build-package.sh --target ubuntu --arch x86_64` exige um ambiente
Ubuntu com as dependências de build e Rust compatível já instalados.

## Estado da validação

Foi gerado um pacote Arch x86_64 e verificado, após extração, o launcher, o
agente 1.18.23 e os imports de voz/MCP. Também passaram, em container Arch limpo, a instalação com pacman,
a verificação de 8135 arquivos sem alterações e a remoção, preservando o dado de
usuário usado no teste. Atualização de versão e execução gráfica instalada
ainda estão pendentes. A CI também validou os DEBs x86_64 e ARM64 em runners
da arquitetura correspondente. As demais receitas, a validação completa do
Flatpak e a matriz de ambientes gráficos continuam pendentes. Veja também `linux-verification.md`
em `docs/notes` para os testes reais já executados.

Os downloads do agente usam URLs e integridade SHA512 fixadas em
`packaging/opencode-sources.json`. As dependências Python são resolvidas durante
o build e registradas no relatório instalado; ainda não há lock completo de
wheels para builds reproduzíveis entre datas diferentes.

## Fedora

A receita local Fedora está em `packaging/rpm/fedora/jarvis-assistant.spec`.
Ela usa as dependências Fedora GTK3/WebKit4.1 e `ffmpeg-free`, compila o overlay
no alvo e inclui um runtime Python privado vinculado ao ABI do sistema.
O RPM e o SRPM podem ser construídos no próprio Fedora:

```sh
scripts/build-package.sh --target fedora --arch x86_64 --output "$PWD/dist/native"
```

Há também um ambiente de build Fedora 44:

```sh
docker build -f packaging/rpm/fedora/Dockerfile -t jarvis-linux-fedora:local .
mkdir -p dist/native
docker run --rm -v "$PWD/dist/native:/out" jarvis-linux-fedora:local
sudo dnf install ./dist/native/jarvis-assistant-0.1.0-1.fc44.x86_64.rpm
jarvis --doctor
jarvis-overlay
```

No ARM64, use o RPM `.aarch64.rpm`. Para atualizar, use `sudo dnf upgrade
./caminho/do/pacote.rpm`; para remover, `sudo dnf remove jarvis-assistant`.
O arquivo `.src.rpm` contém fontes e receita e não instala a aplicação.

O RPM Fedora 44 x86_64 passou pela instalação com dnf, doctor, imports, versão
do agente, presença de pactl, verificação rpm e remoção com preservação do dado
de usuário usado no teste. Não há RPM publicado ou teste gráfico Fedora
concluído. O arquivo `packaging/targets.json` registra as famílias previstas,
separa receita disponível de validação e marca explicitamente os alvos cuja
implementação ainda está pendente. Suporte ARM64 declarado é um alvo de build,
não evidência de execução nessa arquitetura.

A CI acrescentou um teste de importação do AT-SPI que revelou a ausência de
`DBus-1.0.typelib` nas instalações mínimas Fedora x86_64 e ARM64. A receita
agora exige `gobject-introspection`; a correção passou pela instalação limpa, importação AT-SPI,
integridade e remoção em Fedora 44 x86_64 e ARM64 na execução CI 38764598505. O smoke anterior não incluía esse teste e não comprova que
a acessibilidade estava funcional.

## openSUSE Tumbleweed

A receita própria está em `packaging/rpm/suse`. Ela usa WebKit 4.1 fornecido por
`webkitgtk3-devel`, o Python padrão da distribuição e os pacotes GI/AT-SPI do
openSUSE. A CI 38797751372 validou builds e instalação em x86_64 e ARM64,
imports de voz/MCP/AT-SPI, integridade RPM, remoção e preservação de dados.
O teste gráfico isolado confirmou que uma segunda abertura mantém a janela
original e que a saída pela interface funciona. Voz e portais em desktops
openSUSE completos ainda precisam de validação.

```sh
docker build -f packaging/rpm/suse/Dockerfile -t jarvis-linux-suse:local .
mkdir -p dist/suse
docker run --rm -v "$PWD/dist/suse:/out" jarvis-linux-suse:local
sudo zypper install ./dist/suse/jarvis-assistant-0.1.0-1.x86_64.rpm
```

O artefato ARM64 termina em `.aarch64.rpm`. No próprio Tumbleweed com as
ferramentas de build, use `scripts/build-package.sh --target suse --arch x86_64`.
Essa receita ainda não foi validada no openSUSE Leap.

Os testes dos pacotes incluem uma sessão X11 e D-Bus privadas,
abertura repetida do overlay e fechamento pela interface. Esse teste usa um
launcher sem cérebro; não substitui voz, áudio e portais em GNOME/KDE reais.

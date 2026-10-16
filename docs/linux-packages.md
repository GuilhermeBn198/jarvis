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
preservando o dado de usuário usado no teste. O teste de abertura, segunda execução e saída da interface passou em X11
isolado. Atualização de versão e uso completo no desktop continuam pendentes.

## Ubuntu 24.04

A receita usa o mesmo controle Debian, mas compila o overlay e prepara os
wheels no Ubuntu 24.04, com o ABI Python 3.12 dessa distribuição. O toolchain
Rust oficial é fornecido separadamente; os binários do aplicativo são produzidos
no Ubuntu. Os builds x86_64 e ARM64 passaram pela instalação limpa, imports,
integridade, remoção e relançamento da interface em X11 isolado na execução
CI 38910794267. O uso completo no desktop segue em validação.

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

A [CI 38910794267](https://github.com/V1nic1us/jarvis/actions/runs/38910794267)
concluiu os nove testes nativos do commit `9ac3e30`:

| Família | Base | Arquiteturas com teste básico instalado |
|---|---|---|
| Arch | rolling | x86_64 |
| Debian | 13 | x86_64, aarch64 |
| Ubuntu | 24.04 | x86_64, aarch64 |
| Fedora | 44 | x86_64, aarch64 |
| openSUSE | Tumbleweed | x86_64, aarch64 |

Esses testes cobrem instalação pelo gerenciador nativo, diagnóstico, ABI e
imports Python privados, recursos, integridade, abertura e segunda execução da
interface em X11 isolado, saída e remoção preservando o dado de teste.
Não substituem a matriz de áudio, portais, GNOME/KDE e sessões reais.
Atualizações de versão dessas cinco famílias continuam pendentes.

Alpine e RHEL 10 têm receitas adicionais em validação, descritas abaixo.
Os demais alvos permanecem explicitamente pendentes em `packaging/targets.json`.
Veja também os testes reais registrados em `docs/notes/linux-verification.md`.

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
de usuário usado no teste. Não há RPM publicado em repositório oficial. O teste gráfico básico em X11
isolado passou; a validação do desktop completo permanece pendente. O arquivo `packaging/targets.json` registra as famílias previstas,
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

## ABI do Python em pacotes nativos

A preparação do pacote resolve o interpretador do alvo (por exemplo,
`/usr/bin/python3.14`) e cria um link privado em
`/usr/lib/jarvis/runtime/bin/python3`. O launcher e os comandos Python privados
usam esse ABI, mesmo se o alias `python3` mudar. Os RPMs exigem também o provider
GI da mesma versão, além de `python(abi)`. Isso não torna wheels compatíveis com
outro ABI; atualizações que removam o interpretador necessário precisam de um
pacote Jarvis reconstruído para a nova versão.

A regressão local simula a troca do alias e verifica o launcher instalado e o
comando Piper. A CI dos pacotes confere o interpretador e os imports com o ABI
registrado no manifesto de instalação.

## Runtime preparado com dependências da distribuição

Quando uma dependência como ONNX Runtime é fornecida pela distribuição, o
builder pode resolver os pacotes Python em um venv separado, criado com
`--without-pip --system-site-packages`. O pip do ambiente de build instala nesse
venv com `--python` e produz um relatório com `--report`. Nenhum desses comandos
é executado na instalação do pacote pelo usuário.

`prepare-package.py` aceita `--python-environment CAMINHO` e
`--python-report RELATORIO.json` no lugar de `--wheelhouse`. Ele verifica o ABI,
copia somente os módulos locais do venv e recria os comandos pelos metadados dos
pacotes, removendo referências ao caminho de build. Dependências disponíveis
somente no Python da distribuição continuam externas e precisam constar nas
dependências nativas da receita. Esse modo rejeita symlinks nos módulos,
redirecionamentos `.pth` e links de instalações editáveis. O venv deve conter
somente o runtime, sem ferramentas de build.

A regressão local remove o venv original e executa um comando do runtime
copiado. A validação do APK Alpine com as dependências de voz completas ainda
está pendente.


### Alpine 3.24: receita em validação

A receita local `packaging/alpine/APKBUILD` constrói CTranslate2 e Piper para
musl a partir de commits fixados. ONNX Runtime e NumPy vêm dos pacotes Alpine;
as demais dependências Python ficam privadas em `/usr/lib/jarvis/python`.
O agente usa o artefato musl com SHA512 verificado e permanece sem stripping.
A configuração do pacote limita apenas o OpenBLAS a uma thread para evitar
paralelismo aninhado com OpenMP; o CTranslate2 mantém seu paralelismo próprio.

Build completo em container descartável:

```sh
docker build -f packaging/alpine/Dockerfile -t jarvis-linux-alpine .
mkdir -p dist/alpine
docker run --rm -v "$PWD/dist/alpine:/export" jarvis-linux-alpine
```

Dentro de um ambiente Alpine com as dependências de build instaladas, um usuário
não root com chave `abuild` configurada também pode executar
`scripts/build-package.sh --target alpine --output dist/alpine`.
O build precisa de rede; a instalação não executa pip ou downloads de modelos.
O catálogo mantém esta receita como **não verificada** até a conclusão do build
e dos testes de instalação/atualização/remoção. Os testes de voz e interface
x86_64 em ambientes de desenvolvimento não certificam o APK nem ARM64.

### Família RHEL 10: receita em validação

A base de build é AlmaLinux 10, com EPEL e CRB. A receita principal fica em
`packaging/rpm/rhel/jarvis-assistant.spec`. O driver também constrói um RPM
`xdotool` a partir do commit upstream fixado na receita de dependência, pois
os repositórios consultados dessa base não oferecem esse pacote. Os RPMs
binários e de código-fonte são exportados juntos:

```sh
docker build -f packaging/rpm/rhel/Dockerfile -t jarvis-linux-rhel .
mkdir -p dist/rhel
docker run --rm -v "$PWD/dist/rhel:/out" jarvis-linux-rhel
```

O build completo dos dois RPMs e seus SRPMs passou em AlmaLinux 10 x86_64.
Em um container limpo também passaram instalação, ABI/imports privados, recursos,
interface Wayland em Weston isolado, integridade e remoção preservando os dados
de teste. O catálogo registra **installed-smoke** para x86_64 e aarch64: os dois jobs
RHEL da [CI 38947707383](https://github.com/V1nic1us/jarvis/actions/runs/38947707383)
passaram nos testes instalados da arquitetura correspondente.
Atualização de versão, áudio, portais e desktops reais continuam pendentes.
A seleção de repositórios da imagem de build é específica do AlmaLinux; os testes
não certificam outras distribuições da família.

### Void glibc: receita em preparação

A receita local `packaging/void/template` usa o XBPS nativo e mantém o Python
privado vinculado ao ABI 3.14 da distribuição. O driver fixa o commit da coleção
`void-packages` e verifica o SHA256 do arquivo de fontes do checkout. O builder
`packaging/void/Dockerfile` prepara uma imagem descartável com o modo `ethereal`
oferecido pelo próprio `xbps-src`; esse modo modifica a raiz do ambiente e deve
permanecer restrito ao container de build.

O pacote XBPS ainda não foi compilado nem validado. A variante musl depende da
construção nativa do ONNX Runtime, ausente nos repositórios Void consultados;
ela não reutiliza as bibliotecas glibc. Ambas as variantes continuam marcadas
como **não verificadas** no catálogo.

# Pacotes Linux em desenvolvimento

O porte ainda está em validação. A disponibilidade de uma receita não significa
que áudio, captura e controle foram verificados em todas as distribuições.

## NixOS

A flake da raiz fornece `jarvis-assistant` para x86_64-linux e aarch64-linux.
Ela fixa nixpkgs pelo `flake.lock`, compila o overlay com Rust e monta o runtime
Python imutável com dependências do nixpkgs e Piper 1.8.0 fixado. A instalação
não executa pip nem npm. O pacote coloca a aplicação sob o prefixo do Nix Store
e adiciona os binários de áudio e controle ao wrapper do launcher.

Instale diretamente pelo Nix:

```sh
nix --extra-experimental-features "nix-command flakes" profile install .#jarvis-assistant
jarvis --doctor
```

Depois de compilar um output, o ciclo de instalação, verificação do runtime,
remoção e preservação dos dados pode ser repetido em um ambiente Nix descartável:

```sh
sh scripts/test-nix-package.sh "$(readlink -f ./dist/nix/jarvis-assistant)"
```

Para incluir também o smoke do overlay X11 em Xvfb/AT-SPI, instale os pacotes
de teste `xvfb`, `dbus-x11`, `python3-gi`, `gir1.2-atspi-2.0` e `at-spi2-core`
e acrescente `--gui` ao comando.

Ou construa um link do pacote para inspeção:

```sh
scripts/build-package.sh --target nix --output "$PWD/dist/nix"
```

Remova o perfil com `nix profile list` para localizar o índice do Jarvis e
`nix profile remove <índice>`. Builds e ciclo de instalação/verificação/remoção
passaram em x86_64 e AArch64 na CI, com smoke do overlay em Xvfb/D-Bus. A CI
AArch64 executou o pacote no runner ARM; isso ainda não substitui validação numa
sessão NixOS real nem testes com áudio físico e portais. Veja o registro em
`docs/notes/linux-verification.md`.


## Arch Linux

No checkout, em ambiente Arch da mesma arquitetura do pacote:

```sh
scripts/build-package.sh --target arch --arch x86_64 --output "$PWD/dist/native"
sudo pacman -U dist/native/jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst
jarvis --doctor
jarvis --download-voice
jarvis-overlay
```

Para ARM64, use ambiente Arch Linux ARM e `--arch aarch64`. O pacote foi
compilado e passou pelo ciclo de instalação, verificação do overlay em Xvfb e
remoção sob QEMU; o `makepkg` do Arch Linux ARM gera `.pkg.tar.xz` por padrão.
O teste em hardware ARM físico e numa sessão desktop/áudio completa ainda está
pendente.
O pacote inclui overlay, plugins, MCP, agente e dependências Python privadas.
Os wheels são vinculados à versão minor do Python da distribuição; uma atualização
de Python exige reconstruir o pacote. A instalação não executa pip ou npm.
Modelos, configuração e autenticação ficam nos diretórios do usuário.

Em container Arch rolling x86_64, o pacman atualizou o artefato anterior
`0.1.0-1` para o pacote reconstruído do código atual (`0.1.0-2` de teste).
`jarvis --doctor`, OpenCode 1.18.23, `pacman -Qkk`, a preservação do arquivo de
dados do usuário e a remoção passaram. O número de revisão `-2` foi usado só no
ensaio; não altera a revisão da receita publicada no checkout.

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
isolado. A atualização Debian x86_64 de `0.1.0-1` para uma reconstrução de teste
`0.1.0-2` passou com `apt`, preservando dados e integridade; atualização ARM64 e
uso completo no desktop continuam pendentes.

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

Alpine 3.24 e RHEL 10 também passaram por smoke instalado em x86_64 e ARM64;
as lacunas de desktop, áudio e atualização entre versões estão descritas abaixo.
Slackware current tem um SlackBuild local; build, instalação e imports do runtime
foram exercitados em container x86_64, incluindo a reinicialização isolada do
overlay e remoção preservando os dados do usuário. O catálogo registra
**installed-smoke** para x86_64. A receita inclui xdotool, xclip e wl-clipboard
compilados de revisões fixas porque não há pacotes oficiais current para esses
helpers; desktop e áudio reais seguem pendentes.
Solus tem uma receita `package.yml`; build e ciclo eopkg foram validados em
x86_64, incluindo imports privados, integridade, relançamento isolado do overlay,
remoção e preservação dos dados do usuário. Desktop e áudio reais continuam
pendentes. Guix tem receita local e passou por build e ciclo de perfil instalado
em container GNU Guix x86_64; isso ainda não valida desktop ou áudio reais.
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
de usuário usado no teste. Também passou por uma atualização real de `0.1.0-1`
para `0.1.0-2` com DNF, preservando os dados e passando `rpm -V`; o ciclo do
pacote atualizado e o relançamento do overlay em Xvfb também passaram. Não há
RPM publicado em repositório oficial. A validação do desktop completo e do
áudio físico permanece pendente. O arquivo `packaging/targets.json` registra as famílias previstas,
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
original e que a saída pela interface funciona. A atualização de `0.1.0-1` para
`0.1.0-2` pelo Zypper também passou, preservando dados do usuário e verificando
a integridade RPM. Voz e portais em desktops openSUSE completos ainda precisam
de validação.

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
copiado. O APK Alpine x86_64 construído das fontes passou pelos imports do
runtime de voz completo em uma instalação limpa. Síntese e transcrição offline
CPU também passaram com áudio sintético usando o APK instalado; microfone e
integração de áudio em desktop real continuam pendentes.


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
Os APKs completos x86_64 e aarch64 passaram pela instalação assinada em Alpine
limpo, pelos imports e ABI privados, pelos recursos e ferramentas, pela interface
isolada X11 (reabertura e saída), pela integridade e pela remoção preservando
dados de teste. Os dois jobs Alpine da [CI 38953368727](https://github.com/V1nic1us/jarvis/actions/runs/38953368727)
passaram; o catálogo registra **installed-smoke** para ambas as arquiteturas.
O APK x86_64 passou também pela atualização assinada r0→r1 construída das fontes
completas, preservando hashes de configuração, cache e dados do modelo; o teste
está em `.superpowers/sdd/2026-10-14-jarvis-linux/alpine-full-source-signed-upgrade-retry.log`.
A atualização aarch64, microfone e desktops reais seguem pendentes. O APK x86_64
instalado também sintetizou e transcreveu uma frase de teste em português, sem
rede, usando Piper e Whisper tiny/CPU int8. O erro por palavra
foi 13,3%; esse ensaio sintético não certifica captura de microfone nem qualidade
de reconhecimento em situações reais.

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

### Void glibc: ciclo instalado x86_64 validado

A receita local `packaging/void/template` usa o XBPS nativo e mantém o Python
privado vinculado ao ABI 3.14 da distribuição. O driver fixa o commit da coleção
`void-packages` e verifica o SHA256 do arquivo de fontes do checkout. O builder
`packaging/void/Dockerfile` prepara uma imagem descartável com o modo `ethereal`
oferecido pelo próprio `xbps-src`; esse modo modifica a raiz do ambiente e deve
permanecer restrito ao container de build. A receita declara Mesa em runtime:
o WebKitGTK precisa de um backend EGL no Void. Um teste sem Mesa reproduziu a
falha EGL e a janela inacessível; instalado Mesa, o relançamento GTK passou.

A revisão XBPS `_2` foi gerada diretamente com `xbps-src`. Num ambiente sem
Mesa, o XBPS instalou Mesa automaticamente pela dependência declarada. Doctor,
imports/ABI privados, recursos, integridade, janela X11 em Xvfb, remoção e
preservação de dados passaram. O artefato e o log de validação estão em
`.superpowers/sdd/2026-10-14-jarvis-linux/void-glibc-native-artifacts` e
`void-glibc-xbps-src-v2-lifecycle.log`. Também passou uma atualização XBPS da
revisão `_1` para `_2`, com doctor antes e depois e sentinel dos dados do usuário
preservado; isso não substitui atualização entre versões de aplicativo
publicadas. Desktop real, áudio e aarch64 seguem pendentes.

A variante musl tem uma receita XBPS em `packaging/void-musl/template`, que
compila ONNX Runtime 1.24.4 dentro do build nativo em vez de reutilizar wheels
glibc. A revisão `_2` foi construída por `xbps-src` e passou pelo ciclo XBPS
x86_64: instalação, `jarvis --doctor`, ABI/imports privados e AT-SPI, smoke
Xvfb de xdotool/xclip, reabertura do overlay, verificação do banco de pacotes,
remoção e preservação de dados do usuário. O artefato e o log estão em
`.superpowers/sdd/2026-10-14-jarvis-linux/void-musl-native-artifacts` e
`void-musl-native-lifecycle.log`. Desktop real, áudio, portais, atualização
entre versões reais e aarch64 continuam pendentes. O XBPS também passou uma
atualização controlada da revisão `_1` para `_2`, com `jarvis --doctor` antes e
depois e sentinel dos dados do usuário preservado; isso ainda não substitui uma
atualização entre versões de aplicativo publicadas.

### Gentoo rolling: pacote local em validação

O driver `scripts/build-package.sh --target gentoo --output dist/gentoo`
prepara um overlay local, registra o arquivo de fontes sanitizado no Manifest e
usa `ebuild package` para gerar um pacote `gpkg`. O ambiente precisa de Portage,
Git e das dependências de build da receita. A receita fixa Python 3.14 e WebKit
no slot 4.1, exige os recursos de captura/reprodução do FFmpeg e preserva o
payload do agente sem stripping. As dependências privadas são resolvidas durante
o build; a instalação não executa pip nem baixa modelos.

O gpkg atualizado foi compilado e instalado pelo Portage nativo em x86_64.
`jarvis --doctor`, os 7.355 caminhos do manifesto, os imports privados e ABI
Python, AT-SPI, os ganchos de cache XDG, o relançamento em Weston headless e a
remoção preservando um sentinel de dados passaram. O artefato e o log de
validação estão em `.superpowers/sdd/2026-10-14-jarvis-linux/gentoo-native-artifacts`
e `gentoo-native-revised-lifecycle.log`. O catálogo marca **installed-smoke**
somente para x86_64. Atualização e aarch64 seguem pendentes. O overlay é local e
não implica publicação no repositório oficial.

### Slackware current: SlackBuild local

`packaging/slackware/jarvis.SlackBuild` produz um pacote `.txz` local para
x86_64. O ambiente de build precisa de Python 3.10+, pip, Rust/Cargo, Node.js/
npm, pkg-config e headers GTK+3/WebKitGTK 4.1. O SlackBuild verifica essas
ferramentas antes de compilar. Slackware não resolve dependências de runtime
automaticamente: instale primeiro as dependências listadas em
`/usr/doc/jarvis-assistant-0.1.0/README` dentro do pacote.

WebKitGTK 4.1 não aparece na
[lista de pacotes oficial do Slackware current](https://mirrors.slackware.com/slackware/slackware64-current/PACKAGES.TXT).
No Slackware 15.0, há um SlackBuild comunitário para
[`webkit2gtk4.1`](https://slackbuilds.org/repository/15.0/libraries/webkit2gtk4.1/),
validado para essa versão e que requer unifdef, libsoup3, wpebackend-fdo,
bubblewrap, geoclue2 e xdg-dbus-proxy. No current x86_64, o
repositório comunitário [slackware.lngn.net](https://slackware.lngn.net/) publica
o conjunto `webkitgtk`; depois de configurar o slackpkg+ conforme as instruções
do repositório, instale-o com `slackpkg install webkitgtk`. O [Python 3 do
Slackware 15.0](https://packages.slackware.com/?p=python3-3.9.25-x86_64-1_slack15.0.txz&r=slackware64-15.0)
é 3.9, abaixo do mínimo 3.10 do projeto; é necessário
disponibilizar Python 3.10+ no ambiente de build e runtime dessa versão.

```sh
scripts/build-package.sh --target slackware --arch x86_64 --output "$PWD/dist/native"
sudo installpkg dist/native/jarvis-assistant-0.1.0-x86_64-1_local.txz
jarvis --doctor
# Após gerar uma revisão superior, por exemplo com BUILD=2:
BUILD=2 scripts/build-package.sh --target slackware --arch x86_64 --output "$PWD/dist/upgrade"
sudo upgradepkg dist/native/jarvis-assistant-0.1.0-x86_64-1_local.txz%dist/upgrade/jarvis-assistant-0.1.0-x86_64-2_local.txz
sudo removepkg jarvis-assistant-0.1.0-x86_64-2_local
```

Em um container Slackware descartável com dependências gráficas e de áudio já
instaladas, valide o ciclo completo e o overlay X11 isolado usando:

```sh
scripts/test-native-package.sh slackware "$PWD/dist/native/jarvis-assistant-0.1.0-x86_64-1_local.txz"
```

Slackware 15.0 fornece Python 3.9, abaixo do mínimo de Python 3.10 deste
projeto; o alvo de build é Slackware current. A receita compila xdotool
4.20260303.1, xclip 0.13 e wl-clipboard 2.3.0 de commits fixos e os instala em
`/usr/lib/jarvis/bin`, priorizado pelo launcher. As licenças dos helpers são
incluídas no pacote. O build x86_64 no container current passou e o pacote foi
instalado com `installpkg`;
`jarvis --doctor`, OpenCode 1.18.23, imports Python privados e o typelib AT-SPI
passaram. O teste da janela X11 e da remoção preservando um sentinel também
passou. O overlay compilado no Slackware passou também pelo teste de reabertura
e saída sob Weston/Wayland em um container Gentoo; esse teste cruzado não
substitui Wayland nativo no Slackware. Piper também sintetizou offline uma frase
para WAV mono a 22.050 Hz com o modelo baixado e verificado pelo projeto. O
catálogo continua como `unverified`: as bibliotecas transitivas oficiais foram
instaladas e verificadas por MD5; `ldd` não encontrou dependências ausentes em
ffmpeg, ffplay e pactl. `pactl --version`, captura FFmpeg para ALSA `null`,
reprodução via ffplay nesse dispositivo e a captura `capture.record` do Jarvis
com `AUDIO_BACKEND=alsa` passaram. Piper também sintetizou e reproduziu uma
frase via ALSA `null`. Microfone/alto-falantes físicos, servidor PulseAudio em
sessão, clipboard Wayland com seat, atualização entre versões distintas e
aarch64 permanecem pendentes. O catálogo registra **installed-smoke** para
x86_64. Para instalações mínimas,
confira bibliotecas transitivas de ffmpeg/ffplay com `ldd /usr/bin/ffmpeg
/usr/bin/ffplay`; o fechamento pode incluir muitos pacotes, inclusive
`vulkan-sdk`. WebKitGTK 4.1 no current foi obtido do repositório comunitário
citado acima.

No catálogo oficial current, `ffmpeg` fornece `ffmpeg`/`ffplay`, `pulseaudio`
fornece `pactl` e `alsa-utils` fornece `arecord`; xdotool, wl-clipboard e xclip
não aparecem como pacotes oficiais. O SlackBuild compila os três helpers e os
inclui no pacote Jarvis. `scripts/test-native-package.sh` verifica os comandos
depois da instalação e executa um teste de xdotool e roundtrip xclip em Xvfb.
Build e roundtrip X11 passaram no current; clipboard Wayland ainda requer um
compositor com seat.

### Solus: receita eopkg e smoke instalado

`packaging/solus/package.yml` descreve a receita nativa do Solus para x86_64.
O driver cria um arquivo-fonte do checkout, injeta seu SHA256 e URI local na
receita e chama `solbuild`; assim, alterações locais ainda não publicadas podem
ser compiladas. Inicialize e atualize o ambiente de build do Solus uma vez com
`sudo solbuild init -u`, então construa e instale:

```sh
scripts/build-package.sh --target solus --arch x86_64 --output "$PWD/dist/solus"
sudo eopkg install ./dist/solus/jarvis-assistant-0.1.0-1-1-x86_64.eopkg
jarvis --doctor
```

Para atualizar, instale o novo `.eopkg` com `sudo eopkg install
./dist/solus/<arquivo>.eopkg`; para remover, use `sudo eopkg remove
jarvis-assistant`. O pacote foi compilado com `solbuild`, instalado e removido
com eopkg em Solus 4.9 x86_64. Imports privados, ABI, OpenCode 1.18.23,
integridade, relançamento isolado da janela e preservação dos dados passaram; o
catálogo registra **installed-smoke** para x86_64. Desktop e áudio reais,
atualização de versão e Wayland nativo continuam pendentes. O log está em
`docs/notes/linux-verification.md` e no artefato local indicado na matriz.
`networking: true` permite que o build atual baixe dependências npm/Python e o
agente; a instalação do pacote não baixa dependências da aplicação.
Depois de gerar o `.eopkg`, rode o ciclo em um container Solus x86_64:

```sh
scripts/test-native-package.sh solus "$PWD/dist/solus/jarvis-assistant-0.1.0-1-1-x86_64.eopkg"
```

### GNU Guix: pacote nativo local

`packaging/guix/jarvis.scm` define o pacote Guix para x86_64. O driver cria um
arquivo-fonte determinístico, instala `node_modules` a partir do lockfile e
baixa o OpenCode fixado antes de chamar `guix build`; os crates Rust são
declarados por hashes Guix em `packaging/guix/cargo-crate-sources.scm` e usados
offline dentro da derivação.

Em um sistema com GNU Guix, Python 3, npm e acesso aos substituters:

```sh
scripts/build-package.sh --target guix --arch x86_64 --output "$PWD/dist/guix"
guix package --install "$(readlink -f ./dist/guix/jarvis-assistant)"
jarvis --doctor
```

Em um container GNU Guix descartável, o ciclo de instalação em perfil isolado,
imports Python, remoção e preservação de dados pode ser exercitado com:

```sh
sh scripts/test-guix-package.sh "$(readlink -f ./dist/guix/jarvis-assistant)"
```

O build local do Guix e o smoke de perfil instalado passaram em x86_64 num
container GNU Guix (7 testes Rust, imports Python via caminho do launcher,
OpenCode 1.18.23, remoção do perfil e preservação dos dados do usuário). Isso
valida o pacote e seu lifecycle headless; desktop real, áudio/microfone e
Wayland/X11 permanecem sem teste Guix. A receita cobre x86_64; aarch64 ainda
precisa de uma fonte ONNX Runtime compatível e validação própria.

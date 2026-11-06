# Porte nativo do Jarvis para Linux

## Objetivo e autorização

O usuário pediu: “Faça o porte para linux que funcione em toda distro linux”.
Em 2026-10-14 aprovou a direção: execução nativa, voz e overlay, X11 e
Wayland, distribuição Flatpak e instalação pelo código-fonte.
Também pediu instalação pelo gerenciador de pacotes de cada distro, com
pacote ou receita nativa correspondente. Essa entrega é adicional ao Flatpak.
Este documento detalha essa direção para revisão antes da implementação.

O resultado deve preservar conversa por voz, visão, ações, contexto textual,
arquivos, configurações, streaming, gatilhos e controle do cérebro pelo overlay.
Windows/WSL continuam suportados. O caminho Linux não exige Windows,
PowerShell, caminhos `/mnt/c`, dispositivos DirectShow ou serviços WSL.

“Toda distro” exige um caminho comum via runtime Flatpak e caminhos nativos
por família de gerenciadores, sem acoplar o aplicativo a uma distribuição.
Não é possível certificar literalmente todas as versões, arquiteturas e
compositores existentes. A documentação deve distinguir suporte por contrato,
ambientes efetivamente testados e capacidades ausentes no sistema hospedeiro.
Não reduzir o porte a voz ou a X11 para declarar sucesso.

## Estado observado

- `voice/config.py` define ferramentas e arquivos no perfil Windows.
- `voice/capture.py` usa DirectShow nos três modos e na calibração.
- `voice/tts.py` usa Piper Windows ou SAPI; `vision.py` usa gdigrab.
- Plugins `act-tools` e `winfs-tools` executam PowerShell.
- MCP `win_context` usa UI Automation e processos Windows.
- `start_brain` no overlay retorna erro fora do Windows.
- O bundle Tauri está desativado e não existe distribuição Linux.
- Baseline: `python3 -m pytest voice/tests -q`: 317 testes passaram.
  Esses testes não constituem validação de um desktop Linux real.

## Arquitetura

Introduzir uma camada de capacidades de plataforma, separada da lógica de
conversa. Identificar Linux nativo, Windows/WSL e sessão gráfica. Detectar
ferramentas e interfaces realmente disponíveis; não escolher backend pelo nome
da distro. Overrides explícitos continuam tendo precedência sobre settings e
defaults. WSL permanece identificável e selecionável explicitamente.

Cada capacidade retorna resultado verificável ou erro específico com a
dependência/permissão necessária. Backend indisponível não pode produzir
mensagem de sucesso. Uma sessão Wayland não deve cair silenciosamente em
automação X11 que só alcança janelas XWayland.

Os módulos Python de plataforma expõem operações de áudio, screenshot,
desktop e arquivos. Plugins TypeScript preservam nomes e parâmetros atuais,
despachando para Windows ou para um bridge Python Linux por subprocesso com
argumentos separados e entrada/saída JSON. O bridge não interpreta shell.
O SafetyGate continua na fronteira das ferramentas antes da execução.

## Áudio e voz

Captura Linux usa FFmpeg com PulseAudio, que também atende instalações
PipeWire com servidor de compatibilidade. ALSA é alternativa explícita quando
o servidor de áudio não existe. O dispositivo padrão é `default`; seleção,
listagem e calibração funcionam pelos mesmos backends.
Os modos auto, fixed e ptt preservam VAD, limites e limpeza de processos.
Arquivos temporários são exclusivos por operação e removidos após uso.

Piper e reprodução FFplay usam executáveis nativos e caminhos POSIX.
Modelo e configuração de voz ficam no diretório de dados XDG. O instalador
oferece obtenção verificável de uma voz portuguesa e informa tamanho/licença.
Se um fallback Linux adicional for disponibilizado, deve ser declarado nas
configurações e diagnosticado; SAPI só aparece em plataformas compatíveis.
STT continua com faster-whisper; CPU é obrigatória e GPU é opcional.

## Visão e automação do desktop

X11: screenshot via backend nativo; entrada por ferramentas X11 com argumentos
validados; descoberta de janelas e acessibilidade por interfaces apropriadas.
Testar Unicode, teclas, coordenadas, monitores e fatores de escala.

Wayland: screenshot pelo portal Screenshot. Automação de entrada requer
sessão RemoteDesktop autorizada pelo usuário; usar coordenadas coerentes com
o stream/desktop selecionado. O componente que mantém a sessão é persistente
durante o uso e a encerra quando revogada ou ao sair. Negação, cancelamento,
timeout e desaparecimento do portal são resultados distintos.

AT-SPI oferece contexto e ações sem foco onde a aplicação os expõe. Requests
de background não podem ativar uma janela como fallback automático. Se não
houver suporte, informar a limitação e exigir uma nova escolha de foreground.
IDs de janela Linux são opacos; o parâmetro legado `hwnd` continua Windows.
Preservar aliases de ferramentas existentes, introduzindo nomes neutros para
o novo contexto e atualizando os prompts dos agentes por capacidade.

Listagem universal de janelas e always-on-top não são garantidos por Wayland.
Quando o compositor não expuser essas funções, mostrar indisponibilidade e
permitir operar por contexto acessível e screenshot autorizado. Não tratar
essa limitação como equivalência funcional já verificada.

## Contexto e arquivos

O MCP seleciona contexto Linux ou Windows, sem tentar PowerShell no Linux.
Linux oferece processos locais, clipboard apropriado à sessão e árvore AT-SPI
com limites de nós, profundidade e tempo. Ausência de sessão gráfica é
diagnosticada; o bridge textual continua utilizável.

Leitura/escrita Linux usa caminhos locais, sem conversão de drives.
Escrita mantém confirmação e allowlist explícita, resolve caminhos reais e
impede fuga por links simbólicos. Preservar regras de credenciais e operações
destrutivas. Não conceder acesso irrestrito ao filesystem no Flatpak para
contornar a escolha de arquivos: usar portais e diretórios autorizados.

## Overlay, configuração e ciclo de vida

Tauri inicia o cérebro diretamente no Linux, acompanha o processo e encerra
seus filhos sem `pkill` global. Reinício não duplica captura nem servidor.
Logs, settings, modelos e estado seguem XDG; o comando do cérebro continua
sobrescrevível. O overlay preserva menu, estados, medição, seleção de
microfone e anti-órfão. Configurações mostram apenas backends utilizáveis.
Instalação oferece entrada `.desktop` e autostart opt-in sem exigir systemd.
Em Wayland, a apresentação respeita o compositor; oferecer janela acessível
quando a posição/empilhamento do orbe não puderem ser controlados.

## Empacotamento

Flatpak é o caminho comum entre distros: empacotar overlay, cérebro, plugins,
MCP, Python e dependências, FFmpeg/Piper e o agente necessário para operação.
Escolher e fixar runtime/SDK suportados no momento da implementação.
Build usa versões e hashes verificáveis; não depende de baixar pacotes
durante execução. Modelos STT/TTS e autenticação são configurados no primeiro
uso, com erros claros quando offline.

Rede e socket de áudio são necessários. Wayland e fallback X11 atendem GUI;
portais atendem recursos mediados pelo desktop. Acesso AT-SPI deve ser
especificado e testado. Não depender de `flatpak-spawn --host` para o caminho
principal: ferramentas instaladas somente no host não estão automaticamente
disponíveis no sandbox. Aplicativos locais são abertos por integração desktop
autorizada, sem executar texto arbitrário em shell.

Instalação por fonte usa script POSIX, venv e diagnóstico de dependências,
sem exigir apt, dnf, pacman ou systemd. Listar dependências por função e dar
exemplos de instalação por família de distros. Empacotar inicialmente x86_64
e aarch64; artefatos e suporte só são anunciados após build e validação de
dependências em cada arquitetura.

### Pacotes nativos por gerenciador

Entregar receitas de build e pacotes instaláveis no formato de cada família,
com o mesmo código e versão do aplicativo. O gerenciador deve registrar
arquivos, resolver dependências declaradas e permitir atualização e remoção.
Um script que só instala dependências e copia arquivos não substitui o pacote.

| Família / exemplos | Gerenciador | Entrega nativa |
| --- | --- | --- |
| Debian, Ubuntu e derivados | apt / dpkg | `.deb` e fonte `debian/` |
| Fedora, RHEL e derivados | dnf / yum / rpm | `.rpm` e spec RPM por alvo |
| openSUSE | zypper / rpm | `.rpm` e spec adaptada às dependências SUSE |
| Arch, Manjaro e derivados | pacman | `PKGBUILD` e `.pkg.tar.zst` |
| Alpine | apk | `APKBUILD` e `.apk` compilado para musl |
| Void | xbps | template e pacote `.xbps` por variante libc |
| Gentoo | emerge / Portage | ebuild e metadados de overlay |
| NixOS e ambientes Nix | nix | derivação, flake e integração desktop |
| GNU Guix | guix | definição de pacote em canal instalável |
| Slackware | installpkg / upgradepkg / slackpkg | SlackBuild e `.txz` |
| Solus | eopkg | receita e pacote `.eopkg` |

Guardar essas receitas em `packaging/`, por família. Compartilhar recursos
comuns (launcher, desktop entry, ícones e metadados) e separar dependências
específicas. Identificar distribuição e versão por `/etc/os-release` apenas
para orientar instalação; não selecionar pela primeira ferramenta encontrada
no PATH. Permitir escolha explícita do formato/alvo e documentar o comando
real para instalar o artefato local ou a receita de cada gerenciador.

Pacotes binários precisam de builds compatíveis com a ABI de cada alvo;
um RPM Fedora não deve ser anunciado como RPM universal. Receitas baseadas
em fonte também são entregas nativas para gerenciadores que usam esse modelo.
Em musl, compilar e verificar as dependências nativas de STT/TTS e GUI em vez
de reutilizar wheels/binários glibc. Dependências sem pacote no alvo exigem
receitas auxiliares ou inclusão controlada no pacote, com licenças e hashes.
Não substituir o aplicativo completo por um pacote vazio que chama Flatpak.

Build e instalação não executam `pip install` ou downloads como root em
scripts de pós-instalação. Não modificar o Python do sistema; usar dependências
da distro ou ambiente privado preparado no build. Modelos e credenciais
continuam pertencendo ao usuário e não são removidos ao desinstalar o pacote.

Publicar artefatos de release com checksums, versão, arquitetura, distro-alvo
e instruções de instalação/atualização. Não pressupor inclusão em repositórios
oficiais, AUR, Flathub ou canais externos: isso é uma publicação separada.
Para famílias adicionais identificadas durante o porte, incluir adaptador de
empacotamento e validação próprios; nenhuma lista finita comprova cobertura
literal de todos os gerenciadores existentes.

## Validação e critérios de entrega

1. Testes existentes de Python, MCP e SafetyGate continuam passando; novos
   testes verificam seleção de plataforma e falhas, além dos contratos Linux.
2. Build Tauri Linux e build/instalação Flatpak reais, incluindo arranque pelo
   launcher instalado, plugins e MCP. Um manifesto isolado não basta.
3. Executar matriz em Ubuntu/Debian, Fedora, Arch e openSUSE, com GNOME e KDE
   Wayland e pelo menos um desktop X11; testar instalação fonte também em
   ambiente musl quando suas dependências forem compiláveis. Registrar
   versões, arquitetura, sessão e evidências; container não prova GUI/áudio.
4. Em desktops reais: selecionar/gravar mic, VAD/PTT/fixed, STT, TTS normal e
   streaming, captura autorizada, ações de texto/tecla/click/open, contexto,
   arquivos autorizados e bloqueados, menu e reinício/saída do overlay.
5. Wayland: consentimento, cancelamento, revogação, timeout e monitor/escala;
   demonstrar ação em aplicativo Wayland nativo, além de XWayland.
6. Testar acesso em background sem roubar foco/cursor e erro honesto onde
   não for suportado. Nunca anunciar ação confirmada a partir de mero envio.
7. Instalação limpa sem caminhos de desenvolvedor, sem Windows e sem
   dependências implícitas do host; verificação em x86_64 e aarch64.
8. README, documentação e diagnóstico descrevem instalação, permissões,
   dependências, limites comprovados e recuperação. A meta não é concluída
   enquanto houver requisito não implementado ou não verificado.
9. Para cada família da tabela de pacotes nativos, construir em ambiente limpo,
   instalar pelo gerenciador correspondente, verificar dependências e launcher,
   atualizar de uma versão anterior e remover sem deixar arquivos de sistema
   órfãos nem apagar dados do usuário. Verificar x86_64 e aarch64 onde o alvo
   suporta essas arquiteturas; registrar variantes libc e versões dos alvos.
   Receita escrita sem build/instalação real não comprova a entrega.
10. Inspecionar conteúdo, metadados, licenças e scripts dos pacotes; executar
    os validadores de cada formato. Em distros imutáveis, testar o método
    nativo aplicável e manter o Flatpak como opção, sem exigir alteração
    arbitrária da imagem do sistema. Testes de pacote em container não
    substituem os testes funcionais de desktop da matriz.

## Sequência proposta

Primeiro plataforma/configuração e áudio; depois visão, automação/contexto e
arquivos; em seguida overlay/ciclo de vida; finalmente distribuição e matriz
de validação, incluindo cada família de pacotes nativos. Cada etapa mantém
regressão Windows e adiciona evidência Linux.
O plano de implementação será escrito após revisão desta especificação.

## Referências oficiais consultadas

- https://docs.flatpak.org/en/latest/flatpak-command-reference.html
- https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html
- https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html
- https://www.debian.org/doc/manuals/debian-faq/pkg-basics.en
- https://rpm.org/docs/4.20.x/manual/spec.html
- https://man.archlinux.org/man/PKGBUILD.5
- https://wiki.alpinelinux.org/wiki/APKBUILD_Reference

# Porte nativo do Jarvis para Linux

## Objetivo e autorização

O usuário pediu: “Faça o porte para linux que funcione em toda distro linux”.
Em 2026-10-14 aprovou a direção: execução nativa, voz e overlay, X11 e
Wayland, distribuição Flatpak e instalação pelo código-fonte.
Este documento detalha essa direção para revisão antes da implementação.

O resultado deve preservar conversa por voz, visão, ações, contexto textual,
arquivos, configurações, streaming, gatilhos e controle do cérebro pelo overlay.
Windows/WSL continuam suportados. O caminho Linux não exige Windows,
PowerShell, caminhos `/mnt/c`, dispositivos DirectShow ou serviços WSL.

“Toda distro” significa independência do gerenciador de pacotes e das
bibliotecas particulares de uma distribuição, usando um runtime Flatpak.
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

## Sequência proposta

Primeiro plataforma/configuração e áudio; depois visão, automação/contexto e
arquivos; em seguida overlay/ciclo de vida; finalmente distribuição e matriz
de validação. Cada etapa mantém regressão Windows e adiciona evidência Linux.
O plano de implementação será escrito após revisão desta especificação.

## Referências oficiais consultadas

- https://docs.flatpak.org/en/latest/flatpak-command-reference.html
- https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html
- https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html

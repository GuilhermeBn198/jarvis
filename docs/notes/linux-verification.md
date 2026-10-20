# Evidências do porte Linux — execução em andamento

Worktree: `.worktrees/linux-port`, branch `feat/linux-port`.
Não é uma declaração de suporte universal ou conclusão do porte.

A [matriz por distribuição e arquitetura](linux-matrix.json) registra resultados
com comandos e evidências. Os relatos abaixo são históricos: uma pendência
registrada numa etapa anterior pode ter sido resolvida depois. A matriz distingue
o ciclo de instalação em container, a fala sintética offline e a validação ainda
pendente em desktops reais; esses resultados não são intercambiáveis.

## Plataforma/configuração

- Linux nativo seleciona executáveis POSIX e mic default; WSL mantém dshow.
- `--doctor` informa presença de dependências sem iniciar agente/microfone.
- Sessão Wayland tem precedência sobre DISPLAY de XWayland.
- Configuração/settings seguem diretórios XDG absolutos; valores relativos
  de XDG são ignorados em favor dos defaults absolutos.
- Teste antigo de raiz do projeto corrigido para não depender do nome da pasta.
- Suite após etapa 1: 324 passed (Python 3.14, Arch Linux).

### Regressão Python no Arch Linux rolling x86_64 — 2026-10-18

- `python3 -m pytest -q -rs voice/tests`: 444 passed, 10 skipped no host
  Wayland. Os skips foram o teste interativo de desktop (opt-in), testes de
  portal por falta de `dbus_next` no Python do host e STT por falta de
  `faster_whisper` no Python do host. Esses módulos foram importados no smoke
  do pacote Guix; este resultado mede a regressão Python sintética, não a
  captura de áudio nem a integração completa com portais/desktop.
- Log local: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-full-voice-tests-2026-10-18.log`.
- Reexecução em 2026-10-19 no mesmo host Arch Linux x86_64: 452 passed, 10 skipped; log `.superpowers/sdd/2026-10-14-jarvis-linux/linux-voice-tests-2026-10-19.log`, SHA-256 `36254e25be16a07a611259b6934299f8fec1b5bd127785fbc65953341d2c8acb`. A suíte de pacotes Linux também passou: 44 passed.

### Portal D-Bus privado no Arch Linux rolling x86_64 — 2026-10-18

- Com `dbus-next==0.2.3` instalado em um venv temporário, os 12 testes de
  `voice/tests/test_portal.py` passaram, incluindo respostas forjadas,
  cancelamento, negação, timeout, sessão D-Bus persistente e endereço inválido.
  O harness usa `dbus-run-session` e serviços privados; não valida concessão,
  negação ou revogação em portais reais de GNOME/KDE.
- Log local: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-private-dbus-portal-tests-2026-10-18.log`.

### Atualização do pacote Arch x86_64 — 2026-10-18

- Em container Arch rolling, o pacman atualizou o artefato anterior `0.1.0-1`
  para uma reconstrução do código atual em `0.1.0-2`. O build alterou `pkgrel`
  apenas dentro da imagem de teste; a revisão da receita no checkout continua
  inalterada. `jarvis --doctor`, OpenCode 1.18.23, `pacman -Qkk` (8138 arquivos),
  hash do dado de usuário antes/depois, ciclo de instalação/remoção e preservação
  do dado após a remoção passaram.
- Artefato atual: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-upgrade-artifacts/jarvis-assistant-0.1.0-2-x86_64.pkg.tar.zst`.
- Log: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-upgrade-2026-10-18.log`.

## Áudio observado nesta máquina

Ambiente: Arch Linux rolling, x86_64, Wayland, PipeWire com compatibilidade
PulseAudio; FFmpeg disponibiliza entradas pulse e alsa.

- Listagem real: default e dois microfones físicos; monitores excluídos.
- Captura fixed de 0,5 s: WAV válido, 2 canais, 48000 Hz, 26578 frames.
- Calibração de 0,5 s: mean -32,5 dB, max -20,1 dB.
- VAD limitado a 1 s/espera 0,5 s: encerrou sem fala detectada.
- PTT com parada programada após 0,7 s: WAV válido, 50400 frames.
- Artefatos internos usam arquivos exclusivos e limpeza por context manager.
- Falha de gravação implícita reproduzida por teste: temporário vazava;
  correção limpa arquivos próprios ao lançar erro, preservando saída explícita.
- Suite após correção: 333 passed in 10.24s.

## Ainda não verificado

ALSA real, reconhecimento de fala CPU, Piper real/streaming, ações Linux,
portais, contexto AT-SPI, overlay, Flatpak, pacotes nativos e demais distros/
arquiteturas. Instalação das dependências de voz em venv privado em andamento.

## Síntese e portal — evidências adicionais

- Piper 1.8.0 no venv privado sintetizou frase portuguesa em WAV de 22050 Hz,
  54016 frames; FFplay reproduziu e terminou com exit 0.
- Modelo Faber verificado contra o SHA256 LFS anunciado pelo repositório:
  `858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7`.
- Speaker processou duas frases reais, sem erro no worker nem WAV residual.
- faster-whisper 1.2.1 com PyAV 19.0.1 falhou em `metadata_errors`; o teste
  de integração de decode PCM reproduziu o erro. Limite `av<19` em validação.
- Captura X11 no servidor XWayland: PNG 3840x1200, igual às dimensões da root.
  Isso não comprova captura de janelas Wayland nativas.
- D-Bus privado: resposta anterior ao retorno do método, sinal de emissor
  incorreto, cancelamento, recusa, timeout, serviço ausente e endereço inválido
  cobertos; 11 testes passaram. O teste não usa o portal do usuário.
- Portal real de screenshot: chamada aguardou autorização e expirou após 15 s;
  request foi encerrado. Captura Wayland autorizada ainda não foi comprovada.
- Suite no venv com dbus-next: 351 testes passaram antes dos testes adicionais.

Referências de dependências:
https://pyav.basswood.io/docs/stable/development/changelog.html
https://github.com/SYSTRAN/faster-whisper/blob/master/requirements.txt
https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium

## Resultado após ajuste de dependências

- PyAV 18.1.0 com faster-whisper 1.2.1: decode PCM passou e STT tiny/CPU
  transcreveu a frase sintetizada: “Olá, este é um teste do Javismo Linux.”
  A transcrição demonstrou operação real, com erro de reconhecimento no nome.
- Captura ALSA default: WAV válido, 14395 frames a 48000 Hz.
  Enumeração ALSA real ainda depende de instalar `arecord` (alsa-utils), ausente
  neste host; a ausência produz erro explícito. Enumeração Pulse foi validada.
- `voice/requirements-linux.txt` instala também Piper nativo; dependências
  gerais limitam PyAV a `<19` para preservar API usada por faster-whisper 1.x.
- Suíte completa no venv com dependências reais: 354 passed in 11.71s.
- `pip check`: No broken requirements found.

A tarefa de áudio tem implementação e testes reais de captura/STT/TTS; a
validação integral entre backends/ambientes permanece em andamento. A tarefa
de screenshot tem implementação e testes de transporte, mas captura Wayland
com consentimento e execução em outros desktops ainda não foram verificadas.

## Desktop nativo, contexto e arquivos

- Screenshot Wayland autorizado pelo usuário: PNG decodificado de 3840x1200,
  2622279 bytes. Captura real KDE Wayland comprovada nesta máquina.
- Sessão RemoteDesktop autorizada: dois streams, 1920x1200 e 1920x1080, com
  posições/dimensões no espaço do compositor. Conexão D-Bus mantida entre tools.
- Janela GTK forçada a Wayland: recebeu exatamente `Jarvis ação 🙂`; Ctrl+A
  seguido de digitação resultou em `Teste concluído`, verificado pelo widget.
  A API de produção continua retornando unconfirmed quando só envia eventos.
- AT-SPI encontrou a janela de teste e sua árvore com IDs de controles.
- Background: uma janela de teste recebeu `Texto em segundo plano`, enquanto
  uma segunda janela de teste permaneceu ativa e seu campo não foi alterado;
  posição do ponteiro reportada pelo XWayland permaneceu idêntica. O teste
  opt-in `JARVIS_DESKTOP_TESTS=1` passou, sem modificar apps do usuário.
- Rechecagem no host KDE Wayland (2026-10-20): o mesmo teste opt-in foi
  pulado antes de qualquer mutação porque tanto a janela de teste quanto a
  sentinela reportaram `active=false`. O log e o estado do fixture foram
  preservados; essa rechecagem não valida nem invalida o resultado anterior.
- Corrigida ambiguidade GI entre getter de interface `Accessible.get_text`
  e leitura `Atspi.Text.get_text`; falha real reproduzida antes da correção.
- MCP inicializado pelo cliente stdio real: ferramentas neutras registradas e
  consulta de processos respondeu; filtro de nomes é literal, sem shell.
- Bridge de arquivos real: confirmação exigida, escrita/leitura UTF-8 dentro
  da allowlist e recusa fora dela; serviço próprio encerrado ao fim do teste.
- Escrita usa descritores/no-follow e valida inode antes de truncar; testes
  cobrem symlink trocado no instante de open, hardlinks e raiz autorizada
  ausente sem criar ancestrais fora do escopo.
- Regressão: 383 passed, 1 skipped (GUI opt-in) na voz; 118 testes TypeScript
  passaram e 13 testes MCP passaram. O teste GUI foi executado separadamente:
  5 passed (background nativo mais contexto).

Pendências: click real pelo portal, abertura real pelo desktop, clipboard,
revogação real de sessão, lifecycle ligado ao cérebro/overlay, instalação,
Flatpak e pacotes/matriz de distros. As evidências acima não concluem o porte.

Verificação parcial do abridor no host KDE Wayland (2026-10-20):
`open_target` encaminhou um arquivo temporário por `xdg-open`; o processo real
`/usr/bin/kate -b <arquivo>` iniciou com o caminho exato e foi encerrado após
o teste, com o arquivo temporário removido. A ferramenta retornou
`unconfirmed`, como projetado. No primeiro teste o Kate não apareceu na árvore
AT-SPI; a documentação do Qt 6 indica `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1`
como alternativa às propriedades AT-SPI no D-Bus ([Qt QAccessible](https://doc.qt.io/qt-6/qaccessible.html)).
Com essa variável, a árvore AT-SPI expôs o frame de um arquivo com nome único
(`JarvisOpenProbe_<id>.txt — Kate`), confirmando que o desktop abriu o alvo.
O conteúdo não foi exposto; por isso, a matriz aprova somente o dispatch e a
janela, enquanto a API mantém `unconfirmed` por não confirmar o conteúdo.
Logs locais:
`.superpowers/sdd/2026-10-14-jarvis-linux/host-kde-open-2026-10-20.log`
(primeiro teste, SHA256 `b946e9f0a8d97d20f33ddca6e08d9b09190b07ec918f0db2c34672a891d8a820`) e
`.superpowers/sdd/2026-10-14-jarvis-linux/host-kde-open-atspi-2026-10-20.log`
(AT-SPI Qt 6, SHA256 `29b4dab296514b52c9e80a43908846e64eae539a1088d1e2fead2227deb3efa2`) e
`.superpowers/sdd/2026-10-14-jarvis-linux/host-kde-open-confirmed-2026-10-20.log`
(nome de arquivo único visível no frame, SHA256 `fc282bf7d75a78365b7fb0b44c1f32dab98af0bc9b40feb098d58db6adb699a3`).

## Aplicativo instalado e lifecycle

- Overlay Linux compilado com GTK3/WebKitGTK 4.1; 6 testes Rust passaram.
  Native startup usa launcher instalado e grupo próprio; parada não mata um
  processo sentinel alheio. Logs XDG e override de porta runtime verificados.
- Instalador por fonte executado em prefixo privado, incluindo venv, SDK dos
  plugins e ambos os MCPs. Launcher resolveu projeto e Piper no prefixo.
- Overlay instalado iniciou o cérebro nativo; janela e estado HTTP/SSE
  observados. Teste usou limiar 0 dB e backend run para impedir envio de falas
  incidentais ao modelo externo durante a verificação do lifecycle.
- Menu via AT-SPI real: mudo e pausa mudaram flags do cérebro; configurações
  expuseram microfones/tunables/Piper. Reiniciar trocou PID 1520895 por 1525696,
  resetando flags. Sair encerrou cérebro e overlay; nenhum PID de teste ficou
  ativo. Gtk warning de decoração foi corrigido configurando antes de criar.
- Falha real de ativação acessível do orbe reproduzida; agora um botão real e
  um único handler de click atendem mouse, teclado e AT-SPI. Dois testes JS
  cobrem resize sem posições globais (Wayland) e âncora com escala.
- Serviço encerra quando identidade/PID dono termina, cancela requests e
  termina workers próprios; testes de lease e worker RED→GREEN passaram.
- Zipapp iniciado fora do checkout extraiu recursos em cache privado, incluindo
  triggers, plugins, configuração e MCP, com launcher executável.
- Download real de voz com revisão c10ece1aade47bb51c153c893d14e5bf8e5b7117,
  três SHA256s e tamanhos fixados passou. Não substitui arquivo sem verificar.
- Regressão de voz: 391 passed, 1 skipped em 13.42s. Delegate MCP exigia httpx
  no venv de teste; dependência declarada foi instalada, e seus 17 testes
  passaram. Não era falha do pacote fonte instalado, que inclui esse requisito.

Flatpak, formatos nativos, aarch64 e matriz de demais distros permanecem
pendentes. Nada acima comprova conclusão desses entregáveis.

## Pacotes, 2026-10-15

- Arch rolling x86_64: pacote construído com makepkg; instalado com pacman em
  container archlinux:base. Launcher/doctor, agente 1.18.23 e imports de voz/MCP
  passaram. `pacman -Qkk` verificou 8135 arquivos, zero alterados. Remoção passou
  e o dado de usuário usado no teste foi preservado. A configuração NoExtract
  padrão do container foi removida para incluir a documentação no teste.
- Debian 13 x86_64: compilação no próprio Debian trixie com Rust 1.95; instalação
  com apt em container limpo, doctor, agente, imports e `dpkg -V` passaram, assim
  como remoção e preservação do dado de usuário. Uma dependência ausente para
  listagem de microfones, pulseaudio-utils, foi adicionada; o DEB foi reconstruído,
  instalado e removido novamente no container de teste, e pactl está presente.
- A suíte de voz após o início do Flatpak passou em 416 testes, com um teste GUI
  opt-in ignorado. Isso não substitui testes de voz/GUI dos pacotes instalados.

Atualização entre versões, ARM64, execução gráfica dos pacotes e as demais
famílias de distribuição continuam sem validação completa. O Flatpak passou
pela compilação, mas o primeiro teste instalado encontrou corrupção do agente
pela extração automática de símbolos; uma reconstrução com o binário preservado
está em validação. O primeiro bundle não deve ser usado como release.

## Continuação, 2026-10-15

- Suíte atual: 421 testes Python passaram, 1 teste opt-in ignorado; 7 testes
  Rust passaram. Incluem um processo Linux real que confirma o encerramento
  do servidor junto ao grupo de processos do cérebro supervisionado.
- CI no fork, execução 38758047113: Arch x86_64 e Debian 13 x86_64/ARM64
  passaram pela compilação nativa, instalação em container limpo, inspeção
  da arquitetura ELF, imports privados, importação AT-SPI, integridade dos
  arquivos e remoção com preservação do dado de usuário usado no teste.
- Fedora 44 x86_64 passou no smoke local anterior. A CI nas duas arquiteturas
  compilou o RPM, mas o teste adicional de importação AT-SPI revelou um typelib
  DBus ausente. A receita passou a exigir gobject-introspection; a nova CI
  38764598505 está em andamento, sem resultado confirmado neste registro.
- Flatpak x86_64 reconstruído sem processamento do binário do agente: OpenCode
  1.18.23 iniciou corretamente, com SHA256 idêntico ao binário original. A voz
  Faber foi baixada e verificada; captura real de microfone produziu 12000
  frames a 48000 Hz. Piper e FFplay sintetizaram/reproduziram uma frase de teste;
  Whisper tiny em CPU transcreveu a frase sintetizada “Teste de voz no Linux.”
- A janela Flatpak e o HTTP do cérebro iniciaram. O teste dos controles via
  acessibilidade ainda falhou; a correção da identidade GTK está sendo
  reconstruída para repetir esse teste. Isso não comprova o fluxo gráfico
  completo nem autoriza tratar o bundle como release.

Ainda faltam atualização entre versões, a matriz gráfica instalada, ARM64 do
Flatpak e os demais formatos/famílias previstos no plano. Evidência de container
não substitui áudio, permissões de portal ou desktop real na distribuição alvo.

### Correções confirmadas nesta continuação

- Execução CI 38764598505 concluída com sucesso nos cinco jobs: Arch x86_64,
  Debian x86_64/ARM64 e Fedora x86_64/ARM64. Fedora passou pela importação AT-SPI
  após declarar gobject-introspection, além dos demais testes de pacote.
- Flatpak instalado, com identidade GTK correta e `WEBKIT_FORCE_SANDBOX=1`
  aplicado na execução: AT-SPI acessou a interface; mudo e pausa alteraram o
  estado HTTP, configurações abriram e Sair encerrou o cérebro. Um servidor
  OpenCode real iniciado em porta exclusiva estava saudável e foi encerrado
  junto com o overlay. Nenhum servidor preexistente foi encerrado pelo teste.
- O teste encontrou o botão de fechar configurações fora da janela (`y=-30`).
  CSS limitado ao viewport e rolagem corrigiram o posicionamento (`y=19.015625`)
  em renderização real WebKit 2.54.1 do SDK, janela 280×470. O build instalado
  com o manifesto e CSS corrigidos ainda precisa repetir o fluxo completo.
- Pins ARM64 consultados no Flathub para SDK/Platform GNOME 49 e Rust 25.08;
  o driver seleciona commits e nome do bundle por arquitetura. Workflow manual
  prepara builds nativos x86_64/ARM64. Isso ainda não prova que ARM64 compila.

### Ubuntu, ARM64 e regressão de reabertura

- CI 38786962019 passou nos sete jobs: Arch x86_64, Debian 13 x86_64/ARM64,
  Ubuntu 24.04 x86_64/ARM64 e Fedora 44 x86_64/ARM64. Os checks são de pacote,
  ABI ELF, imports, integridade e ciclo de instalação/remoção.
- CI Flatpak 38786961962 passou nas duas arquiteturas, com instalação do bundle,
  OpenCode 1.18.23 e imports de voz/MCP/AT-SPI nos runners nativos. Isso valida
  build/runtime básico, não captura e controle gráfico no ARM64.
- A reabertura do overlay nativo reproduziu um panic: GTK reenviava a ativação
  e Tauri tentava criar outra webview `main`. O teste isolado falhou na versão
  anterior e passou com tauri-plugin-single-instance 2.5.4; o segundo processo
  saiu e a primeira janela permaneceu. O teste usa Xvfb/D-Bus e dados privados.
- No Arch/KDE Wayland, o overlay atual com essa correção passou por mudo, pausa,
  configurações com fechar visível (`y=19`), reinício com troca do PID do cérebro,
  retomada HTTP e saída com encerramento do OpenCode iniciado na porta exclusiva.
- Suíte atual: 426 testes Python passaram, 1 opt-in ignorado; 7 testes Rust
  passaram. Os pacotes com a correção de reabertura ainda precisam repetir a CI.
- A receita Tumbleweed foi adicionada com dependências consultadas no repositório
  nativo; o build local está em andamento. Não há RPM instalado validado ainda.

- CI 38797751372: openSUSE Tumbleweed x86_64 e ARM64 passaram por build,
  instalação RPM, imports privados de voz/MCP/AT-SPI, reabertura X11 isolada,
  integridade RPM, remoção e preservação do dado sentinela. Os testes de sessão
  completa GNOME/KDE, áudio e portais continuam pendentes.
- O contexto Docker agora exclui `docs/research` e os schemas gerados do Tauri.
  Um contexto temporário com arquivos sentinela reproduziu a inclusão com as
  regras antigas e passou com as novas, preservando os arquivos de empacotamento.

- O bundle x86_64 da CI 38793467680 teve SHA256 conferido e foi instalado
  (commit Flatpak `233f5a21e9fc2ff4672f736e57e9fdd8128d299a8c1c46cf1145b57713aea3fd`).
  A sessão local tem o serviço de documentos ativo, mas a montagem `doc` ausente:
  a abertura padrão falhou antes do aplicativo (`bwrap: Can't find source path`).
  Usando apenas `--no-documents-portal` para isolar essa falha do ambiente, o
  teste do bundle confirmou mudo, pausa, configurações com fechar visível em
  `y=19`, reinício com troca do cérebro/retomada HTTP e saída com HTTP parado.
  Não foi usado override de `WEBKIT_FORCE_SANDBOX`; o manifesto fornece esse
  valor. Isso não conclui o teste da abertura padrão nem dos portais.
- O OpenCode instalado ficou saudável em 20,8 segundos no teste isolado.
  O prazo anterior de 20 segundos podia provocar fallback prematuro para `run`.
  O Linux agora espera até 60 segundos por padrão; outros sistemas mantêm 20 e
  prazos explícitos continuam valendo. Testes com relógio controlado reproduziram
  a falha aos 21 segundos e passaram com a mudança (16 testes de servidor).
- Após o ajuste do prazo: suíte no venv de voz com dependências instaladas: 430 passaram, 1 teste de desktop opt-in ignorado. A integração do código de servidor atualizado com o agente do Flatpak instalado também passou (12,73 segundos).

### Slackware current x86_64 — 2026-10-17

- O SlackBuild compilou no container Slackware current com Python 3.12, Rust,
  Node/npm e WebKitGTK 4.1 do repositório comunitário `slackware.lngn.net`.
  A primeira execução revelou que `makepkg` era chamado na raiz do código-fonte
  e incluía os artefatos de compilação Cargo. O SlackBuild agora muda para a
  árvore de staging antes de empacotar; o teste de regressão falhava antes e
  passou depois. O `.txz` validado não contém `gui/src-tauri/target`.
- O pacote foi instalado com `installpkg`; `jarvis --doctor`, OpenCode 1.18.23,
  imports privados de faster-whisper, Piper, MCP, httpx, DBus, PyAV,
  CTranslate2 e ONNX Runtime, além do typelib AT-SPI, passaram. O teste
  `test-overlay-instance.py` em Xvfb/D-Bus passou: a segunda execução saiu e a
  janela da primeira permaneceu. `removepkg` removeu os arquivos do pacote e
  preservou um sentinel em `XDG_DATA_HOME`.
- O overlay compilado no Slackware também passou por `test-overlay-wayland.py`
  em um container Gentoo com Weston headless: a segunda execução saiu e a
  janela primária permaneceu. Isso valida a execução cruzada desse binário em
  Wayland/Gentoo; não comprova Wayland nativo no Slackware.
- Em 2026-10-19, `upgradepkg pacote-antigo%pacote-novo` substituiu a revisão
  `_1_local-fixed` pela `_2_local`, com um marcador distinto na documentação do
  payload novo. `jarvis --doctor` passou antes e depois; o sentinel em
  `XDG_DATA_HOME` sobreviveu à atualização e à remoção. Artefatos, hashes e log
  estão em `slackware-upgrade-artifacts/` e
  `slackware-upgrade-preservation-2026-10-19.log`. Isso valida o fluxo de
  atualização do gerenciador e preservação de dados, não uma migração de banco
  de dados do aplicativo.
- `scripts/test-native-package.sh slackware ...` agora automatiza a instalação
  por `installpkg`, doctor, imports privados/AT-SPI, comandos de áudio disponíveis,
  janela X11 sob Xvfb/D-Bus, remoção por `removepkg` e preservação dos dados do
  usuário. O ciclo completo passou no container current. O harness não declara
  integridade via banco de pacotes para Slackware nem testa os utilitários
  opcionais de clipboard/automação ainda ausentes no container.
- O teste precisou dos pacotes oficiais `pygobject3`, `gobject-introspection`,
  Xvfb, nettle, libXfont2, libxshmfence, libfontenc, xkeyboard-config, xkbcomp e
  libxkbfile no container mínimo. Também instalei as dependências transitivas
  oficiais de ffmpeg/ffplay e PulseAudio, conferindo cada pacote com o
  `CHECKSUMS.md5` oficial. `ldd` não mostra bibliotecas ausentes em ffmpeg,
  ffplay ou pactl; `pactl --version` passou.
- FFmpeg capturou um segundo do dispositivo ALSA virtual `null` para WAV e
  reproduziu um tom nele. O pacote Jarvis instalado enumerou `default` e `null`
  com `AUDIO_BACKEND=alsa` e `capture.record` gerou WAV de aproximadamente 785
  kB. Piper sintetizou uma frase e o `ffplay` tocou o WAV via ALSA `null`.
  Esses testes validam o caminho de software com dispositivo virtual, não
  microfone/alto-falante físico nem servidor PulseAudio em sessão real.
- `scripts/build-slackware-helpers.py` busca e confere os commits fixados de
  xdotool 4.20260303.1, xclip 0.13 e wl-clipboard 2.3.0, compila os três e os
  instala no staging privado `/usr/lib/jarvis/bin`, incluindo as licenças.
  Builder executado no Slackware current: compilação dos três passou; `ldd` não
  encontrou bibliotecas ausentes nos binários resultantes.
- `scripts/test-x11-tools.py` passou com os binários staged: `xdotool
  getmouselocation --shell` e roundtrip do `xclip` em Xvfb. Weston headless
  não fornece um seat para `wl-copy`; em seguida, o roundtrip Wayland foi
  validado com Weston 14.0.2 usando backend X11 sobre Xvfb executado dentro do
  container Gentoo. Os binários `wl-copy`/`wl-paste` saíram do staging do pacote
  Slackware e trocaram o texto `Slackware wl-clipboard on Weston X11 seat`.
  Log: `.superpowers/sdd/2026-10-14-jarvis-linux/slackware-wl-clipboard-cross-distro.log`
  (SHA256 `41b4470155c5a5813ac11ef590d37fc5ddd60143491bf66754cdd9e3c824f8bd`).
  Isso valida o helper em uma sessão Wayland com seat virtual, não uma sessão
  Wayland nativa do Slackware.
- O SlackBuild reconstruiu o `.txz` com os quatro helpers em
  `/usr/lib/jarvis/bin` e as três licenças em `usr/doc/.../third-party`; `xz -t`
  passou. O ciclo final por `installpkg` validou `command -v`, o smoke Xvfb de
  xdotool/xclip, runtime/imports, overlay, `removepkg`, limpeza dos arquivos do
  pacote e porta 4096 fechada. Log local:
  `.superpowers/sdd/2026-10-14-jarvis-linux/slackware-current-package-helpers-lifecycle.log`.
- A sessão Wayland nativa, áudio com dispositivos reais, atualização entre
  versões distintas e aarch64 continuam pendentes. Por isso o catálogo mantém
  Slackware como `unverified`.
- O modelo `pt_BR-faber-medium.onnx` foi baixado pelo comando instalado
  `jarvis --download-voice`; o downloader verificou tamanho e SHA256 fixados.
  Com o Python privado do pacote, Piper sintetizou “Teste de voz no Slackware
  Linux.” em WAV mono, 22.050 Hz, 38.656 frames. Com o XDG de teste, `--doctor`
  reconheceu o modelo e a capacidade Piper. O WAV foi reproduzido via ffplay
  sobre ALSA `null`; áudio em dispositivo físico e captura via PulseAudio seguem
  sem validação.
- Com o cache isolado em `/tmp`, faster-whisper baixou o modelo base padrão
  selecionado pela biblioteca e executou inferência CPU int8 sobre WAVs de Piper. A
  transcrição retornou texto e a amostra maior reconheceu corretamente a frase
  “está funcionando corretamente”, mas distorceu palavras curtas/nome próprio;
  isso comprova execução do backend, não a qualidade acústica final no Slackware.


### Void glibc x86_64 — atualização XBPS — 2026-10-17

- XBPS instalou a revisão `_1` do repositório local; `jarvis --doctor` passou.
  Depois da criação do sentinel em `XDG_DATA_HOME`, o XBPS atualizou o pacote
  para `_2`; doctor passou novamente, o sentinel permaneceu intacto e a remoção
  do pacote também preservou os dados.
- Os repositórios locais mantêm uma revisão por índice. Cada revisão foi
  indexada em diretório próprio, permitindo verificar e instalar a versão
  esperada antes e depois da atualização. Log:
  `.superpowers/sdd/2026-10-14-jarvis-linux/void-glibc-upgrade-preservation.log`;
  artefatos e hashes constam no catálogo.

### Void musl x86_64 — 2026-10-17

- A revisão XBPS `_2` foi instalada pelo XBPS a partir de um repositório local
  descartável. `jarvis --doctor`, imports e ABI Python privados, AT-SPI,
  ferramentas de voz e versão do OpenCode passaram. O smoke executou xdotool e
  xclip em Xvfb e validou a segunda execução do overlay mantendo a janela
  primária. `xbps-pkgdb --checks files,dependencies,alternatives,pkgdb` passou;
  a remoção do pacote deixou o sentinel do usuário intacto.
- O teste ocorreu no container Void musl de smoke com dependências runtime já
  instaladas; Xvfb e D-Bus foram adicionados via XBPS. A primeira tentativa com
  o artefato renomeado para `jarvis-assistant.x86_64-musl.xbps` falhou na
  verificação de checksum do repositório local. A repetição com o nome XBPS
  completo, `jarvis-assistant-0.1.0_2.x86_64-musl.xbps`, passou.
- Artefato SHA256
  `e159f50017508d0169202e66dab58a0c3a1106b8f14b5d52850687a9730c4278`; log
  SHA256 `e49bcfbf03090e3a57a8d16a0401506c3d0bad9dcc3ef2a2b2f95bd73dda7de3`.
  Isso valida Void musl x86_64 em Xvfb, não desktop/áudio real nem aarch64.
- XBPS atualizou o pacote instalado da revisão `_1` para `_2`; `jarvis --doctor`
  passou nas duas revisões. O sentinel em `XDG_DATA_HOME` permaneceu idêntico
  durante a atualização e após `xbps-remove`. Isso comprova preservação de dados
  entre revisões do pacote, sem afirmar migração entre versões do aplicativo.
  Log: `void-musl-upgrade-preservation.log`; revisões e hashes também constam no
  catálogo de validação.

### Nix x86_64 — perfil instalado e smoke X11 — 2026-10-18

- O flake foi construído no SDK Nix com o nixpkgs fixado no `flake.lock`; o
  pacote foi instalado em um perfil Nix e `jarvis --doctor` passou. O doctor
  reconheceu Linux, ffmpeg/ffplay, Piper e OpenCode; sem baixar um modelo, a
  capacidade de síntese de voz não fica disponível.
- O overlay instalado passou por `scripts/test-overlay-instance.py` sob
  Xvfb/D-Bus: a segunda execução saiu e a janela principal permaneceu; o botão
  Sair encerrou a janela. O SDK não fornece os caminhos de sistema que o smoke
  espera, então a execução apontou AT-SPI, D-Bus e Mesa EGL diretamente para o
  Nix Store. Isso valida o pacote x86_64 e o overlay isolado; não substitui um
  teste em sessão NixOS real.
- Atualização em 2026-10-20: a execução CI `39345908495` concluiu os jobs
  x86_64 e AArch64. Em ambos, o pacote foi compilado e instalado em perfil
  descartável e passou doctor, imports do runtime, smoke Xvfb/AT-SPI, remoção e
  preservação de dados (`PASS: Nix profile install, runtime imports, removal
  and user data preservation`). Evidência AArch64:
  https://github.com/GuilhermeBn198/jarvis/actions/runs/39345908495/job/118378324844;
  x86_64: https://github.com/GuilhermeBn198/jarvis/actions/runs/39345908495/job/118378325163.
  Isso valida o ciclo do pacote sob runner ARM, não uma sessão NixOS real;
  áudio físico, portais e desktop real seguem pendentes.

### Solus 4.9 x86_64 — pacote eopkg instalado — 2026-10-17

- O pacote foi compilado em Solus `solbuild` com a remoção automática de símbolos
  desativada para preservar o executável Bun/OpenCode. `opencode --version`
  retornou 1.18.23 após a instalação.
- O ciclo eopkg passou por dependências Xvfb/D-Bus, doctor, imports e ABI do
  runtime Python privado, recursos instalados, AT-SPI typelib, arquitetura ELF,
  integridade do pacote, segunda execução do overlay mantendo a janela, remoção
  e preservação do sentinel do usuário.
- O log local completo é
  `.superpowers/sdd/2026-10-14-jarvis-linux/solus-eopkg-lifecycle-x86_64.log`.
  O ambiente headless com Xvfb não valida sessão Solus Wayland/X11 real,
  microfone, playback em hardware ou atualização entre versões.

### GNU Guix x86_64 — pacote e perfil instalado — 2026-10-18

- A derivação Guix compilou o overlay e executou os 7 testes Rust com sucesso.
  As fases de instalação, strip e restauração do binário OpenCode passaram;
  `opencode --version` retornou 1.18.23.
- `scripts/test-guix-package.sh` instalou o pacote em perfil descartável,
  `jarvis --doctor` reconheceu os executáveis, os imports Python passaram usando
  o caminho de módulos embutido no launcher, e a remoção preservou os dados do
  usuário. O log local registra Guix commit `03460e6f` e o store output
  `/gnu/store/1pwpi865n6mashq0aw5wphv9ylva2v70-jarvis-assistant-0.1.0`.
- O teste foi headless em container GNU Guix, sem desktop, microfone ou áudio
  físico; não valida GNOME/KDE, portais ou Wayland/X11 reais. aarch64 permanece
  sem suporte verificado.

### Fedora 44 x86_64 — atualização RPM — 2026-10-18

- O DNF atualizou `jarvis-assistant` de `0.1.0-1.fc44` para `0.1.0-2.fc44`
  em container Fedora 44 descartável. `jarvis --doctor`, OpenCode 1.18.23 e
  `rpm -V jarvis-assistant` passaram após a atualização; o hash SHA-256 do
  sentinel em `XDG_DATA_HOME` permaneceu igual durante atualização e remoção.
- O pacote atualizado também passou pelo ciclo nativo de instalação, imports e
  ABI Python privados, AT-SPI, ferramentas X11/clipboard, relançamento isolado
  do overlay em Xvfb, integridade RPM, remoção e preservação de dados.
- Para este teste, `Release: 2` foi aplicado somente à cópia dentro do container
  de build; a receita versionada segue inalterada. Logs locais:
  `fedora-package-upgrade-2026-10-18.log` e
  `fedora-native-package-lifecycle-2026-10-18.log`. Evidências e hashes estão
  em `docs/notes/linux-matrix.json`. Isso ainda não valida desktop GNOME/KDE
  real, Wayland, áudio físico ou Fedora ARM64 além do smoke CI já registrado.

### openSUSE Tumbleweed x86_64 — atualização RPM — 2026-10-18

- O Zypper atualizou `jarvis-assistant` de `0.1.0-1` para `0.1.0-2` em
  container Tumbleweed descartável. `jarvis --doctor`, OpenCode 1.18.23 e
  `rpm -V jarvis-assistant` passaram; o sentinel em `XDG_DATA_HOME` manteve o
  mesmo SHA-256 durante a atualização e após remover o pacote.
- O RPM atualizado passou pelo ciclo de instalação, imports/ABI do runtime
  privado, AT-SPI, ferramentas X11/clipboard, relançamento do overlay em Xvfb,
  integridade, remoção e preservação de dados. O Release 2 foi aplicado apenas
  à cópia da receita dentro do container de build.
- Logs locais: `suse-package-upgrade-2026-10-18.log` e
  `suse-native-package-lifecycle-2026-10-18.log`; artefatos e hashes estão na
  matriz. Isso não cobre openSUSE Leap, desktop real, Wayland nem áudio físico.

### AlmaLinux 10 — ciclo RPM e Xwayland headless — 2026-10-20

- A execução CI `39348581463` passou nos jobs x86_64 e AArch64. O RPM foi
  instalado, inspecionado e removido em containers limpos; `jarvis --doctor`,
  ABI e recursos do runtime privado, imports AT-SPI, integridade e preservação
  do sentinel de dados passaram.
- RHEL 10 não fornece Xvfb nesse ambiente. O teste X11 usa o `xwfb-run` de
  `xwayland-run` com `-c weston`, executa o roundtrip real de xdotool e xclip
  sobre Xwayland headless e, em seguida, valida o overlay nativo em Weston
  headless. Logs CI e arquiteturas estão em `linux-matrix.json`.
- O resultado valida os testes headless e o ciclo de pacote; não substitui
  sessões GNOME/KDE reais, permissões de portal nem captura/reprodução em
  hardware de áudio.

### Void musl x86_64 e AArch64 — ciclo nativo — 2026-10-20

- Os jobs `void-musl-x86_64` e `void-musl-aarch64` do workflow
  `39383364143`, no commit `cba55c571cc4fba0feaab4dd8fa8fa44ca6ba086`,
  concluíram com sucesso. Cada job compilou o XBPS no ambiente Void musl nativo,
  exportou pacote e checksum, instalou em container limpo, inspecionou e removeu
  o pacote, e publicou o artefato.
- A evidência por arquitetura está registrada em
  `docs/notes/linux-matrix.json` com links diretos aos dois jobs. Isso valida o
  lifecycle de pacote nas duas arquiteturas; desktop real, atualização entre
  versões, captura de áudio e sessão Wayland continuam pendentes.

### Overlay nativo na sessão KDE Wayland — 2026-10-20

- O fixture de lifecycle do overlay foi executado no compositor KDE Wayland
  ativo do host Arch x86_64, usando configuração de usuário temporária e uma
  sessão D-Bus privada. A janela principal ficou acessível após um segundo
  lançamento, e os controles acessíveis encerraram a janela sem erro.
- Comando:
  ```sh
  env GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-1 XDG_SESSION_TYPE=wayland GTK_USE_PORTAL=0 LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_COMPOSITING_MODE=1 dbus-run-session -- python3 scripts/test-overlay-instance.py --inside-session gui/src-tauri/target/debug/jarvis-overlay
  ```
- Log: `.superpowers/sdd/2026-10-14-jarvis-linux/host-kde-overlay-wayland-2026-10-20.log`
  (SHA256 `d930710bedce2b6185a2f96b446f47ca9f1ff26af81fa40ece18353a8dedd105`).
- Isto valida somente o lifecycle do overlay no KDE Wayland. O pacote instalado,
  concessões/revogação dos portais, áudio físico e outros desktops continuam
  pendentes.

### Screenshot Wayland e testes D-Bus locais — 2026-10-20

- Com `dbus-next==0.2.3` em um venv temporário, passaram os 12 testes do
  harness privado D-Bus em `voice/tests/test_portal.py` e os 8 testes de
  screenshot/X11 em `voice/tests/test_linux_screen.py`; nenhum ficou pulado.
- Os testes confirmam despacho Wayland ao portal, validação/cópia da URI PNG,
  tamanho da captura X11, falha sem retornar imagem antiga e erro explícito em
  sessão headless. Eles usam portal simulado e não provam consentimento,
  concessão ou revogação em GNOME/KDE reais.
- Logs e hashes: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-private-dbus-portal-tests-2026-10-20.log`
  (`f8c66788eb652ca13bf9db1c01c05789f08d66b365605e3290b05ccc3c56b5a8`) e
  `.superpowers/sdd/2026-10-14-jarvis-linux/arch-linux-screen-portal-tests-2026-10-20.log`
  (`46531d98af9cf9dc800252a196ea7d13e555233134f913a8cd56263e6045ef03`).

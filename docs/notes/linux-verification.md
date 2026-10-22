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
- Rechecagem em 2026-10-21 no host: `jarvis --download-voice` baixou o modelo
  Faber no `XDG_DATA_HOME` temporário e validou os hashes SHA256 fixados; a
  integração `tts.speak_piper` gerou WAV mono PCM a 22050 Hz com 60672 frames.
  O arquivo não foi reproduzido. Hash do modelo:
  `858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7`.
- Também em 2026-10-21, `capture.record` e `measure_level` usaram FFmpeg/ALSA
  com o dispositivo sintético `null`; a gravação temporária foi um WAV PCM
  estéreo válido de 48000 Hz. Isso valida o caminho ALSA sem capturar áudio do
  microfone físico. Este host não tem `arecord`, então enumeração ALSA não foi
  testada aqui; os pacotes nativos declaram `alsa-utils` como dependência.
- Artefatos internos usam arquivos exclusivos e limpeza por context manager.
- Falha de gravação implícita reproduzida por teste: temporário vazava;
  correção limpa arquivos próprios ao lançar erro, preservando saída explícita.
- Suite após correção: 333 passed in 10.24s.

## Ainda não verificado

ALSA real, reconhecimento de fala CPU, streaming Piper, ações Linux,
portais, contexto AT-SPI, overlay, Flatpak, pacotes nativos e demais distros/
arquiteturas. Instalação das dependências de voz em venv privado em andamento.

### Auditoria de disponibilidade de libei para entrada Wayland — 2026-10-22

As receitas atuais não declaram `libei`; a integração de produção ainda usa
RemoteDesktop D-Bus e o mapeamento real do ponteiro segue sem validação. Antes
de escolher uma dependência obrigatória, foi consultada a disponibilidade nos
repositórios dos alvos já declarados:

- Confirmado em Arch, Debian 13, Ubuntu 24.04, Fedora 44, RHEL 10, openSUSE
  Tumbleweed, Alpine 3.24, Gentoo, Nixpkgs e GNU Guix. Nomes dos pacotes variam
  (`libei`, `libei1`, `libei-devel`, `libei-dev`); Alpine e Debian também
  separam headers/runtime em subpacotes.
- Não confirmado nesta auditoria: Void glibc/musl, Slackware, Solus e o
  runtime GNOME Platform do Flatpak. “Não confirmado” não significa que esteja
  ausente.
- Fontes consultadas: [Arch package](https://archlinux.org/packages/extra/x86_64/libei/),
  [Debian 13](https://packages.debian.org/trixie/source/libei),
  [Ubuntu](https://packages.ubuntu.com/noble/libei-dev),
  [Fedora](https://packages.fedoraproject.org/pkgs/libei/libei/),
  [RHEL 10](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/10.0_release_notes/new-features),
  [openSUSE](https://build.opensuse.org/package/show/GNOME%3ASTABLE%3A45/libei),
  [Alpine 3.24](https://pkgs.alpinelinux.org/package/v3.24/community/ppc64le/libei),
  [Gentoo](https://packages.gentoo.org/packages/dev-libs/libei),
  [Nixpkgs](https://search.nixos.org/packages?channel=unstable&show=libei),
  [Guix](https://toys.whereis.social/?show=libei).

Esta checagem é inventário de repositórios, não teste de build, carregamento
dinâmico ou sessão Wayland. A decisão de tornar o backend EIS/libei primário
continua pendente de aprovação do desenho.

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

### Regressão Arch Linux x86_64 — 2026-10-22

- `python3 -m pytest -q -rs voice/tests`: **492 passed, 10 skipped** em
  16,92 s no host Arch Linux rolling, Python 3.14.8, Wayland. Os skips foram
  o teste de desktop interativo (opt-in), 8 testes que precisam de `dbus_next`
  e um teste que precisa de `faster_whisper`; estes dois grupos passaram quando
  reexecutados com as dependências em venv isolado.
- `PYTHONPATH=voice /tmp/jarvis-linux-optional-tests/bin/python -m pytest -q -rs voice/tests/test_portal.py voice/tests/test_stt.py`: **17 passed** em 1,04 s,
  com `dbus-next==0.2.3`, `faster-whisper` 1.x e PyAV `<19`. O portal foi
  exercitado em sessão D-Bus privada; isso não concede nem revoga permissões em
  um portal real. O teste STT verificou compatibilidade de decode PCM, sem
  baixar modelo ou testar reconhecimento nessa execução.
- `python3 -m pytest -q voice/tests/test_linux_packages.py`: **79 passed** em
  2,04 s; junto com `voice/tests/test_linux_install.py`, **84 passed** em
  3,00 s, cobrindo staging, relocação e ciclo dos pacotes.
- A tentativa opt-in `JARVIS_DESKTOP_TESTS=1 PYTHONPATH=voice
  voice/.venv/bin/python -m pytest -q -rs voice/tests/test_atspi_desktop.py`
  foi pulada antes de enviar texto porque a janela sentinela não recebeu foco;
  nenhuma janela do usuário foi modificada. A aprovação anterior no KDE Wayland
  permanece registrada separadamente.
- O venv temporário está em `/tmp/jarvis-linux-optional-tests`; não altera as
  dependências do sistema nem do projeto.
- Captura real de entrada Pulse por 0,5 s no host: `measure_level` retornou
  mean -40,7 dBFS e pico -26,6 dBFS. FFmpeg enviou os samples ao muxer null;
  nenhum WAV foi salvo ou transcrito. Log:
  `.superpowers/sdd/2026-10-14-jarvis-linux/arch-pulse-capture-measure-level-2026-10-22.log`
  (SHA-256 `16a84b94bc96f8b3b100c33f3dfa315a1adc87c8b7486ba664a402acc43cc499`).
- Captura real de entrada ALSA por 0,5 s no host: `measure_level` retornou
  mean -41,3 dBFS e pico -28,6 dBFS. FFmpeg enviou os samples ao muxer null;
  nenhum WAV foi salvo ou transcrito. Log:
  `.superpowers/sdd/2026-10-14-jarvis-linux/arch-alsa-capture-measure-level-2026-10-22.log`
  (SHA-256 `5f89b81e2c86dab1806ccd9e6842a54dab6ef1d1ec68ce65faa03fe3760be97d`).
- O pacote Arch 0.1.0-2 extraído em diretório temporário também passou
  `AUDIO_BACKEND=pulse jarvis --mic-level` por 5 s: mean -38,4 dB e pico
  -22,5 dB. O caminho encaminha os samples ao muxer null; nenhum WAV foi salvo
  ou transcrito. O artefato usa o source commit `02381f5`; `voice/capture.py` e
  `voice/audio.py` não mudaram desde então. Log e SHA-256:
  `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-pulse-mic-level-2026-10-22.log`
  (`ad87a3c1d1c8bf74c27959d8c38ff135d137040574a90ec2a4b28b7b92a1c8b0`).
- O caminho VAD do pacote Arch 0.1.0-2 também foi exercitado em uma captura
  Pulse ociosa de até 3 s; não detectou fala e não deixou WAV no cache XDG
  temporário. STT não foi iniciado. O artefato usa o source commit `02381f5`;
  `voice/capture.py` e `voice/audio.py` não mudaram desde então. Evidência:
  `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-pulse-vad-idle-2026-10-22.log`
  (SHA-256 `e79957e6a1c644725985d34fb68ab8f73798ec1515627db5dd4458d0df6fde33`).
  Isso cobre ausência de falso positivo e limpeza no host, não detecção de fala real.
- O pacote Arch 0.1.0-2 também passou VAD positivo com fixture sintética
  silêncio→tom→silêncio de 16 kHz: o tom foi detectado, gerou segmento de
  49.230 bytes e não deixou WAV no cache temporário. O teste usou um wrapper
  FFmpeg sobre `record_auto`; não usou microfone real nem STT. O artefato usa
  source commit `02381f5`. Log e hash:
  `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-vad-synthetic-positive-2026-10-22.log`
  (`e0deb28fdd041caefff9c133ef7ea915135abe338afefeeb0a07627e7b6ab3ed`).
- A bateria Linux focada na venv do projeto (`test_linux_install`,
  `test_linux_packages`, contexto, entrada, tela, plataformas, áudio, captura,
  diagnóstico, portal e STT) passou com **177 testes** em 6,55 s. Ela inclui os
  84 testes de instalação/pacote acima. `sh -n` passou em todos os scripts
  `scripts/*.sh`.

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
- Rechecagem inicial no host KDE Wayland (2026-10-20) foi pulada antes de
  qualquer mutação porque as janelas reportaram `active=false`. Uma execução
  seguinte alcançou o pedido AT-SPI, mas falhou porque o socket `bus_1` do host
  recusou conexões. O serviço `at-spi-dbus-bus` aparecia ativo; reiniciá-lo
  restaurou o socket e a chamada D-Bus.
- Após a correção do barramento da sessão, `JARVIS_DESKTOP_TESTS=1 python3 -m pytest voice/tests/test_atspi_desktop.py -q -rs`
  passou com 1 teste. O campo
  descartável recebeu texto em background, a janela sentinela manteve o foco e
  a posição do ponteiro permaneceu inalterada. Log e hash:
  `.superpowers/sdd/2026-10-14-jarvis-linux/atspi-wayland-focus-recheck-pass-2026-10-20.log`
  (`85c3e34df3337375b023792993d5880ace51098d60f8a6d4b62bb027a039340d`). O teste
  continua limitado a esta sessão KDE Wayland e não cobre outros desktops.
- Rechecagem em 2026-10-21 reproduziu a recusa no socket `bus_1` embora
  `at-spi-dbus-bus.service` estivesse ativo. Reiniciar somente esse serviço da
  sessão restaurou a conexão; `JARVIS_DESKTOP_TESTS=1 PYTHONPATH=voice python3
  -m pytest -q -rs voice/tests/test_atspi_desktop.py` passou com **1 teste**.
  A confirmação continua restrita à sessão KDE Wayland atual.
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

Pendências naquele checkpoint: click real pelo portal, clipboard, revogação real
de sessão, lifecycle ligado ao cérebro/overlay, instalação, Flatpak e matriz de
distros. A validação posterior abaixo confirmou o despacho de abertura e a
janela do Kate em KDE Wayland; o conteúdo do arquivo e a aceitação pelo app
continuam sem confirmação. As evidências não concluem o porte.

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
- A mesma prova foi repetida com o binário release recém-compilado no worktree:
  `cargo build --release --locked --manifest-path gui/src-tauri/Cargo.toml --bin jarvis-overlay`
  terminou em 43,23 s e o fixture passou no KDE Wayland. O log está em
  `.superpowers/sdd/2026-10-14-jarvis-linux/host-kde-overlay-wayland-release-2026-10-20.log`
  (SHA256 `8ee7bdd8a7cf4efd89f16de2f72b25b9b00f204b13f49c2c631756b37f6f7ff1`).
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

### Regressão Linux e serviços MCP — 2026-10-20

- Em venv isolado no host Arch x86_64, `voice/tests` passou com 481 testes e
  1 skip. O único skip restante é o teste opt-in que digita numa janela
  descartável da sessão gráfica; não foi habilitado nesta execução.
- Os 12 testes do portal D-Bus privado e o teste STT de decodificação PCM
  passaram com `dbus-next==0.2.3`, `faster-whisper==1.2.1` e `av==18.1.0`,
  respeitando os limites de `voice/requirements.txt`.
- `mcp_servers/win_context/tests`: 13 passed; `mcp_servers/delegate_local/tests`:
  17 passed. As dependências foram instaladas no mesmo venv conforme os
  arquivos `requirements.txt` dos serviços (`mcp==2.3.0`).
- Esses testes usam serviços D-Bus privados ou doubles; não validam concessão
  real de portal, hardware de áudio, nem o comportamento em cada desktop/distro.

### Bundle Flatpak x86_64 instalado no Arch — 2026-10-20

- O artefato `jarvis-flatpak-x86_64` da CI 39449565922 foi baixado e seu
  SHA256 `584b92f2b1c3ec751bbef9defaf3438e6e42a3c2034017e2ad63acca44beee1` conferido.
  A CI usou o commit `2d4cc2ea934719201b5f94ea247b3aecfa6928da`; até
  `12279e468fc53a43ad5e49727bcff5d332d3fecf`, não houve mudanças no runtime
  Flatpak, GUI, voz ou scripts de instalação.
- A instalação de usuário passou. `flatpak run --user --command=jarvis com.jarvis.overlay --doctor`
  encontrou OpenCode, Piper e o modelo de voz;
  reportou sessão Wayland e backend Pulse disponível. Isso não confirma gravação
  física de microfone nem síntese TTS real. Os imports de faster-whisper, Piper,
  MCP, httpx, D-Bus e AT-SPI também passaram no smoke anterior.
- `flatpak run --user com.jarvis.overlay` abriu o overlay, visível na sessão
  KDE Plasma/Wayland em Arch rolling x86_64. Screenshot local:
  `.superpowers/sdd/2026-10-14-jarvis-linux/flatpak-desktop-smoke-2026-10-20.png`
  (SHA256 `5888c45f615564bb35aa46cb73a87fcb41dc1fda1b4c9b70df8d036b4a68efe5`).
- O primeiro lançamento avisou que não conseguiu conectar ao AT-SPI e uma
  consulta direta ao socket `bus_1` do host também foi recusada. O serviço
  `at-spi-dbus-bus` estava ativo, mas não aceitava conexões; após reiniciá-lo,
  chamadas locais e do sandbox passaram. Com o Flatpak aberto, `list_windows`
  encontrou a janela `jarvis:listening` e `accessibility_tree` leu o frame, o
  documento web e o botão “Abrir menu Jarvis”. Log e hash:
  `.superpowers/sdd/2026-10-14-jarvis-linux/flatpak-atspi-tree-2026-10-20.log`
  (`d3e4b7395853f35c45e29b7d64d66f4f38b3b3c8cd246d6a4c8847038c900664`). Isto
  confirma descoberta/leitura da árvore AT-SPI, não ativação do botão ou portal.
- O app foi removido sem `--delete-data`. O diretório de dados do usuário
  permaneceu com 362975429 bytes, incluindo o modelo de voz de 63201294 bytes.
  Portais e gravação física de áudio seguem pendentes.

### Suíte de integração Linux de código-fonte — 2026-10-20

- `test_linux_context`, `test_linux_input`, `test_linux_install`,
  `test_linux_screen`, `test_portal` e `test_flatpak_build` passaram juntos:
  **58 passed**, sem skips, em Arch rolling x86_64.
- O host não tinha `dbus-next`; a versão fixada `0.2.3` foi instalada em um
  diretório temporário isolado, sem alterar o ambiente do sistema. O resultado
  está em `.superpowers/sdd/2026-10-14-jarvis-linux/linux-source-integration-suite-2026-10-20.log`
  (SHA256 `f2e04a751215aa6392e6b2a7dafca9e65f9321df6977c13b416c7d9cd1d0c88b`).
- São testes de código e harnesses locais; consentimento real de portal, áudio
  físico e funcionamento em outras sessões desktop continuam pendentes.
- Reexecução no checkout atual (`4ec4d80`): **58 passed, sem skips**, com
  `dbus-next==0.2.3` isolado em `/tmp/jarvis-portal-test-deps`. Log:
  `.superpowers/sdd/2026-10-14-jarvis-linux/linux-source-integration-suite-current-2026-10-20.log`
  (SHA256 `1f81eee383857373a4863cb478a77a589e027655de3dcac17c3b201e66babed9`).

### CI de pacotes Linux — 2026-10-20

- O workflow [39501884094](https://github.com/V1nic1us/jarvis/actions/runs/39501884094)
  passou nos 13 jobs de instalação, inspeção e remoção em Arch, Debian, Ubuntu,
  Fedora, openSUSE, RHEL e Alpine, x86_64/AArch64 conforme cada alvo. Os jobs
  Debian e Ubuntu atualizaram revisões DEB nas duas arquiteturas; Alpine fez
  atualização assinada APK nas duas arquiteturas, preservando os dados do usuário.
  Os IDs por alvo e arquitetura estão na matriz JSON.
- O workflow [39501884092](https://github.com/V1nic1us/jarvis/actions/runs/39501884092)
  passou build, instalação em perfil descartável, imports e remoção em Nix
  x86_64 e AArch64, preservando dados. Ambos foram executados em runners nativos.
- A execução ocorreu no commit de código `91c7bba`; commits posteriores só
  atualizaram evidências. Esses resultados são de ciclo de pacote headless e
  não substituem desktops reais, áudio físico, nem concessão/revogação de portais.

### Coerência das receitas e matriz de pacotes — 2026-10-20

- `python3 -m pytest -q voice/tests/test_linux_packages.py`: **63 passed**.
  A suíte verifica declarações de alvos contra arquivos de receita, arquiteturas,
  evidências de lifecycle e configuração dos workflows. Log:
  `.superpowers/sdd/2026-10-14-jarvis-linux/linux-package-recipe-tests-current-2026-10-20.log`
  (SHA256 `106194d44b683958bbf138d9f5f2c7d196e448659b6cbbea67f088768695af0d`).

### Atualização e preservação de dados do Flatpak — 2026-10-20

- Em um perfil Flatpak isolado, instalei o bundle x86_64 do run
  `39444588292`, confirmei `jarvis --doctor`, gravei uma sentinela no
  `XDG_DATA_HOME` do sandbox e atualizei in-place para o bundle do run
  `39480053338` com `flatpak install --bundle --or-update`.
- O `jarvis --doctor` passou antes e depois da atualização, e a sentinela
  permaneceu com o mesmo SHA256. Os dois bundles conferiram com seus sidecars.
  O log reproduzível está em
  `.superpowers/sdd/2026-10-14-jarvis-linux/flatpak-x86_64-upgrade-2026-10-20.log`
  (SHA256 `9c47ef6f9561fedee554d4b7463a9461468ba838e81cf4b8c6e233e4e4e3e15e`).
- Isso fecha somente o lifecycle de atualização e preservação de dados Flatpak
  x86_64; autorização real de portal e captura de áudio continuam pendentes.

### Reprodutibilidade do arquivo de fontes — 2026-10-20

- No checkout `5b8aa04`, gerei duas vezes `scripts/source-archive.py` em diretório
  temporário. Os arquivos produziram o mesmo SHA256:
  `4a0e70b06bbe64dec8327a4e15d8087cac6e76d818ddb23a650f9f6b1b3c57f5`.
- O tarball tem 235 entradas e inclui `LICENSE`, `voice/`, `gui/`, `mcp_servers/`,
  `packaging/` e `scripts/`. Ambientes locais, `.superpowers`, `.worktrees` e
  arquivos de configuração do usuário são excluídos pelo arquivador.
- Repeti a verificação em checkout limpo de `5aa0407`: ambas as gerações deram
  SHA256 `9ff8f82bd3519a1de507e6052ece0c84d0058d5a51ffa8666a4e25ffafc9cf80`,
  também com 235 entradas e `LICENSE` presente.
- Isso comprova reprodutibilidade do arquivo de fontes do checkout, mas ainda
  não associa cada pacote publicado ao seu arquivo de fontes nem gera SBOM ou
  confirma a presença dos avisos de licença de todas as dependências.

### Auditoria de avisos de licença e fontes de dependências — 2026-10-20

- `scripts/fetch-opencode.py` valida o SHA256 do tarball do OpenCode e extrai
  somente o membro `opencode`. O manifesto declara MIT, mas o pacote não recebe
  o texto da licença nem o código-fonte correspondente desse componente.
- As receitas Flatpak compilam/bundlam xclip, xdotool, wl-clipboard e libXmu,
  mas não instalam seus avisos upstream. Slackware inclui avisos de xclip,
  xdotool e wl-clipboard; RHEL empacota xdotool à parte com `%license`.
- Os metadados `dist-info/licenses` dos wheels Python e os arquivos de licença
  do `node_modules` seguem no runtime privado. Isto ainda requer conferência por
  artefato e não cobre automaticamente componentes sem esses metadados.
- Esses achados deixam pendentes a correção dos avisos/fonte do OpenCode, os
  avisos dos auxiliares Flatpak, a correspondência entre cada pacote e suas
  fontes, o SBOM e a revisão legal independente.

### Nix profile upgrade lifecycle — 2026-10-21

- CI run [39685647412](https://github.com/V1nic1us/jarvis/actions/runs/39685647412) passou nos dois alvos, `x86_64-linux` e `aarch64-linux`: build, instalação em perfil descartável, imports do runtime, `jarvis --doctor`, `nix profile upgrade --all`, remoção e preservação do sentinel em `XDG_DATA_HOME`.
- Esse check exercita o comando de atualização no perfil Nix; não representa uma migração entre duas versões publicadas diferentes. Guix e Gentoo AArch64 continuam pausados a pedido do usuário.

### Revalidação Void e Flatpak — 2026-10-21

- O run [39681218050](https://github.com/V1nic1us/jarvis/actions/runs/39681218050) passou build, instalação, inspeção e remoção de Void glibc e musl em x86_64 e AArch64.
- O run [39685647380](https://github.com/V1nic1us/jarvis/actions/runs/39685647380) passou build e instalação/inspeção do bundle Flatpak x86_64 e AArch64.

### RHEL x86_64 e Void glibc — 2026-10-21

- O job RHEL x86_64 do run [39683082677](https://github.com/V1nic1us/jarvis/actions/runs/39683082677/job/119518679135) concluiu build, instalação, inspeção e remoção do RPM.
- O run [39685647431](https://github.com/V1nic1us/jarvis/actions/runs/39685647431) concluiu o mesmo ciclo para Void glibc x86_64 e AArch64. Void musl e Fedora continuam em execução.

- Atualização do run [39683082677](https://github.com/V1nic1us/jarvis/actions/runs/39683082677/job/119518678470): Fedora x86_64 passou build, instalação, inspeção e remoção; Fedora AArch64 é o único job nativo ainda ativo.

### Matriz nativa completa — 2026-10-21

- O run [39683082677](https://github.com/V1nic1us/jarvis/actions/runs/39683082677) concluiu com sucesso os 13 alvos nativos: Alpine x86_64/AArch64, Arch x86_64, Debian e Ubuntu x86_64/AArch64, Fedora x86_64/AArch64, RHEL x86_64/AArch64 e openSUSE x86_64/AArch64. Cada job construiu e instalou o pacote, verificou o runtime e removeu o pacote; os workflows também executaram os testes de atualização e preservação de dados aplicáveis a cada gerenciador.


### Void musl AArch64 — 2026-10-21

- O job [39685647431](https://github.com/V1nic1us/jarvis/actions/runs/39685647431/job/119523619735) passou build, instalação, inspeção e remoção do pacote Void musl AArch64. O job x86_64 da mesma rodada ainda compila.
- A nova rodada nativa [39691135658](https://github.com/V1nic1us/jarvis/actions/runs/39691135658) iniciou 14 builds, incluindo Arch ARM64; seus resultados ainda estão pendentes.


- O run [39691135412](https://github.com/V1nic1us/jarvis/actions/runs/39691135412) repetiu com sucesso build, profile install/upgrade/removal, runtime imports e preservação de dados Nix em x86_64 e AArch64.


### Revalidação Nix e Flatpak — 2026-10-21

- O run [39692211308](https://github.com/V1nic1us/jarvis/actions/runs/39692211308) passou o build e ciclo de perfil Nix em x86_64 e AArch64, incluindo `nix profile upgrade --all`, runtime imports e preservação dos dados do usuário.
- O run [39692211264](https://github.com/V1nic1us/jarvis/actions/runs/39692211264) passou build e instalação/inspeção do bundle Flatpak em ambas as arquiteturas.

### Atualização da CI nativa, aviso MIT e upgrade Nix — 2026-10-21

- O run [39692211142](https://github.com/V1nic1us/jarvis/actions/runs/39692211142) passou os jobs Arch x86_64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39692211142/job/119549500146)) e Arch Linux ARM AArch64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39692211142/job/119549500247)), incluindo build, instalação, inspeção e remoção. No x86_64, o smoke instalado exige `xdg-open` e confere o aviso MIT do binário OpenCode. Isso substitui os dois registros de falha baseados no pacote local antigo de 18/10, que não refletia a receita atual.
- Nix passou novamente instalação, `nix profile upgrade --all`, imports, remoção e preservação dos dados em x86_64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39692211308/job/119540863404)) e AArch64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39692211308/job/119540863678)).
- RHEL AArch64 falhou antes do build ao baixar os metadados EPEL: mirrors retornaram TLS e checksum errors. É falha de infraestrutura externa observada no [job](https://github.com/V1nic1us/jarvis/actions/runs/39692211142/job/119549499983), que requer nova tentativa; não confirma falha da receita Jarvis.
- Na hora deste registro, o run nativo ainda construía Fedora x86_64/AArch64, RHEL x86_64 e openSUSE x86_64. Builds Gentoo e Guix permanecem pausados conforme pedido.

### Ciclo Void glibc e musl nas duas arquiteturas — 2026-10-22

- O run [39692211144](https://github.com/V1nic1us/jarvis/actions/runs/39692211144) concluiu com sucesso build, instalação, inspeção e remoção dos pacotes Void glibc e Void musl em x86_64 e AArch64. Jobs: [musl x86_64](https://github.com/V1nic1us/jarvis/actions/runs/39692211144/job/119543030144), [glibc AArch64](https://github.com/V1nic1us/jarvis/actions/runs/39692211144/job/119543030306), [musl AArch64](https://github.com/V1nic1us/jarvis/actions/runs/39692211144/job/119543030529) e [glibc x86_64](https://github.com/V1nic1us/jarvis/actions/runs/39692211144/job/119543031023).
- Isso encerra a validação de lifecycle de pacote nas quatro combinações Void desta rodada. Os testes de upgrade com preservação de dados em Void AArch64 continuam pendentes.
- Estado supersedido pelo rerun [39705918455](https://github.com/V1nic1us/jarvis/actions/runs/39705918455), que passou upgrade `_1`→`_2` e preservação de dados nas quatro combinações Void (glibc/musl, x86_64/AArch64). A frase acima descreve somente o checkpoint daquela hora.

### Conclusão da CI nativa — 2026-10-22

- O rerun RHEL AArch64 do run [39692211142](https://github.com/V1nic1us/jarvis/actions/runs/39692211142/job/119558803431) passou build, instalação, inspeção/remoção e upgrade RPM com preservação dos dados do usuário. A primeira tentativa havia falhado ao baixar metadados EPEL por erros TLS/checksum dos mirrors.
- O job Arch Linux ARM AArch64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39692211142/job/119558804315)) também passou upgrade entre revisões, `pacman -Qkk` e preservação dos hashes de configuração/dados/cache. Com esse resultado, os 14 jobs nativos e os testes de atualização configurados passaram. A validação continua restrita aos alvos/arquiteturas do catálogo e não certifica desktops reais, áudio ou portais em todas as distros.

### Regressão Arch e rechecagem AT-SPI — 2026-10-22

- `voice/.venv/bin/python -m pytest -q -rs voice/tests`: **494 passed, 1 skipped** em 16,35 s no host Arch Linux x86_64 Wayland. O único skip é o teste interativo opt-in. Log: `.superpowers/sdd/2026-10-14-jarvis-linux/linux-voice-tests-2026-10-22.log`, SHA-256 `7d884865027d89e1c364a2562d0001f61ecbce6f4b36f80930dac8ae83d83f92`.
- A rechecagem `JARVIS_DESKTOP_TESTS=1` do teste AT-SPI foi pulada antes de qualquer mutação porque a fixture sentinela não recebeu foco. Nenhuma janela real do usuário foi modificada. Log: `.superpowers/sdd/2026-10-14-jarvis-linux/atspi-desktop-current-session-skip-2026-10-22.log`, SHA-256 `e63ed49708f3ebe2537d2181b0917cb994f0d19528c0184317f7fe1d785ee638`. A aprovação anterior do teste na sessão KDE continua válida; esta execução não a substitui.

### Regressão de escopo de shell nos upgrades Void — 2026-10-22

- No run [39703429679](https://github.com/V1nic1us/jarvis/actions/runs/39703429679), Void glibc x86_64/AArch64 e musl x86_64/AArch64 passaram pelo build/export e falharam na inspeção/instalação. A etapa de instalação referenciava `$previous`, definido apenas na etapa de exportação; o shell de cada etapa do Actions é separado, então o caminho do pacote anterior ficava vazio.
- A correção em `631404ec409696cbe780a462c3dd590bbfd13347` procura o pacote anterior dentro da própria etapa de instalação para glibc e musl. O teste de regressão `test_void_upgrade_steps_locate_previous_package_in_their_own_shell` está coberto por `python -m pytest -q voice/tests/test_linux_packages.py`: **79 passaram** no commit registrado acima.
- O run antigo terminou com falha nos quatro jobs. O rerun [39705918455](https://github.com/V1nic1us/jarvis/actions/runs/39705918455), que contém a correção, concluiu os quatro jobs com sucesso: glibc e musl em x86_64 e AArch64 passaram build, upgrade, inspeção, preservação de dados e remoção. Jobs: [glibc x86_64](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338707), [glibc AArch64](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338492), [musl x86_64](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338606) e [musl AArch64](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338351).
- Evidência local: `.superpowers/sdd/2026-10-14-jarvis-linux/void-workflow-variable-scope-2026-10-22.log`.

### Revalidação nativa de pacotes — 2026-10-22

- O run [39705918511](https://github.com/V1nic1us/jarvis/actions/runs/39705918511), no commit `631404ec409696cbe780a462c3dd590bbfd13347`, terminou com **14/14 jobs aprovados** para Alpine, Arch, Debian, Fedora, openSUSE, RHEL e Ubuntu em x86_64/AArch64. Foram aprovados build, instalação/inspeção/remoção e os ciclos de atualização/preservação de dados configurados para cada gerenciador.
- No rerun [39705918455](https://github.com/V1nic1us/jarvis/actions/runs/39705918455), Void glibc passou os upgrades x86_64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338707)) e AArch64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338492)). Void musl também passou build, instalação, upgrade `_1`→`_2`, preservação de dados e remoção em x86_64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338606)) e AArch64 ([job](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338351)). Os quatro jobs Void terminaram com sucesso; os logs mostram as revisões atualizadas e os smokes de integridade/GUI isolada.
- Rechecagem às **02:17 UTC**: a API do GitHub ainda mostrava [Void musl AArch64](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338351) e [Void musl x86_64](https://github.com/V1nic1us/jarvis/actions/runs/39705918455/job/119592338606) na etapa `Build musl .xbps in native Void environment`; ambos iniciaram às 01:50 UTC. Não há resultado final desses upgrades para acrescentar à matriz.
- Esses checks não substituem a matriz GNOME/KDE, Wayland/X11, portais ou áudio físico. Gentoo e Guix ARM64 continuam pausados conforme pedido.

### Regressão da suíte Python — 2026-10-22

- No host Arch Linux x86_64 Wayland, `voice/.venv/bin/python -m pytest -q -rs voice/tests` passou **501 testes**; 1 teste AT-SPI interativo foi pulado porque exige uma sessão de desktop autorizada. Evidência: `.superpowers/sdd/2026-10-14-jarvis-linux/linux-voice-tests-2026-10-22-rerun.log`, SHA-256 `714e2fde2eb9a7630097eea742d8567db9c8ead7949490bc22b9883b6303a450`.
- `voice/.venv/bin/python -m pytest -q voice/tests/test_linux_packages.py` passou **79 testes**. Evidência: `.superpowers/sdd/2026-10-14-jarvis-linux/linux-package-recipe-tests-current-2026-10-22.log`, SHA-256 `dfc76be55c53ad0262d5bd0e0a0fbd010796848fe68dbfddf09e7b20c9fb01d3`.
- Essas verificações cobrem a regressão Python e as receitas declaradas; não substituem o teste do runtime instalado em cada distro, desktop, áudio físico ou portais.

### Integridade das fontes e rechecagem AT-SPI — 2026-10-22

- O arquivo fonte determinístico usado pelas receitas nativas contém 240 arquivos regulares, todos idênticos byte a byte ao checkout no commit `0ce1d68`; nenhuma divergência. SHA-256 do tarball: `9de99fdf45e97aaef1fed71862092fb75f59a80326547c18f18cc63b2d706f0d`. Registro: `.superpowers/sdd/2026-10-14-jarvis-linux/source-archive-integrity-2026-10-22.log`.
- A rechecagem AT-SPI opt-in do host Arch Wayland pulou antes da ação porque a sentinela não recebeu foco. Nenhuma mutação foi tentada. A aprovação positiva anterior na sessão KDE Wayland permanece como evidência separada; o resultado atual não a substitui. Registro: `.superpowers/sdd/2026-10-14-jarvis-linux/atspi-desktop-current-session-rerun-2026-10-22.log`.

### Pacote Arch construído do HEAD e smoke extraído — 2026-10-22

- `npm_config_audit=false scripts/build-package.sh --target arch --arch x86_64 --output /tmp/jarvis-arch-head` gerou o pacote Arch nativamente no host Arch x86_64 usando o commit `56324ac`. O pacote tem 229.834.022 bytes e SHA-256 `847a060134565455c6a69496c8242e099f66f5e4ba8f223e78bc865a02367dbd`.
- Sem instalar o pacote, extraí o artefato em diretório temporário. O launcher empacotado passou `--doctor` e `--list-mics`; o FFmpeg enumerou `default` e duas fontes PipeWire/Pulse ALSA. Nenhum áudio foi gravado. O diretório XDG isolado não tinha modelo Piper, e o comportamento de desktop autorizado por portal continua pendente.
- A primeira execução do build ficou parada em `npm ci` durante a auditoria npm; a repetição desativou apenas a auditoria para essa execução e concluiu. Evidência: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-current-head-package-smoke-2026-10-22.log`, SHA-256 `13e2cf00b80f3cd309d9e03308a390ae1e0e59ab11cf0f5c73afd07997d9ca54`.
- O overlay do mesmo pacote passou `python3 scripts/test-overlay-instance.py` em X11/Xvfb isolado com D-Bus privado. A instância secundária saiu sem derrubar a primária, e o menu e saída responderam via AT-SPI. Isso não substitui uma sessão Wayland real nem valida autorização/revogação de portais.
- Também validei o TTS do runtime extraído: Piper sintetizou uma frase de teste usando o modelo português local e produziu WAV PCM mono 22.050 Hz, com 2,90 s. O arquivo e o modelo foram usados sem tocar áudio nem acessar microfone. Registro: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-tts-smoke-2026-10-22.log`.
- No mesmo runtime extraído, a volta TTS→STT offline reconheceu “Olá tudo bem?” para a frase sintetizada “Olá, tudo bem?”, usando o modelo português Piper e o modelo Whisper base local, CPU int8. O WAV de 1,10 s, o log e seus hashes estão registrados na matriz; não houve captura física nem playback.
- Verifiquei também o overlay do pacote Arch dentro de Debian 13 Trixie com Weston headless. `ldd` resolveu as bibliotecas com requisito máximo `GLIBC_2.39` no host glibc 2.41; o teste de relançamento e AT-SPI passou. GDK emitiu avisos de seat sem teclado no Weston headless; o teste não cobre teclado/pointer reais, portais ou áudio. Evidência: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-overlay-debian-wayland-2026-10-22.log`.
- O pacote Arch do HEAD também passou VAD com fala sintética em tempo real: o fixture de 3,8 s continha 1,2 s de silêncio inicial, fala Piper e 1,5 s de silêncio final; a captura fechou em 3,07 s e o Whisper empacotado reconheceu “Olá tudo bem?”. A fala foi gerada localmente; microfone e playback não foram usados. Script, WAV segmentado e hashes estão registrados na matriz.

### Regressão dos portais Wayland — 2026-10-22

- `test_portal.py`: 12 testes passaram no harness de D-Bus privado. `test_linux_input.py`: 16 testes passaram para o backend Wayland e revogação simulada. `test_linux_screen.py`: 8 testes passaram para dispatch de captura e validação de URI/PNG.
- O serviço D-Bus da sessão KDE Wayland expõe Screenshot e RemoteDesktop; a introspecção confirmou os métodos de sessão e entrada. Nenhuma solicitação real de captura ou controle foi enviada. Consentimento, negação e revogação em portal real seguem sem validação.

### MCP empacotado no Arch — 2026-10-22

- O runtime extraído do pacote Arch atual inicializou por stdio os servidores
  `win_context` e `delegate_local` e listou as 9 ferramentas esperadas. Evidência
  e script: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-mcp-stdio-smoke-2026-10-22.{log,py}`.
- Nenhuma ferramenta foi chamada. Clipboard, processos, acessibilidade, contexto
  de desktop e acesso ao modelo continuam sem validação neste teste. A matriz
  passa a registrar **97/99** verificações; as duas não verificadas continuam
  sendo Gentoo AArch64 e Guix AArch64, cujos builds seguem pausados a pedido do usuário.

### Overlay Wayland do pacote Arch sob Weston isolado — 2026-10-22

- O binário do pacote Arch passou o relaunch/saída e a ativação dos controles
  AT-SPI no fixture `test-overlay-wayland.py`, executado em Debian 13 com Weston,
  D-Bus e AT-SPI privados. Log: `.superpowers/sdd/2026-10-14-jarvis-linux/arch-package-wayland-overlay-debian-run-2026-10-22-rerun.log`.
- Houve avisos GDK de seat no compositor sem hardware. O teste confirma o ciclo
  isolado Wayland, não entrada real, portais, áudio ou sessão desktop instalada.
  A matriz passa a registrar **98/100** verificações; Gentoo AArch64 e Guix
  AArch64 seguem sem validação e com builds pausados.

### Preparação de upgrade Solus — 2026-10-22

- `build-package.sh` agora aceita `--release` exclusivamente no alvo Solus; o
  padrão continua release 1. Quatro testes cobrem release padrão, geração da
  revisão 2 com hash da fonte, rejeição de zero e rejeição em outro alvo.
- A auditoria da matriz permite somente os dois alvos meta conhecidos
  (`linux source archive` e `debian cross-distro smoke`) e exige suas capacidades
  correspondentes. Regressão completa: 501 passed, 1 skipped.
- A mudança permite gerar os dois `.eopkg` necessários para o próximo teste,
  mas o upgrade real via eopkg ainda não foi executado e não aumenta a contagem
  aprovada da matriz.
- O novo `scripts/test-native-solus-upgrade.sh` foi exercitado em Arch descartável
  com eopkg/launcher simulados: releases 1→2, doctor, integridade, remoção e
  preservação dos sentinels passaram; uma segunda execução alterou um sentinel e
  foi recusada pelo comparador. Isso valida o fluxo do script, não o
  comportamento real do gerenciador Solus; a validação nativa segue pendente.

### Estado do upgrade eopkg Solus antes da execução nativa — 2026-10-22

- Na medição desta nota, a matriz incluía o upgrade Solus x86_64 como
  `unverified`. O script `test-native-solus-upgrade.sh` passou o fluxo positivo
  e detectou a alteração deliberada de um sentinel com eopkg simulado; isso não
  comprova instalação nem atualização pelo gerenciador real.
- Sem `eopkg`, `solbuild` ou artefato `.eopkg` disponível naquele momento, o teste
  real ficava pendente. O registro então marcava 98/101 verificações aprovadas
  (97,0%); Gentoo AArch64, Guix AArch64 e upgrade Solus x86_64 permaneciam sem
  validação.

### Auditoria do arquivo-fonte no HEAD atual — 2026-10-22

- `scripts/source-archive.py` gerou um arquivo com 242 membros regulares no
  commit `7244c6b`. Comparei cada membro byte a byte com o checkout: zero
  divergências. Log e SHA-256 do arquivo estão registrados em
  `docs/notes/linux-matrix.json`. Isso fecha a correspondência entre checkout e
  arquivo usado pelas receitas; a geração de SBOM continua pendente.

### Upgrade nativo eopkg Solus 4.9 x86_64 — 2026-10-22

- Duas releases `.eopkg` foram compiladas por `solbuild` no perfil Solus 4.9
  x86_64 e instaladas/atualizadas em um container descartável Solus. `eopkg
  check` e `jarvis --doctor` passaram antes e depois da atualização; os
  sentinelas de XDG CONFIG/DATA/CACHE/STATE permaneceram idênticos e a remoção
  manteve os dados do usuário.
- Os pacotes, logs de build e log do teste estão em
  `.superpowers/sdd/2026-10-14-jarvis-linux/` e seus hashes estão registrados
  na matriz. Isso comprova o ciclo de pacote no container, não a integração com
  desktop ou áudio físico.
- A matriz passa a 99/101 verificações aprovadas (98,0%). Guix AArch64 e Gentoo
  AArch64 continuam sem validação e pausados a pedido do usuário.

### Solus: addon nativo musl em pacote glibc — 2026-10-22

- A análise ABI do build Solus apontou `Missing library: libc.so` porque o
  `node_modules` trazia também `node.abi115.musl.node`, embora o pacote seja
  glibc. A receita agora elimina o addon musl durante a montagem do pacote.
- A release 3 foi construída com solbuild; o relatório não acusa mais
  `libc.so`. O abi-wizard ainda imprime um diagnóstico não fatal ao tentar
  seguir o link do Python externo `/usr/bin/python3.14` no staging.
- O upgrade da release 2 para a 3 passou em container Solus atualizado:
  `eopkg check`, `jarvis --doctor`, preservação byte a byte dos sentinelas
  XDG CONFIG/DATA/CACHE/STATE e remoção do pacote passaram. Artefato e logs têm
  hashes registrados na linha Solus de `docs/notes/linux-matrix.json`.


### Solus: enumeração ALSA pelo pacote instalado — 2026-10-22

- Em container Solus atualizado, a release 3 foi instalada e o launcher rodou
  `AUDIO_BACKEND=alsa jarvis --list-mics`. A enumeração listou `default`,
  `null` e `sysdefault:CARD=sofhdadsp`; `eopkg check` e remoção passaram.
- O log foi registrado na matriz. O container era headless: isso valida o
  caminho de enumeração do pacote, não captura de um microfone físico.


### Solus: fala sintética pelo runtime do pacote — 2026-10-22

- Na release 3 instalada, o Piper empacotado sintetizou “Olá, tudo bem?”.
  Um wrapper do FFmpeg alimentou a fala com silêncios sintéticos ao VAD
  empacotado; o faster-whisper empacotado reconheceu “Olá tudo bem?” em CPU.
  O segmento de 3,065 s terminou antes do fixture de 3,8 s, e `eopkg check`
  e remoção passaram.
- O teste foi headless e sintético: não capturou microfone físico nem reproduziu
  som. Script, pacote e log estão na linha Solus da matriz com SHA-256. A matriz
  atualiza para 101/103 verificações aprovadas (98,1%).


### Solus: reprodução Piper pelo pacote — 2026-10-22

- A release 3 instalada sintetizou “Olá, tudo bem?” com Piper e reproduziu a
  fala via ffplay e protocolo PulseAudio do PipeWire do host, direcionando-a a
  um sink nulo temporário. A captura do monitor teve áudio não silencioso
  (média −26,0 dB, pico −0,0 dB). O container não usou alto-falantes físicos
  nem capturou microfone.
- Script, pacote, captura WAV e medição de nível estão registrados com hashes
  na matriz. O estado atual é 102/104 verificações aprovadas (98,1%).


### Solus: inicialização dos servidores MCP instalados — 2026-10-22

- Com a release 3 instalada, o cliente MCP do runtime iniciou `win_context` e
  `delegate_local` pelo launcher `/usr/bin/jarvis --mcp` e concluiu
  `initialize` e `tools/list`. Recebeu as 8 ferramentas esperadas de
  `win_context` e a ferramenta `delegate_local`, com protocolo 2025-11-25.
- O teste não invocou ferramentas, portanto não valida clipboard, processos,
  acessibilidade ou agente. `eopkg check` e remoção passaram. Logs e script
  estão na matriz com hashes; o estado atual é 103/105 (98,1%).


### Solus: chamada somente leitura pelo MCP instalado — 2026-10-22

- O cliente MCP invocou `desktop_processes_text` com filtro literal `python` no
  servidor `win_context` da release 3. A chamada retornou `python3` e PID do
  próprio container descartável; `eopkg check` e remoção passaram.
- Isso exercita a rota de contexto Linux, mas lista processos do container, não
  do desktop hospedeiro. Não valida clipboard, AT-SPI ou outras ações. Script e
  log estão na matriz com hashes; total atual: 104/106 verificações aprovadas
  (98,1%).


### Arch: bloqueio de nomes dotenv sem diferenciar maiúsculas — 2026-10-22

- O pacote Arch x86_64 foi reconstruído a partir do commit `7c739d0`; `pacman -Qp`
  confirmou o metadado `jarvis-assistant 0.1.0-1`. O código `voice/local_files.py`
  extraído do artefato recusou escrita em `.ENV` e `.ENV.production` com erro de
  credencial/segredo, sem criar os arquivos.
- O smoke executou o código empacotado em diretório temporário. Não instalou o
  pacote com pacman; os hashes do pacote, script e log estão na matriz. Estado
  atualizado: 105/107 verificações aprovadas (98,1%).


### Arch: ciclo pacman com o pacote reconstruído — 2026-10-22

- O pacote `0.1.0-1` do commit `7c739d0` foi instalado no container Arch
  rolling descartável pelo pacman. `jarvis --doctor`, imports do runtime privado,
  `pacman -Qkk`, preservação dos dados do usuário, relançamento do overlay em
  Xvfb e remoção do pacote passaram.
- O relançamento foi isolado em Xvfb; isso não comprova uma sessão Arch real,
  áudio ou portais. Log e artefato estão na matriz com hashes. Estado atualizado:
  106/108 verificações aprovadas (98,1%).


### Arch: MCP empacotado informa capacidades headless — 2026-10-22

- O cliente MCP stdio iniciou o servidor `win_context` pelo launcher do pacote
  Arch x86_64 reconstruído no commit `365cd19`. A listagem de janelas e a leitura
  de clipboard retornaram `is_error=true` com o motivo específico de sessão
  gráfica ausente; a consulta somente leitura de processos continuou funcionando.
- O teste conferiu que os arquivos MCP/desktop do arquivo `.pkg.tar.zst` são
  idênticos aos usados pelo launcher no staging. É smoke do payload empacotado,
  não instalação pacman; o ciclo pacman está registrado separadamente. Script,
  log e pacote têm hashes na matriz. Estado atualizado: 107/109 (98,2%).


### Retomada Arch e verificação do arquivo Gentoo — 2026-10-22

- A instalação Arch do host continua em `jarvis-assistant 0.1.0-1`; o artefato
  local `arch-release5-build` foi produzido no commit `365cd19`, antes da
  atualização da explicação de capacidade Wayland em `505aa4a`.
- Tentei reconstruir o pacote atual com
  `scripts/build-package.sh --target arch --arch x86_64 --output
  /var/tmp/jarvis-current-package`. O build Rust incremental e `npm ci`
  passaram, mas `prepare-package.py` parou durante `pip install --target` com
  `OSError: [Errno 122] Disk quota exceeded`. Não foi gerado pacote novo nem
  executado `pacman -U`; a instalação do host permanece inalterada. Log em
  `/var/tmp/jarvis-current-package-build.log`, SHA-256
  `cb5b9eea24fac7714ba1037a746fca971b462dea89e6cf4ac10d787d71e92227`.
- A hipótese de que o worktree montado impede `scripts/source-archive.py` de
  acessar Git não foi reproduzida: o script gerou um tarball dentro de
  `jarvis-gentoo-aarch64` usando o mount `/src`. O container foi parado após a
  verificação e nenhum build Gentoo/Guix foi iniciado.


### Arch: instalação do pacote atual pelo pacman — 2026-10-22

- Baixei o artefato `jarvis-arch-x86_64` do CI no commit `8a63692`. O ZIP passou
  em `unzip -t`; seu SHA-256 bateu com o digest da API do GitHub, e o SHA-256 do
  pacote `0.1.0-1` bateu com `SHA256SUMS` do artefato.
- O pacote foi reinstalado pelo pacman no host Arch. `pacman -Qkk` reportou
  8.140 arquivos e nenhum alterado. `jarvis --doctor` agora informa Wayland
  disponível, autorização do portal necessária e validação de runtime pendente.
- `jarvis --list-mics` enumerou a fonte padrão e duas fontes PipeWire/ALSA; não
  gravei áudio.
- Os launchers instalados `win_context` e `delegate_local` completaram MCP
  initialize e `tools/list` por stdio, expondo 8 e 1 ferramentas. Nenhuma
  ferramenta foi invocada; controle real do desktop e áudio físico continuam
  pendentes. Log e hash estão registrados em `linux-matrix.json`.


### Arch: medição física de nível pelo pacote instalado — 2026-10-22

- Usando `capture.measure_level` do runtime instalado, FFmpeg capturou 0,5 s
  pela fonte padrão PipeWire/Pulse (média −27,6 dBFS, pico −10,9 dBFS) e 0,5 s
  pelo dispositivo ALSA `default` (média −25,8 dBFS, pico −14,3 dBFS).
- Ambos usaram o muxer `null`: nenhum WAV foi salvo e nenhuma fala foi
  transcrita. Isso comprova a medição de entrada pelo pacote instalado no Arch;
  PTT/VAD/STT e playback físico continuam pendentes. Log e hash estão na matriz.


### Rechecagem AT-SPI no KDE Wayland — 2026-10-22

- `JARVIS_DESKTOP_TESTS=1` executado com a venv do projeto: **1 passou**. A janela GTK descartável recebeu `Texto em segundo plano`; a sentinela manteve o foco e o campo vazio, e a posição do ponteiro permaneceu igual. Nenhum aplicativo do usuário foi alvo.
- Uma tentativa imediatamente anterior falhou porque o AT-SPI não conseguiu verificar qual controle mantinha foco. As duas tentativas seguintes passaram sem reiniciar o serviço AT-SPI. O resultado mostra funcionamento nesta sessão, com uma falha intermitente a investigar.
- Log: `.superpowers/sdd/2026-10-14-jarvis-linux/atspi-desktop-current-session-pass-2026-10-22.log`; SHA-256 `0d70d5e3025d41820ee8d7865e5ffaa062debd9f4fd30ca4b26f7820dfb180f9`.
- Isso valida edição acessível em segundo plano no KDE Wayland. Não valida injeção de teclado/clique pelo portal RemoteDesktop, revogação real, outros desktops ou outras distribuições.


### Portal RemoteDesktop real input probe — 2026-10-22

- Em uma janela GTK temporária mantida viva entre chamadas, o portal KDE Wayland enviou `Jarvis RemoteDesktop OK 123`; o próprio campo confirmou o texto e registrou os eventos de teclado. A ferramenta manteve o retorno `unconfirmed`, que informa corretamente que ela não verifica por si só a aceitação pelo app.
- O teste de ponteiro não passou: um clique destinado ao botão da janela descartável retornou `unconfirmed`, mas o contador ficou em zero e a janela perdeu o estado ativo. Parei os cliques nesse ponto. O mapeamento de coordenadas/stream continua sem prova funcional.
- Um novo pedido de consentimento ficou pendente no KDE e foi encerrado sem emitir entrada. O teste precisa de nova autorização explícita no diálogo do portal para continuar.
- Evidência local: `.superpowers/sdd/2026-10-14-jarvis-linux/wayland-remotedesktop-input-probe-2026-10-22.log`; SHA-256 `b4bd5074338ea466470a2b797792d1399922db67cc38c637ab1858812a269776`.
- Referência do protocolo: [XDG Remote Desktop](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html) especifica consentimento no `Start()` e coordenadas absolutas no espaço lógico do stream. [XDG ScreenCast](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html) define `position`/`size` em coordenadas do compositor; a falha observada ainda precisa ser localizada no mapeamento do compositor KDE ou na seleção do stream.

### Resolver de nomes do menu Linux — Arch KDE Wayland — 2026-10-22

- `open_target("System Settings")` resolveu o nome visível pelo arquivo `.desktop` instalado; `open_target("systemsettings")` usou o executável do `PATH`.
- Em cada chamada, o processo `systemsettings` recebeu um PID novo. Encerrei somente os dois processos descartáveis criados pelo teste.
- Os dois retornos permaneceram `unconfirmed`: a validação prova despacho e início do processo, não o conteúdo/estado da janela. Ela cobre Arch KDE Wayland, não outras distros/ambientes.
- Testes: `test_linux_input.py` 23 passed; `test_linux_packages.py` 80 passed; `test_linux_install.py` 5 passed. `compileall` e `git diff --check` passaram.
- Evidência: `.superpowers/sdd/2026-10-22-linux-desktop-app-name-resolution/host-kde-app-name-resolution.log`, SHA-256 `7566ec59cd67648ce8417b63711a5800723807515f40ce51a8ee6acb1e05369e`.

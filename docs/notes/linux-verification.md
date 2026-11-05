# Evidências do porte Linux — execução em andamento

Worktree: `.worktrees/linux-port`, branch `feat/linux-port`.
Não é uma declaração de suporte universal ou conclusão do porte.

### Regressão completa do worktree atual — 2026-10-27

- `scripts/verify-linux.sh` saiu com código 0. Resultados: voz **560 passou, 1
  ignorado** (precondição de sessão desktop autorizada), `win_context` MCP **16**,
  `delegate_local` MCP **17**, GUI **5**, OpenCode **120**, testes Tauri Rust **7**;
  build release Tauri com `--locked` passou.
- Esta execução cobre regressões do código-fonte no worktree. Não conclui os
  ciclo de pacote Guix ARM64 nem valida autorizações reais de portais,
  sessões GNOME/X11 completas ou áudio físico ponta a ponta.

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

### Regressão direcionada no worktree atual — 2026-10-26

- `node --test gui/tests/model-settings.test.mjs`: 3 passed.
- `python3 -m pytest -q voice/tests/test_model_selection.py voice/tests/test_linux_input.py`:
  34 passed.
- Estes testes cobrem o catálogo/seleção do modelo e a resolução de ações Linux;
  não substituem ciclos de pacote, autorização em desktop real ou validação de
  áudio físico.
- Regressão estendida no mesmo worktree: `node --test gui/tests/*.test.mjs`
  passou (5 testes) e `python3 -m pytest -q voice/tests/test_linux_packages.py
  voice/tests/test_linux_install.py voice/tests/test_linux_input.py` passou
  (116 testes, 2026-10-26). Essa execução cobre receitas e instalação Linux em
  mocks, não a instalação em cada gerenciador nativo.
- Suíte completa de voz no worktree atual: `python -m pytest -q -rs
  voice/tests` passou (529 passed, 1 skipped em 31,55 s, 2026-10-26). O skip
  foi `test_atspi_desktop.py`, que exige sessão interativa Linux autorizada.
- Suítes MCP no venv atual: `voice/.venv/bin/python -m pytest -q -c
  mcp_servers/win_context/pytest.ini mcp_servers/win_context/tests` passou
  (16 testes) e o comando equivalente de `delegate_local` passou (17 testes,
  2026-10-26).
- Suíte de plugins/OpenCode no worktree atual: `node
  --experimental-strip-types --test $(rg --files .opencode -g '*.test.ts'
  -g '!node_modules/**' | sort)` passou (120 testes, 2026-10-26), incluindo
  dois testes novos do plugin `select_jarvis_model` para tag local e aviso de
  privacidade do modelo cloud. O plugin usa `fetch` simulado e não acessa o
  serviço Jarvis real.
- Testes dos scripts de empacotamento e CI: `python3 -m pytest -q
  scripts/tests` passou (9 testes, 2026-10-26).
- Source archive do worktree atual: gerei e inspecionei um tarball temporário
  (257 arquivos, 545.256 bytes); confirmou presença dos manifests npm e da
  receita Gentoo, e exclusão de `node_modules` e `target`.

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

Na auditoria de 2026-10-22, as receitas não declaravam `libei` e a integração
usava RemoteDesktop D-Bus; o mapeamento real do ponteiro ainda não tinha sido
validado. Antes de escolher uma dependência obrigatória, foi consultada a
disponibilidade nos repositórios dos alvos já declarados:

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
dinâmico ou sessão Wayland. Depois dela, o backend EIS/libei foi implementado
como caminho opcional, com fallback para RemoteDesktop legado.

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
- A inspeção do caminho confirmou que `WaylandInput.execute` envia o node ID do stream selecionado e `(x,y)` sem escala, limitando-os a `logical_size`; streams sem essa propriedade agora são recusados com `unsupported` (sem fallback para `size`). Isso corresponde à especificação de `NotifyPointerMotionAbsolute`, que define coordenadas no espaço lógico do stream. O resultado anterior não identifica se a falha foi seleção de stream, posição fornecida pelo agente ou comportamento do portal/compositor; nenhuma correção no mapeamento foi aplicada sem nova reprodução autorizada.
- Um novo pedido de consentimento ficou pendente no KDE e foi encerrado sem emitir entrada. O teste precisa de nova autorização explícita no diálogo do portal para continuar.
- Evidência local: `.superpowers/sdd/2026-10-14-jarvis-linux/wayland-remotedesktop-input-probe-2026-10-22.log`; SHA-256 `b4bd5074338ea466470a2b797792d1399922db67cc38c637ab1858812a269776`.
- Referência do protocolo: [XDG Remote Desktop](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html) especifica consentimento no `Start()` e coordenadas absolutas no espaço lógico do stream. [XDG ScreenCast](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html) define `position`/`size` em coordenadas do compositor; a falha observada ainda precisa ser localizada no mapeamento do compositor KDE ou na seleção do stream.

### Resolver de nomes do menu Linux — Arch KDE Wayland — 2026-10-22

- `open_target("System Settings")` resolveu o nome visível pelo arquivo `.desktop` instalado; `open_target("systemsettings")` usou o executável do `PATH`.
- Em cada chamada, o processo `systemsettings` recebeu um PID novo. Encerrei somente os dois processos descartáveis criados pelo teste.
- Os dois retornos permaneceram `unconfirmed`: a validação prova despacho e início do processo, não o conteúdo/estado da janela. Ela cobre Arch KDE Wayland, não outras distros/ambientes.
- Testes: `test_linux_input.py` 23 passed; `test_linux_packages.py` 80 passed; `test_linux_install.py` 5 passed. `compileall` e `git diff --check` passaram.
- Evidência: `.superpowers/sdd/2026-10-22-linux-desktop-app-name-resolution/host-kde-app-name-resolution.log`, SHA-256 `7566ec59cd67648ce8417b63711a5800723807515f40ce51a8ee6acb1e05369e`.


### Build Arch padrão do working tree e regressão atual — 2026-10-23

- `scripts/build-package.sh --target arch --arch x86_64 --output /tmp/jarvis-arch-current-build-network` concluiu a partir da árvore de trabalho. O downloader obteve o OpenCode 1.18.23 fixado e validou seu checksum; `npm audit` reportou zero vulnerabilidades; o runtime Python privado instalou e passou pelos imports nativos/staging doctor; `makepkg` gerou `jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst`.
- O pacote mede 230.793.449 bytes; SHA-256 `99c681b5441721f2f0a10b8093c66bc97bb7560311f5159e8b080cb3a8a659e2`. `pacman -Qip` confirmou arquitetura x86_64, versão e dependências declaradas. O artefato foi construído e inspecionado, mas não instalado; o lifecycle de dependências/upgrade/remoção desta compilação permanece pendente.
- O doctor do staging encontrou a sessão Wayland e runtime Piper/OpenCode, mas marcou captura Pulse indisponível porque o host não expõe fontes de entrada enumeráveis. Não houve gravação, autorização de portal ou alteração do pacote instalado.
- Regressão da árvore atual: `python -m pytest -q -rs voice/tests` — **519 passed, 10 skipped**; skips: integração AT-SPI requer desktop autorizado, oito casos portal precisam de `dbus_next` no Python host (disponível no runtime privado), e um caso STT precisa de `faster_whisper` no host. Os sete arquivos/suítes Node executados passaram; `cargo test --manifest-path gui/src-tauri/Cargo.toml` — **7 passed**; `git diff --check` passou.
- O primeiro pytest sem permissão de socket falhou ao tentar abrir localhost; a execução autorizada sem essa restrição passou. A enumeração de fontes de áudio e o build do pacote não contam como validação física de microfone/alto-falante.


### Segurança do plugin, lifecycle Arch e SBOM — 2026-10-24

- O `npm audit` atualizou a base de avisos e encontrou duas vulnerabilidades altas em `zod@4.1.8`, dependência de `@opencode-ai/plugin@1.18.23`. O fix automático propunha downgrade major do plugin para `0.9.11`, incompatível com o OpenCode empacotado. Adicionei override restrito para `zod@4.6.6`, preservando as versões do OpenCode e do `effect@4.0.6`. A árvore instalada mostra `@opencode-ai/plugin@1.18.23` + `zod@4.6.6`; o audit retorna zero vulnerabilidades e os **112 testes Node** de segurança, ações, modelos e interface passaram.
- Rebuild padrão: `scripts/build-package.sh --target arch --arch x86_64 --output dist/native`. O artefato `jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst` tem 231.379.841 bytes e SHA-256 `754e021089b49b5fcb81a4b799d2d5ce71c496af834a07e413a9bd3dc405345c`. Inspeção confirmou x86_64, dependências/licenças Arch e Zod 4.6.6 no conteúdo.
- O lifecycle completo em Arch descartável passou: sincronização do alvo, resolução de dependências, instalação via pacman, doctor/imports do runtime, `pacman -Qkk` (**8.388 arquivos, 0 alterados**), smoke de clipboard e relançamento/saída do overlay em Xvfb, remoção e preservação dos dados de usuário. Container terminou com exit code 0. O teste não executou upgrade de uma revisão anterior deste exato artefato.
- Gerei o SBOM CycloneDX JSON 1.7 do pacote com Syft 1.55.0. O inventário contém 189 componentes, incluindo dependências npm/Python; CycloneDX CLI validou o arquivo sem erros. Artefatos e hashes estão em `dist/native/` (diretório ignorado pelo Git).
- O host segue sem fonte Pulse enumerável e não houve captura física de voz nem autorização nova do portal. O SBOM e o lifecycle de pacote não substituem essas verificações de desktop e áudio.

### Catálogo e seleção de modelos Ollama — Arch Linux — 2026-10-22

- O backend consulta `/api/tags` no `OLLAMA_HOST`, marca tags `:cloud`, valida a seleção por correspondência exata e persiste `agent_model`; tentativa inválida não substitui a escolha anterior. O endpoint `/settings` não aceita contornar essa validação.
- `/models` e `/model` têm cobertura HTTP; o catálogo injeta todos os IDs atuais no provider Ollama via `OPENCODE_CONFIG_CONTENT`. No host Arch, com OpenCode 1.18.23 e Ollama local, `opencode models ollama` listou as tags recebidas do catálogo (`beam:cloud`, `minimax-m3.1-flash:cloud`, `qwen3:8b` e outras), além do modelo local já configurado. Não foi feita inferência nem alterada a seleção persistida do usuário.
- Um `opencode serve` temporário, iniciado na raiz do projeto com a configuração dinâmica, respondeu à API `/config` com disponibilidade para `ollama/minimax-m3.1-flash:cloud` e `ollama/qwen3:8b`. A sonda não fez inferência; o servidor temporário foi encerrado. Se um servidor já existente não declarar o modelo escolhido, o Jarvis agora o detecta e usa `opencode run` com o catálogo atualizado, sem encerrar o processo existente.
- A seleção é encaminhada às próximas chamadas de chat, visão e ações; `local-executor` continua com seu modelo fixo independente. O plugin de voz só troca após pedido explícito e alerta sobre envio de transcrição/prompt/contexto visual para modelos cloud.
- Testes Python completos: **524 passed, 1 skipped** com temporários em `/dev/shm`; instalação/pacotes: **85 passed**. Testes Node completos de plugins, SafetyGate, ações e painel: **116 passed**. O diretório `/tmp` estava sob quota, então a verificação foi movida para `/dev/shm`; nenhum dado ou artefato foi apagado.
- O ensaio real confirmou descoberta das tags pelo OpenCode, não uma chamada de inferência, troca via painel/voz ou persistência após reinício. Essas validações continuam pendentes.
- Revisão independente encontrou dois caminhos de execução sem a configuração dinâmica: `--do` e o fallback `opencode run` da visão. Ambos agora recebem o catálogo Ollama atual. Também foi corrigida a precedência dos `.desktop` do usuário sobre cópias do sistema, com teste de regressão; a resolução de locale agora respeita `LC_ALL`/`LC_MESSAGES` antes de `LANGUAGE`.
- Revalidação após as correções: suíte Python completa **527 passed, 1 skipped** (AT-SPI exige desktop interativo); suíte Node **116 passed**. `compileall`, validação JSON e `git diff --check` também passaram.


### Rebuild e reinstalação pacman do working tree — Arch — 2026-10-22

- Compilei o pacote nativo Arch a partir do working tree e reinstalei pelo Polkit. O pacote mantém a versão `0.1.0-1`; foi uma reinstalação do mesmo release para colocar no sistema as alterações atuais. SHA-256 do pacote gerado: `f6ffadb1de2baed1695f9a06501a488b7fb0dbf7b29a9a69735768cb2b7f6743`.
- `pacman -Qk jarvis-assistant`: 8.142 arquivos, nenhum ausente. `jarvis --doctor` encontrou FFmpeg/FFplay, Piper, OpenCode empacotado, modelo de voz e backend Wayland. O teste não concedeu consentimento ao portal nem enviou entrada ao desktop.
- Também validei uma inferência isolada com MiniMax Cloud e registrei seu resultado e escopo na matriz.
- A pedido do usuário, removi somente duas pastas temporárias identificadas como scratch de testes Jarvis e sem processos usando-as: `/tmp/jarvis-flatpak-lifecycle-20261020` e `/tmp/jarvis-arch-package-smoke.pd3zI5`. `/tmp` passou de 92% para 68% de uso; pastas de progresso Guix/Gentoo, evidências Flatpak e arquivos de outros aplicativos foram preservados.


### Correção da auditoria npm do plugin OpenCode — Arch — 2026-10-22

- Fixei `@opencode-ai/plugin` em `1.18.23`, mesma versão do binário, e substituí a dependência transitiva `effect@4.0.0-beta.83` por `effect@4.0.6`. A instalação npm reportou zero vulnerabilidades; uma verificação de `tool()` confirmou a API usada pelos plugins.
- Recompilei e reinstalei o pacote pacman. `pacman -Qk` encontrou 8.203 arquivos sem ausências, `jarvis --doctor` reconheceu dependências e backend, e uma chamada real iniciada a partir de `/usr/lib/jarvis` retornou `INSTALLED_JARVIS_PLUGIN_OK` com um prompt sem dados pessoais.
- O teste local com `qwen3:8b` excedeu 180 s sob carga de CPU; o teste equivalente no MiniMax Cloud autorizado terminou com sucesso. O timeout não indicou erro de carregamento do plugin.
- SHA-256 do pacote atualizado: `d6fa9c8f3bc814d685ba5912817994be1ed3f20b2daf827ae532a90143b77183`.


### Síntese local de voz — pacote instalado no Arch — 2026-10-22

- O Piper empacotado sintetizou a frase descartável `Teste de síntese local do Jarvis.` em um WAV PCM mono de 22.050 Hz e 1,997 s, verificado com `ffprobe`. O arquivo foi criado em `/dev/shm`; não reproduzi áudio. Isso confirma síntese, mas a saída física pelo alto-falante continua pendente.

### Investigação do tempo de inferência local — Arch sem GPU NVIDIA — 2026-10-22

- A inferência direta de `qwen3:8b` por `/api/generate` respondeu em 10,1 s. Pela API OpenAI-compatible, a mesma classe de resposta com `reasoning_effort: none` terminou em 2,2 s. Isso mostra que o modelo e o servidor Ollama respondem localmente.
- Já `RunClient` (que executa OpenCode 1.18.23 com os plugins e o agente do Jarvis) excedeu 90 s tanto com `qwen3:8b` quanto com `qwen2.5-coder:7b`; um teste anterior do Qwen3 excedeu 180 s. Nos logs do Ollama, os pedidos chegaram por `/v1/chat/completions`; um prompt de 541 tokens levou 34,5 s só na avaliação, e o OpenCode disparou outra solicitação de 1.813 tokens. A máquina está executando os modelos em CPU, sem driver NVIDIA ativo.
- A causa está no caminho/contexto/gerações do OpenCode e do modelo local nesta máquina, não na disponibilidade de tags nem no empacotamento Arch. Mantive o limite como pendência de runtime. O teste cloud MiniMax instalado passou com uma resposta curta. O repositório upstream registra relatos compatíveis de chamadas longas de modelos Ollama com raciocínio pelo OpenCode; [issue upstream #43293](https://github.com/anomalyco/opencode/issues/43293).
- Rechecagem em 2026-10-25: a API direta `/v1/chat/completions` com prompt de 29 tokens, `reasoning_effort=none` e `max_tokens=16` respondeu `JARVIS_LOCAL_SMOKE_OK` em 3,18 s. No OpenCode 1.18.23, `RunClient` ainda excedeu 90 s na configuração padrão. Com configuração temporária de `reasoningEffort: none`, a chamada continuou gerando no CPU a cerca de 5 tokens/s; o log registrou um contexto de 544 tokens e uma segunda solicitação de 1.822 tokens. Uma tentativa curta expirou em 30 s. Configurar `maxTokens: 16` no modelo não concluiu o fluxo dentro desse limite. As chamadas enviaram somente prompts de smoke sem dados pessoais.
- O contraste confirma que Ollama e o modelo respondem neste host, enquanto o caminho OpenCode/agente com contexto e ferramentas continua lento. Não encontrei ainda um ajuste de configuração compatível com o OpenCode empacotado que feche a chamada; não tratar como falha de empacotamento Linux. A pendência de runtime segue aberta; MiniMax Cloud continua sendo a rota validada para resposta rápida neste host.
- Em seguida, o backend padrão `ServeClient` foi exercitado com um `opencode serve` descartável na porta 4117, modelo `ollama/qwen3:8b` e o mesmo prompt não pessoal. A chamada excedeu o timeout explícito de 60 s. O log do Ollama registrou prompt de 541 tokens, 26,63 s para avaliar 512 tokens e saída a cerca de 5,1 tokens/s antes do cancelamento. O processo OpenCode iniciado para o teste foi encerrado no `finally`; não ficou servidor na porta 4117. Isso confirma a lentidão também no caminho padrão Linux, sem alterar settings nem enviar dados pessoais.

### Regressão atual do working tree — Arch Linux — 2026-10-22

- `python -m pytest -q -rs voice/tests`: **518 passaram, 10 foram ignorados**.
  Os skips foram 1 teste de desktop que exige sessão interativa autorizada, 8
  testes de portal sem `dbus_next` no Python do host e 1 teste STT sem
  `faster_whisper` no host.
- Suíte Node de SafetyGate, ferramentas Windows/OpenCode, catálogo de modelos e
  painel: **112 passaram**.
- São verificações sintéticas no working tree; não substituem builds em cada
  distro, testes de portal em sessão real nem áudio físico. O registro está na
  última entrada de `linux-matrix.json`.

### Rebuild do payload e instalação pacman a partir do working tree — Arch — 2026-10-22

- O build padrão compilou Rust e instalou as dependências npm sem vulnerabilidades,
  mas o download do arquivo de release OpenCode 1.18.23 expirou após 60 s. A
  execução encerrou sem instalar o resultado parcial.
- Continuei usando o binário OpenCode já presente no pacote instalado. Sua versão
  é `1.18.23` e seu SHA-256 (`de0724a36eaf3166e7f1ff38d0f4478b95ccc47725e9597b3fe66d3d3e18baa2`)
  bate byte a byte com o bundle cacheado da compilação anterior. Com esse bundle,
  `prepare-package.py` montou o payload atual: `jarvis --doctor` e os imports do
  runtime passaram. O doctor detectou FFmpeg/FFplay, Piper, o OpenCode e o backend
  Wayland; não concedi autorização de portal nem iniciei controle da área de trabalho.
- Empacotei o payload preparado com `makepkg` temporário e instalei
  `jarvis-assistant 0.1.0-2` via pacman. `pacman -Qkk` encontrou 8.203 arquivos,
  0 alterados. SHA-256: `984e1493b0988f7f90f53b55aebc1d2ebf862d9e825eab31188db000b784d6ce`.
- Isso verifica o payload e o ciclo de instalação Arch do working tree; ainda é
  necessário repetir `scripts/build-package.sh` depois de um download novo do
  arquivo oficial. O resultado e essa limitação também constam na matriz.

### Regressão X11 isolada do pacote Arch atual — 2026-10-22

- `python scripts/test-overlay-instance.py /usr/bin/jarvis-overlay` passou em
  Xvfb/D-Bus privado: a janela principal ficou acessível, a segunda execução
  encerrou sem substituir a primeira, e as ações acessíveis de menu e saída
  fecharam o processo de teste corretamente.
- `python scripts/test-x11-tools.py` passou: `xdotool` consultou o ponteiro e
  `xclip` fez roundtrip de uma string descartável no clipboard X11 isolado.
- Esses smokes usam o pacote Arch 0.1.0-2 instalado a partir do payload atual.
  Não usam microfone, portal real nem aplicativos do usuário; não provam sessão
  GNOME/KDE real ou clipboard de Wayland. A tentativa de repetir o ciclo completo
  em container ficou impedida por timeout ao baixar dependências do mirror Arch.

- A continuação do ciclo em container sincronizou e atualizou a base Arch, mas
  abortou ao baixar as dependências do pacote: o mirror transferiu a assinatura
  de `iso-codes` abaixo do limite de 1 byte/s e o pacman encerrou a transação antes
  de instalar o Jarvis. O processo não estava parado na extração do pacote.
- Em separado, com a rede desativada e o perfil seccomp padrão do Docker,
  `pacman -Udd --noconfirm` instalou o arquivo local e `pacman -Q` reconheceu
  `jarvis-assistant 0.1.0-3`. Esse ensaio ignora dependências (`-dd`), então prova
  apenas leitura/transação do arquivo local; o ciclo completo continua pendente.

### Preservação de configuração inline OpenCode e reinstalação pacman — Arch — 2026-10-22

- Corrigi `opencode_catalog_environment`: agora mescla as tags Ollama com
  `OPENCODE_CONFIG_CONTENT` já definido, preservando modelo padrão, outros
  provedores, opções do Ollama e modelos configurados manualmente. O teste novo
  falhou antes da correção pela ausência do campo `model`, e passou depois.
- Regressão completa: **519 passed, 10 skipped** em Python (1 desktop interativo,
  8 portal sem `dbus_next`, 1 STT sem `faster_whisper` no Python host) e **112
  passed** em Node.
- Repreparei e instalei o working tree como `jarvis-assistant 0.1.0-3` via
  pacman, usando o OpenCode 1.18.23 que já estava instalado; o download padrão
  do arquivo de release continua pendente. `pacman -Qkk` encontrou 8.203 arquivos,
  0 alterados; o arquivo Python e o plugin instalados correspondem ao checkout,
  e `jarvis --doctor` passou. SHA-256: `39fa51857168b2de1e8ebff07331e91dd7a0e0ebd790dc3ba078c29e5eb079f2`.


### Compatibilidade de npm nas receitas e ciclo Debian atualizado — 2026-10-24

- O primeiro build Debian Trixie com a atualização do lockfile falhou no `npm ci` do npm 9.2, que não reconhecia as dependências efetivas de overrides criadas por npm 10. Uma regeneração limpa do lock com npm 10.9.9 resolveu `effect@4.0.6` e `zod@4.6.6`; audit e instalação limpa passaram sem vulnerabilidades.
- Adicionei `scripts/npm-ci.sh`, fixado em npm 10.9.9 via `npx`, e direcionei as receitas de pacote e preparadores Flatpak/Guix/instalação fonte por ele. Isso mantém o lock reproduzível em sistemas que ainda distribuem npm 9.
- O build Debian Trixie x86_64 passou: Rust, instalação npm, auditoria zero, download/verificação do OpenCode 1.18.23, staging/imports Python e `dpkg-buildpackage`. `.deb` SHA-256 `4ceb09b855436b612239200018465e9e750c82af35e867a88006d300c279170c`; `dbgsym` SHA-256 `3183eeae88559383b32b325412612702f4e6a386ec1fbcea4d449473b392fd88`. O pacote extraído contém `zod@4.6.6`.
- O lifecycle Debian em container descartável passou: resolução/instalação apt, doctor, imports privados e AT-SPI, integridade, smoke X11 de clipboard/overlay, preservação de dados e remoção. Não houve teste de upgrade ou áudio físico.


### Source archive e lifecycle RPM Fedora 44 — 2026-10-25

- O primeiro build Fedora 44 mostrou que um `.opencode/.gitignore` local podia esconder `package.json` e `package-lock.json` num índice Git vazio; o source archive não incluía os manifests e `npm ci` falhava. `scripts/source-archive.py` agora adiciona explicitamente os dois manifests essenciais. Um checkout temporário com índice novo confirmou os membros dos manifests e `scripts/npm-ci.sh` no arquivo.
- Build Fedora 44 x86_64 passou para RPM `0.1.0-1.fc44` e `0.1.0-2.fc44`, mais SRPMs. npm 10.9.9 auditou zero vulnerabilidades; Rust, Python 3.14 privado, staging e imports passaram. RPMs: SHA-256 `e3475673329174033d1f64246fc34cb1ef14df996b387441a50f7cf50451e805` e `c1347b69b818fa8bc9c2c858adb938621cecf6a2fcf50f3a775d4be9d8d7d8ee`.
- O teste descartável Fedora instalou a revisão 1, verificou runtime/imports/integridade e smoke do overlay em Xvfb, gravou fixtures de configuração/modelo/cache, atualizou para revisão 2, confirmou hashes sem alteração, repetiu os checks e removeu o pacote. Resultado final `PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.


### Upgrade do DEB Debian atual — 2026-10-25

- Gerei a revisão `0.1.0-2` do `.deb` `0.1.0-1` reconstruindo apenas os metadados de versão, conforme o workflow Debian existente. No container Debian 13, o teste instalou a revisão 1, gravou fixtures de configuração/modelos/cache, atualizou para revisão 2, confirmou hashes preservados, executou doctor/imports/integridade e smoke do overlay em Xvfb, removeu o pacote e confirmou os hashes novamente. Resultado: `PASS: DEB upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.
- SHA-256 `.deb` revisão 1: `4ceb09b855436b612239200018465e9e750c82af35e867a88006d300c279170c`; revisão 2: `1d8a211034e27633116c57dfa4fa3a48078e16d9506609862e8020bd35d4c4cc`.


### Flatpak x86_64 reconstruído pelo lockfile atual — 2026-10-25

- Os commits do GNOME SDK 49, GNOME Platform 49 e Rust extension 25.08 instalados no host coincidiram com `runtime-pins.json`. `scripts/build-flatpak.sh dist/current-lock/flatpak` passou: preparo do source archive (Cargo vendorizado, npm via CLI fixado e wheelhouse privado), download/checksum do OpenCode, build offline no SDK, commit no OSTree local e geração do bundle de 172 MiB. SHA-256: `c204474528354854c9f8f1509e84327c175689a9609493ab4fce97c2618c2db8`.
- Instalei o bundle no escopo do usuário pela origem local `jarvis-linux-validation`; doctor e imports privados/AT-SPI passaram, a versão OpenCode é 1.18.23. Doctor confirma sessão Wayland e backend Pulse disponível; gravação física, síntese Piper e controle via portal continuam sem validação funcional. Não lancei interação gráfica nem solicitei autorização nova do portal.


## Build Arch x86_64 do worktree atual

Em 2026-10-25, `makepkg --nodeps --force` gerou `jarvis-assistant 0.1.0-2`
com as fontes atuais e `scripts/npm-ci.sh`; `npm audit` reportou zero
vulnerabilidades. O build Rust release, o runtime Python privado, o doctor de
staging, imports nativos e a criação do pacote passaram. Para contornar o
download GitHub que não progredia, foi reutilizado o OpenCode 1.18.23 local; seu
SHA-256 (`de0724a3…e18baa2`) coincide com as duas cópias retidas dos builds Arch
e com `/usr/lib/jarvis/bin/opencode`. O pacote resultante tem SHA-256
`d8a11df0…d663eb9`.

O ciclo foi concluído em um container Arch descartável preparado com as
dependências: instalou `0.1.0-1`, atualizou para `0.1.0-2`, confirmou hashes
inalterados para configuração/modelos/cache, verificou 8.388 arquivos com zero
alterações, executou o smoke de overlay/AT-SPI em Xvfb e removeu o pacote. O
resultado final foi `PASS: Arch package upgrade, installed runtime/integrity,
removal and unchanged config/model-data/cache hashes`.


## Build e upgrade DEB no Ubuntu 24.04 x86_64

Em 2026-10-25, o Dockerfile Ubuntu compilou as fontes atuais do worktree com
Rust 1.95 e Python 3.12. `scripts/npm-ci.sh` instalou as dependências com zero
vulnerabilidades; o staging do runtime Python privado e os imports passaram. O
download do OpenCode 1.18.23 no GitHub não avançou, então o build temporário
recebeu o binário local já verificado (SHA-256
`de0724a36eaf3166e7f1ff38d0f4478b95ccc47725e9597b3fe66d3d3e18baa2`). Nenhum
arquivo versionado foi alterado para essa substituição.

O DEB `0.1.0-1` (SHA-256
`65c9c0cf9f7a04ddeb4521cc9d4c773e934e58af0f3103c36e6745c6437502ad`) foi
instalado em Ubuntu 24.04; doctor, imports/runtime, integridade, overlay em
Xvfb/AT-SPI e remoção passaram. Para o ciclo de upgrade, foi produzido um
segundo pacote com o mesmo payload e apenas `DEBIAN/control` alterado para
versão `0.1.0-2` (SHA-256
`ddd81386e9fc5bb5f20f3f72aec51a93f7b8e88c8dc30ec89adb0dd42da80e67`). O teste
instalou `0.1.0-1`, atualizou para `0.1.0-2`, preservou hashes de configuração,
modelos e cache, rodou novamente o smoke de instalação/remoção e terminou com
`PASS: DEB upgrade, installed runtime/GUI/integrity, removal and unchanged
config/model-data/cache fixture hashes`. A revisão 2 verifica o mecanismo de
upgrade do dpkg, não é um segundo build de fontes.


## Build e ciclo instalado do APK Alpine 3.24 x86_64 do worktree atual

- `docker build --progress=plain --build-arg JARVIS_TEST_PACKAGE_UPGRADE=1 -f packaging/alpine/Dockerfile -t jarvis-alpine-current-upgrade .` compilou CTranslate2 e Piper para musl, compilou o overlay, verificou OpenCode 1.18.23 e criou APKs assinados `0.1.0-r0` e `0.1.0-r1`.
- SHA-256 do APK r0: `0c744ca8e6fc1d6cfb1f95ada3c0111daf8e8f1da269a886ba9477724a20e890`; r1: `ed063a4d5b229f97e2fe0755df9305786408d2160ff805a81721cfcc0bdf9857`.
- `test-native-apk-upgrade.sh` instalou r0 com `JARVIS_APK_REQUIRE_SIGNATURE=1`, atualizou para r1, preservou hashes de `settings.json`, dados em `models/` e cache, validou runtime/imports, AT-SPI, ferramentas e overlay em Xvfb, removeu Jarvis e confirmou os hashes novamente. Resultado: `PASS: APK update, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.
- Artefatos retidos em `dist/current-lock/alpine-upgrade/`; o teste não cobre áudio físico, TTS, portais ou desktop real.

Em 2026-10-25, `docker build -f packaging/alpine/Dockerfile` concluiu com as
fontes atuais. A receita compilou CTranslate2, Piper, o overlay Tauri e o runtime
Python musl; OpenCode 1.18.23 foi verificado para `x86_64-musl`, imports nativos
passaram e `npm audit` encontrou zero vulnerabilidades. O APK
`jarvis-assistant-0.1.0-r0.apk` tem SHA-256
`391c5a52ace36f634f808fb688b7c1db505c170d5fcbcfc31139d1596cd089eb`.

A primeira tentativa achou uma falha nas receitas: o lockfile atual não instala
mais o addon opcional `msgpackr-extract`, mas Alpine e Void ainda o exigiam e
Gentoo tentava removê-lo sem verificar se existia. Removi essas suposições das
receitas Alpine, Void glibc/musl e Gentoo; o rebuild completo passou.

O APK assinado foi instalado em container Alpine 3.24 descartável com a chave
pública do build confiada e `JARVIS_APK_REQUIRE_SIGNATURE=1`. Doctor, imports do
runtime privado, AT-SPI, ferramentas nativas, relançamento/saída do overlay sob
Xvfb, remoção e preservação dos dados de usuário passaram. O resultado foi
`PASS: package lifecycle/imports/integrity/data preservation and isolated GUI
relaunch`. O build e o doctor estavam headless: áudio físico, síntese TTS,
autorização de portais e upgrade entre duas revisões continuam sem validação
para este artefato atual.

## Build e ciclo instalado RPM RHEL 10 x86_64 do worktree atual

- `docker build --progress=plain --build-arg JARVIS_TEST_PACKAGE_UPGRADE=1 -f packaging/rpm/rhel/Dockerfile -t jarvis-rhel-current-upgrade .` gerou as revisões 1 e 2 do RPM Jarvis e o RPM xdotool em AlmaLinux 10 x86_64.
- SHA-256 do RPM Jarvis revisão 1: `5de274ec65176d3dfbbd88a47d08a559d818e7e88d043c1a631a0bc4986b5b4f`; revisão 2: `8c5cbb3dd4f751f08a0d3c1efe1d9275accf48ba853a277db897b3fe1c1a44d1`.
- `test-native-rpm-upgrade.sh` instalou a revisão 1, conferiu `jarvis --doctor`, fez upgrade à revisão 2, revalidou runtime/imports/GUI e integridade RPM e removeu Jarvis. Os hashes de `settings.json`, arquivo de usuário em `models/` e cache ficaram inalterados. Resultado final: `PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.
- Artefatos retidos em `dist/current-lock/rhel-upgrade/`; esse ciclo cobre o RPM atual no AlmaLinux 10 x86_64, não upgrade entre versões publicadas, áudio físico ou sessão gráfica real.

Em 2026-10-25, o container baseado em AlmaLinux 10 (EPEL + CRB) compilou o
worktree atual e produziu `jarvis-assistant-0.1.0-1.el10.x86_64.rpm` e
`xdotool-4.20260303.1-1.el10.x86_64.rpm`. SHA-256 dos RPMs binários:
`9e671f3cdbcc70e24010324b49e3fe0e241fa03da29b682b2509504e9adf4b01` (Jarvis) e
`db60b3196b27b79e9d576834f089d6aacc32c5aaf01ad55b955f20c83376266d` (xdotool).
O build completou a compilação Rust/Tauri, empacotou o runtime Python e
verificou OpenCode 1.18.23 para `x86_64-glibc`; `npm audit` reportou zero
vulnerabilidades.

O teste instalou ambos os RPMs num container AlmaLinux 10 descartável, passou
doctor, imports privados, AT-SPI, verificações de integridade, ferramentas X11,
relançamento/saída do overlay em Xvfb e Weston isolado, remoção dos pacotes e
preservação dos dados do usuário. Resultado: `PASS: package
lifecycle/imports/integrity/data preservation and isolated GUI relaunch`.
Isso não verifica áudio físico, síntese TTS, portais numa sessão gráfica real,
upgrade entre revisões ou a arquitetura AArch64.

## Build e ciclo instalado RPM openSUSE Tumbleweed x86_64 do worktree atual

- `docker build --progress=plain --build-arg JARVIS_TEST_PACKAGE_UPGRADE=1 -f packaging/rpm/suse/Dockerfile -t jarvis-suse-current-upgrade .` gerou as revisões 1 e 2 do RPM Jarvis em openSUSE Tumbleweed x86_64.
- SHA-256 da revisão 1: `758846a84ebd0e587c729facee6a4cf05623d83302f2483f0dca4e9c75ae20b4`; revisão 2: `f9c230b0118f06233b93e0c98cd7fe0b64cd68412e233b83ef612a21a6c6d80f`.
- `test-native-rpm-upgrade.sh` instalou revisão 1, preservou hashes de `settings.json`, dados em `models/` e cache, atualizou para revisão 2, validou doctor/runtime/GUI em Xvfb e integridade RPM, e removeu Jarvis. Resultado final: `PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.
- Artefatos retidos em `dist/current-lock/suse-upgrade/`; desktops reais, áudio físico e ARM64 não são validados por esse ciclo.

Em 2026-10-25, `packaging/rpm/suse/Dockerfile` compilou o worktree atual em
openSUSE Tumbleweed e gerou `jarvis-assistant-0.1.0-1.x86_64.rpm` (SHA-256
`988ec4665d66d647e691e9122b87afec29f95260a0421bafc83b4a5ebb7e1a04`). O RPM
inclui o runtime Python e o overlay Tauri; OpenCode 1.18.23 foi verificado para
`x86_64-glibc`, `npm audit` reportou zero vulnerabilidades e o RPM spec passou.

O smoke instalou o RPM em container openSUSE descartável, resolveu dependências
nativas pelo zypper, passou doctor, imports privados, AT-SPI, integridade,
ferramentas X11, relançamento/saída do overlay em Xvfb e Weston isolado,
remoção e preservação dos dados. Resultado: `PASS: package
lifecycle/imports/integrity/data preservation and isolated GUI relaunch`.
Áudio físico, TTS, portais numa sessão real, upgrade entre revisões e AArch64
continuam fora desta validação.

## Build e upgrade XBPS Void glibc x86_64 do worktree atual

Em 2026-10-25, `docker build --progress=plain -f packaging/void/Dockerfile -t jarvis-void-glibc-current-worktree .` compilou o worktree atual em Void glibc x86_64 com o commit `08c37783199592347f91cc3e3bf6f97213450ec5` de `void-packages`. O build compilou o overlay Rust, verificou OpenCode 1.18.23, preparou o runtime Python privado e gerou duas revisões do pacote XBPS.

- `_1`: `dist/current-lock/void-upgrade/jarvis-assistant-0.1.0_1.x86_64.xbps`, SHA-256 `601171cba9dcd3b39a1099d7873ee3d3ef750be610cea241965d1b6b5958e6d0`.
- `_2`: `dist/current-lock/void/jarvis-assistant-0.1.0_2.x86_64.xbps`, SHA-256 `3974750aa62860a73ca5c0b9d45864fdbebb5e8f3a0a2227c6ebbe6531dd1da2`.

`sh scripts/test-native-package.sh void-glibc <_2> <_1>` passou num container descartável. O XBPS instalou `_1`, atualizou para `_2` via repositório local, executou `jarvis --doctor`, conferiu o runtime Python/ABI e imports privados, OpenCode, arquivos e integridade, executou o overlay em Xvfb e removeu o pacote. O sentinel XDG permaneceu idêntico após upgrade e remoção. Resultado: `PASS: package lifecycle/imports/integrity/data preservation and isolated GUI relaunch`. Esse resultado headless não verifica áudio físico, portais ou desktop real. A matriz de capacidade foi atualizada em `linux-matrix.json`.

## Testes de regressão do worktree Linux atual

Em 2026-10-25, `voice/.venv/bin/pytest -q voice/tests` passou com 528 testes e 1 skip; `node --test gui/tests/*.test.mjs` passou com 5 testes; `node --experimental-strip-types --test $(rg --files .opencode -g '*.test.ts' | tr '\n' ' ')` passou com 118 testes. Isso cobre regressões Python, GUI e ferramentas/plugins OpenCode no worktree. Não substitui ciclos de pacote, testes de sessão desktop, portais ou áudio físico. A evidência foi adicionada à matriz `linux-matrix.json`.

A suíte Rust do overlay também passou no host Arch: `CARGO_NET_OFFLINE=true cargo test --locked --manifest-path gui/src-tauri/Cargo.toml` — 7 passaram, nenhum falhou. A matriz inclui esse resultado junto às demais suítes de regressão.

Também foi compilado o overlay Tauri de release no worktree atual em modo offline (`CARGO_NET_OFFLINE=true cargo build --locked --release --manifest-path gui/src-tauri/Cargo.toml`) e validado com `python3 scripts/test-overlay-instance.py gui/src-tauri/target/release/jarvis-overlay` sob Xvfb. Resultado: `PASS: second launch exits and installed primary window survives`. Isso é smoke X11 isolado; não substitui Wayland ou sessão desktop real.

`CARGO_NET_OFFLINE=true cargo clippy --locked --all-targets -- -D warnings` também passou para `gui/src-tauri`, sem warnings. A matriz registra a análise estática junto aos testes.

## Build e instalação smoke Gentoo x86_64 do worktree atual

Em 2026-10-25, `scripts/build-package.sh --target gentoo --arch x86_64`
concluiu o build nativo em Gentoo rolling, incluindo WebKitGTK 4.1, overlay
Tauri e runtime Python. O pacote gerado foi
`dist/current-lock/gentoo/jarvis-assistant-0.1.0-1.gpkg.tar`, SHA-256
`1ddea224cce1675a18ae750ae19b3f26c5b50467962c5ddbbebcb398a1f4239e`.

Em container descartável, o Portage instalou o binpkg com `--nodeps` usando as
dependências que já estavam na imagem de build. `jarvis --doctor` executou,
imports privados passaram no Python 3.14, hooks do banco de ícones/desktop
passaram durante merge e unmerge, e a remoção preservou o sentinel em
`~/.config/jarvis`. Este smoke valida o artefato e seu ciclo básico de arquivos;
não revalida a resolução de dependências, sessão gráfica, upgrade ou áudio. O
ciclo Gentoo anterior com Weston está registrado separadamente e não representa
este snapshot.


## Build e upgrade XBPS Void musl x86_64 do worktree atual

Em 2026-10-25, `docker build -f packaging/void-musl/Dockerfile -t jarvis-void-musl-current-worktree .` compilou o worktree atual em Void musl x86_64, incluindo Node.js musl, ONNX Runtime, CTranslate2, wheels Python e o overlay Tauri. O build gerou revisões `_1` e `_2` para testar atualização:

- `_1`: `dist/current-lock/void-musl-upgrade/jarvis-assistant-0.1.0_1.x86_64-musl.xbps`, SHA-256 `aace956e645da372a54f7c2fa0eae5e19ae08513f36af812e4336293a21d9da4`.
- `_2`: `dist/current-lock/void-musl/jarvis-assistant-0.1.0_2.x86_64-musl.xbps`, SHA-256 `d6d2a107daecfcebd65b28aa7e6a7d429d8adb15762d4514a5d8f627fb417c98`.

`sh scripts/test-native-package.sh void-musl <_2> <_1>` passou em container descartável: instalação `_1`, upgrade XBPS para `_2`, doctor, imports privados, integridade, relançamento do overlay em Xvfb, remoção e preservação dos dados do usuário. Resultado: `PASS: package lifecycle/imports/integrity/data preservation and isolated GUI relaunch (full desktop/audio pending)`. Esse ciclo não valida desktop/portais reais, áudio físico ou migração entre versões publicadas.


## Build Nix x86_64 do worktree atual

Em 2026-10-25, gerei `dist/current-lock/nix-source.tar.gz` pelo `scripts/source-archive.py` e compilei o flake atual em um container descartável `nixos/nix:latest` (Nix 2.35.3). O output foi `/nix/store/ygg1pkcknsg77d58k0pdzmp5bqfzxgfv-jarvis-assistant-0.1.0`. SHA-256 do snapshot: `7b3ab9a6b8d4babc4d6aecd4008e2685795ca2f58d6af218b9989fe4a5dc91db`.

A primeira compilação detectou que `npmDepsHash` em `packaging/nix/default.nix` não correspondia ao lockfile atual; o valor reportado pelo Nix foi `sha256-DqqV4xwHMWfevxHxgje2F4owhCTKVFux0AqMdrGBkmM=`. Atualizei a receita e o build seguinte passou. `scripts/test-nix-package.sh` instalou o output em perfil temporário, executou doctor e imports de faster-whisper, Piper, MCP, HTTPX e dbus-next, atualizou e removeu o perfil e preservou os dados XDG. Resultado: `PASS: Nix profile install/upgrade, runtime imports, removal and user data preservation`. Este ciclo headless não verifica GUI, portais ou áudio físico.

## Regressão focada da seleção de modelo — Arch — 2026-10-25

- `python3 -m pytest -q voice/tests/test_model_selection.py voice/tests/test_state.py voice/tests/test_serve.py voice/tests/test_loop_do.py voice/tests/test_config.py voice/tests/test_settings.py`: **101 passaram** em 7,78 s. Cobrem catálogo Ollama, persistência, propagação para Run/Serve/visão e configurações.
- `node --test gui/tests/model-settings.test.mjs`: **3 passaram**. Cobrem catálogo, seleção persistida quando indisponível e aviso/validação de modelo cloud.

## Correção de loader Guix AArch64 — 2026-10-25

A fase de instalação do pacote Guix escolhia sempre `ld-linux-x86-64.so.2`,
inclusive para `aarch64-linux`. A receita agora injeta o caminho de loader
correspondente à arquitetura alvo antes de aplicar `patchelf` ao OpenCode.
Adicionei uma regressão em `voice/tests/test_linux_packages.py`; a suíte de
empacotamento passou (**81 testes**) e `git diff --check` passou. O host não tem
os módulos do GNU Guix instalados, então a avaliação/build ARM64 e o ciclo de
perfil instalado ainda precisam de execução nativa.
- Verificação de integridade documental: ambos os JSON de targets/matriz parseiam e `git diff --check` passou. O ciclo não substitui regressão completa da aplicação nem testes em outras distros.

## Regressão de pacotes Linux — Arch — 2026-10-25

`python3 -m pytest -q voice/tests/test_linux_packages.py voice/tests/test_linux_install.py scripts/tests`: **93 passaram** em 2,50 s. A primeira execução encontrou dois testes desatualizados: o hash Nix esperado precedia a atualização verificada do `npmDepsHash`, e a allowlist de metadados não incluía entradas já registradas de testes do worktree. Atualizei as expectativas e repeti a suíte completa com sucesso. Isso valida verificações de pacote em código, não builds/instalação das distros.

## Regressão Linux completa com runtime privado — Arch — 2026-10-25

- `PYTHONPATH=voice:/usr/lib/jarvis/python PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -rs voice/tests`: **528 passaram, 1 foi ignorado** em 19,59 s. Ao usar os pacotes privados instalados, os testes do portal D-Bus e do decode faster-whisper também foram executados. O único skip é `test_atspi_desktop.py`, que requer interação numa sessão Linux autorizada.
- `node --test .opencode/act/*.test.ts .opencode/plugins/*.test.ts .opencode/safety/*.test.ts gui/tests/*.test.mjs`: **123 passaram**. Cobrem segurança, ações, seleção de modelo e layout da interface. Não substituem a validação de portais autorizados nem a cobertura noutras distros.

- AT-SPI opt-in reexecutado em 2026-10-25 no KDE Wayland: o teste não enviou texto porque a janela sentinela descartável não recebeu foco; o teste fechou as fixtures e não modificou outras janelas. O resultado é skip de precondição, não falha do caminho de digitação em background. Para novo ensaio, a janela sentinela precisa ser ativada durante a execução.

## Regressão de voz do worktree atual — 2026-10-26

- `voice/.venv/bin/python -m pytest voice/tests -q`: **529 passaram, 1 ignorado** em 27,78 s. A matriz recebeu um registro separado para esta execução. O skip requer precondição de interação desktop; esta suíte não cobre sessões autorizadas, o ciclo dos pacotes ARM64 pendentes nem áudio físico ponta a ponta.
- `node --test gui/tests/*.test.mjs`: **5/5 passaram**; `node --experimental-strip-types --test <todos os testes .opencode/**/*.test.ts>`: **118/118 passaram**. Ambos foram registrados como verificações distintas na matriz; a cobertura de código não comprova autorização em portal real.
- `scripts/verify-linux.sh` executado de ponta a ponta: voz **529 passaram/1 ignorado**, MCP win_context **16**, delegate_local **17**, GUI **5**, OpenCode **118**, Rust **7**; build release Tauri com `--locked` também passou. O script está disponível para repetir regressões locais, mas não declara cobertura de desktop/portais autorizados, áudio físico ou builds por distro.
- KDE Wayland interativo: `JARVIS_DESKTOP_TESTS=1 voice/.venv/bin/python -m pytest -q -rs voice/tests/test_atspi_desktop.py` passou. O teste enviou texto somente à janela GTK descartável em background, confirmou o sentinel com foco intacto e sem texto, verificou o ponteiro imóvel e limpou as janelas. Isto cobre foco/AT-SPI nessa sessão; portais, RemoteDesktop clique, clipboard e outras combinações seguem pendentes.
- Investigação do clique Wayland: o contrato de `NotifyPointerMotionAbsolute` usa coordenadas lógicas do stream, mas a documentação não define de forma consistente se `logical_size` ou `size` é a dimensão autoritativa. A [issue upstream #1976](https://github.com/flatpak/xdg-desktop-portal/issues/1976) discute offsets em Plasma/GNOME e recomenda EIS/libei para mapear regiões; isso é uma hipótese para o clique falho local, não prova causalidade. O clique permanece `unverified` até novo teste real com coordenadas/regiões confirmadas e consentimento do portal.


## Reconstrução e ciclo nativo Arch x86_64 — 2026-10-26

- `npm_config_audit=false scripts/build-package.sh --target arch --arch x86_64 --output /tmp/jarvis-linux-current-arch` concluiu no host Arch usando o worktree atual (HEAD `87908bd6cecab4764285edd6b8e4a1fa5f1f3bed`, com alterações locais). O overlay Rust compilou com `cargo build --release --locked`; OpenCode 1.18.23 x86_64-glibc teve o checksum verificado. Pacote `jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst`, SHA-256 `fd90c97c92767c737631b3e8adbf28e0c4930d79cdcebd4b12cfe7b8cebb21b2`.
- O pacote foi instalado num container Arch descartável pelo `scripts/test-native-package.sh arch`: `jarvis --doctor`, imports do runtime privado/AT-SPI, `pacman -Qkk` (**8.393 arquivos, 0 alterados**), relançamento isolado da GUI sob Xvfb e remoção passaram; os dados XDG de teste foram preservados. Evidência também registrada na linha Arch x86_64 da matriz.
- O container não tinha sessão de desktop nem dispositivos de áudio. Este ciclo não verifica captura/transcrição física, reprodução física, portal real, clipboard ou desktop Wayland autorizado. O build foi feito de um worktree sujo e não pode ser atribuído exclusivamente ao commit HEAD.


## Rebuild do pacote Slackware current x86_64 — 2026-10-26

- O SlackBuild rodou no container Slackware current nativo, a partir da árvore atual (HEAD 87908bd6cecab4764285edd6b8e4a1fa5f1f3bed, com alterações locais). Como /src/.git é um ponteiro de worktree do host e não resolve dentro do container, gerei o source archive com um índice Git temporário. As variáveis desse índice foram removidas antes dos clones dos helpers fixados; overlay Rust compilado com cargo build --release --locked --jobs 2.
- O artefato jarvis-assistant-0.1.0-x86_64-1_local.txz foi criado; xz -t e leitura integral do tar passaram. SHA-256 d1a7939e366059da42337edf7758f5bf662c1b86a205fc854bdbf3bf3e545430 (169.744.284 bytes). O manifesto declara Python ABI 3.12 e 7.663 arquivos; jarvis-overlay e OpenCode são ELF64 x86_64. A evidência está na matriz.
- Isto comprova build e inspeção do pacote, não o ciclo de instalação/remoção Slackware deste artefato. Áudio físico e sessão gráfica real também não foram exercitados.

## Segurança das coordenadas absolutas Wayland — 2026-10-26

O portal RemoteDesktop define `NotifyPointerMotionAbsolute` no espaço lógico do
stream. `WaylandInput` agora usa somente `logical_size` e retorna `unsupported`
quando o portal fornece apenas `size`; assim evita tratar dimensões de pixels
como coordenadas lógicas e clicar em uma posição incorreta. A issue upstream
[#1976](https://github.com/flatpak/xdg-desktop-portal/issues/1976) registra a
inconsistência entre as propriedades documentadas e offsets observados em
compositores. Isso torna a recusa mais segura, mas não comprova o mapeamento do
clique real: essa validação continua pendente.

- `python3 -m pytest -q voice/tests/test_linux_input.py`: **31 passaram**.
- A regressão reproduziu primeiro o comportamento incorreto (`size` aceito) e
  passou depois da alteração, junto com o teste de envio de coordenadas quando
  `logical_size` está disponível.

## Regressão completa de voz no worktree Linux — 2026-10-27

`python3 -m pytest -q voice/tests`: **521 passaram, 10 foram ignorados** em
26,44 s. Essa execução cobre a suíte de voz no worktree atual; os skips e as
limitações de validação em desktop/áudio físico permanecem conforme os casos
individuais e a matriz Linux.

Com o runtime Python privado do pacote instalado no host, a execução completa
foi repetida para incluir D-Bus e faster-whisper:
`PYTHONPATH=voice:/usr/lib/jarvis/python PYTHONDONTWRITEBYTECODE=1
/usr/lib/jarvis/runtime/bin/python3 -m pytest -q -rs voice/tests`: **530
passaram, 1 foi ignorado** em 29,35 s. O único skip requer uma sessão Linux
interativa autorizada (`test_atspi_desktop.py`).

Os testes de receita de pacote e instalação Linux também passaram:
`python3 -m pytest -q voice/tests/test_linux_packages.py
voice/tests/test_linux_install.py scripts/tests`: **95 passaram** em 6,77 s.
Eles validam scripts e metadados locais; não substituem os ciclos reais de
build/instalação Gentoo e Guix ARM64, que estavam em andamento nessa execução. O Gentoo ARM64 foi concluído depois; Guix ARM64 segue pendente.

## Regressão do polling AT-SPI em desktop — 2026-10-27

A primeira execução opt-in mostrou `state.json` vazio. O polling antigo usava
`continue` quando lia JSON incompleto e pulava o intervalo de 50 ms; assim podia
esgotar as tentativas antes da primeira escrita do GTK. Extraí o polling para
`_wait_for_sentinel_state`, que espera e tenta novamente; o novo teste com estado
inicial vazio e escrita atrasada passou. A suíte completa com o runtime privado
após a correção passou (**531 passaram, 1 ignorado**). A tentativa opt-in real
abriu a janela descartável, mas o compositor não ativou o sentinela; a integração
foi ignorada sem enviar texto, então a validação interativa continua pendente. Nova repetição às 08:44 no mesmo KDE Wayland: o GTK reportou `active=false` para a janela principal descartável e para o sentinela após 2 s; `xdotool getwindowfocus` não reportou uma janela XWayland focada. O teste terminou com 1 passou e 1 ignorado, sem mutação. Para validar o caminho AT-SPI em background, uma próxima execução precisa de foco explícito nas janelas descartáveis.

As regressões da interface e da seleção de modelo também passaram:
`node --test gui/tests/*.test.mjs`: **5 passaram**;
`node --experimental-strip-types --test .opencode/plugins/model-tools.test.ts`:
**2 passaram**.
O conjunto TypeScript completo do OpenCode também passou: **120 testes**. Comando:
`find .opencode -path .opencode/node_modules -prune -o -type f -name '*.test.ts' -print | sort | xargs -r node --experimental-strip-types --test`.

As duas suítes MCP passaram com o runtime privado e seu `PYTHONPATH`:
`mcp_servers/win_context/tests`: **16 passaram**;
`mcp_servers/delegate_local/tests`: **17 passaram**.

## Frontend Rust/Tauri no host Linux — 2026-10-27

Com alvo temporário no tmpfs e dois jobs, `cargo test --locked --manifest-path
gui/src-tauri/Cargo.toml`: **7 passaram**. `cargo build --locked --release
--manifest-path gui/src-tauri/Cargo.toml` também terminou; `file` identificou o
executável como ELF x86-64. O SHA-256 do artefato foi
`5a48d7bf27955e8afdb49c036b4c598359dd3b408775fe65a55685f56bcda2fd`.
Depois da validação, `cargo clean` removeu o alvo temporário (3,8 GiB). Isso
verifica o frontend Tauri no host x86-64; o ciclo Guix AArch64 segue pendente.

### Inspeção somente leitura da sessão KDE/Wayland — 2026-10-27

- A sessão interativa ativa é KDE Plasma em Wayland (com XWayland); os serviços
  `xdg-desktop-portal`, `xdg-desktop-portal-kde` e o frontend GTK estão ativos.
  A introspecção D-Bus do portal anuncia Screenshot, RemoteDesktop, ScreenCast,
  OpenURI, FileChooser e Settings.
- Esta inspeção não iniciou pedidos de portal nem concedeu autorização, não
  capturou tela/áudio e não controlou aplicativos. Portanto, confirma que as
  interfaces estão disponíveis nesta sessão, mas não valida os fluxos de
  consentimento ou o comportamento real de Screenshot/RemoteDesktop; esses
  testes continuam pendentes.

## Gentoo AArch64: build e ciclo do binpkg — 2026-10-27

- `scripts/build-package.sh --target gentoo --arch aarch64 --output /out`
  terminou com código 0 no container Gentoo ARM64 executado sob QEMU. O binpkg
  produzido tem 209.950.720 bytes e SHA-256
  `27ddec294ac0e43bb57cd9939a58a5ae5307b2ead47e2e3f5441e7b6fd3bb6fe`.
- `emerge --oneshot --usepkg --nodeps
  =app-misc/jarvis-assistant-0.1.0::jarvis-local` instalou o pacote; Portage
  verificou os checksums do binpkg. `jarvis --doctor` executou. OpenCode
  1.18.23 e o aviso MIT passaram; o runtime Python 3.14 importou Faster-Whisper,
  Piper, MCP, HTTPX e dbus-next pelos caminhos privados do pacote. O manifesto
  e os binários confirmaram ABI Python 3.14 e ELF AArch64.
- `emerge --unmerge app-misc/jarvis-assistant` removeu launcher, overlay e
  runtime. O arquivo sentinel em `XDG_DATA_HOME/jarvis/package-test` continuou
  com o conteúdo `preserved`.
- Limites observados pelo doctor no container headless: sem modelo `.onnx` do
  Piper e sem fonte Pulse disponível; síntese real, captura física, GUI e
  validação em hardware ARM nativo permanecem pendentes. O warning de ONNX
  Runtime sobre vendor de CPU desconhecido ocorreu sob QEMU; os imports
  concluíram com sucesso.
- Artefato preservado no host em
  `/tmp/jarvis-gentoo-aarch64/out/jarvis-assistant-0.1.0-1.gpkg.tar`.

- Repetição AT-SPI no KDE Wayland em 2026-10-27 às 08:44: o probe GTK descartável iniciou em `wayland-1`, mas após 2 s ambas as janelas (`Jarvis Linux input probe` e sentinela) continuavam com `active=false`; a chamada AT-SPI não foi feita. `xdotool getwindowfocus` não encontrou janela XWayland ativa. Resultado do pytest: 1 passou, 1 ignorado, sem mutação. Um probe descartável foi aberto às 08:47 para permitir foco manual e prosseguir a verificação em background.
- Diagnóstico adicional do probe AT-SPI às 08:48: o worker privado listou ambas as janelas descartáveis (títulos e PID esperados), confirmando que D-Bus/AT-SPI as enxerga; ambas continuam `active=false`. As janelas foram mantidas abertas até 08:50 UTC; sem foco manual recebido, encerrei o processo descartável sem mutação.

### Reproducing KDE Wayland AT-SPI focus precondition — 2026-10-27

- Reran `JARVIS_DESKTOP_TESTS=1 voice/.venv/bin/python -m pytest -q -rs voice/tests/test_atspi_desktop.py`: helper regression passed; the interactive case skipped before typing because neither GTK window became active.
- Launched the disposable GTK fixture directly and inspected its own state after two seconds. It reported `display=wayland-1`, `active=false`, and `sentinel_active=false`; `xdotool` could not enumerate its native Wayland windows. This narrows the failure to the fixture/compositor activation precondition, before the Jarvis AT-SPI request. No evidence here distinguishes denied Wayland activation from another session/compositor condition; no workaround or code change was made.


## KDE Wayland AT-SPI foco em background — 2026-10-27 15:15 UTC

A repetição opt-in de `voice/tests/test_atspi_desktop.py` passou com 2 testes e
nenhum skip. Nesta sessão o compositor ativou a janela GTK descartável e o
sentinela; o caso interativo pôde executar o caminho AT-SPI e confirmar a
entrada em background. Isso resolve a precondição que havia falhado às 08:44
nesta repetição, mas não valida GNOME, X11, portais, clique RemoteDesktop,
clipboard ou áudio físico.


## Overlay Tauri em Xvfb/AT-SPI — 2026-10-27 15:37 UTC

O binário release do worktree passou `python3 scripts/test-overlay-instance.py`:
a segunda instância encerrou com sucesso, a primária permaneceu acessível, os
controles de menu e saída responderam via AT-SPI e os processos auxiliares foram
limpos. É uma validação X11 isolada, sem GNOME real, autorização de portal ou
áudio físico.


## KDE Wayland AT-SPI foco em background — 2026-10-27 17:47 UTC

Reexecução de `JARVIS_DESKTOP_TESTS=1 voice/.venv/bin/python -m pytest -q -rs voice/tests/test_atspi_desktop.py`: **2 passaram, 0 ignorados**. O caminho interativo exercitou somente a fixture GTK descartável e limpou as janelas ao terminar. Não cobre clique RemoteDesktop, autorização/recusa/revogação de portal, clipboard, GNOME/X11 ou áudio físico.


## Entrada EIS para cliques Wayland — 2026-10-27

O backend Wayland agora tenta libei/EIS para cliques absolutos, usando regiões
lógicas de dispositivo; se os bindings, biblioteca nativa ou versão v2 do portal
não estiverem disponíveis, conserva o caminho RemoteDesktop legado. A dependência
Python `python-libei==0.6.1` é incluída nos runtimes preparados a partir de
`voice/requirements-linux.txt`. As receitas Nix e Guix também passaram a
declarar o binding. Nix inclui a biblioteca nativa; Guix inclui `libei` em
x86_64. O catálogo Guix atual não oferece `libei` AArch64, então nessa
arquitetura o binding importa, mas o clique continua no fallback.

Em 2026-10-27, a receita Nix atual foi avaliada no Nix 2.35.3. A primeira
tentativa x86_64 construiu `libei`, `python-libei==0.6.1` (com import check)
e o overlay Tauri, mas falhou ao executar `voice/loop.py --doctor` durante a
preparação do pacote (exit 1). A imagem descartável foi removida antes de
capturar a causa completa. O diagnóstico posterior identificou que a flake Git
omitia `voice/model_selection.py` e `voice/linux_eis.py`, ainda não rastreados.
A reconstrução com `JARVIS_SOURCE_TREE` filtrado e `--impure` incluiu esses
módulos, passou `--doctor` e imports, e concluiu instalação, upgrade, remoção
de perfil e preservação de dados XDG; detalhes e limites estão registrados na
seção “Nix dirty worktree: build, doctor e ciclo de perfil — 2026-10-27 20:29 UTC”.

A suíte completa `scripts/verify-linux.sh` passou após a mudança: voz 542/1
ignorado, MCP 16+17, GUI 5, OpenCode 120, Rust 7 e build release Tauri. Uma
tentativa real em KDE Wayland carregou libei e PyGObject, abriu uma fixture
descartável de 420×240 no XWayland e aguardou consentimento RemoteDesktop. O
portal expirou em `Start` após 75 s; o contador permaneceu zero, sem enviar clique,
e a fixture foi encerrada. Portanto, o código e a negociação estão cobertos por
regressão local, mas o envio real de clique ainda requer consentimento do portal
e permanece sem validação.


## KDE Wayland AT-SPI foco em background — 2026-10-27 19:54 UTC

Reexecução de `JARVIS_DESKTOP_TESTS=1 voice/.venv/bin/python -m pytest -q -rs voice/tests/test_atspi_desktop.py`: **2 passaram, 0 ignorados**. A fixture GTK descartável recebeu entrada AT-SPI em background; o sentinela manteve foco e o ponteiro não mudou. As fixtures foram encerradas. Não cobre GNOME, X11, clique RemoteDesktop, autorização/recusa/revogação de portal, clipboard ou áudio físico.


## Cleanup da sessão EIS em revogação — 2026-10-27 20:00 UTC

Foi reproduzida uma falha: ao receber `Session.Closed` da sessão RemoteDesktop
observada, o backend limpava teclado/streams, mas mantinha a sessão EIS de
ponteiro e o `Sender`. `WaylandInput.revoked()` agora fecha também o backend
EIS. A regressão específica passou; os testes focados de entrada/EIS passaram
41/41. A primeira execução da suíte de voz também mostrou que o registro AT-SPI
das 19:54 UTC precisava ser incluído na whitelist de capacidades meta. Após
atualizar a whitelist, a suíte inteira passou: 544 passaram, 1 ignorado. Isso
não valida revogação ao vivo da própria sessão EIS nem substitui consentimento
real do portal.


## Guarda de pausa EIS e regressão completa — 2026-10-27 20:05 UTC

A sessão EIS agora consulta eventos pendentes do Sender antes de injetar
cliques. Se receber `DEVICE_PAUSED`, recusa a entrada; remoção de dispositivo,
remoção de seat ou desconexão encerram a sessão. A suíte focada de entrada/EIS
passou 42 testes. A regressão completa `PYTHONPATH=voice
voice/.venv/bin/python -m pytest -q -rs voice/tests` passou com **545 aprovados,
1 ignorado**; o ignorado exige desktop interativo autorizado. A matriz foi
atualizada para 184 registros (179 aprovados, 4 parciais e 1 sem validação).
Os builds Nix x86_64 e Guix AArch64 continuam em andamento; consentimento e
revogação reais do portal EIS ainda não foram validados.


## Ordem de eventos EIS durante aquisição — 2026-10-27 20:08 UTC

A revisão do lifecycle encontrou outra corrida: `DEVICE_PAUSED` no mesmo lote
inicial após `DEVICE_RESUMED` não era consumido pela aquisição do dispositivo.
Foi adicionado um teste que falhava porque o código enviava o clique; agora a
entrada é recusada. `voice/tests/test_linux_eis.py` focado passou no caso novo,
e `voice/tests` passou com **546 aprovados, 1 ignorado**. A matriz registra 185
verificações, 180 aprovadas, 4 parciais e 1 sem validação (97,3% aprovadas).

## Precisão dos builds Nix/Guix em andamento — 2026-10-27 20:11 UTC

O build persistente Nix x86_64 avançou do download da closure Rust/WebKit para a
compilação do overlay. Guix AArch64 continua compilando Rust stage1. Ambos os
snapshots foram iniciados antes da correção EIS de ordenação inicial (adicionada
às 20:07 UTC); mesmo se terminarem com sucesso, será necessário reconstruir com
o source atualizado para comprovar o pacote atual. A matriz foi ajustada para
manter esse limite explícito.

Às 20:12 UTC, o build Nix havia baixado mais de 2,3 GB e compilava o overlay
(GTK e `javascriptcore-rs-sys` entre as dependências). Guix avançava pelo
bootstrap stage1 até `rustc_baked_icu_data` e `fluent-bundle`. Nenhum dos dois
havia terminado; logs e limites de snapshot estão registrados na matriz.

Às 20:14 UTC, Nix avançava na compilação de `tauri`, bindings WebKitGTK e D-Bus
no overlay (CPU perto de 400%; transferência acima de 2,35 GB). Guix compilava
macros do type IR do compilador Rust (CPU perto de 100%). Ambos continuavam
ativos; nenhum resultado final foi registrado.


## Build Nix com source completo do worktree — 2026-10-27 20:20 UTC

O build Nix anterior falhou durante `--doctor`: `voice/model_selection.py` não
estava no source da flake porque o arquivo ainda não era rastreado pelo Git.
A mesma falha também omitiria o módulo opcional `voice/linux_eis.py`. O flake
agora aceita `JARVIS_SOURCE_TREE` com `--impure` e filtra a cópia para diretórios
e arquivos do projeto, excluindo `.git`, ambientes Python, `node_modules`,
`target`, `dist`, arquivos de configuração local e logs. A avaliação Nix 2.35.3
passou; os 84 testes de empacotamento passaram. Um build novo está em execução
no container persistente `jarvis-nix-current`; log no container em
`/host-tmp/jarvis-nix-dirty-current.log`. `--doctor`, instalação e ciclo de
perfil ainda aguardam o resultado desse build.

Às 20:21 UTC, a reconstrução Nix com o source filtrado compilava bindings
`webkit2gtk`/PNG e dependências de polling; Guix havia avançado até
`rustc_errors`, `rustc_feature` e `rustc_session` no bootstrap AArch64.

A inspeção direta confirmou que `/nix/store/rrlb28fwbw6n1pnf4nyg6pvxjcl01hai-jarvis-worktree-source`
contém `voice/model_selection.py` e `voice/linux_eis.py`; `.git`, `.venv`,
`node_modules`, `target` e `dist` estão fora do source Nix. A compilação do
overlay continua ativa, então o teste decisivo ainda é a nova execução do
`--doctor` dentro do build.


## Nix dirty worktree: build, doctor e ciclo de perfil — 2026-10-27 20:29 UTC

Com `JARVIS_SOURCE_TREE` e `--impure`, o build atual incluiu os módulos Python
que faltavam e terminou com sucesso. O output
`/nix/store/2v0apgisnqy3mfrfs9bq4mszspdhxa34-jarvis-assistant-0.1.0` passou
`--doctor`, imports `faster_whisper`, Piper, MCP, HTTPX, dbus-next e libei,
OpenCode 1.18.23, instalação/upgrade/remoção em perfil isolado e preservação
do sentinel XDG. O primeiro smoke usou um output anterior, e detectou que a
flake instalava um store path mais novo; repetir com o output exato passou. A
suíte completa de voz/empacotamento passou com **547 aprovados, 1 ignorado**.
O doctor não encontrou fontes Pulse no container; GUI, portais e áudio físico
continuam fora desta validação.

Após incluir o novo resultado Nix na whitelist da matriz, `voice/tests/test_linux_packages.py`
foi reexecutado: **84 passaram**. Guix AArch64 segue no bootstrap de `rustc_middle`;
a instalação/runtimes Guix ainda aguardam seu artefato final.

Às 20:31 UTC, o Guix AArch64 seguia compilando `rustc_middle` sob QEMU; o
processo rustc ativo tinha 3m27s de elapsed, a árvore Rust ocupava 3,1 GiB e o
cgroup reportava zero eventos OOM. O build ainda não terminou e usa snapshot
anterior à última correção EIS.

O teste de source archive foi ampliado para exigir também os novos módulos
`voice/model_selection.py` e `voice/linux_eis.py`, que estavam fora do índice
Git. A geração do arquivo incluiu ambos e a suíte de empacotamento passou com
**84 testes**. Isso protege os builds distribuídos pelo archive contra a mesma
classe de omissão identificada no caminho Nix.


O smoke Guix foi ampliado para importar `python-libei` e exercitar `EISPointer`
quando `libei` ou a API do portal não estiver disponível, confirmando retorno
`unsupported` sem tentar clicar. A suíte `test_linux_packages.py` passou com
**85 testes** e `sh -n scripts/test-guix-package.sh` passou. Isto verifica o
harness; a validação no runtime Guix AArch64 aguarda o build em andamento.


A regressão completa após essa alteração passou com **548 aprovados e 1 ignorado**
(2026-10-27 20:36 UTC). O ignore continua sendo o teste AT-SPI interativo, que
exige uma sessão Linux autorizada.

Às 20:37 UTC, o processo AArch64 de `rustc_middle` seguia ativo havia 9m32s
com 99,6% de CPU; o cgroup continuava sem OOM. O build Guix segue sem exit
marker.

## Reteste interativo AT-SPI — KDE Wayland — 2026-10-27 20:40 UTC

`JARVIS_DESKTOP_TESTS=1 voice/.venv/bin/python -m pytest -q -rs voice/tests/test_atspi_desktop.py`: **2 passaram, 0 ignorados**. A entrada AT-SPI foi enviada somente à fixture GTK descartável em segundo plano; o sentinel manteve o foco e o ponteiro permaneceu imóvel. O reteste confirma esse caminho nesta sessão, mas não valida consentimento RemoteDesktop, clique EIS, clipboard, GNOME/X11 ou áudio físico.

## PTT/VAD Linux com fonte Pulse virtual — 2026-10-27 20:51 UTC

O comando repetível `PYTHONPATH=voice:/usr/lib/jarvis/python voice/.venv/bin/python
scripts/linux_virtual_audio_smoke.py` gerou fala com Piper, capturou-a por um
`module-null-sink` temporário via FFmpeg Pulse em `record_ptt` e `record_auto`,
e transcreveu ambos com faster-whisper (2,55 s e 3,55 s). O módulo foi removido
no `finally`, confirmei que não restaram sink, source ou módulo de teste, e a
suíte de unidade do harness passou (**3 testes**). O microfone físico não foi
aberto. Isso valida captura/PTT/VAD/STT sintéticos, mas não acústica de
microfone, reprodução em alto-falante ou consentimento do portal.

## Regressão Linux completa — 2026-10-27 20:55 UTC

`scripts/verify-linux.sh` passou: voz **548 passaram, 1 ignorado**; MCP
`win_context` **16**, `delegate_local` **17**, GUI **5**, OpenCode **120**,
Tauri **7** e build Tauri release. `scripts/tests` passou com **12 testes**.
Isto cobre a regressão local atual; portais autorizados, áudio físico e builds
nativos por distribuição continuam com gates separados.

## Probe silencioso de roteamento FFplay — 2026-10-27 21:02 UTC

O `ffplay` deste host usa SDL. Um probe com `SDL_AUDIODRIVER=pulseaudio`,
`PULSE_SINK` apontado para `module-null-sink` e volume `0` mostrou o fluxo SDL
alocado ao sink padrão do desktop (índice 944), não ao sink virtual. O probe foi
interrompido em volume zero; não foi feita validação acústica. Uma tentativa
anterior chamou `speak_piper` sem volume zero e o monitor virtual registrou
apenas −91 dB; como o stream pode ter seguido ao sink padrão, esse resultado é
inconclusivo para playback e não conta como teste aprovado. A frase era apenas
sintética; nenhum áudio do microfone foi capturado. Para evitar reproduzir som
no dispositivo físico sem confirmação, não repeti a reprodução audível.

## TTS Piper por Pulse em sink virtual — 2026-10-27 21:30 UTC

`scripts/linux_virtual_audio_smoke.py` agora verifica também a reprodução que
`voice/tts.py` usa no Linux: Piper gera a fala, FFmpeg envia o WAV ao sink
selecionado por `PULSE_SINK`, e o monitor do `module-null-sink` captura a saída.
O faster-whisper reconheceu a frase sintética no monitor (captura de 8,01 s).
O mesmo harness manteve PTT (2,55 s) e VAD (3,55 s) com reconhecimento correto;
o módulo Pulse temporário e os WAVs foram removidos. Testes de TTS e do harness:
18 passaram. O microfone e os alto-falantes físicos não foram usados.

A primeira sondagem FFmpeg sem `-re` terminou antes de o monitor receber blocos
Pulse e pareceu silenciosa; a repetição em tempo real passou. A implementação
Linux agora usa `ffmpeg -re -f pulse -device "$PULSE_SINK"` (ou `default`) e
mantém `ffplay` como fallback quando o sink padrão não aceita a saída Pulse.
Com `PULSE_SINK` explícito, uma falha é retornada ao chamador em vez de desviar o
áudio a outro dispositivo. A antiga sondagem SDL/ffplay descreve o backend de
fallback e não substitui a validação atual do caminho Pulse.

## Regressão após saída TTS Pulse — 2026-10-27 21:31 UTC

`scripts/verify-linux.sh` passou após a correção do TTS Linux: voz **551
passaram, 1 ignorado**; MCP `win_context` **16**, `delegate_local` **17**, GUI
**5**, OpenCode **120**, Tauri **7** e build release passaram. A suíte focada
`voice/tests/test_tts.py voice/tests/test_audio.py
scripts/tests/test_linux_virtual_audio_smoke.py` passou com **30 testes**. Não
cobre portal autorizado nem áudio físico.

### Nix current worktree com TTS Pulse — 2026-10-27 21:40 UTC

O build x86_64 do worktree filtrado terminou com sucesso em `/nix/store/n4bw9csr6mac1p1nm6l0kzfnczsky0r4-jarvis-assistant-0.1.0`, incluindo o caminho Linux Piper→FFmpeg→Pulse com seleção por `PULSE_SINK`. O ciclo de perfil passou: instalação, `jarvis --doctor`, imports do runtime, atualização, remoção e preservação dos dados XDG. O smoke usou a cópia exata da árvore filtrada que originou a derivação; no container headless, doctor indicou corretamente ausência de sessão gráfica, modelo e fonte Pulse.

## Conversão de coordenadas EIS por região — 2026-10-27 21:42 UTC

A regressão do clique EIS foi reproduzida: a coordenada global `(1120, 580)` caía numa região deslocada em `(1000, 500)`, mas `pointer_motion_absolute` recebia `(1120, 580)` em vez do ponto local `(120, 80)`. `EISPointer` agora consulta a região e aplica `Region.convert_point()` antes de enviar o movimento; coordenadas sem região ou fora dela continuam recusadas. Isso segue o contrato da libei: [regiões EIS](https://libinput.pages.freedesktop.org/libei/api/structei__region.html) podem usar um layout próprio e a documentação do binding descreve `convert_point()` para transformar coordenadas globais em locais.

O teste focado falhou antes da alteração ao observar a coordenada global sendo enviada. Depois da alteração, `voice/.venv/bin/python -m pytest -q voice/tests/test_linux_eis.py voice/tests/test_linux_input.py` passou (**43 testes**). O clique real em KDE ainda requer consentimento do portal e segue sem validação ao vivo.

## Regressão Linux completa após correção de região EIS — 2026-10-27 21:48 UTC

`scripts/verify-linux.sh` passou: voz **551 passaram, 1 ignorado**; MCP `win_context` **16**, `delegate_local` **17**, GUI **5**, OpenCode **120**, testes Tauri **7** e build release passaram. `git diff --check` também passou. Isto valida regressão de código, mas não substitui o clique Wayland ao vivo, consentimento de portal, áudio físico nem o ciclo Guix AArch64.

## Guix AArch64 recipe atualizado após conversão EIS — 2026-10-27 21:50 UTC

Gerei um novo arquivo de fonte determinístico para Guix, SHA-256 `77a8cbc6423715d4670ef7f2bc21adfd4960194b00932b54f13e049210b7ce2c`, confirmei que `voice/linux_eis.py` dentro dele contém `Region.convert_point()` e rodei `guix build --dry-run --system=aarch64-linux -f ./jarvis.scm`: avaliação passou e produziu `/gnu/store/0zpkykgkfzjg8mm6y87gcy1zq9szbkw6-jarvis-assistant-0.1.0.drv`. O build Guix ativo ainda compila snapshot anterior, portanto precisa terminar antes do build completo desta derivação atualizada.

## Nix x86_64 rebuild com mapeamento EIS — 2026-10-27 22:01 UTC

O build atual do worktree passou para `/nix/store/3r9i9lfjsyk1yiqf7lykimbj2fwa8142-jarvis-assistant-0.1.0`, contendo a conversão EIS `Region.convert_point()`. Preservei o snapshot filtrado exato de 911 MiB e confirmei que ele resolve para a mesma derivação `/nix/store/kkpz7mshv5l1af5rirhbh6zv7dix8q6l-jarvis-assistant-0.1.0.drv`. `scripts/test-nix-package.sh` passou: instalação, doctor, imports do runtime, upgrade, remoção e preservação dos dados XDG. Doctor detectou corretamente a ausência de sessão gráfica, modelo Piper e fonte Pulse no container headless.

O runtime já instalado no pacote Nix passou também um probe sintético local: `EISPointer._click_device` recebeu coordenada global `(1120, 580)` e enviou movimento para `(120, 80)` após aplicar o offset da região. O probe não abriu o portal nem moveu o ponteiro real.

## Arch x86_64 pacote atual após correção EIS — 2026-10-27 22:15 UTC

Reconstruí `jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst` do worktree atual (233.343.841 bytes; SHA-256 `22486664a128cea3e1168f4f475c57f2ead631cf23a74620c7a72cbb06d2fdc2`), incluindo o mapeamento local `Region.convert_point()` do EIS. O ciclo no Arch Linux rolling instalou o pacote depois de atualizar o container, executou `jarvis --doctor`, validou imports privados, recursos e typelib AT-SPI, e confirmou `pacman -Qkk`: 8.417 arquivos, zero alterados. O smoke GUI isolado passou com consulta de ponteiro via xdotool, roundtrip da área de transferência via xclip e relançamento sem encerrar a janela principal. A remoção passou e preservou o sentinel de dados XDG. Por estar headless, o doctor identificou corretamente ausência de fonte Pulse, modelo Piper e autorização desktop ao vivo; isso não cobre áudio físico nem portal real.

## Proteção de origem da API local — 2026-10-27

A revisão de código encontrou `Access-Control-Allow-Origin: *` e endpoints POST
que permitiam a uma página externa alterar modelo, configurações e comandos do
servidor loopback. Testes escritos antes da correção falharam em 6 expectativas.
Agora o CORS permite somente origens do WebView Tauri: Linux usa
`tauri://localhost`; Windows e Android usam `http://tauri.localhost` e
`https://tauri.localhost`. A implementação segue a [documentação oficial do
Tauri](https://docs.rs/tauri/latest/tauri/struct.Builder.html). Origins externos
são recusados; POST também exige uma origem permitida, enquanto GET sem Origin
continua aceito para clientes não-browser. A suíte focada passou (**38 testes**).

`scripts/verify-linux.sh` passou: voz **560 passou, 1 ignorado**; MCP
`win_context` **16**, `delegate_local` **17**, GUI **5**, OpenCode **120**, testes
Tauri **7** e build release passaram. Isso valida regressões automatizadas; o
servidor ainda precisa ser exercitado na WebView Tauri Linux real.


## Pacote Debian x86_64 com proteção de origem — 2026-10-27 23:03 UTC

Reconstruí o `.deb` em Debian Trixie a partir do worktree atual. O Rust release,
`npm ci` com npm 10.9.9 e auditoria sem vulnerabilidades, download/checksum do
OpenCode 1.18.23, runtime Python privado e `dpkg-buildpackage` passaram. O pacote
`jarvis-assistant_0.1.0-1_amd64.deb` tem 179.084.492 bytes e SHA-256
`715f524c97531aab0c18637bfa3bae64423c8143478d35d2f1784648798710c3`. O payload
foi inspecionado e inclui `tauri://localhost` na proteção da API de estado.

O ciclo em Debian Trixie descartável passou: instalação, doctor, imports privados,
typelib AT-SPI, ferramentas nativas, clipboard sob Xvfb, relançamento e saída do
overlay, integridade do pacote, remoção e preservação dos dados XDG. Isso não
verifica WebView/portais ao vivo, áudio físico, upgrade a partir de uma versão
publicada ou arquitetura AArch64.


## Pacote Arch x86_64 com proteção de origem — 2026-10-27 23:08 UTC

Reconstruí o pacote nativamente no Arch x86_64. `makepkg` passou; npm audit
reportou zero vulnerabilidades e o OpenCode 1.18.23 teve checksum validado. O
artefato `jarvis-assistant-0.1.0-1-x86_64.pkg.tar.zst` tem 233.343.533 bytes e
SHA-256 `ca6703485c0165d58fff37953bbe8862bd551bedd8e7c54d8fdf3868c65a17a6`.

No Arch rolling descartável, o ciclo passou após atualização completa do sistema:
doctor, imports privados, typelib AT-SPI, consulta de ponteiro e clipboard em Xvfb,
relançamento isolado, integridade pacman (8.417 arquivos, zero alterados), remoção
e preservação do sentinel XDG. O pacote contém a correção de origem da API local.
Portais autorizados ao vivo e áudio físico continuam pendentes.


## Pacote Nix x86_64 com proteção de origem — 2026-10-27 23:23 UTC

Reconstruí a derivação com `JARVIS_SOURCE_TREE` filtrado e `--impure`, incluindo
os arquivos locais não rastreados. O output
`/nix/store/3mcccis387q3j4yr5fgppcslvwnmjsz6-jarvis-assistant-0.1.0` passou no
preparo e `--doctor`; imports privados passaram. `scripts/test-nix-package.sh`
passou com instalação, upgrade e remoção do perfil, imports de faster-whisper,
Piper, MCP, HTTPX, dbus-next e libei, e preservação dos dados XDG. O payload contém
a origem Linux `tauri://localhost` na política da API de estado. O ciclo é
headless; WebView/portais ao vivo e áudio físico continuam pendentes.


## Pacote Ubuntu 24.04 x86_64 com proteção de origem — 2026-10-27 23:41 UTC

O build em Ubuntu 24.04 passou com Rust 1.95, npm 10.9.9 e auditoria sem
vulnerabilidades, OpenCode 1.18.23 com checksum verificado, runtime Python privado
e `dpkg-buildpackage`. O pacote tem SHA-256
`2b0e8f45b81f4709120ad8bf4d1418a9da338e58cb5f3bcd2bb0baee739cb853` e 189.612.816
bytes; inclui a política da API de estado para `tauri://localhost`.

No Ubuntu 24.04 descartável, instalação e remoção passaram; doctor, imports,
AT-SPI, ferramentas nativas, clipboard Xvfb, relançamento do overlay, integridade
`dpkg` e preservação dos dados XDG passaram. Este teste não fez upgrade de uma
versão publicada usando o payload com a correção. Portais reais, áudio físico e
AArch64 continuam fora desta validação.


## APK Alpine 3.24 x86_64 com proteção de origem — 2026-10-28 00:06 UTC

O build Alpine 3.24/musl reconstruiu CTranslate2 4.8.3, Piper 1.8.0 e o overlay
Tauri com fontes fixadas, preparou o runtime privado e gerou um APK assinado.
`jarvis-assistant-0.1.0-r0.apk`: SHA-256
`2eefadf6bce71c63a88267902d1e076a99734e770703813a48c645caf7773167`, 177.509.457
bytes. A chave pública usada no builder tem SHA-256
`ce3a9f9254950a79ad74491b30a414a564849119cbae1c3432bedaa47aabe2f9`.

O ciclo descartável exigiu assinatura (`JARVIS_APK_REQUIRE_SIGNATURE=1`) e passou:
instalação, doctor, imports, AT-SPI, ferramentas nativas, relançamento/saída em
Xvfb, integridade, remoção e preservação dos dados XDG. Esta validação headless
não cobre portais reais nem áudio físico.

## 2026-10-28 Fedora 44 current-worktree RPM refresh

- Rebuilt Fedora 44 x86_64 RPM revisions 1 and 2 from the current worktree. The state API Origin allowlist fix is included. Both release builds, pinned npm 10.9.9 audit (0 vulnerabilities), OpenCode checksum verification, and Python runtime packaging/import checks passed.
- RPM revision 1: 214724586 bytes, SHA-256 `3b67e9307ee93dfd860512480936aef091a24d4cc89c856507df6bc46d88ed58`. Revision 2: 214724588 bytes, SHA-256 `210e4898fb67b4de45d67fa96ab207b9ca6b885ae245fbd2f2422b259894b696`.
- Fedora 44 disposable-container lifecycle passed: install revision 1, runtime/import/integrity and Xvfb GUI relaunch checks, upgrade to revision 2, preserved config/model/cache fixture hashes, repeated checks, and removal. Output: `PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.

## 2026-10-28 RHEL 10 current-worktree RPM refresh

- Rebuilt AlmaLinux 10 x86_64 RPM revisions 1 and 2 from the current worktree with the state API Origin fix. Rust/Tauri release compile, pinned npm audit (0 vulnerabilities), OpenCode 1.18.23 checksum/target check and private Python runtime packaging/import checks passed. The xdotool helper RPM was rebuilt too.
- Jarvis RPM revisions 1 and 2 are each 190996151 bytes. SHA-256 revision 1: `52b05e2fe7c238d0ca3c374b0f33b69efd2969b9955a8f6d450c1732d74dcfd7`; revision 2: `4c9c9168a4a1d308330ed60604101face498195df20d67cf56b7691e099450da`. The xdotool RPM is 75632 bytes, SHA-256 `a99a15298dd18c042cbb47c32c50b339f5441eb154d5799f4d595371b2269498`.
- AlmaLinux 10 disposable-container lifecycle passed: install revision 1 and dependencies, doctor/runtime/import/integrity checks, isolated Xvfb GUI relaunch, upgrade to revision 2, unchanged configuration/model/cache fixture hashes, repeat checks and removal. Output ended with `PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.
- The RHEL rpmbuild log reports missing build-id warnings for vendored Python wheels/shared objects and an absolute symlink from the bundled runtime to `/usr/bin/python3.12`; runtime checks passed with this layout.

## 2026-10-28 openSUSE Tumbleweed current-worktree RPM refresh

- Rebuilt RPM revisions 1 and 2 from the current worktree with the state API Origin allowlist fix. The Tumbleweed Rust/Tauri release build, npm audit (0 vulnerabilities), OpenCode 1.18.23 x86_64-glibc verification, and private Python 3.13 runtime staging/import checks passed.
- Revision 1: 190446122 bytes, SHA-256 `28850d66021562e56864d1ddf7f98c52443819b93970e642859a10fc3ca9aebf`. Revision 2: 190445576 bytes, SHA-256 `39c3bd8c6724ded842a271e3f814b5c7c06380ed24f4ef179227eba7dde9024d`.
- Disposable Tumbleweed lifecycle passed: install revision 1 and dependencies, doctor/runtime/import/integrity checks, isolated Xvfb GUI relaunch, upgrade to revision 2, unchanged configuration/model/cache fixture hashes, repeated checks and removal. Final output: `PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes`.
- Container verification required downloading the current Tumbleweed repository metadata and resolving 147 packages. This is a package/runtime container check and does not substitute for physical desktop/audio validation.

## 2026-10-28 Slackware current x86_64 package refresh

- Rebuilt revision 2 after updating the disposable Slackware current environment to the 2026-10-28 package snapshot. The current-worktree Origin fix is included. SlackBuild completed; archive integrity passed. SHA-256: `a5c87feadda9ba4169bcaa908acd5811fc7e183b41833b84dda225f7022f6eff`; size: 169,663,488 bytes.
- Overlay `ldd` had no unresolved libraries. The native package lifecycle harness passed private Python imports and AT-SPI, doctor, Xvfb pointer/clipboard, isolated overlay relaunch, install/removal and preservation of XDG data. `upgradepkg` from the historical revision 1 package also passed doctor and preserved the user data sentinel.
- The refreshed artifact is preserved at `dist/current-refresh/slackware/originfix/jarvis-assistant-0.1.0-x86_64-2_local.txz`. Native Wayland, physical audio and aarch64 remain pending.

## 2026-10-28 Flatpak x86_64 current-worktree refresh

- Rebuilt the Flatpak from the current source archive using the pinned GNOME SDK/Platform 49 and Rust extension. Cargo vendoring, npm CI/audit, Python wheelhouse preparation, OpenCode 1.18.23 verification, overlay compile, private runtime staging/imports, OSTree export and bundle creation passed.
- Bundle: `dist/current-refresh/flatpak/x86_64/jarvis-x86_64.flatpak`; 180,765,096 bytes; SHA-256 `a15f895559aae4dabb5e0e62620841db0ce07827d4c08daff386cb4aac000504`. Source archive SHA-256: `a8f781a9ddc2ae13e9d591fcbe629a7306f23932fbf2c51e1873622570ce4c7c`.
- Installed the new bundle into a separate temporary Flatpak user profile backed by hardlinks to existing runtime files. `jarvis --doctor`, imports for `gi`, `dbus_next`, `faster_whisper`, and `av`, and uninstall passed. The existing user profile app deployment was preserved. This does not validate portal interaction or physical audio.

## 2026-10-28 Void glibc x86_64 current-worktree refresh

- Built the XBPS package from the current worktree in the pinned Void current builder. Artifact: `dist/current-refresh/void-glibc/originfix/jarvis-assistant-0.1.0_2.x86_64.xbps`; 212,235,099 bytes; SHA-256 `0fdd413ec89463c1b9c57a566e73ca924022172e55afcf966255eea8ff7c72e3`.
- The disposable Void package lifecycle passed: local XBPS indexing/install, `jarvis --doctor`, private Python runtime imports, package integrity, Xvfb pointer/clipboard checks, overlay single-instance relaunch, `xbps-remove`, and XDG data sentinel preservation. The first test attempt used a noncanonical package filename and failed checksum lookup; rerunning with the generated canonical XBPS filename passed.

## 2026-10-28 Solus x86_64 current-worktree Origin-fix refresh

- Built release 4 from the current worktree using the pinned Solus unstable-x86_64 solbuild profile. Artifact: `dist/current-refresh/solus/jarvis-assistant-0.1.0-4-1-x86_64.eopkg`; 205,558,388 bytes; SHA-256 `3d72c24bec08705aecd6b50a04c0168e28a15f36a6b919f87eba6be648fd5a6f`. Source archive SHA-256: `ee2abc261403109ec34e22fe7b34a6f16c2a17d91c72c9fe89021bfa993ff73c`.
- In a disposable current Solus chroot, installed the package and its runtime dependencies; `jarvis --doctor`, imports for `faster_whisper`, `piper`, `mcp`, and `dbus_next`, and `eopkg check jarvis-assistant` passed. The Xvfb overlay single-instance/relaunch smoke passed. Removed the package and confirmed the XDG data sentinel remained.
- The first chroot inspection found its declared `python3` package database entry without corresponding Python standard-library files. Reinstalling that distro package restored the chroot runtime; no Jarvis package change was needed. Solbuild emitted a non-fatal ABI scan diagnostic after successfully creating the eopkg.
- This completes the current-worktree x86_64 package refresh for Solus. Live desktop sessions, physical audio, and upgrade testing for this release remain separate gates; AArch64 is outside the active scope.

## Escopo de arquitetura atualizado — 2026-10-28

- A pedido do usuário, a compatibilidade ativa do porte Linux fica restrita a x86_64. AArch64 deixa de ser requisito e de ser executado pelos workflows Linux nativos, Flatpak, Nix e Void. Linhas de validação AArch64 anteriores permanecem somente como histórico.
- `packaging/targets.json` e as receitas de pacote declaram apenas `x86_64`; os scripts de pacote recusam outras arquiteturas. Os workflows ARM64 foram removidos. Gentoo e GNU Guix continuam excluídos do escopo de entrega.
- Permanecem as validações x86_64 de desktop real, portais, áudio físico e revisão completa.


## 2026-10-28 x86_64 synthetic audio smoke and harness fix

The first run of `scripts/linux_virtual_audio_smoke.py` stopped at STT with
`No module named faster_whisper`. The package's private Python modules are laid
out directly under `/usr/lib/jarvis/python`; the harness had only changed the
`PYTHONPATH` environment variable after its Python process started, which does
not update that process's `sys.path`. It now adds the private runtime directory
to both the current process and child processes. A regression test was first
observed failing, then the focused harness tests passed (4 passed).

The rerun passed: Piper output was captured from an isolated Pulse monitor and
recognized by faster-whisper; synthetic PTT and VAD also transcribed the expected
phrase. Durations were 8.01 s, 2.55 s, and 3.55 s. The temporary Pulse module
was unloaded and generated WAVs removed. The physical microphone was not opened;
the default speaker sink is muted, so physical speaker output remains pending.


## 2026-10-28 tentativa de áudio físico x86_64

Com autorização do usuário, reproduzi uma frase curta do Piper no sink padrão
de fones a 15% e gravei 8 segundos da fonte física Mic2 padrão. O caminho Pulse
aceitou a reprodução e o FFmpeg gravou; faster-whisper retornou texto que não
correspondeu à frase esperada, então a validação ponta a ponta não passou. Não
conservo a gravação. O volume original foi restaurado a 61%, sem mute, e a fonte
permaneceu sem mute. A validação sintética anterior continua passando.

## 2026-10-28 revisão do fluxo de seleção de modelo

A revisão independente encontrou que o plugin local do OpenCode enviava
`POST /model` sem `Origin`, embora a API exija uma origem Tauri confiável em
requisições mutáveis. O plugin agora envia `Origin: tauri://localhost` e o teste
confirma esse cabeçalho. O teste do plugin passou (**2 testes**) e
`PYTHONPATH=voice python3 -m pytest -q voice/tests/test_state.py` passou
(**38 testes**), incluindo a rejeição de requisições sem origem confiável.
`git diff --check` também passou.

## 2026-10-28 validação Nix do worktree atual

O pacote Nix foi compilado do worktree atual com `JARVIS_SOURCE_TREE` e
`--impure`, incluindo o módulo não rastreado `voice/model_selection.py`. O
ciclo real do perfil atualizou a versão anterior, confirmou imports Python
(incluindo `libei`), removeu o perfil descartável e preservou os dados do
usuário. A saída foi
`/nix/store/fgk3xasqbx86j2lh6bf54i1dfwb5i64c-jarvis-assistant-0.1.0`.
O registro detalhado e o hash estão em
[linux-nix-current-worktree-2026-10-28.txt](linux-nix-current-worktree-2026-10-28.txt).
É uma validação headless de pacote; desktop e áudio continuam como gates
separados. O build usou o worktree sujo com HEAD base
`87908bd6cecab4764285edd6b8e4a1fa5f1f3bed`.

## 2026-10-28 Void musl x86_64 do worktree atual

O build do pacote terminou em 14/14 etapas com a imagem
`sha256:592b9b09299a38eef37af362f513687a1910214b5a7726cb4227a7df561ea6c1`.
No container Void musl, o ciclo instalou `0.1.0_1`, atualizou para `0.1.0_2`,
validou doctor/imports/integridade e overlay isolado no Xvfb (ponteiro xdotool,
roundtrip de clipboard xclip e segunda instância), e removeu o pacote mantendo
os dados de usuário. Os hashes dos dois pacotes e o log completo estão na
[matriz](linux-matrix.json) e em
[linux-void-musl-current-worktree-2026-10-28.txt](linux-void-musl-current-worktree-2026-10-28.txt).
O build partiu do worktree sujo com HEAD base
`87908bd6cecab4764285edd6b8e4a1fa5f1f3bed`; teste de desktop real/portal e áudio
físico continuam gates separados.

## 2026-10-28 revisão de portal e CI Flatpak

A hipótese de vazamento de handler D-Bus não se confirmou: a definição local
`def handle(message)` vincula a função à variável removida no `finally`.
`dbus-next` mantém handlers do usuário em lista e `remove_message_handler`
remove essa mesma função. Com o runtime `dbus-next` empacotado no Void musl atual,
`pytest -q voice/tests/test_portal.py` passou (**12 testes**), incluindo duas
requisições na conexão persistente.

A revisão também encontrou que o workflow Flatpak não disparava em pull requests.
Agora o evento `pull_request` cobre os mesmos arquivos e branches do evento `push`,
incluindo `packaging/targets.json` e `packaging/opencode-sources.json`. A
validação completa do upgrade Solus 3→4 segue pendente: a imagem Solus comum não
forneceu o serviço de inhibitor lock exigido pelo eopkg; o teste precisa rodar no
ambiente/chroot solbuild usado para validações nativas.

## 2026-10-28 upgrade Flatpak do worktree atual

Em `FLATPAK_USER_DIR` e `HOME` temporários, instalei o bundle anterior e
atualizei para o bundle atual do worktree. `jarvis --doctor` passou nas duas
versões; o commit instalado mudou de `b0a66949…` para `6f65e122…`. O sentinel
XDG permaneceu após o update e a desinstalação. O log, hashes e tamanho dos
bundles estão em [linux-flatpak-current-upgrade-2026-10-28.txt](linux-flatpak-current-upgrade-2026-10-28.txt).

## 2026-10-28 upgrade Solus release 3→4

Em um container Solus 4.9 x86_64 descartável com systemd, instalei a release 3,
verifiquei `jarvis --doctor` e `eopkg check`, atualizei para a release 4 do
worktree atual e repeti os checks. Os sentinelas XDG CONFIG/DATA/CACHE/STATE
permaneceram iguais; a remoção do Jarvis também os preservou. O log, hashes e
artefatos estão em [linux-solus-current-upgrade-2026-10-28.txt](linux-solus-current-upgrade-2026-10-28.txt).
O teste executado em um container comum falhou antes da instalação porque
faltava o serviço inhibitor do Solus; no container descartável com systemd o
ciclo passou.


## 2026-10-28 regressão Linux completa após correção do salvamento

`scripts/verify-linux.sh` passou: voice **560 passed/1 skipped**, helpers
**13 passed**, `win_context` **16 passed**, `delegate_local` **17 passed**, GUI
**7 passed**, OpenCode **120 passed**, Tauri Rust **7 passed**, e build release
do Tauri concluído com exit 0. A GUI agora distingue falha ao salvar configurações
de falha posterior ao selecionar modelo; se só o modelo falhar, informa que as
configurações foram salvas e mantém o fluxo de reinício. Isso é evidência
automatizada headless; portais/sessões gráficas reais e áudio físico continuam
pendentes.


## 2026-10-28 revisão de manifestos e matrizes CI

A revisão final corrigiu o nome raiz do lockfile OpenCode para `.opencode`,
preservando suas versões resolvidas. O manifest e o lockfile foram comparados, e
`npm ci --ignore-scripts --dry-run --no-audit --no-fund` terminou com “up to
date”. Os 13 alvos ativos em `packaging/targets.json` e as matrizes dos cinco
workflows Linux foram conferidos: somente x86_64 está ativo.


## 2026-10-28 gravação segura e limpeza de sessão portal

`write_text` agora escreve em inode temporário e substitui a entrada do destino
atomicamente; criação de arquivo usa instalação atômica sem sobrescrever um nome
criado em corrida. Um teste determinístico injeta um hardlink entre `fstat` e a
escrita e confirma que o alias externo mantém o conteúdo original, tanto para
sobrescrita quanto append. `PortalClient` agora remove o handler e o `RemoveMatch`
quando a sessão RemoteDesktop fecha, evitando acúmulo em conexões persistentes.
O teste usa `dbus-run-session` privado, não o portal da sessão do usuário.

Após essas mudanças, `scripts/verify-linux.sh` passou: voice **564 passed/1
skipped**, scripts **13**, MCPs **16** e **17**, GUI **7**, OpenCode **120**,
Tauri Rust **7** e build release Tauri, exit 0.


## 2026-10-28 pacote Arch atualizado após correções de segurança

Reconstruí o pacote Arch x86_64 do worktree com o código de escrita atômica e
limpeza dos match rules do portal. Em container Arch descartável, instalei a
versão anterior, atualizei para o artefato atual, confirmei doctor, integridade
`pacman -Qkk`, runtime Python privado, licença/OpenCode, overlay X11 em Xvfb
(pointer, clipboard e segunda instância), removi o pacote e confirmei hashes
inalterados para CONFIG/DATA/CACHE. Artefatos e SHA-256 estão na matriz.

## 2026-10-28 pacote Debian atualizado após correções de segurança

Reconstruí o `.deb` Debian Trixie x86_64 após a gravação atômica segura contra
hardlinks e a limpeza de match rules do portal. O build release Rust levou
2m24s; o build completo no Docker levou cerca de 9 minutos, incluindo downloads
e exportação da imagem. SHA-256 do `.deb`:
`99b50b45f5679b27cbfa6bd202a69151c46c3228124e8b6038bf4a9a16396e60`.

O ciclo em container descartável passou: instalação, doctor, imports privados,
integridade, ponteiro/clipboard em Xvfb, relançamento do overlay e remoção,
preservando dados do usuário. O container não tinha fonte Pulse nem hardware de
áudio; este resultado não valida áudio físico nem uma sessão desktop real.

## 2026-10-28 pacote Fedora 44 atualizado após correções de segurança

Reconstruí os RPMs x86_64 do worktree atual, com revisões 1 e 2, após a gravação
atômica segura contra hardlinks e a limpeza de match rules do portal. O build
Docker levou 24m15s porque o helper RPM compilou e empacotou ambas as revisões
separadamente. SHA-256 dos RPMs: revisão 1
`a9a7b3c4f640820fc2a072bcb34a8c1e7e9a6d9e6ba5fe8c5750d52e3c8cf278`; revisão 2
`73b8ca571973c979d4a48477e62695341aa1bfd98d1e903dd0a2878e3fcd28e6`.

O ciclo de upgrade Fedora 44 descartável passou: DNF instalou a revisão 1,
`jarvis --doctor` passou, atualização para a revisão 2 preservou sentinelas de
configuração/dados/cache, verificações RPM e overlay X11 em Xvfb passaram e a
remoção preservou os dados. O payload ocupa cerca de 912 MiB instalado (RPM
compactado de 205 MiB). O container não tem hardware/sessão de áudio real.

## 2026-10-28 pacote Ubuntu 24.04 atualizado após correções de segurança

Reconstruí o `.deb` x86_64 do worktree atual depois das correções de gravação
atômica e limpeza de sessões de portal. O build completo levou 8m28s; Rust release
compilou em 2m21s. SHA-256: `3d1d8bf802a86c1c8647a867409e60d4d2389fee473155635a42e23f0870a9b1`.

O ciclo em container Ubuntu 24.04 passou: instalação, doctor, imports privados,
integridade, ponteiro/clipboard e relançamento do overlay no Xvfb, remoção e
preservação dos dados de usuário. O container é headless e não valida áudio físico
ou sessão desktop real.

## 2026-10-28 pacote openSUSE Tumbleweed atualizado após correções de segurança

Reconstruí o RPM x86_64 do worktree atual. O build Rust release levou 3m58s e o
build Docker completo cerca de 13 minutos, incluindo a preparação das rodas
Python. Artefato: `dist/current-refresh/security-fix/suse/jarvis-assistant-0.1.0-1.x86_64.rpm`,
190.454.646 bytes; SHA-256
`257edbca098d880f499cc91f0776fe7ec014398ff0973c7fa8be138fda012a98`.

O ciclo em container descartável Tumbleweed passou: zypper resolveu 372 novos
pacotes incluindo o Jarvis, a instalação, doctor, imports privados, integridade,
ponteiro/clipboard e relançamento do overlay em Xvfb passaram; a remoção também
passou preservando dados do usuário. O container não valida áudio físico nem
uma sessão desktop real.

## 2026-10-28 pacote AlmaLinux 10 atualizado após correções de segurança

Reconstruí os RPMs x86_64 de Jarvis e xdotool do worktree atual. O build Rust
release levou 6m05s e o Docker completo cerca de 18 minutos. O RPM Jarvis está em
`dist/current-refresh/security-fix/rhel/jarvis-assistant-0.1.0-1.el10.x86_64.rpm`,
191.008.893 bytes, SHA-256
`d6031fa795faef8368a69173f90e3300f15448701145f0539fab9c246dabfb13`; o RPM
auxiliar xdotool também foi armazenado na mesma pasta.

O ciclo em container AlmaLinux 10 descartável passou depois de habilitar EPEL e
CRB: instalação, doctor, imports privados, integridade, ponteiro/clipboard via
Xwayland, relançamento/saída do overlay no Weston e remoção, preservando os dados
de usuário. O container não tinha hardware de áudio nem sessão desktop real.

## 2026-10-28 pacote Alpine 3.24 atualizado após correções de segurança

Reconstruí o APK x86_64 do worktree atual para musl. O build completo levou cerca
de 19 minutos e compilou CTranslate2, Piper e o overlay Tauri nativamente. APK:
`dist/current-refresh/security-fix/alpine/jarvis-assistant-0.1.0-r0.apk`,
177.523.321 bytes; SHA-256
`00dea1e9788eb81613b4c3d08632f7a77b03f1315faeafbb2e9eecc4127c1f31`. A chave
pública temporária do builder também foi guardada na pasta ao lado do APK.

Alpine 3.24 verificou a assinatura e instalou o APK com 375 dependências de
sistema. Doctor, imports privados, integridade, ponteiro/clipboard e relançamento
do overlay em Xvfb passaram; a remoção preservou os dados. Esse container não
valida áudio físico nem uma sessão desktop real.

## 2026-10-28 bundle Flatpak atualizado após correções de segurança

Preparei um snapshot de fontes novo, recompilado offline no SDK GNOME 49 fixado,
e gerei o bundle x86_64 em
`dist/current-refresh/security-fix/flatpak/jarvis-x86_64.flatpak` (181.425.376
bytes; SHA-256 `86c6f4777768505129f7ceb6a3fd9b7577944cb10296f39e8f3f056831df0b5e`).
O bundle foi importado novamente no repositório OSTree local; OpenCode reportou
1.18.23 e `jarvis --doctor` passou dentro do sandbox de build. A instalação,
upgrade e remoção pelo Flatpak ainda precisam de ciclo próprio, então esse alvo
está parcial na matriz e não entra na contagem de ciclos completos.

Durante a exportação, o limite padrão de espaço livre de 3% do OSTree bloqueou o
commit no disco quase cheio. Reduzi o limite somente no repositório temporário
desse build para 2%; o host ainda tinha aproximadamente 14 GiB livres. Removi
caches de compilação Flatpak gerados após preservar o build final e liberei
13 GiB removendo imagens Docker de build já concluídas.

## 2026-11-05 pacote Void glibc atualizado após correções de segurança

Extraí da imagem Docker de build atual os pacotes XBPS x86_64 `0.1.0_1` e
`0.1.0_2`. O pacote atual está em
`dist/current-refresh/security-fix/void-glibc/jarvis-assistant-0.1.0_2.x86_64.xbps`
(212.860.928 bytes; SHA-256
`3e969762a69f47f324ee62b1a7a474b5642d9d5ba408a5a73db005de3a08f128`).

O ciclo em container Void glibc descartável passou: instalação da revisão `_1`,
atualização para `_2`, doctor, imports do runtime privado, integridade XBPS,
ponteiro/clipboard e relançamento do overlay no Xvfb; a remoção preservou os
dados do usuário. O container não valida áudio físico nem sessão desktop real.

## 2026-11-05 ajuste de escopo dos pacotes Linux

A pedido do usuário, retirei Void musl, Nix, Slackware e Solus dos builds ativos
x86_64. As receitas, artefatos e resultados anteriores ficam preservados como
histórico; Gentoo e GNU Guix já estavam excluídos. O workflow Void agora gera
apenas glibc e o workflow Nix foi removido. A matriz marca os quatro alvos como
fora do escopo ativo.

O build Void musl que havia sido iniciado localmente foi cancelado antes da
compilação do pacote; não houve novo artefato. Após a alteração, a rodada ativa
tem 9 alvos: 8 ciclos completos e o Flatpak com bundle compilado, aguardando o
ciclo de instalação/upgrade/remoção.

## 2026-11-05 ciclo Flatpak após as correções de segurança

O bundle antigo `flatpak-native-2026-10-19` foi instalado em um `FLATPAK_USER_DIR`
temporário com HOME separado. Clonei por hardlink os objetos do repositório
OSTree e os runtimes existentes para evitar downloads duplicados; o app e seus
dados foram implantados somente no perfil temporário. `jarvis --doctor`,
OpenCode 1.18.23 e imports privados (`faster_whisper`, `piper`, `mcp`, `httpx`,
`dbus_next` e `gi`) passaram.

Atualizei para
`dist/current-refresh/security-fix/flatpak/jarvis-x86_64.flatpak`. O commit mudou
de `b0a66949e5d567b28e446317c5cee408fcc951657d895b364da88d6b273fdcad` para
`3de43fe01588959b8d199b76a28043694ffecc9bb0920e17d4462dccb262ddc4`; doctor,
OpenCode e preservação do sentinel passaram. A remoção do app manteve os dados.
O app no perfil padrão continuou instalado no commit
`7e693a6d30680495c2c18326df291625f879fcd4280a8605a286c49572fadd43`. Esse ciclo
headless não valida interação gráfica, autorização de portais nem áudio físico.

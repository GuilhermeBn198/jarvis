# Linux nativo

O porte ativo suporta **somente x86_64**. Resultados AArch64/ARM64 anteriores
são históricos. O catálogo contém 15 receitas: 9 alvos ativos e 6 excluídos
(Gentoo, GNU Guix, Void musl, Nix, Slackware e Solus). Os ciclos dos 9 alvos
ativos passaram, incluindo upgrade Flatpak em perfil isolado. Consulte a
[matriz](notes/linux-matrix.json) para evidências e limitações por validação.

Os resultados Nix abaixo são históricos; Nix está fora do escopo ativo desde
2026-11-05.

No Arch/KDE Wayland, o pacote instalado passou o diagnóstico e o fluxo sintético
Piper→fonte Pulse virtual→PTT/VAD→faster-whisper. Uma tentativa física enviou
fala Piper ao sink de fones a 15% e gravou 8 s do microfone Mic2; a transcrição
não correspondeu à frase esperada, então o teste ponta a ponta falhou. O WAV foi
apagado e o volume original (61%, sem mute) foi restaurado. Ainda faltam PTT/VAD
com fala física reconhecida, confirmação de reprodução audível, autorização e
revogação reais dos portais e validação em outras sessões/desktops. A reprodução
sintética de TTS foi roteada por FFmpeg/Pulse
para um sink virtual e capturada/transcrita pelo monitor; isso não valida o
som em alto-falantes físicos. O backend agora tenta
libei/EIS para clique Wayland com fallback RemoteDesktop; o pedido real de
consentimento expirou sem resposta, então a entrega do clique continua sem
confirmação. O teclado foi validado numa janela de teste. O timeout de Ollama
via OpenCode também segue em investigação em host CPU-only.

Veja [pacotes Linux](linux-packages.md) e [registro de verificação](notes/linux-verification.md)
para status, artefatos e limites por teste.

Para executar as regressões locais de voz, MCP, GUI, OpenCode e Rust, rode
`scripts/verify-linux.sh`; `scripts/verify-linux.sh --list` mostra as etapas.
Esse comando não substitui validação em desktop/portal real, áudio físico ou
build dos pacotes em cada distribuição.

## Instalação por fonte

Requer Python 3.10+, Rust, ferramentas de compilação GTK3/WebKitGTK 4.1,
FFmpeg com PulseAudio/ALSA, FFplay, Node/npm e o agente opencode instalado e
configurado. Para contexto acessível, instale PyGObject e os typelibs AT-SPI
compatíveis com o Python da distro. Clipboard usa wl-clipboard no Wayland ou
xclip no X11; a enumeração ALSA usa alsa-utils. O script não exige um gerenciador
específico e não instala bibliotecas do sistema por conta própria.

```sh
cargo build --release --manifest-path gui/src-tauri/Cargo.toml
./scripts/install-source.sh --download-voice
# Prefixo padrão: ~/.local. --prefix permite outro diretório.
~/.local/bin/jarvis --doctor
~/.local/bin/jarvis-overlay
```

O instalador cria venv privado, instala dependências Python e SDK dos plugins
no prefixo do aplicativo. Bibliotecas GI da distro são disponibilizadas via
system-site-packages; `JARVIS_ACCESSIBILITY_PYTHON` permite selecionar outro
Python com PyGObject/AT-SPI. Não usar instalação pip no Python do sistema.

`--autostart` adiciona uma entrada XDG para iniciar no login; é opcional.
O overlay inicia o cérebro automaticamente. Configure voz e agente antes de
abrir; o modo auto começa a captar por detecção de fala quando o cérebro está
ativo. Mudo, pausa e saída estão no menu; o menu também é acessível por teclado.

## Voz e configuração

```sh
~/.local/bin/jarvis --download-voice
~/.local/bin/jarvis --list-mics
~/.local/bin/jarvis --mic-level
~/.local/bin/jarvis --voice
```

A voz padrão Faber brasileira tem 63,2 MB. O comando verifica tamanho e SHA256
contra um manifesto fixado em revisão do repositório, incluindo modelo,
configuração e MODEL_CARD. O MODEL_CARD informa CC0 para o dataset; consulte
seus termos completos. Modelos personalizados usam `PIPER_MODEL`.

Dados/modelos ficam em `$XDG_DATA_HOME/jarvis` (default `~/.local/share/jarvis`),
settings em `$XDG_CONFIG_HOME/jarvis` e logs em `$XDG_STATE_HOME/jarvis`.
Variáveis de ambiente prevalecem sobre settings. `AUDIO_BACKEND=pulse` é o
padrão e funciona com PipeWire-Pulse; `AUDIO_BACKEND=alsa` é alternativa.
`MIC_DEVICE=default` pode ser substituído por um nome da enumeração.
`jarvis --doctor` verifica se o FFmpeg tem entrada para o backend escolhido e
se consegue enumerar fontes; isso não grava áudio. `--list-mics` usa `pactl`
no Pulse e `arecord` no ALSA para mostrar nomes de dispositivos, então instale
`alsa-utils` se esse comando falhar com `AUDIO_BACKEND=alsa`. Para testar a
alternativa ALSA no diagnóstico:

```sh
AUDIO_BACKEND=alsa ~/.local/bin/jarvis --doctor
```

Para verificar a captura de fato, execute
`~/.local/bin/jarvis --mic-level` numa sessão em que seja seguro gravar o
microfone.

O arquivo `~/.config/jarvis/overlay.json` aceita `launcher` (caminho para
jarvis) ou `loop_cmd` (comando definido pelo usuário). `JARVIS_OVERLAY_CONFIG`
seleciona outro arquivo; `JARVIS_STATE_PORT` funciona também no overlay em
runtime. No Wayland, o modo padrão usa janela normal, respeitando o compositor;
`JARVIS_WINDOW_MODE=orb` solicita o modo sem decoração.


## Seleção do modelo

O painel de configurações lista os modelos do Ollama e salva a seleção para as
próximas solicitações. Modelos com sufixo `:cloud` são executados remotamente e
podem receber transcrição, prompt e contexto de tela; confira o aviso do painel
antes de selecionar um.

A resposta de modelo local depende do hardware e do caminho de solicitação. No
host Arch CPU-only testado, `qwen3:8b` respondeu por chamada direta ao Ollama,
mas o fluxo completo do Jarvis pelo OpenCode excedeu 90 s; as tentativas
posteriores apontaram geração perto de 5 tokens/s no CPU. Portanto, `qwen3:8b`
nesse perfil de CPU não é uma configuração recomendada para conversa interativa;
use aceleração compatível ou escolha um modelo menor e meça a latência no seu
hardware. O catálogo e a seleção continuam disponíveis, mas não garantem que
todo modelo listado tenha latência adequada. O uso via cloud MiniMax passou um
smoke curto.

## Desktop e permissões

Screenshot Wayland solicita autorização no diálogo do desktop. Controle de
teclado/mouse solicita uma sessão RemoteDesktop; autorização de screenshot
não é autorização de controle. Recusa/timeout não produzem sucesso.

No Wayland, clicks usam coordenadas do compositor locais ao stream autorizado,
não pixels da imagem. Com vários monitores, o stream deve ser selecionado.
Contexto/listagem dependem do que os apps expõem via AT-SPI; não há garantia de
listagem global de toda janela Wayland. Texto em background usa controle
editável acessível e verifica texto/foco; atalhos arbitrários em background
são recusados, sem trazer a janela para frente automaticamente.

O serviço de desktop usa socket privado em `$XDG_RUNTIME_DIR/jarvis`, verifica
UID e acompanha o PID/identidade do cérebro. Serviços iniciados por comandos
isolados expiram após inatividade. Encerrar o cérebro encerra sua sessão e
seus workers; aplicativos abertos por uma ação continuam pertencendo ao usuário.

Arquivos Linux usam `file_read`/`file_write`; aliases `win_read`/`win_write`
continuam disponíveis. Escrita exige confirmação e uma lista JSON de diretórios
existentes, por exemplo:

```sh
export JARVIS_ALLOW_WRITE='["/home/seu-usuario/Documentos/autorizados"]'
```

A ferramenta não segue symlinks, recusa hardlinks/arquivos especiais e bloqueia
caminhos de credenciais. Leitura UTF-8 é limitada a 64 KiB; escrita a 256 KiB.
O MCP preserva aliases Windows e oferece ferramentas `desktop_*` no Linux.

## Zipapp

`./scripts/build-pyz.sh` embute também triggers, plugins, configuração e
servidores MCP. Fora do checkout, extrai esses recursos em cache privado para
o agente poder carregá-los. Dependências pesadas continuam externas; use o
Python/venv que as tem. `JARVIS_PROJECT_ROOT` explícito mantém precedência.

## Verificação

```sh
voice/.venv/bin/python -m pytest voice/tests -q
voice/.venv/bin/python -m pytest mcp_servers/win_context/tests -q
node --test '.opencode/**/*.test.ts' gui/tests/*.test.mjs
cargo test --manifest-path gui/src-tauri/Cargo.toml
```

Testes GUI opt-in usam somente janelas descartáveis próprias:
`JARVIS_DESKTOP_TESTS=1 voice/.venv/bin/python -m pytest voice/tests/test_atspi_desktop.py -q`.
Um resultado no Arch/KDE não comprova funcionamento nas demais distros,
arquiteturas ou gerenciadores. Os checks de CI validam os alvos listados na
matriz, mas não substituem testes de desktop real, microfone, áudio e portais em
cada combinação.

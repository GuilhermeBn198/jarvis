# Linux nativo

O porte está em implementação. Voz, screenshot, ações, contexto AT-SPI,
arquivos e overlay já têm implementação nativa e evidências no Arch/KDE
Wayland. Flatpak e pacotes de cada gerenciador ainda não foram entregues.
Veja `docs/notes/linux-verification.md` para os testes e as lacunas atuais.

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

O arquivo `~/.config/jarvis/overlay.json` aceita `launcher` (caminho para
jarvis) ou `loop_cmd` (comando definido pelo usuário). `JARVIS_OVERLAY_CONFIG`
seleciona outro arquivo; `JARVIS_STATE_PORT` funciona também no overlay em
runtime. No Wayland, o modo padrão usa janela normal, respeitando o compositor;
`JARVIS_WINDOW_MODE=orb` solicita o modo sem decoração.

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
arquiteturas ou gerenciadores. A matriz completa e os pacotes seguem pendentes.

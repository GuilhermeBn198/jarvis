# Porte Linux — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Executar o Jarvis nativamente em Linux e entregar Flatpak e pacotes/receitas para todos os gerenciadores previstos na especificação.

**Architecture:** Backends selecionados por capacidades preservam Windows/WSL e acrescentam Linux. O cérebro fornece operações Linux ao overlay, aos plugins e ao MCP; empacotamento compartilha uma árvore instalada e adapta dependências por alvo.

**Tech Stack:** Python 3.10+, FFmpeg, Piper, faster-whisper, Rust/Tauri 2, TypeScript, D-Bus/portais, AT-SPI, Flatpak e ferramentas nativas de pacote.

**Spec:** `docs/superpowers/specs/2026-10-14-jarvis-linux-design.md`

## Global Constraints

- O caminho Linux não exige Windows, PowerShell, caminhos `/mnt/c`, dispositivos DirectShow ou serviços WSL.
- Windows/WSL continuam suportados.
- CPU é obrigatória e GPU é opcional.
- Não reduzir o porte a voz ou a X11 para declarar sucesso.
- Background não pode ativar uma janela como fallback automático.
- Escrita mantém confirmação e allowlist explícita.
- Não depender de `flatpak-spawn --host` para o caminho principal.
- Não modificar o Python do sistema nem baixar dependências como root no pós-instalação.
- Entregar x86_64 e aarch64 onde os alvos suportarem essas arquiteturas.
- Receita escrita sem build/instalação real não comprova a entrega.
- A meta não é concluída enquanto houver requisito não implementado ou não verificado.

## Review Focus

- Sessão Wayland com DISPLAY de XWayland: nunca anunciar controle de aplicativo nativo a partir de ações em X11 (tarefas 1 e 4).
- Negação/revogação de portal no meio de um turno: encerrar sessão e não repetir entrada nem anunciar sucesso (tarefas 3 e 4).
- Diretórios XDG e caminhos de instalação com espaços/Unicode: preservar argumentos e localizar plugins/modelos (tarefas 1 e 7).
- Symlink trocado durante escrita: não escapar da allowlist por corrida de resolução (tarefa 6).
- Atualização de pacote com dados/modelos do usuário: preservar dados e remover somente arquivos pertencentes ao pacote (tarefa 9).

## Organização e execução

O plano é dividido em quatro blocos testáveis: plataforma/voz (1–2), desktop (3–6), aplicação instalada (7), distribuição e auditoria (8–10). Eles compõem uma única entrega e têm dependências explícitas. Executar em worktree isolada; registrar resultados por tarefa e fazer commits pequenos. Não iniciar publicação externa de repositórios de pacotes sem autorização específica.

## Task 1: Plataforma, configuração e diagnóstico

**Files:** criar `voice/platforms.py`, `voice/diagnostics.py`, `voice/tests/test_platforms.py`, `voice/tests/test_diagnostics.py`; modificar `voice/config.py`, `voice/paths.py`, `voice/settings.py`, `voice/loop.py`, `voice/tests/test_config.py`.

**Interfaces:** `detect_platform(env: dict, release: str) -> str` retorna `linux`, `wsl` ou `windows`; `desktop_session(env: dict) -> str` retorna `wayland`, `x11` ou `headless`. `xdg_path(kind: str, env: dict) -> pathlib.Path` suporta config/data/cache/state/runtime. Config recebe `platform` e `audio_backend` (`pulse`, `alsa`, `dshow`). `diagnose(config: Config) -> dict` informa capacidade, backend e motivo de indisponibilidade.

- [ ] Escrever testes: Linux usa `ffmpeg`, `ffplay`, `piper` e mic `default`; WSL mantém defaults Windows; override explícito vence settings; XDG relativo é rejeitado; XDG com espaços é preservado; Wayland vence DISPLAY; headless não escolhe automação gráfica. SAPI no Linux retorna erro de configuração.
- [ ] Rodar `python3 -m pytest voice/tests/test_platforms.py voice/tests/test_config.py voice/tests/test_diagnostics.py -q`; confirmar falhas pelas interfaces ausentes.
- [ ] Implementar interfaces e flags `JARVIS_PLATFORM`, `AUDIO_BACKEND`, `--doctor`; a detecção não usa nome da distro. Diagnóstico não grava áudio nem injeta eventos.
- [ ] Rodar os testes acima e `python3 -m pytest voice/tests -q`; todas as expectativas devem passar. Tornar testes Windows explícitos em vez de mudar expectativas para Linux.
- [ ] Commit: `feat: detecta capacidades Linux e preserva backend WSL`.

## Task 2: Captura, temporários e TTS nativos

**Files:** criar `voice/audio.py`, `voice/tests/test_audio.py`; modificar `voice/capture.py`, `voice/tts.py`, `voice/stream.py`, `voice/loop.py`, `voice/tests/test_capture.py`, `voice/tests/test_tts.py`, `voice/tests/test_stream.py`.

**Interfaces:** `input_args(cfg: Config) -> list[str]`; `list_devices(cfg: Config) -> list[str]`; `temporary_audio(cfg: Config)` é context manager de arquivo exclusivo acessível à plataforma; `speak` e funções públicas de captura preservam assinaturas atuais.

- [ ] Testar argv de pulse/alsa/dshow, listagem pactl/ALSA, dispositivos inexistentes, ausência do servidor de áudio, VAD sem fala, cancelamento/saída do processo e duas sínteses concorrentes sem colisão. Confirmar que caminhos Linux não sofrem conversão de drives.
- [ ] Rodar `python3 -m pytest voice/tests/test_audio.py voice/tests/test_capture.py voice/tests/test_tts.py voice/tests/test_stream.py -q` e confirmar falhas novas.
- [ ] Implementar captura e calibração compartilhando `input_args`; usar temporários exclusivos para artefatos internos e preservar arquivos solicitados pelo usuário. Liberar FFmpeg e arquivos em todos os caminhos. Piper Linux e FFplay recebem argv nativo; texto passa por stdin.
- [ ] Rodar testes e comprovar mic real em pulse e ALSA, modos auto/fixed/ptt, STT CPU, Piper normal/streaming. Registrar evidência em `docs/notes/linux-verification.md`, incluindo dependências e voz utilizada.
- [ ] Commit: `feat: habilita captura e fala nativas no Linux`.

## Task 3: Screenshot com X11 e portal

**Files:** criar `voice/portal.py`, `voice/linux_screen.py`, `voice/tests/test_portal.py`, `voice/tests/test_linux_screen.py`; modificar `voice/vision.py`, `voice/tests/test_vision.py`, `voice/requirements.txt`.

**Interfaces:** `PortalError(code: str, detail: str)`; `PortalClient.request(interface: str, method: str, args: tuple, timeout_s: float) -> dict`; `screenshot(out_path: str, cfg: Config) -> str`. D-Bus usa biblioteca Python com dependência fixada no build; callback de Response é instalado antes da chamada, validando sender/path/token.

- [ ] Testar Response imediato, timeout, cancelamento, recusa, URI com espaços, arquivo ausente e portal desaparecido. X11 falhando não retorna PNG antigo; Wayland não chama gdigrab/X11 como fallback.
- [ ] Rodar `python3 -m pytest voice/tests/test_portal.py voice/tests/test_linux_screen.py voice/tests/test_vision.py -q` e confirmar falhas.
- [ ] Implementar screenshot X11 e portal, importação/limpeza segura do PNG e limites de tempo. Preservar agente vision sem ferramentas e tratamento de conteúdo não confiável.
- [ ] Rodar testes; validar captura real em GNOME/KDE Wayland e X11, incluindo negação e múltiplos monitores. Registrar resultados.
- [ ] Commit: `feat: captura tela Linux com consentimento via portal`.

## Task 4: Automação Linux e bridge das ferramentas

**Files:** criar `voice/desktop_service.py`, `voice/desktop_bridge.py`, `voice/linux_input.py`, `voice/tests/test_linux_input.py`, `voice/tests/test_desktop_bridge.py`, `.opencode/act/platform.ts`, `.opencode/act/linux.ts`, `.opencode/act/linux.test.ts`; modificar `.opencode/plugins/act-tools.ts`, `voice/loop.py`, `opencode.json`.

**Interfaces:** `DesktopService.execute(operation: str, args: dict) -> dict` retorna `status`, `detail` e dados opcionais. Estados: `ok`, `unsupported`, `denied`, `cancelled`, `unconfirmed`, `error`. Bridge: uma requisição JSON por stdin e uma resposta JSON por stdout; código não zero em erro. Serviço por socket Unix em runtime privado (0700), peer UID validado, sem porta pública. `runLinux(operation: string, args: object): Promise<string>` invoca bridge com argv e timeout. Sessão RemoteDesktop pertence ao serviço, não ao subprocesso transitório.

- [ ] Testar texto Unicode/literal com metacaracteres, atalhos válidos/inválidos, click fora da área autorizada, coordenadas escaladas, foreground/background, peer estranho, requisição excessiva, consentimento recusado e sessão revogada. Não retornar sucesso por simples envio de entrada. Background sem suporte retorna `unsupported` sem ativar janela.
- [ ] Rodar `python3 -m pytest voice/tests/test_linux_input.py voice/tests/test_desktop_bridge.py -q` e `node --test .opencode/act/linux.test.ts`; confirmar falhas.
- [ ] Implementar X11 com ferramentas nativas validadas e Wayland pelo RemoteDesktop/ScreenCast com mapeamento de stream. Abrir URL/arquivo pelo desktop, executável por argv validado; não executar shell arbitrário. Acrescentar ações AT-SPI onde verificáveis. SafetyGate permanece antes do dispatch; Windows usa funções existentes.
- [ ] Rodar testes Python/TypeScript e SafetyGate. Demonstrar type/key/click/open em apps Wayland nativos e X11, revogação e saída limpando sessão. Background exige prova de foco/cursor preservados ou erro honesto.
- [ ] Commit: `feat: oferece acoes Linux por backend e permissao`.

## Task 5: Contexto textual e MCP multiplataforma

**Files:** criar `voice/linux_context.py`, `voice/tests/test_linux_context.py`; modificar `mcp_servers/win_context/context.py`, `mcp_servers/win_context/server.py`, seus testes/README, `.opencode/plugins/act-tools.ts`, `opencode.json`.

**Interfaces:** `list_windows() -> list[dict]` com ID Linux opaco; `accessibility_tree(window_id: str, max_nodes: int, timeout_s: float) -> str`; `clipboard_text() -> str`; `processes(name_filter: str) -> str`. Manter aliases Windows e adicionar nomes neutros; `hwnd` não é reinterpretado como ID Linux.

- [ ] Testar árvore AT-SPI cíclica, excesso de nós, app travado, clipboard ausente, headless, IDs ambíguos e indisponibilidade de listagem global Wayland. Confirmar que import Linux não tenta PowerShell.
- [ ] Rodar `python3 -m pytest voice/tests/test_linux_context.py -q` e `python3 -m pytest mcp_servers/win_context/tests -q`; confirmar falhas novas.
- [ ] Implementar contexto com limites e formatação compacta, selecionar plataforma no MCP e atualizar prompts para capacidades/IDs/background. Não ler clipboard ou desktop espontaneamente no diagnóstico.
- [ ] Rodar testes; verificar MCP real por cliente e AT-SPI em app acessível, app não acessível e timeout.
- [ ] Commit: `feat: adiciona contexto desktop Linux ao MCP`.

## Task 6: Arquivos locais com controle de escrita

**Files:** criar `voice/local_files.py`, `voice/tests/test_local_files.py`; modificar bridge, `.opencode/plugins/winfs-tools.ts`, `.opencode/safety/rules.ts` e seus testes, `opencode.json`.

**Interfaces:** `read_text(path: str) -> str`; `write_text(path: str, content: str, append: bool, confirm: bool, allowlist: list[str]) -> dict`. `JARVIS_ALLOW_WRITE` usa lista JSON de diretórios absolutos. Nomes neutros `file_read`/`file_write` e aliases legados obedecem ao mesmo SafetyGate.

- [ ] Testar falta de confirmação, allowlist vazia, prefixo vizinho, `..`, symlinks internos/externos, troca de symlink entre checagem e abertura, arquivo novo, append e credenciais bloqueadas.
- [ ] Rodar `python3 -m pytest voice/tests/test_local_files.py -q` e testes SafetyGate; confirmar falhas.
- [ ] Implementar travessia por descritores com no-follow e validação no ponto de abertura; não confiar só em resolve seguido de open. Flatpak aceita caminhos expostos por portal/diretórios autorizados. Atualizar regras e mensagens sem ampliar permissões.
- [ ] Rodar testes e demonstrar leitura/escrita autorizadas e recusas no aplicativo instalado.
- [ ] Commit: `feat: suporta arquivos Linux com allowlist segura`.

## Task 7: Overlay e instalação comum

**Files:** criar `gui/src-tauri/src/brain.rs`, `scripts/install-source.sh`, `packaging/common/jarvis.desktop`, `packaging/common/launcher`, `packaging/common/install-layout.json`; modificar `gui/src-tauri/src/main.rs`, Cargo/config Tauri, frontend, `jarvis`, `voice/__main__.py`, `scripts/build-pyz.sh` e testes zipapp.

**Interfaces:** `brain::start(config: &OverlayConfig) -> Result<Child, String>`, `brain::stop(child: &mut Child) -> Result<(), String>`. Árvore de staging contém launcher, overlay e aplicação em `lib/jarvis` (voice, plugins, MCP, opencode.json e runtime privado quando necessário); launcher aceita prefixo instalado e não exige checkout/venv de desenvolvimento.

- [ ] Testar arranque/reinício/saída com processo fake que cria filho, preservação de processos alheios, comando/path Unicode e espaços, logs XDG, ausência de HOME e dependência ausente. Testar launcher instalado e zipapp preservando projeto/plugins.
- [ ] Rodar `cargo test --manifest-path gui/src-tauri/Cargo.toml` e testes Python relevantes; confirmar falhas Linux novas.
- [ ] Implementar lançamento direto Linux com encerramento da árvore própria, config/log XDG e backend Windows existente. UI mostra backends disponíveis; janela acessível em Wayland quando orbe não suporta empilhamento/posição. Instalador fonte POSIX verifica ferramentas sem escolher gerenciador automaticamente; autostart opt-in via XDG desktop.
- [ ] Rodar cargo test/build e regressão Python; instalar staging em prefixo com espaços, abrir overlay, usar menu/settings/mic, reiniciar e sair. Confirmar zero processos próprios órfãos.
- [ ] Commit: `feat: executa overlay e launcher diretamente no Linux`.

## Task 8: Flatpak completo

**Files:** criar `packaging/flatpak/com.jarvis.overlay.yml`, `packaging/flatpak/com.jarvis.overlay.metainfo.xml`, `scripts/build-flatpak.sh`, `.github/workflows/linux-flatpak.yml`; modificar documentação e manifestos de dependências.

**Interfaces:** `scripts/build-flatpak.sh` gera bundle instalável e checksum a partir de fontes versionadas. Runtime/SDK e dependências são fixados na implementação com hashes; empacotar o agente e ferramentas necessárias dentro do sandbox.

- [ ] Escrever smoke test de instalação que falha sem launcher, plugin, MCP, agente, Piper, FFmpeg ou bibliotecas nativas; provar que não usa executáveis exclusivos do host.
- [ ] Executar smoke test contra staging incompleto e confirmar falha.
- [ ] Implementar build Flatpak com rede, áudio, Wayland/fallback X11 e portais/AT-SPI autorizados; sem host spawn principal nem acesso filesystem irrestrito. Primeiro uso configura autenticação e modelos verificáveis com licença/tamanho, erro offline claro.
- [ ] Rodar `flatpak-builder --force-clean build-flatpak packaging/flatpak/com.jarvis.overlay.yml`; instalar/run bundle em usuário de teste e verificar versões/doctor e fluxo completo no sandbox. Validar x86_64 e aarch64 por builds reais.
- [ ] Commit: `build: distribui aplicativo completo em Flatpak`.

## Task 9: Gerenciadores nativos

**Files:** criar `packaging/debian/`, `packaging/rpm/fedora/`, `packaging/rpm/suse/`, `packaging/arch/PKGBUILD`, `packaging/alpine/APKBUILD`, `packaging/void/template`, `packaging/gentoo/`, `packaging/nix/flake.nix`, `packaging/guix/jarvis.scm`, `packaging/slackware/jarvis.SlackBuild`, `packaging/solus/package.yml`, `scripts/build-package.sh`, `.github/workflows/linux-packages.yml`, `packaging/targets.json`, `docs/linux-packages.md`.

**Interfaces:** `scripts/build-package.sh --target <target> --arch <arch> --output <dir>`; target é explícito, registrado em JSON com distro/version/libc/arquitetura/formato. O script falha fora do ambiente correspondente em vez de gerar artefato falsamente universal. Cada receita instala a árvore da tarefa 7 e declara dependências específicas; fonte e licença acompanham redistribuição.

Executar o ciclo abaixo separadamente para cada família da tabela da spec, com commits por família; não marcar a tarefa inteira por um único DEB/RPM.

- [ ] Preparar teste de pacote que exige metadados, dependências, arquivos, launcher e recursos da árvore comum; instalação em ambiente vazio deve falhar antes da receita existir.
- [ ] Construir usando dpkg-buildpackage, rpmbuild (Fedora/SUSE separados), makepkg, abuild, xbps-src, ebuild, nix build, guix build, SlackBuild e ferramenta de build Solus nos respectivos alvos. Dependências musl recebem build próprio; não reutilizar wheels glibc.
- [ ] Inspecionar artefato com ferramentas nativas e validadores disponíveis (lintian/rpmlint/namcap etc.); instalar pelo gerenciador do alvo com dependências, executar launcher/doctor e overlay em desktop real.
- [ ] Construir segunda versão, atualizar, verificar dados/modelos existentes e remover. Asserções: dados do usuário idênticos; arquivos de sistema do pacote removidos; zero pip/download de root em pós-instalação. Testar x86_64/aarch64 onde suportados e Void glibc/musl.
- [ ] Documentar comandos de artefato local/receita, distro/versão/ABI, checksums e atualização. Não anunciar disponibilidade em repositório oficial sem publicação real.
- [ ] Commit por família: `build: adiciona pacote nativo <familia>`.

## Task 10: Matriz funcional e auditoria final

**Files:** criar `scripts/verify-linux.sh`, `docs/notes/linux-matrix.json`, `docs/linux.md`; modificar `README.md`, `voice/README.md`, `mcp_servers/win_context/README.md`, `docs/notes/linux-verification.md` e workflows.

**Interfaces:** Cada resultado da matriz registra distro/version/arch/libc/desktop/session/package, comando, resultado e evidência. Campo sem evidência é `unverified`, nunca `passed`.

- [ ] Rodar regressão `python3 -m pytest voice/tests -q`, suites MCP separadas, `node --test '.opencode/**/*.test.ts'`, cargo test/build e builds de distribuição. Confirmar suporte do Node a TypeScript antes de escolher versão de CI.
- [ ] Executar matriz Ubuntu/Debian, Fedora, Arch, openSUSE, GNOME/KDE Wayland e X11; demais alvos da tarefa 9 incluem validação de pacote e funcionalidade instalada. Containers comprovam pacote, não substituem áudio/GUI reais. Registrar arquiteturas e musl.
- [ ] Verificar em cada desktop os fluxos da spec: mic/calibração/VAD/PTT/fixed/STT/TTS/streaming, screenshot e consentimento, ações e contexto, arquivos, menu/settings/reinício/saída e ausência de órfãos. Incluir Wayland nativo, multi-monitor/escala, revogação e background sem mudança de foco.
- [ ] Atualizar documentação com somente resultados comprovados, limitações por capacidade, requisitos externos e recuperação. Não apresentar resultados simulados como E2E real.
- [ ] Auditar os dez critérios da spec requisito por requisito e ligar cada um à evidência atual. Corrigir lacunas ou manter objetivo incompleto quando faltarem ambientes; não concluir pelo total de unit tests.
- [ ] Solicitar revisão independente do diff completo conforme método escolhido, resolver achados, repetir somente verificações afetadas e fazer commit `docs: registra validacao e instalacao do porte Linux`.

## Handoff

Este plano depende da revisão do usuário e da escolha de execução: nativa nesta sessão ou por agentes com revisão por tarefa. Não criar implementações antes desse aceite. Durante execução, impedimentos de acesso a ambientes reais são registrados, sem substituir a meta por um subconjunto testado.

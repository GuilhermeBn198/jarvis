# Evidências do porte Linux — execução em andamento

Worktree: `.worktrees/linux-port`, branch `feat/linux-port`.
Não é uma declaração de suporte universal ou conclusão do porte.

## Plataforma/configuração

- Linux nativo seleciona executáveis POSIX e mic default; WSL mantém dshow.
- `--doctor` informa presença de dependências sem iniciar agente/microfone.
- Sessão Wayland tem precedência sobre DISPLAY de XWayland.
- Configuração/settings seguem diretórios XDG absolutos; valores relativos
  de XDG são ignorados em favor dos defaults absolutos.
- Teste antigo de raiz do projeto corrigido para não depender do nome da pasta.
- Suite após etapa 1: 324 passed (Python 3.14, Arch Linux).

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

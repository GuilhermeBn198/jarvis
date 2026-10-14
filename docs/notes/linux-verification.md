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

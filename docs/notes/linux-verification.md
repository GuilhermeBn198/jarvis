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

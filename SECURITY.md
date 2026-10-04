# Política de segurança

## Reportar uma vulnerabilidade

Não abra issue pública para falhas de segurança. Reporte em privado ao dono do
repositório (`@GuilhermeBn198`) pelo contato no perfil do GitHub. Descreva o
impacto e, se possível, um passo a passo para reproduzir.

## Escopo

Áreas sensíveis deste projeto:

- O loop de voz e os binários que ele invoca (`ffmpeg`, `piper`, `powershell`).
- As tools de ação no PC (`act_*`) e o **SafetyGate** (`.opencode/safety`), que
  decide `allow`/`ask`/`deny`.
- A tool `see_screen` e o conteúdo de tela, tratado como **não-confiável**.
- O `StateHub` HTTP/SSE local (`127.0.0.1`).

## Práticas

- Segredos nunca vão para o repositório; `.gitignore` cobre `.env`, `local.conf`,
  `settings.json`, `jarvis-config.json` e logs.
- O Jarvis não executa comandos a partir de conteúdo lido da tela ou de janelas.
- Alterações no `SafetyGate` e nas tools `act_*` exigem revisão do dono.

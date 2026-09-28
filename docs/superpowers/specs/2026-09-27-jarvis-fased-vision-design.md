# Jarvis Fase D — Visão de tela (Design)

- **Data:** 2026-09-27
- **Status:** aprovada (implementação)
- **Fase:** D. Depende de C (voz) em `main`.
- **Objetivo:** "jarvis, olha pra minha tela e …" — capturar a tela do Windows e perguntar a um **modelo de visão**, com acionamento **explícito**.

## 1. Viabilidade (validada nesta máquina)

| Item | Resultado |
|---|---|
| Captura | ✅ `ffmpeg.exe -f gdigrab -i desktop -frames:v 1 -update 1 shot.png` → PNG 1920×1080 |
| Visão | ✅ `opencode-go/deepseek-v4-flash-vision-exp` via `opencode run -f <png>` descreveu a tela corretamente |
| `-f` (attach) | ⚠️ a mensagem deve vir **antes** de `-f` (senão o `-f` a engole) |
| Saída | inclui ANSI + cabeçalho → já tratado por `sanitize`/`RunClient` |

## 2. Arquitetura

```
usuário ("olha pra tela..." ou --see "...")
   │
   ▼
vision.capture()  →  PNG (ffmpeg gdigrab no Windows)
   │
   ▼
vision.see(prompt, png)  →  opencode run -m <vision_model> -f <png>
   │
   ▼
resposta (sanitizada → TTS / texto)
```

## 3. Componentes e interfaces

NEW `voice/vision.py`:
- `capture(out_path: str | None = None, config=None) -> str` — roda o ffmpeg (gdigrab) e retorna o **caminho WSL** do PNG.
- `see(prompt: str, png_path: str, config=None) -> str` — chama `opencode run --pure <prompt> -m <VISION_MODEL> -f <png>` (mensagem antes de `-f`), limpa a saída e retorna o texto; erros → `AgentError`/`VoiceError`.

`voice/config.py`: novos campos
- `vision_model` (env `VISION_MODEL`, default `opencode-go/deepseek-v4-flash-vision-exp`)
- `vision_trigger` (env `VISION_TRIGGER`, default `olha`)
- `vision_png` (env `VISION_PNG`, default `C:\Users\bguil\tools\shot.png`; converter p/ WSL)

`voice/loop.py`:
- `main()` ganha `--see "pergunta"` (one-shot: captura + vê + imprime/fala).
- `voice_loop`: se o transcript **começa** com a `vision_trigger` (ex.: "olha"), remove o gatilho e usa o restante como pergunta de visão (captura + `see`), em vez do agente normal.
- Loga o turno de visão em `convlog` (prompt+resposta; **não** a imagem).

## 4. Reuso/sanitização
- O caminho de arquivo WSL↔Windows reutiliza o helper existente (`_to_windows_path` invertido em `vision`).
- A resposta da visão passa por `sanitize.speechify` antes do TTS (igual aos outros turnos).

## 5. Tratamento de erro
| Situação | Comportamento |
|---|---|
| ffmpeg falha / sem tela | `VoiceError` claro; o loop segue |
| modelo de visão indisponível | `AgentError`; informa |
| prompt de visão vazio | usa um default ("Descreva o que está na tela") |

## 6. Testes
- `capture`: monkeypatch `subprocess.run`; assert argv `gdigrab` + conversão de caminho.
- `see`: monkeypatch `subprocess.run`; assert ordem (prompt antes de `-f`), `-m <vision_model>`, `-f <png>`.
- `loop --see`: monkeypatch `capture`/`see`; assert chamados; saída fala o sanitizado.
- gatilho de voz: transcript começando com `olha` → caminho de visão; caso negativo → agente normal.

## 7. Não-objetivos
- Automação de cliques (é a Fase E).
- Captura contínua / streaming de tela.
- Janela ativa/região específica (v1 = tela toda; evolução depois).

## 8. Riscos
| Risco | Mitigação |
|---|---|
| Privacidade (print pode ter segredos) | acionamento **explícito**; a imagem **não** é logada |
| Latência (startup do `run`) | aceitável no uso ocasional; otimizar via `serve` depois |
| `-f` engolir a mensagem | mensagem **antes** de `-f` (fixado em teste) |

## 9. Critério de sucesso
`python loop.py --see "o que tem na tela?"` captura, consulta o modelo de visão e retorna/pronuncia uma descrição correta; e na voz, uma frase começando com o gatilho faz o mesmo.

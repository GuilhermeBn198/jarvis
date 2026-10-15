# Diagnóstico e limitações conhecidas

Como diagnosticar falhas e conviver com as limitações conhecidas das tools do Windows (`act_*`, `win_*`, visão) e do loop de voz. Cada limitação segue o mesmo formato: **sintoma · repro · causa · workaround · issue**.

> Doc vivo: atualizado conforme as correções entram. Status das issues desta onda no fim do documento.

---

## Como diagnosticar

1. **Log do cérebro (`brain.log`)** — quando o loop roda pelo overlay, stdout/stderr vão para `%LOCALAPPDATA%\jarvis\brain.log`. É o primeiro lugar para `[erro] ...`, `[voz] nada transcrito` e, com `JARVIS_HEARTBEAT=true`, `[hb]`/`[watchdog]`.
2. **Canais diretos** (WSL, sem overlay):
   - `./jarvis --voice --once 1` — um turno completo (captura → STT → agente → TTS) com o log no terminal;
   - `./jarvis --see-text "descreva a tela"` — visão isolada (captura + modelo), mesma da tool `see_screen`;
   - `./jarvis --list-mics` — microfones vistos pelo `dshow` (o ativo leva `*`);
   - `./jarvis --mic-level` — ruído de fundo e sugestão de `VOICE_NOISE_DB`.
3. **Texto antes de imagem**: peça `win_list`/`win_list_text` e `win_tree_text` antes de recorrer a `see_screen` — é mais barato e legível.
4. **Resposta da própria tool**: `act_*` devolvem status explícito (`confirmed`, `unconfirmed`, `ambiguous`, `erro`); a mensagem costuma indicar a ação seguinte.
5. **Plugins/tools do opencode**: `opencode run --print-logs "responda apenas: ok"` mostra falha de carregamento de plugin.
6. **`act_type` com `JARVIS_ACT_DEBUG=1`** — log opt-in em stderr com os **argumentos brutos** recebidos pela tool (antes de montar o script), para decidir se um `\` perdido chegou até o `execute` ou se a perda é a montante ([#20](https://github.com/GuilhermeBn198/jarvis/issues/20)). O log **pode conter o texto digitado** — ligue só durante a coleta e revise antes de compartilhar. A env é lida pelo processo que hospeda as tools: o serve do opencode é reutilizado, então **encerre-o e relance** depois de ligar a env (ex.: `JARVIS_ACT_DEBUG=1` no `local.conf` + `./jarvis`).

### Checklist de coleta (para reportar)

- Versão: `git rev-parse --short HEAD` (e a branch, se não for `main`).
- Ambiente: distro do WSL e versão/build do Windows; app/janela alvo (ex.: Bloco de Notas, Windows Terminal) e modo usado (`foreground`/`background`, `window`/`hwnd`).
- Saída exata da tool/CLI e o trecho correspondente do `brain.log`.
- Passos mínimos para reproduzir (comando/tool + argumentos).

---

## Template de limitação

> **Sintoma** — o que se observa.
> **Repro** — passos ou chamada mínima.
> **Causa** — por que acontece (quando conhecida).
> **Workaround** — o que fazer agora.
> **Issue** — link e status.

---

## Tools `act_*`

### Windows Terminal (e afins) ignora entrada em segundo plano — esperado

- **Sintoma**: `act_type` com `window`/`hwnd` do Terminal responde `unconfirmed|sem controle de edicao (WM_CHAR no topo)`; nenhum texto aparece. O Jarvis então pede confirmação antes de trazer a janela para frente.
- **Repro**: `act_type { window: "Terminal", text: "echo oi" }` (ou o `hwnd` obtido com `win_list`).
- **Causa**: o Terminal é `CASCADIA_HOSTING_WINDOW_CLASS`, sem controle Edit/Document exposto à UIA, e o input real entra pelo ConPTY — `WM_CHAR`/`WM_KEYDOWN` postados são ignorados. É comportamento do app, não bug do Jarvis.
- **Workaround**: repetir com `mode="foreground"` (sem `window`/`hwnd`); a janela recebe o foco e a digitação é real.
- **Issue**: [#28](https://github.com/GuilhermeBn198/jarvis/issues/28) (mensagens por causa) — aberta.

### Bloco de Notas: background funciona; sessão restaurada e latência alta

- **Sintoma**: (a) ao abrir o Notepad aparece o conteúdo da sessão anterior — parece que o Jarvis "achou" texto antigo; (b) a chamada `act_type` em background demora ~11s.
- **Repro**: `act_type { window: "Notepad", text: "linha de teste" }` — no recon retornou `confirmed|digitado`, com o foco intacto.
- **Causa**: (a) o Notepad moderno (Win11) restaura a sessão anterior ao abrir; (b) o custo é o startup do PowerShell + bootstrap da UIA (o job de verificação em si roda em ~0,6s).
- **Workaround**: aguarde o retorno da chamada (demora não significa falha; não repita às cegas); `append=true` concatena em vez de substituir.
- **Issue**: [#28](https://github.com/GuilhermeBn198/jarvis/issues/28) — aberta.

### `act_key` em background: sintaxe própria e hotkeys do sistema

- **Sintoma**: teclas enviadas em background às vezes não têm efeito; `Win+R` não abre o Executar; combinações como `ctrl+v` não funcionam como no caminho em foco.
- **Repro**: `act_key { window: "Notepad", keys: "^v" }` (equivalente a Ctrl+V em background) vs. `act_key { window: ..., keys: "win+r" }` (sem efeito).
- **Causa**: o background posta `WM_KEYDOWN`/`WM_KEYUP` com um parser estilo SendKeys (`^` Ctrl, `%` Alt, `+` Shift, `{ENTER}`/`{TAB}`/...); hotkeys globais (`Win+R`, `Alt+Tab`) são resolvidas pelo sistema e não chegam por `PostMessage`. A verificação de efeito é indisponível: a tool só reporta "teclas enviadas em segundo plano".
- **Workaround**: use a sintaxe SendKeys (`^v`, `{ENTER}`) nos apps que aceitam background; para hotkeys do sistema ou combos, use `mode="foreground"`.
- **Issue**: [#19](https://github.com/GuilhermeBn198/jarvis/issues/19) — aberta.

### `act_click` só em foreground

- **Sintoma**: `act_click` não aceita `window`/`hwnd` e clica na coordenada da tela, não num controle.
- **Repro**: `act_click { x: 100, y: 200 }` — vale para a posição física; não há como mirar numa janela específica.
- **Causa**: o clique move o cursor físico (coordenada absoluta de tela), então exige o alvo visível no ponto — não há caminho em background.
- **Workaround**: garanta que o alvo esteja visível e clique por coordenadas; prefira atalhos (`act_key`) quando possível.
- **Issue**: — (limitação de v1).

### `act_open` de execução exige consentimento

- **Sintoma**: pedir para abrir terminal/interpretador/script (ex.: `act_open { target: "cmd", args: ["/c", "dir"] }`) responde `recusado: ... exige confirm=true`.
- **Repro**: `act_open { target: "cmd" }` (ou `powershell`, `wsl`, `wt`, `mshta`, `rundll32`, `.bat`, `.ps1`, `.vbs`, `.js`, ...) sem `confirm`.
- **Causa**: política da #23 — alvos que abrem caminho de execução exigem consentimento explícito; o `confirm=true` só deve ser usado depois do "sim" do usuário. Não é defeito.
- **Workaround**: confirme com o usuário e repita com `confirm=true`; padrões destrutivos/credenciais continuam bloqueados mesmo com confirm (SafetyGate sobre target + args).
- **Issue**: [#23](https://github.com/GuilhermeBn198/jarvis/issues/23) — corrigido nesta branch.

### Latência das tools `act_*`: cada chamada sobe um PowerShell

- **Sintoma**: uma ação simples (digitar/teclas) leva segundos; no recon, ~11s até o retorno.
- **Repro**: qualquer `act_type` em background — o tempo é dominado pelo startup do PowerShell, não pela ação.
- **Causa**: cada chamada é um `powershell.exe` novo (interop WSL→Windows) — o startup domina; o trabalho em si é subsegundo.
- **Workaround**: aguarde o retorno antes de repetir; prefira um único `act_type` a uma sequência de chamadas.

---

## Arquivos do Windows (`winfs`)

### `win_read`: só caminhos do Windows (e sem listagem de diretórios)

- **Sintoma**: ler um caminho do WSL (ex.: `/home/<voce>/...`) responde "apenas caminhos do Windows (/mnt/<drive>/...) sao aceitos"; passar um diretório devolve erro cru (exit 1).
- **Repro**: `win_read { path: "/etc/hostname" }`.
- **Causa**: a versão atual roteia tudo para o PowerShell com guard `/mnt/`; leitura WSL e listagem estão na issue.
- **Workaround**: use `/mnt/c/...` para arquivos do Windows; para arquivos do WSL, leia pelo próprio terminal/agente no WSL.
- **Issue**: [#24](https://github.com/GuilhermeBn198/jarvis/issues/24) — aberta.

### `win_write`: exige allowlist + `confirm=true`

- **Sintoma**: `win_write` responde `recusado: JARVIS_WIN_ALLOW_WRITE vazio (nenhum diretorio autorizado)` mesmo com `confirm=true`; ou `fora da allowlist`.
- **Repro**: `win_write { path: "/mnt/c/Users/<voce>/notas.txt", content: "x", confirm: true }` sem allowlist configurada.
- **Causa**: por padrão nada é autorizado (allowlist vazia) e a escrita também exige `confirm=true` (escopo explícito e auditável).
- **Configuração/workaround**: aponte `JARVIS_WIN_ALLOW_WRITE` para uma **pasta de trabalho** (nunca o drive inteiro), em formato Windows (`C:\Users\<voce>\Notas`) ou WSL (`/mnt/c/Users/<voce>/Notas`); separe múltiplos diretórios com `;`/`:` **seguidos de espaço** (o parser atual não separa quando o próximo caminho começa com `/` — ex.: dois caminhos WSL colados; correção prevista na [#22](https://github.com/GuilhermeBn198/jarvis/issues/22)). O diretório precisa existir.
  - O plugin lê a env do processo que roda o opencode. Na prática: `local.conf` na raiz do repo (gitignored) é carregado pelo launcher `./jarvis` com `set -a` e herdado pelo loop → opencode.
  - **Trocar a env exige reiniciar o cérebro** (o plugin lê no startup do opencode).
- **Issue**: [#22](https://github.com/GuilhermeBn198/jarvis/issues/22) (documentar + corrigir o parser) — aberta.

### Caminhos do Windows hardcoded nos defaults

- **Sintoma**: em outra máquina, captura, TTS ou visão falham ao encontrar os binários/arquivos dos defaults (`ffmpeg`, `piper`, `shot.png` etc.).
- **Repro**: rodar `./jarvis --voice --once 1` (ou `--see-text`) numa instalação onde `ffmpeg`/`piper` estão fora de `$JARVIS_WIN_HOME/tools/...`, sem apontar env.
- **Causa**: os defaults são caminhos do Windows derivados de `$JARVIS_WIN_HOME/tools/...` (`voice/config.py`), e o default do `JARVIS_WIN_HOME` é neutro (`/mnt/c/Users/Public`) — não reflete o perfil da sua máquina.
- **Workaround**: aponte `JARVIS_WIN_HOME` para `/mnt/c/Users/<voce>` (via `local.conf`) e/ou sobrescreva cada caminho por env: `FFMPEG_EXE`, `FFPLAY_EXE`, `PIPER_EXE`, `PIPER_MODEL`, `PIPER_OUT_WAV`, `VISION_PNG` (tabela no [README](../README.md)).
- **Issue**: — (limitação de configuração; ajuste por env).

---

## Contexto do Windows (`win_*` / MCP `win_context`)

### Tools de contexto ainda não liberadas no `chat`

- **Sintoma**: o agente `chat` não vê `win_list_text`/`win_tree_text`/`win_clipboard_text`/`win_processes_text`.
- **Causa**: a config do `chat` nega tudo (`"*": "deny"`) e só habilita `act_*`/`win_list`/`win_read`/`win_write`/`see_screen`; a liberação das tools do MCP está na issue.
- **Workaround**: use `win_list` (já liberada no chat) e `see_screen` como fallback; a leitura de contexto estruturado chega na issue.
- **Issue**: [#25](https://github.com/GuilhermeBn198/jarvis/issues/25) — aberta.

### UIA vazia em apps Electron

- **Sintoma**: `win_tree_text` devolve árvore vazia ou pobre em apps Electron (ex.: VS Code).
- **Repro**: `win_list_text` para achar o `hwnd` do VS Code e `win_tree_text(hwnd)` → resultado vazio.
- **Causa**: esses apps não expõem a árvore de acessibilidade ao UIA por padrão.
- **Workaround**: use `see_screen` como fallback (captura + modelo de visão).
- **Issue**: — (limitação dos apps; documentado).

### Timeout da UIA (~5s)

- **Sintoma**: `act_type` em background devolve `unconfirmed|UIA timeout (janela nao respondeu em 5s)`.
- **Repro**: `act_type { window: "<app>", text: "x" }` com um diálogo modal aberto na janela alvo.
- **Causa**: a busca UIA roda com timeout de ~5s para não travar o loop quando a janela está ocupada (modal, diálogo, travada).
- **Workaround**: feche diálogos modais; tente novamente; se persistir, use `foreground`.
- **Issue**: [#8](https://github.com/GuilhermeBn198/jarvis/issues/8) (fechada — timeout implementado).

---

## Visão (`see_screen`)

### Prefira texto (`win_context`) a imagem (`see_screen`)

- **Sintoma**: `see_screen` custa segundos (captura + modelo multimodal) e mais tokens; para "o que está aberto?" o texto resolve.
- **Causa**: a visão captura a tela e consulta um modelo; o MCP `win_context` devolve a UIA em texto puro.
- **Workaround**: peça `win_list`/`win_tree_text` quando a UIA expõe o conteúdo; use `see_screen` para Electron/jogos/canvas (onde a UIA é vazia).
- **Issue**: [#6](https://github.com/GuilhermeBn198/jarvis/issues/6) (fechada — MCP em produção).

### Visão: modelo válido e erro com causa real

- **Sintoma**: `see_screen` falhava com exit code 1 sem causa útil.
- **Causa**: o modelo de visão configurado não existia mais.
- **Status**: corrigido na [#21](https://github.com/GuilhermeBn198/jarvis/issues/21) — modelo válido (`VISION_MODEL`, default `opencode-go/deepseek-v4.1-flash`) e erro apontando a etapa/causa real.

---

## Áudio e loop

- **Onde ver o erro**: `%LOCALAPPDATA%\jarvis\brain.log` (com overlay) ou o próprio terminal (`./jarvis --voice`).
- **Nada transcrito / sensibilidade**: calibre com `./jarvis --list-mics` e `./jarvis --mic-level`; `media` perto de −90 dB indica mic mudo/sem ganho (troque de device ou ajuste no Windows). Tunables (`VOICE_NOISE_DB`, `VOICE_INPUT`, etc.) no [README](../README.md).
- **Mic "preso" em outros apps** ([#4](https://github.com/GuilhermeBn198/jarvis/issues/4), mitigado): a captura `dshow` pode segurar o dispositivo; use `JARVIS_REQUIRE_GUI=1` (anti-órfão), a trava de instância (`JARVIS_VOICE_LOCK`) e, no Windows, desmarque "Permitir que os aplicativos tenham controle exclusivo".
- **Loop órfão**: se o overlay sumir e o loop continuar, `pkill -f loop.py` no WSL; com `JARVIS_REQUIRE_GUI=1` ele encerra em ~15s sozinho.
- **Sem barge-in**: não dá para interromper a fala do Jarvis falando por cima ([#40](https://github.com/GuilhermeBn198/jarvis/issues/40)).
- **Log de turnos**: `VOICE_LOG` (`~/.local/share/jarvis/voice-log.jsonl`) guarda timings (`first_audio_s`, `stream`) para investigar latência.

---

## Como reportar

1. Reproduza no canal mais direto (item 2 de "Como diagnosticar").
2. Cole a saída exata, o trecho do log e os passos mínimos — use o template acima.
3. Informe a versão (`git rev-parse --short HEAD`), WSL/Windows e a janela/app afetados.
4. Abra a issue em [GuilhermeBn198/jarvis/issues](https://github.com/GuilhermeBn198/jarvis/issues); se já existir uma issue do sintoma, comente nela.
5. **Não cole segredos nem caminhos pessoais** — censure `C:\Users\<voce>` e remova tokens/chaves (veja [`SECURITY.md`](../SECURITY.md)).

---

## Status desta onda (2026-10-14)

| Issue | Tema | Status |
|---|---|---|
| [#21](https://github.com/GuilhermeBn198/jarvis/issues/21) | `see_screen` (modelo + erro real) | **corrigido** (na `main`) |
| [#29](https://github.com/GuilhermeBn198/jarvis/issues/29) | CI roda os testes em todo PR | **corrigido** (na `main`) |
| [#19](https://github.com/GuilhermeBn198/jarvis/issues/19) | `act_key` envia teclas de verdade | aberta |
| [#20](https://github.com/GuilhermeBn198/jarvis/issues/20) | `act_type` preserva barras invertidas | aberta (diagnóstico: `JARVIS_ACT_DEBUG=1`) |
| [#22](https://github.com/GuilhermeBn198/jarvis/issues/22) | allowlist de escrita documentada (+ parser) | aberta |
| [#23](https://github.com/GuilhermeBn198/jarvis/issues/23) | `act_open` com argumentos | **corrigido** (nesta branch) |
| [#24](https://github.com/GuilhermeBn198/jarvis/issues/24) | `win_read` lê WSL e lista diretórios | aberta |
| [#25](https://github.com/GuilhermeBn198/jarvis/issues/25) | clipboard/contexto Windows no `chat` | aberta |
| [#28](https://github.com/GuilhermeBn198/jarvis/issues/28) | mensagens de background por causa | aberta |

import { type Plugin, tool } from "@opencode-ai/plugin";

import { buildPsScript, encode, toArgList } from "../act/ps.ts";
import { buildWinListScript, chooseActScript, parseActResult } from "../act/win.ts";
import { isExecutionTarget } from "../safety/rules.ts";

// ATENCAO: o loader do opencode invoca toda funcao exportada como factory de
// plugin. Este arquivo exporta APENAS `ActTools`; os helpers puros ficam em
// `../act/ps.ts` e `../act/win.ts`.

// Diagnostico opt-in da #20 (perda de barras invertidas): com
// JARVIS_ACT_DEBUG=1, loga em stderr os argumentos BRUTOS que chegaram ao
// execute, ANTES de montar o script — e o suficiente para decidir se o `\`
// chegou ate aqui ou se a perda e a montante. PODE CONTER O TEXTO DIGITADO:
// ligue so durante a coleta do repro e desligue depois (default: nada e logado).
function debugRawTypeArgs(args: unknown): void {
  if (process.env.JARVIS_ACT_DEBUG !== "1") return;
  const record = (args ?? {}) as Record<string, unknown>;
  const barras = (String(record.text ?? "").match(/\\/g) ?? []).length;
  process.stderr.write(
    `[act_type] JARVIS_ACT_DEBUG args brutos (barras invertidas no texto: ${barras}): ${JSON.stringify(args)}\n`,
  );
}

export const ActTools: Plugin = async ({ $ }) => ({
  tool: {
    act_type: tool({
      description: "Digita um texto. Padrao: janela em foco (foreground). Com window/hwnd ou mode=background: injeta na janela-alvo sem roubar foco. append=true concatena ao conteudo atual (default substitui).",
      args: {
        text: tool.schema.string(),
        mode: tool.schema.string().optional(),
        window: tool.schema.string().optional(),
        hwnd: tool.schema.number().optional(),
        append: tool.schema.boolean().optional(),
      },
      async execute(args) {
        debugRawTypeArgs(args);
        const bg = chooseActScript("act_type", args);
        if (!bg) {
          return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_type", args))}`).text();
        }
        const out = (await $`powershell.exe -NoProfile -EncodedCommand ${encode(bg)}`).text();
        const r = parseActResult(out);
        if (r.status === "unconfirmed") {
          return `${r.detail} — a janela nao aceita entrada em segundo plano. Focalize a janela-alvo e repita com mode="foreground" (sem window).`;
        }
        if (r.status === "ambiguous") return `multiplas janelas: ${r.detail}. Escolha um hwnd em win_list.`;
        return `${r.status}: ${r.detail}`;
      },
    }),
    act_key: tool({
      description:
        "Envia teclas/atalho em sintaxe natural (case-insensitive). " +
        "Teclas: enter esc tab backspace delete space up down left right home end pgup pgdn f1..f24, letras/digitos, plus. " +
        "Combos: ctrl+/alt+/shift+/win+ (ex.: ctrl+c, ctrl+shift+esc, alt+f4). " +
        "Acordes separados por espaco ou virgula (ex.: \"ctrl+s , enter\"). " +
        "Padrao: janela em foco (foreground). Com window/hwnd ou mode=background: envia a janela-alvo sem roubar foco. " +
        "Limites do background: win+r nao funciona (hotkey do sistema, nunca chega via PostMessage); " +
        "combos com ctrl/alt sao best-effort (apps que consultam GetKeyState podem ignora-los).",
      args: {
        keys: tool.schema.string(),
        mode: tool.schema.string().optional(),
        window: tool.schema.string().optional(),
        hwnd: tool.schema.number().optional(),
      },
      async execute(args) {
        try {
          const bg = chooseActScript("act_key", args);
          if (!bg) {
            return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_key", args))}`).text();
          }
          const out = (await $`powershell.exe -NoProfile -EncodedCommand ${encode(bg)}`).text();
          const r = parseActResult(out);
          if (r.status === "ambiguous") return `multiplas janelas: ${r.detail}. Escolha um hwnd em win_list.`;
          if (r.status === "error") return `erro: ${r.detail}`;
          // Timeout nao e sucesso: as teclas podem nunca ter sido postadas.
          if (/timeout/i.test(r.detail)) {
            return `timeout: a janela nao respondeu em 5s — as teclas podem nao ter sido enviadas (confirme o estado da janela antes de repetir)`;
          }
          return `teclas enviadas em segundo plano (confirmacao indisponivel) — ${r.detail}`;
        } catch (err) {
          // Sintaxe invalida falha no parser, antes de qualquer script rodar.
          return `erro: ${err instanceof Error ? err.message : String(err)}`;
        }
      },
    }),
    act_open: tool({
      description:
        "Abre uma URL, arquivo ou aplicativo (Start-Process). args (opcional) sao repassados ao alvo com quoting Windows. " +
        "Alvos de execucao — terminais/interpretadores/scripts (cmd, powershell, pwsh, wsl, wt, wscript, cscript, mshta, rundll32, regsvr32, .bat/.cmd/.ps1/.vbs/.js) — " +
        "exigem confirm=true: sem ele a tool recusa — PERGUNTE ao usuario (\"quer que eu abra X para executar Y?\") antes de repetir com confirm=true.",
      args: {
        target: tool.schema.string(),
        args: tool.schema.array(tool.schema.string()).optional(),
        confirm: tool.schema.boolean().optional(),
      },
      async execute(args) {
        const target = String(args.target ?? "");
        if (isExecutionTarget(target) && args.confirm !== true) {
          const argv = toArgList(args.args);
          const extra = argv.length > 0 ? ` com os argumentos [${argv.join(", ")}]` : "";
          return `recusado: "${target}" abre caminho de execucao${extra} e exige confirm=true — PERGUNTE ao usuario antes ("quer que eu abra ${target} para executar?") e repita com confirm=true somente apos o ok`;
        }
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_open", args))}`).text();
      },
    }),
    act_click: tool({
      description: "Move o mouse para (x,y) e clica (left/right).",
      args: { x: tool.schema.number(), y: tool.schema.number(), button: tool.schema.string().optional() },
      async execute(args) {
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_click", args))}`).text();
      },
    }),
    win_list: tool({
      description: "Lista janelas abertas do Windows (hwnd, titulo, processo). Use para descobrir o alvo antes de agir em segundo plano.",
      args: {},
      async execute() {
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildWinListScript())}`).text();
      },
    }),
  },
});

import { type Plugin, tool } from "@opencode-ai/plugin";

import { buildPsScript, encode } from "../act/ps.ts";
import { buildWinListScript, chooseActScript, parseActResult } from "../act/win.ts";

// ATENCAO: o loader do opencode invoca toda funcao exportada como factory de
// plugin. Este arquivo exporta APENAS `ActTools`; os helpers puros ficam em
// `../act/ps.ts` e `../act/win.ts`.
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
      description: "Envia teclas/atalho. Padrao: janela em foco. Com window/hwnd ou mode=background: envia a janela-alvo sem roubar foco.",
      args: {
        keys: tool.schema.string(),
        mode: tool.schema.string().optional(),
        window: tool.schema.string().optional(),
        hwnd: tool.schema.number().optional(),
      },
      async execute(args) {
        const bg = chooseActScript("act_key", args);
        if (!bg) {
          return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_key", args))}`).text();
        }
        const out = (await $`powershell.exe -NoProfile -EncodedCommand ${encode(bg)}`).text();
        const r = parseActResult(out);
        if (r.status === "ambiguous") return `multiplas janelas: ${r.detail}. Escolha um hwnd em win_list.`;
        if (r.status === "error") return `erro: ${r.detail}`;
        return "teclas enviadas em segundo plano (confirmacao indisponivel)";
      },
    }),
    act_open: tool({
      description: "Abre uma URL, arquivo ou aplicativo (Start-Process).",
      args: { target: tool.schema.string() },
      async execute(args) {
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

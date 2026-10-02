import { type Plugin, tool } from "@opencode-ai/plugin";

import { buildPsScript, encode } from "../act/ps.ts";
import { buildWinListScript } from "../act/win.ts";

// ATENCAO: o loader do opencode invoca toda funcao exportada como factory de
// plugin. Este arquivo exporta APENAS `ActTools`; os helpers ficam em
// `../act/ps.ts`.
export const ActTools: Plugin = async ({ $ }) => ({
  tool: {
    act_type: tool({
      description: "Digita um texto na janela em foco (Windows).",
      args: { text: tool.schema.string() },
      async execute(args) {
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_type", args))}`).text();
      },
    }),
    act_key: tool({
      description: "Envia teclas/atalho via SendKeys (ex.: ^c, %{F4}, {ENTER}).",
      args: { keys: tool.schema.string() },
      async execute(args) {
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildPsScript("act_key", args))}`).text();
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

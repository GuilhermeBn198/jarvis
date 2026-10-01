import { type Plugin, tool } from "@opencode-ai/plugin";

// Tool de visao do agente `chat`: tira um print da tela (Windows) e devolve a
// descricao via o modelo de visao. Delega pro CLI `./jarvis --see-text`, que ja
// encapsula captura + modelo (agente TOOL-LESS `vision`).
//
// ATENCAO: o loader do opencode invoca toda funcao exportada como factory de
// plugin. Este arquivo exporta APENAS `SeeTools`.
export const SeeTools: Plugin = async ({ $ }) => ({
  tool: {
    see_screen: tool({
      description:
        "Tira um print da tela do usuario e retorna a descricao do que aparece (modelo de visao). Use quando pedirem para 'olhar a tela' ou algo visual.",
      args: { prompt: tool.schema.string().optional() },
      async execute(args) {
        const q =
          (args.prompt ?? "").trim() || "Descreva o que esta na tela.";
        return (await $`/home/guilherme/github/jarvis/jarvis --see-text ${q}`).text();
      },
    }),
  },
});

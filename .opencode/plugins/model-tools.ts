import { type Plugin, tool } from "@opencode-ai/plugin";

// Exposes only the local Jarvis model-selection endpoint; no arbitrary settings
// or provider configuration can be written through this tool.
export const ModelTools: Plugin = async () => ({
  tool: {
    select_jarvis_model: tool({
      description:
        "Troca o modelo principal do Jarvis somente quando o usuário pedir explicitamente para trocar ou configurar o modelo. Aceita uma tag exata do catálogo Ollama. A seleção vale para a próxima solicitação; modelos cloud podem receber transcrições, prompts e contexto de tela.",
      args: { model: tool.schema.string() },
      async execute(args) {
        const port = process.env.JARVIS_STATE_PORT ?? "8765";
        const response = await fetch(`http://127.0.0.1:${port}/model`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Origin: "tauri://localhost",
          },
          body: JSON.stringify({ model: args.model.startsWith("ollama/") ? args.model : `ollama/${args.model}` }),
        });
        const result = await response.json() as { selected?: string; cloud?: boolean; error?: string };
        if (!response.ok) return `Não foi possível trocar o modelo: ${result.error ?? response.statusText}`;
        return `Modelo selecionado para a próxima solicitação: ${result.selected}${result.cloud ? ". Atenção: o modelo é cloud e pode receber transcrição, prompt e contexto de tela enviados pelo Jarvis." : ". Modelo local."}`;
      },
    }),
  },
});

import type { Plugin } from "@opencode-ai/plugin";
import { askHook, beforeToolCall } from "../safety/hook.ts";

export const SafetyGate: Plugin = async ({ client }) => ({
  // `permission.ask` é declarado nos tipos, mas não é despachado no runtime
  // 1.17.18. Mantido para forward-compat.
  "permission.ask": (input, output) =>
    askHook(input, output, (message) => {
      if (client?.app?.log) {
        void client.app.log({ body: { service: "safety-gate", level: "error", message } });
      } else {
        console.error(message);
      }
    }),
  // Gate efetivo: bloqueia (throw) quando a regra decide deny.
  "tool.execute.before": async (input, output) => {
    beforeToolCall(input.tool, output.args);
  },
});

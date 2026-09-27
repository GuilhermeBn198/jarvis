import type { Plugin } from "@opencode-ai/plugin";
import { askHook } from "../safety/hook.ts";

export const SafetyGate: Plugin = async ({ client }) => ({
  "permission.ask": (input, output) =>
    askHook(input, output, (message) => {
      if (client?.app?.log) {
        void client.app.log({ body: { service: "safety-gate", level: "error", message } });
      } else {
        console.error(message);
      }
    }),
});

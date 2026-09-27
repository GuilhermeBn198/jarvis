import type { Plugin } from "@opencode-ai/plugin";
import { askHook } from "../safety/hook.ts";

export const SafetyGate: Plugin = async () => ({
  "permission.ask": askHook,
});

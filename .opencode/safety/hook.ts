import { decide } from "./rules.ts";

export type Logger = (message: string) => void;

export async function askHook(
  input: { type: string; pattern?: string | string[]; title?: string; metadata?: unknown },
  output: { status: "allow" | "ask" | "deny" },
  log?: Logger,
): Promise<void> {
  try {
    output.status = decide(input).status;
  } catch (err) {
    if (output) output.status = "ask";
    const message = `fail-safe: erro no SafetyGate, aplicando ask — ${String(err)}`;
    if (log) log(message);
    else console.error(message);
  }
}

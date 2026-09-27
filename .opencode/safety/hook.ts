import { decide } from "./rules.ts";

export async function askHook(
  input: { type: string; pattern?: string | string[]; title?: string; metadata?: unknown },
  output: { status: "allow" | "ask" | "deny" },
): Promise<void> {
  try {
    output.status = decide(input).status;
  } catch {
    output.status = "ask";
  }
}

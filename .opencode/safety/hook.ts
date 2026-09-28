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

// Mapeia uma chamada de tool do opencode para o shape ActionInput do motor.
// `bash` traz o comando em `command`; read/write/edit trazem o caminho em
// `filePath` (ou `path`). Tools sem padrão relevante ficam só com o tipo.
export function actionFromToolCall(
  tool: string,
  args: unknown,
): { type: string; pattern?: string } {
  const a = (args ?? {}) as Record<string, unknown>;
  if (tool === "bash") {
    return { type: "bash", pattern: typeof a.command === "string" ? a.command : undefined };
  }
  if (tool === "read" || tool === "write" || tool === "edit") {
    const p = a.filePath ?? a.path;
    return { type: tool, pattern: typeof p === "string" ? p : undefined };
  }
  if (tool === "act_type") return { type: "act", pattern: String(a.text ?? "") };
  if (tool === "act_key") return { type: "act", pattern: String(a.keys ?? "") };
  if (tool === "act_open") return { type: "act", pattern: String(a.target ?? "") };
  if (tool === "act_click") return { type: "act", pattern: `${a.x},${a.y}` };
  return { type: tool };
}

// Gancho `tool.execute.before`: bloqueia (throw) quando o motor decide deny.
// O runtime despacha este hook de fato (ao contrário de `permission.ask` em
// 1.17.18). Para tools comuns, `ask` NÃO é bloqueado aqui — a camada de
// permissões do opencode continua responsável por pedir confirmação.
//
// Exceção: tools `act_*` (action type === "act") NÃO têm prompt interativo. Uma
// tecla ou texto pode chegar a um terminal com foco, então `ask` também é
// bloqueado por segurança. `deny` vale para todos os tipos.
export function beforeToolCall(tool: string, args: unknown): void {
  const action = actionFromToolCall(tool, args);
  const d = decide(action);
  if (d.status === "deny") throw new Error(`SafetyGate bloqueou (${d.reason})`);
  if (action.type === "act" && d.status === "ask") {
    throw new Error(`SafetyGate bloqueou (act sem prompt: ${d.reason})`);
  }
}

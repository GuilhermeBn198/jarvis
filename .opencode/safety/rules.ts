export type DecisionStatus = "allow" | "ask" | "deny";
export type Decision = { status: DecisionStatus; reason: string };
export type ActionInput = {
  type: string;
  pattern?: string | string[];
  title?: string;
  metadata?: unknown;
};

const DENY: Array<[RegExp, string]> = [
  [/\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(\/|~|\$HOME)(?:\b|$)/, "remocao recursiva de raiz/home"],
  [/\bmkfs(\.\w+)?\b/, "formatacao de filesystem"],
  [/\bdd\b[^\n]*\bof=\/dev\//, "escrita em device de bloco"],
  [/:\s*\(\s*\)\s*\{.*\|.*&.*\}\s*;\s*:/, "fork bomb"],
  [/\b(shred|wipefs)\b/, "destruicao de dados"],
];

const ASK: Array<[RegExp, string]> = [
  [/\bsudo\b/, "privilegio elevado"],
  [/\bgit\s+push\b[^\n]*--force\b/, "push forcado"],
  [/\bgit\s+reset\s+--hard\b/, "reset destrutivo"],
  [/\bchmod\s+(-R\s+)?777\b/, "permissao ampla"],
  [/\bchown\s+-R\b/, "chown recursivo"],
  [/\b(curl|wget)\b[^\n]*\|\s*(sh|bash)\b/, "execucao de script remoto"],
  [/\brm\s+-[a-zA-Z]*r/, "remocao recursiva"],
];

const ALLOW_TYPES = new Set(["read", "glob", "grep", "list"]);
const ALLOW_CMD = [
  /^\s*git\s+(status|diff|log|show|branch|remote)\b/,
  /^\s*(ls|pwd|cat|head|tail|wc|echo|which|whoami)\b/,
];

export function decide(input: ActionInput): Decision {
  const patterns =
    input.pattern === undefined ? [] : Array.isArray(input.pattern) ? input.pattern : [input.pattern];
  const text = patterns.join("\n");

  for (const [re, reason] of DENY) if (re.test(text)) return { status: "deny", reason };
  for (const [re, reason] of ASK) if (re.test(text)) return { status: "ask", reason };

  if (ALLOW_TYPES.has(input.type)) return { status: "allow", reason: `tipo seguro: ${input.type}` };
  if (input.type === "bash" && ALLOW_CMD.some((re) => re.test(text))) {
    return { status: "allow", reason: "comando de leitura" };
  }
  return { status: "ask", reason: "desconhecido (conservador)" };
}

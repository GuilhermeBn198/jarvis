export type DecisionStatus = "allow" | "ask" | "deny";
export type Decision = { status: DecisionStatus; reason: string };
export type ActionInput = {
  type: string;
  pattern?: string | string[];
  title?: string;
  metadata?: unknown;
};

const DENY: Array<[RegExp, string]> = [
  [/\bmkfs(\.\w+)?\b/i, "formatacao de filesystem"],
  [/\bdd\b[^\n]*\bof\s*=\s*\/dev\//i, "escrita em device de bloco"],
  [/:\s*\(\s*\)\s*\{.*\|.*&.*\}\s*;\s*:/, "fork bomb"],
  [/\b(shred|wipefs)\b/i, "destruicao de dados"],
];

// Spec §3: ler/exfiltrar credenciais (~/.ssh, .env, ~/.aws, tokens) e DENY.
// Aplicado ao texto inteiro ANTES da allowlist de leitura (read/glob/...), pois
// o `pattern` de uma leitura traz o caminho.
const CREDENTIAL =
  /(^|[\/\s])(\.ssh|\.aws|\.gnupg|\.git-credentials|\.netrc|\.env(\.[\w-]+)?\b|id_rsa|id_ed25519|authorized_keys|known_hosts|credentials|\.npmrc|\.pypirc|shadow|sudoers)\b/i;

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
  /^\s*git\s+(status|diff|log|show)(\s|$)/,
  /^\s*(ls|pwd|cat|head|tail|wc|echo|which|whoami)(\s|$)/,
];
const UNSAFE_FOR_ALLOW = /[;&|><`$(){}\[\]*?\n\r]/;

function isDangerousRm(text: string): boolean {
  for (const line of text.split("\n")) {
    if (!/\brm\b/.test(line)) continue;
    const recursive = /(?:--recursive\b|-[a-z]*r[a-z]*\b)/i.test(line);
    const force = /(?:--force\b|-[a-z]*f[a-z]*\b)/i.test(line);
    // Qualquer alvo absoluto ou relativo ao home e "rootish". Consequencia
    // deliberada: `rm -rf /tmp` agora e deny (antes ask) — tradeoff safety-first.
    const rootish = /(?:^|\s)(?:\/|~|\$HOME|\$\{HOME\})(?:[^\s]*)(?:\s|$|[;&|])/.test(line);
    if (recursive && force && rootish) return true;
  }
  return false;
}

export function decide(input: ActionInput): Decision {
  const patterns =
    input.pattern === undefined ? [] : Array.isArray(input.pattern) ? input.pattern : [input.pattern];
  const text = patterns.join("\n");

  if (isDangerousRm(text)) return { status: "deny", reason: "rm recursivo+forcado de raiz/home" };
  if (CREDENTIAL.test(text)) return { status: "deny", reason: "acesso a credencial/segredo" };
  for (const [re, reason] of DENY) if (re.test(text)) return { status: "deny", reason };
  for (const [re, reason] of ASK) if (re.test(text)) return { status: "ask", reason };

  if (ALLOW_TYPES.has(input.type)) return { status: "allow", reason: `tipo seguro: ${input.type}` };
  if (
    input.type === "bash" &&
    !UNSAFE_FOR_ALLOW.test(text) &&
    !/(^|\s)-{1,2}o(utput)?\b/.test(text) &&
    ALLOW_CMD.some((re) => re.test(text))
  ) {
    return { status: "allow", reason: "comando de leitura" };
  }
  return { status: "ask", reason: "desconhecido (conservador)" };
}

// Helper puro de erro para os plugins do Jarvis (prefactor da #26).
// Erros de subprocesso hoje vazam crus ("exit code 1"); aqui extraimos a causa
// real (stderr/stdout/message), redigimos segredos e formatamos uma mensagem
// unica. NAO lanca: os plugins capturam o erro do shell e RETORNAM a string
// formatada (consistente com os status "erro: …"/"recusado: …" ja usados).
//
// Garantias:
// - nunca ecoa conteudo sensivel: padroes de token (sk-/ghp_/AKIA/Bearer) e o
//   blob de `-EncodedCommand` viram [REDACTADO];
// - `detail` e um resumo curto de comando/alvo (o chamador decide o conteudo);
// - o helper nao recebe nem ecoa conteudo de arquivo/clipboard.

export type ErrorContext = { tool: string; step: string; detail?: string; action?: string };

const LIMITE_CAUSA = 400;
const SUFIXO_TRUNCADO = " (truncado)";

// Padroes de credencial conhecidos. Ordem importa: Bearer antes de sk-/ghp_
// (um Bearer pode carregar qualquer token dentro).
const PADROES_SEGREDO: Array<[RegExp, string]> = [
  [/(-EncodedCommand)\s+\S+/gi, "$1 [REDACTADO]"],
  [/(\bBearer)\s+\S+/gi, "$1 [REDACTADO]"],
  [/\bsk-[A-Za-z0-9_-]{4,}/g, "[REDACTADO]"],
  [/\bghp_[A-Za-z0-9]{10,}/g, "[REDACTADO]"],
  [/\bAKIA[A-Z0-9]{16}/g, "[REDACTADO]"],
];

// Remove sequencias de escape ANSI (cores, cursor, etc.).
function stripAnsi(text: string): string {
  return text.replace(/\u001b\[[0-9;?]*[ -/]*[@-~]/g, "");
}

// Colapsa espacos/newlines em um espaco simples.
function collapse(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

// Troca padroes de token por [REDACTADO] (exportada para teste).
export function redact(text: string): string {
  let out = text;
  for (const [re, sub] of PADROES_SEGREDO) out = out.replace(re, sub);
  return out;
}

// Limita o tamanho com sufixo explicito (exportada para teste).
export function truncate(text: string, limit = LIMITE_CAUSA): string {
  if (text.length <= limit) return text;
  return text.slice(0, limit).trimEnd() + SUFIXO_TRUNCADO;
}

// Extrai a causa bruta: erros de shell ({exitCode, stderr, stdout}) tem
// prioridade; sem eles, cai para message / String(err).
function causaBruta(err: unknown): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const o = err as Record<string, unknown>;
    const stderr = typeof o.stderr === "string" ? o.stderr : "";
    const stdout = typeof o.stdout === "string" ? o.stdout : "";
    const exitCode = typeof o.exitCode === "number" ? o.exitCode : undefined;
    const corpo = stderr.trim() ? stderr : stdout;
    if (exitCode !== undefined || corpo.trim()) {
      if (!corpo.trim()) return `exit code ${exitCode}`;
      return exitCode !== undefined ? `exit code ${exitCode}: ${corpo}` : corpo;
    }
    if (typeof o.message === "string" && o.message.trim()) return o.message;
  }
  const s = String(err);
  return s === "" || s === "undefined" || s === "null" ? "erro desconhecido" : s;
}

// Causa pronta para exibir: sem ANSI, sem segredos, whitespace colapsado e
// truncada para nao dominar o contexto do modelo.
export function extractCause(err: unknown): string {
  const limpo = collapse(redact(stripAnsi(causaBruta(err))));
  return truncate(limpo || "erro desconhecido");
}

// Mensagem unica no formato:
//   erro em <tool> (etapa: <step>): <causa>
// com detalhe curto opcional no prefixo e acao sugerida opcional no fim.
export function formatToolError(ctx: ErrorContext, cause: unknown): string {
  const detalhe = ctx.detail ? `; ${redact(collapse(ctx.detail))}` : "";
  const acao = ctx.action ? ` — ${redact(collapse(ctx.action))}` : "";
  return `erro em ${ctx.tool} (etapa: ${ctx.step}${detalhe}): ${extractCause(cause)}${acao}`;
}

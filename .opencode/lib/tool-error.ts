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
  // biome-ignore lint/suspicious/noControlCharactersInRegex: ESC (0x1b) inicia os codigos ANSI que queremos remover.
  return text.replace(/\u001b\[[0-9;?]*[ -/]*[@-~]/g, "");
}

// stderr/stdout do ShellError do Bun vem como Buffer (Uint8Array), nao string:
// sem isto a causa cairia no message generico ("Failed with exit code: 1").
function comoTexto(v: unknown): string {
  if (typeof v === "string") return v;
  if (v instanceof Uint8Array) return new TextDecoder().decode(v);
  return "";
}

// Colapsa espacos/newlines em um espaco simples.
function collapse(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

// stderr do PowerShell 5.1 pode vir em CLIXML ("#< CLIXML <Objs...>"): markup
// XML + escapes _xHHHH_ escondem a mensagem real e fragmentos de progresso
// ("Preparando modulos para primeiro uso...") consomem o orcamento do
// truncamento. Extrai SO os fragmentos <S S="Error"> — concatenados, porque o
// PowerShell corta a mensagem no meio ("n" + "&#xE3;o") — desescapa _xHHHH_ e
// entidades, e sem fragmento de erro remove o preambulo.
const CLIXML_MARCADOR = "#< CLIXML";
const CLIXML_PREAMBULO = /#< CLIXML\r?\n?/;

function unescapeClixml(text: string): string {
  return text
    .replace(/_x([0-9A-Fa-f]{4})_/g, (_, hex: string) =>
      String.fromCharCode(Number.parseInt(hex, 16)),
    )
    .replace(/&#x([0-9A-Fa-f]+);/g, (_, hex: string) =>
      String.fromCharCode(Number.parseInt(hex, 16)),
    )
    .replace(/&#(\d+);/g, (_, dec: string) => String.fromCharCode(Number.parseInt(dec, 10)))
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

function decodeClixml(text: string): string {
  const inicio = text.indexOf(CLIXML_MARCADOR);
  if (inicio < 0) return text;
  // Preserva o que veio antes do CLIXML (ex.: "exit code 1: ").
  const prefixo = text.slice(0, inicio);
  const clixml = text.slice(inicio);
  const fragmentos = [...clixml.matchAll(/<S S="Error">([\s\S]*?)<\/S>/g)].map((m) => m[1]);
  if (fragmentos.length === 0) return prefixo + clixml.replace(CLIXML_PREAMBULO, "");
  return prefixo + unescapeClixml(fragmentos.join(""));
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
    const stderr = comoTexto(o.stderr);
    const stdout = comoTexto(o.stdout);
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

// Causa pronta para exibir: CLIXML decodificado, sem ANSI, sem segredos,
// whitespace colapsado e truncada para nao dominar o contexto do modelo.
// A decodificacao vem ANTES de redact/truncate: o markup pode esconder segredo
// e o corte nao pode cair no meio do CLIXML (perderia a mensagem real).
export function extractCause(err: unknown): string {
  const limpo = collapse(redact(stripAnsi(decodeClixml(causaBruta(err)))));
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

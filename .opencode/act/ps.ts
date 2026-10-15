// Helpers puros das tools act_*. Ficam fora do arquivo de plugin porque o
// loader do opencode invoca TODA funcao exportada por um plugin como factory;
// assim `.opencode/plugins/act-tools.ts` exporta apenas `ActTools`.

import { buildForegroundKeyScript } from "./keys.ts";

const SENDFLARE = /([+^%~(){}[\]])/g; // caracteres especiais do SendKeys

export function encode(script: string): string {
  return Buffer.from(script, "utf16le").toString("base64");
}

// Port fiel de subprocess.list2cmdline (CPython): regras de quoting da linha
// de comando do MS C runtime. Barras invertidas so dobram antes de aspas
// internas; aspas viram \" ; espaco/tab/vazio forcam o par de aspas; barra
// final dobra quando o arg e cotado. O recon validou saida identica ao Python
// para espacos, aspas, `\` final e `%`.
export function buildWindowsArgs(seq: readonly string[]): string {
  const out: string[] = [];
  for (const arg of seq) {
    let bs = 0; // barras pendentes (literal, ou dobra antes de aspa)
    if (out.length > 0) out.push(" ");
    const needquote = arg.includes(" ") || arg.includes("\t") || arg.length === 0;
    if (needquote) out.push('"');
    for (const c of arg) {
      if (c === "\\") bs += 1;
      else if (c === '"') {
        out.push("\\".repeat(bs * 2), '\\"');
        bs = 0;
      } else {
        if (bs > 0) {
          out.push("\\".repeat(bs));
          bs = 0;
        }
        out.push(c);
      }
    }
    if (bs > 0) out.push("\\".repeat(bs));
    if (needquote) {
      // Barra final antes da aspa de fechamento precisa do segundo par.
      if (bs > 0) out.push("\\".repeat(bs));
      out.push('"');
    }
  }
  return out.join("");
}

// Normaliza `args` vindo do modelo: so array vira lista (escalares viram
// string; null/undefined somem). Vazio sinaliza o caminho antigo sem
// -ArgumentList.
export function toArgList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v) => v !== undefined && v !== null).map((v) => String(v));
}

export function buildPsScript(name: string, args: Record<string, unknown>): string {
  if (name === "act_type") {
    const text = String(args.text ?? "").replace(SENDFLARE, "{$1}");
    return `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('${text.replace(/'/g, "''")}')`;
  }
  if (name === "act_key") {
    // Sintaxe natural (keys.ts) via keybd_event; SendKeys nao interpreta
    // "enter"/"ctrl+v" como teclas — digitava o texto literal.
    return buildForegroundKeyScript(String(args.keys ?? ""));
  }
  if (name === "act_open") {
    const target = String(args.target ?? "").replace(/'/g, "''");
    const argv = toArgList(args.args);
    if (argv.length === 0) return `Start-Process '${target}'`;
    const line = buildWindowsArgs(argv).replace(/'/g, "''");
    return `Start-Process -FilePath '${target}' -ArgumentList '${line}'`;
  }
  if (name === "act_click") {
    const x = Number(args.x ?? 0), y = Number(args.y ?? 0);
    const right = String(args.button ?? "left") === "right";
    const flag = right ? "0x0008" : "0x0002"; // RIGHTDOWN/LEFTDOWN
    const up = right ? "0x0010" : "0x0004";
    return `Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);'; [W.U]::SetCursorPos(${x}, ${y}); [W.U]::mouse_event(${flag}, 0, 0, 0, 0); Start-Sleep -Milliseconds 40; [W.U]::mouse_event(${up}, 0, 0, 0, 0)`;
  }
  throw new Error(`unknown act tool: ${name}`);
}

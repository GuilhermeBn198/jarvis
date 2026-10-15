// Helpers puros das tools act_*. Ficam fora do arquivo de plugin porque o
// loader do opencode invoca TODA funcao exportada por um plugin como factory;
// assim `.opencode/plugins/act-tools.ts` exporta apenas `ActTools`.

import { buildForegroundKeyScript } from "./keys.ts";

const SENDFLARE = /([+^%~(){}[\]])/g; // caracteres especiais do SendKeys

export function encode(script: string): string {
  return Buffer.from(script, "utf16le").toString("base64");
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
    return `Start-Process '${target}'`;
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

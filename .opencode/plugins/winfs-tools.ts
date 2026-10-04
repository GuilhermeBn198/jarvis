import { type Plugin, tool } from "@opencode-ai/plugin";

import { encode } from "../act/ps.ts";
import {
  buildReadScript,
  buildWriteScript,
  isAllowedWrite,
  normalizeWinPath,
  parseAllowlist,
} from "../act/winfs.ts";

// Tools de leitura/escrita de arquivos do Windows (sub-projeto C). O cerebro
// roda no WSL e alcanca /mnt/c; aqui nao abrimos terminal/editor.
//
// ATENCAO: o loader invoca toda funcao exportada como factory; exporte APENAS
// o plugin.
export const WinFsTools: Plugin = async ({ $ }) => ({
  tool: {
    win_read: tool({
      description:
        "Le um arquivo do Windows como texto (via /mnt/c). Aceita caminho WSL ou Windows. Sem abrir editor/terminal.",
      args: { path: tool.schema.string() },
      async execute(args) {
        const p = normalizeWinPath(String(args.path ?? ""));
        if (!p.startsWith("/mnt/")) return "apenas caminhos do Windows (/mnt/<drive>/...) sao aceitos";
        const win = toWindowsPath(p);
        return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(buildReadScript(win))}`).text();
      },
    }),
    win_write: tool({
      description:
        "Escreve (ou concatena com append=true) um arquivo do Windows via /mnt/c. Exige confirm=true e o caminho dentro da allowlist JARVIS_WIN_ALLOW_WRITE.",
      args: {
        path: tool.schema.string(),
        content: tool.schema.string(),
        append: tool.schema.boolean().optional(),
        confirm: tool.schema.boolean().optional(),
      },
      async execute(args) {
        const p = normalizeWinPath(String(args.path ?? ""));
        const allow = parseAllowlist(process.env.JARVIS_WIN_ALLOW_WRITE ?? "");
        if (args.confirm !== true) {
          return "recusado: escrita exige confirm=true (escopo explicito e auditavel)";
        }
        if (!isAllowedWrite(p, allow)) {
          return allow.length === 0
            ? "recusado: JARVIS_WIN_ALLOW_WRITE vazio (nenhum diretorio autorizado)"
            : `recusado: ${p} fora da allowlist (${allow.join(", ")})`;
        }
        const win = toWindowsPath(p);
        const out = (await $`powershell.exe -NoProfile -EncodedCommand ${encode(
          buildWriteScript(win, String(args.content ?? ""), args.append === true),
        )}`).text();
        return `${args.append === true ? "concatenado" : "escrito"}: ${p}${out.trim() ? ` (${out.trim()})` : ""}`;
      },
    }),
  },
});

// /mnt/c/Users/me/a.txt -> C:\Users\me\a.txt (para o PowerShell).
function toWindowsPath(p: string): string {
  const m = p.match(/^\/mnt\/([a-z])\/(.*)$/);
  if (!m) return p;
  return `${m[1].toUpperCase()}:\\${m[2].replace(/\//g, "\\")}`;
}

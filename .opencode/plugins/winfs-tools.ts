import { type Plugin, tool } from "@opencode-ai/plugin";

import { isNativeLinux } from "../act/platform.ts";
import { runLinux } from "../act/linux.ts";

import { encode } from "../act/ps.ts";
import {
  buildWriteScript,
  isAllowedWrite,
  normalizeWinPath,
  parseAllowlist,
  readWindowsPath,
  readWslPath,
  routeRead,
  toWindowsPath,
} from "../act/winfs.ts";
import { formatToolError } from "../lib/tool-error.ts";

// Tools de leitura/escrita de arquivos do Windows (sub-projeto C). O cerebro
// roda no WSL e alcanca /mnt/c; aqui nao abrimos terminal/editor.
//
// ATENCAO: o loader invoca toda funcao exportada como factory; exporte APENAS
// o plugin.
const ALLOW_HINT = [
  "para autorizar, defina no local.conf (raiz do repo, gitignored):",
  '  JARVIS_WIN_ALLOW_WRITE="C:\\Users\\<voce>\\Notas"',
  "aceita formato Windows ou WSL (/mnt/c/Users/<voce>/Notas);",
  "varios diretorios separados por ';'; o diretorio precisa existir",
  "NAO aponte o drive inteiro (C:\\ ou /mnt/c): use apenas pastas de trabalho",
  "o 'opencode serve' guarda a env antiga; para valer: pkill -f '[o]pencode serve'",
  "e reinicie o cerebro (./jarvis)",
].join("\n");

export const WinFsTools: Plugin = async ({ $ }) => ({
  tool: {
    ...(isNativeLinux() ? {
      file_read: tool({
        description: "Le arquivo UTF-8 local Linux (ate 64 KiB), sem seguir links nem acessar credenciais.",
        args: { path: tool.schema.string() },
        async execute(args) { return runLinux("file_read", args); },
      }),
      file_write: tool({
        description: "Escreve arquivo Linux autorizado por JARVIS_ALLOW_WRITE (lista JSON de diretorios existentes). Exige confirm=true; nao segue links.",
        args: { path: tool.schema.string(), content: tool.schema.string(), append: tool.schema.boolean().optional(), confirm: tool.schema.boolean().optional() },
        async execute(args) { return runLinux("file_write", args); },
      }),
    } : {}),
    win_read: tool({
      description:
        "Le um arquivo como texto ou lista um diretorio (JSON-lines com nome/tipo/tamanho). Aceita caminho do WSL (/home/...) ou do Windows (/mnt/<drive>/... ou C:\\...). Sem abrir editor/terminal.",
      args: { path: tool.schema.string() },
      async execute(args) {
        if (isNativeLinux()) return runLinux("win_read", args);
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
        if (isNativeLinux()) return runLinux("win_write", args);
        const p = normalizeWinPath(String(args.path ?? ""));
        const allow = parseAllowlist(process.env.JARVIS_WIN_ALLOW_WRITE ?? "");
        if (args.confirm !== true) {
          return "recusado: escrita exige confirm=true (escopo explicito e auditavel)";
        }
        if (!isAllowedWrite(p, allow)) {
          return allow.length === 0
            ? `recusado: JARVIS_WIN_ALLOW_WRITE vazio (nenhum diretorio autorizado)\n${ALLOW_HINT}`
            : `recusado: ${p} fora da allowlist (${allow.join(", ")})\n${ALLOW_HINT}`;
        }
        const win = toWindowsPath(p);
        // #26: falha do shell nunca vaza crua — vira "erro em win_write (etapa: ...)".
        try {
          const out = (
            await $`powershell.exe -NoProfile -EncodedCommand ${encode(
              buildWriteScript(win, String(args.content ?? ""), args.append === true),
            )}`
          ).text();
          return `${args.append === true ? "concatenado" : "escrito"}: ${p}${out.trim() ? ` (${out.trim()})` : ""}`;
        } catch (err) {
          return formatToolError({ tool: "win_write", step: "escrever arquivo", detail: p }, err);
        }
      },
    }),
  },
});

import { type Plugin, tool } from "@opencode-ai/plugin";

import { encode } from "../act/ps.ts";
import { extractCause } from "../lib/tool-error.ts";
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
  "reinicie o cerebro (./jarvis) para a nova env valer",
].join("\n");

export const WinFsTools: Plugin = async ({ $ }) => ({
  tool: {
    win_read: tool({
      description:
        "Le um arquivo como texto ou lista um diretorio (JSON-lines com nome/tipo/tamanho). Aceita caminho do WSL (/home/...) ou do Windows (/mnt/<drive>/... ou C:\\...). Sem abrir editor/terminal.",
      args: { path: tool.schema.string() },
      async execute(args) {
        const bruto = String(args.path ?? "").trim();
        const p = normalizeWinPath(bruto);
        const rota = routeRead(bruto);
        if (rota === "invalid") {
          return "informe um caminho absoluto: WSL (/home/...) ou Windows (/mnt/c/... ou C:\\...)";
        }
        try {
          if (rota === "wsl") return await readWslPath(bruto);
          return await readWindowsPath(p, async (script) => {
            return (await $`powershell.exe -NoProfile -EncodedCommand ${encode(script)}`).text();
          });
        } catch (e) {
          return `erro ao ler ${p}: ${extractCause(e)}`;
        }
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
            ? `recusado: JARVIS_WIN_ALLOW_WRITE vazio (nenhum diretorio autorizado)\n${ALLOW_HINT}`
            : `recusado: ${p} fora da allowlist (${allow.join(", ")})\n${ALLOW_HINT}`;
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

// Helpers puros das tools de arquivos do Windows (sub-projeto C).
// O cerebro roda no WSL e alcanca /mnt/c; aqui so montamos scripts de leitura/
// escrita e decidimos a politica. NAO e arquivo de plugin.
//
// Leitura (#24): roteada pela forma do caminho — /mnt/<letra>/… fala com o
// PowerShell; caminho absoluto do WSL e lido com o fs do proprio Node. O script
// do Windows e combinado (stat -> conteudo | JSON-lines) e nunca lanca no
// shell: falhas viram `JARVIS-ERR:<codigo>:<mensagem>` no stdout com exit 0
// (PowerShell 5.1 poluiria stderr com CLIXML).

import { readdir, readFile, type Stats, stat } from "node:fs/promises";
import { join } from "node:path";

export type FsOp = "read" | "write" | "append";

export const LIST_CAP = 200;
export const LIST_SENTINEL = "JARVIS-LIST";
export const ERR_SENTINEL = "JARVIS-ERR:";

export type ListEntry = { name: string; type: "file" | "dir"; size: number };
export type ReadRoute = "windows" | "wsl" | "invalid";
export type ReadResult =
  | { kind: "content"; text: string }
  | { kind: "list"; entries: ListEntry[] }
  | { kind: "error"; code: string; message: string };

// Executa um script PowerShell e devolve o stdout (injetado para teste; o
// plugin passa o `$` do opencode).
export type PsRunner = (script: string) => Promise<string>;

// Politica: escrita so dentro da allowlist (dirs do Windows). Leitura livre
// (o SafetyGate ainda nega credenciais). Allowlist vem do ambiente, separada
// por ';' ou ':': ';' sempre separa; ':' so quando nao esta colado numa barra
// (senao 'C:\' / 'C:/' viraria dois itens). Formatos Windows OU WSL.
export function parseAllowlist(raw: string): string[] {
  return (raw || "")
    .split(/(?:;|:(?![\\/]))\s*/)
    .map((p) => normalizeWinPath(p.trim()))
    .filter((p) => p.length > 0);
}

// Normaliza `C:\Users\x` e `/mnt/c/Users/x` para `/mnt/c/Users/x` (sem barra final).
export function normalizeWinPath(p: string): string {
  if (!p) return "";
  let s = p.replace(/\\/g, "/");
  const m = s.match(/^([a-zA-Z]):\/(.*)$/);
  if (m) s = `/mnt/${m[1].toLowerCase()}/${m[2]}`;
  s = s.replace(/\/+$/, "");
  return s;
}

// True se `path` esta sob `dir` (prefixo de diretorio, nao de string solta).
export function isUnder(path: string, dir: string): boolean {
  const p = normalizeWinPath(path);
  const d = normalizeWinPath(dir);
  if (!p || !d) return false;
  return p === d || p.startsWith(d + "/");
}

export function isAllowedWrite(path: string, allowlist: string[]): boolean {
  const p = normalizeWinPath(path);
  if (!p.startsWith("/mnt/")) return false; // escrita fora do Windows: nao
  return allowlist.some((d) => isUnder(p, d));
}

// Escapa aspas simples para string 'single-quoted' do PowerShell.
export function psQuote(v: string): string {
  return String(v).replace(/'/g, "''");
}

// /mnt/<letra>(\/…)? -> Windows (PowerShell); outro absoluto Unix -> WSL (fs).
export function routeRead(p: string): ReadRoute {
  const n = normalizeWinPath(p);
  if (/^\/mnt\/[a-z](\/|$)/i.test(n)) return "windows";
  if (/^\/[^/]/.test(n)) return "wsl";
  return "invalid";
}

// /mnt/c/Users/me/a.txt -> C:\Users\me\a.txt (para o PowerShell).
export function toWindowsPath(p: string): string {
  const m = normalizeWinPath(p).match(/^\/mnt\/([a-zA-Z])(?:\/(.*))?$/);
  if (!m) return p;
  return `${m[1].toUpperCase()}:\\${(m[2] ?? "").replace(/\//g, "\\")}`;
}

// Script unico: stat -> conteudo (arquivo) ou marcador + JSON-lines
// {"name","type","size"} (diretorio). Erros viram sentinela e exit 0.
export function buildReadScript(path: string): string {
  const p = psQuote(path);
  const err = (code: string, msg: string) => `Write-Output '${ERR_SENTINEL}${code}:${msg}'; exit 0`;
  return [
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
    "$ProgressPreference = 'SilentlyContinue'",
    "$ErrorActionPreference = 'Stop'",
    `try { $item = Get-Item -LiteralPath '${p}' -Force }`,
    `catch [System.Management.Automation.ItemNotFoundException] { ${err("not_found", "path not found")} }`,
    `catch [System.UnauthorizedAccessException] { ${err("denied", "access denied")} }`,
    `catch { ${err("error", "stat failed")} }`,
    "try {",
    "  if ($item.PSIsContainer) {",
    `    $children = Get-ChildItem -LiteralPath '${p}' -Force`,
    `    Write-Output '${LIST_SENTINEL}'`,
    "    foreach ($c in $children) {",
    "      $t = if ($c.PSIsContainer) { 'dir' } else { 'file' }",
    "      $s = if ($c.PSIsContainer) { 0 } else { $c.Length }",
    "      Write-Output ([pscustomobject]@{ name = $c.Name; type = $t; size = $s } | ConvertTo-Json -Compress)",
    "    }",
    `  } else { Get-Content -LiteralPath '${p}' -Raw -Encoding UTF8 }`,
    `} catch [System.UnauthorizedAccessException] { ${err("denied", "access denied")} }`,
    `catch { ${err("error", "read failed")} }`,
  ].join("\n");
}

export function buildWriteScript(path: string, content: string, append: boolean): string {
  const p = psQuote(path);
  const c = psQuote(content);
  const cmd = append ? "Add-Content" : "Set-Content";
  return `${cmd} -LiteralPath '${p}' -Value '${c}' -Encoding UTF8 -NoNewline`;
}

function semBom(s: string): string {
  return s.startsWith("\uFEFF") ? s.slice(1) : s;
}

// Linha de sentinela -> resultado de erro; qualquer outra -> null.
function erroDaLinha(linha: string): ReadResult | null {
  const m = linha.trim().match(/^JARVIS-ERR:([a-z_]+):(.*)$/);
  return m ? { kind: "error", code: m[1], message: m[2].trim() } : null;
}

// Interpreta o stdout do script do Windows (ou um texto equivalente).
export function parseReadOutput(out: string): ReadResult {
  const limpo = semBom(out);
  const primeira = (limpo.split(/\r?\n/, 1)[0] ?? "").trim();
  const direto = erroDaLinha(primeira);
  if (direto) return direto;
  if (primeira === LIST_SENTINEL) {
    const nl = limpo.indexOf("\n");
    const resto = nl === -1 ? "" : limpo.slice(nl + 1);
    for (const linha of resto.split(/\r?\n/)) {
      const erro = erroDaLinha(linha); // sentinela apos o marcador = erro
      if (erro) return erro;
    }
    return { kind: "list", entries: parseListLines(resto) };
  }
  return { kind: "content", text: out };
}

// Converte as JSON-lines da listagem; linha malformada e ignorada.
export function parseListLines(text: string): ListEntry[] {
  const entries: ListEntry[] = [];
  for (const linha of text.split(/\r?\n/)) {
    const t = linha.trim();
    if (!t.startsWith("{")) continue;
    let o: Record<string, unknown>;
    try {
      o = JSON.parse(t) as Record<string, unknown>;
    } catch {
      continue;
    }
    if (!o || typeof o.name !== "string") continue;
    entries.push({
      name: o.name,
      type: o.type === "dir" ? "dir" : "file",
      size: typeof o.size === "number" && Number.isFinite(o.size) ? o.size : 0,
    });
  }
  return entries;
}

// Renderiza a listagem: cabecalho + JSON-lines + "…N omitidas" quando passa do cap.
export function formatListing(
  path: string,
  entries: ListEntry[],
  total = entries.length,
  cap = LIST_CAP,
): string {
  const mostradas = entries.slice(0, Math.max(0, cap));
  const linhas = [
    `listagem de ${path} (${total} entradas):`,
    ...mostradas.map((e) => JSON.stringify(e)),
  ];
  const omitidas = total - mostradas.length;
  if (omitidas > 0) linhas.push(`…${omitidas} omitidas`);
  return linhas.join("\n");
}

const READ_ERRORS: Record<string, string> = {
  not_found: "caminho não existe",
  denied: "sem permissão",
};

// Mensagem final de erro de leitura (codigo conhecido -> texto claro em PT).
export function formatReadError(path: string, code: string, message = ""): string {
  const motivo = READ_ERRORS[code] ?? (message.trim() || code);
  return `erro ao ler ${path}: ${motivo}`;
}

function nodeErrCode(e: unknown): string {
  const code =
    e && typeof e === "object" && typeof (e as { code?: unknown }).code === "string"
      ? (e as { code: string }).code
      : "";
  if (code === "ENOENT" || code === "ENOTDIR") return "not_found";
  if (code === "EACCES" || code === "EPERM") return "denied";
  return "error";
}

// Caminho absoluto do WSL: stat -> conteudo | listagem (mesmo shape do Windows).
export async function readWslPath(p: string, cap = LIST_CAP): Promise<string> {
  let info: Stats;
  try {
    info = await stat(p);
  } catch (e) {
    return formatReadError(p, nodeErrCode(e));
  }
  if (!info.isDirectory()) {
    try {
      return await readFile(p, "utf8");
    } catch (e) {
      return formatReadError(p, nodeErrCode(e));
    }
  }
  try {
    const entradas = await readdir(p, { withFileTypes: true });
    entradas.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    const mostradas = entradas.slice(0, Math.max(0, cap));
    const lista: ListEntry[] = [];
    for (const d of mostradas) {
      const ehDir = d.isDirectory();
      let size = 0;
      if (!ehDir) {
        try {
          size = (await stat(join(p, d.name))).size;
        } catch {
          size = 0;
        }
      }
      lista.push({ name: d.name, type: ehDir ? "dir" : "file", size });
    }
    return formatListing(p, lista, entradas.length, cap);
  } catch (e) {
    return formatReadError(p, nodeErrCode(e));
  }
}

// Caminho /mnt/<letra>/…: monta o script, roda via `run` e formata a saida.
export async function readWindowsPath(p: string, run: PsRunner): Promise<string> {
  const out = await run(buildReadScript(toWindowsPath(p)));
  const r = parseReadOutput(out);
  if (r.kind === "error") return formatReadError(p, r.code, r.message);
  if (r.kind === "list") return formatListing(p, r.entries);
  return r.text;
}

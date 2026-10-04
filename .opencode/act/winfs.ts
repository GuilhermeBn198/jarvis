// Helpers puros das tools de arquivos do Windows (sub-projeto C).
// O cerebro roda no WSL e alcanca /mnt/c; aqui so montamos scripts de leitura/
// escrita e decidimos a politica. NAO e arquivo de plugin.

export type FsOp = "read" | "write" | "append";

// Politica: escrita so dentro da allowlist (dirs do Windows). Leitura livre
// (o SafetyGate ainda nega credenciais). Allowlist vem do ambiente, separada
// por ';' ou ':', em formato Windows OU WSL (normalizado).
export function parseAllowlist(raw: string): string[] {
  return (raw || "")
    .split(/[;:](?![\\/])\s*/)
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

export function buildReadScript(path: string): string {
  return `Get-Content -LiteralPath '${psQuote(path)}' -Raw -Encoding UTF8`;
}

export function buildWriteScript(path: string, content: string, append: boolean): string {
  const p = psQuote(path);
  const c = psQuote(content);
  const cmd = append ? "Add-Content" : "Set-Content";
  return `${cmd} -LiteralPath '${p}' -Value '${c}' -Encoding UTF8 -NoNewline`;
}

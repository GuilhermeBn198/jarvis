// Helpers puros das acoes Windows em segundo plano (background).
// NAO e arquivo de plugin (o loader so varre .opencode/plugins/*.ts), entao
// pode exportar varios helpers publicos.

export type WinInfo = { hwnd: number; title: string; process: string };

// P/Invoke Win32 + resolucao de alvo, reutilizado por todos os scripts.
// INVARIANTE: este snippet NUNCA chama SetForegroundWindow/SetCursorPos.
export const WIN32_SNIPPET = `
Add-Type -Namespace W -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint procId);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
'@
function Get-JarvisWindows {
  $out = New-Object System.Collections.ArrayList
  $cb = [W.Win+EnumWindowsProc]{
    param([IntPtr]$h,[IntPtr]$l)
    if ([W.Win]::IsWindowVisible($h)) {
      $sb = New-Object System.Text.StringBuilder 512
      [void][W.Win]::GetWindowTextW($h,$sb,512)
      $t = $sb.ToString()
      if ($t.Trim().Length -gt 0) {
        $procId = 0
        [void][W.Win]::GetWindowThreadProcessId($h,[ref]$procId)
        $p = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
        [void]$out.Add([pscustomobject]@{ hwnd=[int64]$h; title=$t; process=[string]$p })
      }
    }
    return $true
  }
  [void][W.Win]::EnumWindows($cb,[IntPtr]::Zero)
  return $out
}
function Resolve-JarvisTarget([string]$window,[long]$hwnd) {
  $all = Get-JarvisWindows
  if ($hwnd -gt 0) { return @($all | Where-Object { $_.hwnd -eq $hwnd }) }
  if ($window) { return @($all | Where-Object { $_.title -like "*$window*" -or $_.process -like "*$window*" }) }
  return @()
}
`;

export function buildWinListScript(): string {
  return `${WIN32_SNIPPET}\n(Get-JarvisWindows | ForEach-Object { $_ | ConvertTo-Json -Compress })`;
}

export function parseWinList(stdout: string): WinInfo[] {
  const out: WinInfo[] = [];
  for (const line of stdout.split(/\r?\n/)) {
    const t = line.trim();
    if (!t.startsWith("{")) continue;
    try {
      const o = JSON.parse(t) as Record<string, unknown>;
      if (typeof o.hwnd === "number" && typeof o.title === "string") {
        out.push({ hwnd: o.hwnd, title: o.title, process: String(o.process ?? "") });
      }
    } catch {
      // linha de ruido: ignora
    }
  }
  return out;
}

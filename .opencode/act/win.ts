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

export type ActStatus = "confirmed" | "unconfirmed" | "ambiguous" | "error";
export type ActResult = { status: ActStatus; detail: string };

const UIA_SETUP = `
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
`;

// Escapa um valor para string 'single-quoted' do PowerShell.
function psQuote(v: string): string {
  return v.replace(/'/g, "''");
}

function resolveBlock(window: string, hwnd: number): string {
  return `
$target = Resolve-JarvisTarget '${psQuote(window)}' ${hwnd}
$cands = @($target)
if ($cands.Count -eq 0) { Write-Output 'JARVIS_RESULT=error|nenhuma janela corresponde'; exit 0 }
if ($cands.Count -gt 1) {
  $list = ($cands | ForEach-Object { "$($_.hwnd):$($_.title)" }) -join ' ; '
  Write-Output ('JARVIS_RESULT=ambiguous|' + $list); exit 0
}
$h = [IntPtr]$cands[0].hwnd
`;
}

export function buildBackgroundTypeScript(a: { text: string; window?: string; hwnd?: number }): string {
  const text = psQuote(String(a.text ?? ""));
  return `${WIN32_SNIPPET}${UIA_SETUP}${resolveBlock(String(a.window ?? ""), Number(a.hwnd ?? 0))}
$text = '${text}'
$edit = $null
$ok = $false
try {
  $root = [System.Windows.Automation.AutomationElement]::FromHandle($h)
  $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
  $edit = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
  if ($edit) {
    $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $vp.SetValue($text)
    $ok = $true
  }
} catch { $ok = $false }
if (-not $ok) {
  foreach ($ch in $text.ToCharArray()) { [void][W.Win]::PostMessageW($h, 0x0102, [IntPtr][int][char]$ch, [IntPtr]::Zero) }
}
$got = ''
$uiaRead = $false
try {
  if ($edit) {
    $got = [string]$edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
    $uiaRead = $true
  }
} catch { $uiaRead = $false }
if ($uiaRead -and $text -and $got.Contains($text)) { Write-Output 'JARVIS_RESULT=confirmed|digitado' }
else { Write-Output 'JARVIS_RESULT=unconfirmed|sem confirmacao' }
`;
}

export function parseActResult(stdout: string): ActResult {
  for (const line of stdout.split(/\r?\n/)) {
    const m = line.trim().match(/^JARVIS_RESULT=(confirmed|unconfirmed|ambiguous|error)\|(.*)$/);
    if (m) return { status: m[1] as ActStatus, detail: m[2] };
  }
  return { status: "error", detail: (stdout || "").trim().slice(0, 300) || "sem saida" };
}

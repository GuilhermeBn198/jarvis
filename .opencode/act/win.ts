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
  $edit = $null
  foreach ($ct in @([System.Windows.Automation.ControlType]::Document, [System.Windows.Automation.ControlType]::Edit)) {
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, $ct)
    $cand = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if ($cand) { $edit = $cand; break }
  }
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

export function buildBackgroundKeyScript(a: { keys: string; window?: string; hwnd?: number }): string {
  const keys = psQuote(String(a.keys ?? ""));
  return `${WIN32_SNIPPET}${resolveBlock(String(a.window ?? ""), Number(a.hwnd ?? 0))}
$keys = '${keys}'
$map = @{ 'ENTER'=0x0D; 'TAB'=0x09; 'ESC'=0x1B; 'BACKSPACE'=0x08; 'DELETE'=0x2E; 'SPACE'=0x20; 'UP'=0x26; 'DOWN'=0x28; 'LEFT'=0x25; 'RIGHT'=0x27; 'HOME'=0x24; 'END'=0x23; 'F1'=0x70; 'F2'=0x71; 'F3'=0x72; 'F4'=0x73; 'F5'=0x74; 'F6'=0x75; 'F7'=0x76; 'F8'=0x77; 'F9'=0x78; 'F10'=0x79; 'F11'=0x7A; 'F12'=0x7B }
$MOD = @{ '^'=0x11; '%'=0x12; '+'=0x10 }
$mods = New-Object System.Collections.ArrayList
$main = New-Object System.Collections.ArrayList
$i = 0
while ($i -lt $keys.Length) {
  $c = $keys[$i]
  if ($MOD.ContainsKey([string]$c)) { [void]$mods.Add($MOD[[string]$c]); $i++; continue }
  if ($c -eq '{') {
    $end = $keys.IndexOf('}', $i)
    if ($end -gt $i) {
      $name = $keys.Substring($i+1, $end-$i-1).ToUpper()
      if ($map.ContainsKey($name)) { [void]$main.Add($map[$name]) }
      $i = $end + 1; continue
    }
  }
  $vk = if ([char]::IsLetter($c)) { [int][char]([string]$c).ToUpperInvariant() } else { [int][char]$c }
  [void]$main.Add($vk)
  $i++
}
foreach ($vk in $mods) { [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$vk, [IntPtr]::Zero) }
foreach ($vk in $main) { [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$vk, [IntPtr]::Zero); [void][W.Win]::PostMessageW($h, 0x0101, [IntPtr]$vk, [IntPtr]::Zero) }
$mods.Reverse()
foreach ($vk in $mods) { [void][W.Win]::PostMessageW($h, 0x0101, [IntPtr]$vk, [IntPtr]::Zero) }
Write-Output 'JARVIS_RESULT=unconfirmed|teclas enviadas (verificacao indisponivel)'
`;
}

export function parseActResult(stdout: string): ActResult {
  for (const line of stdout.split(/\r?\n/)) {
    const m = line.trim().match(/^JARVIS_RESULT=(confirmed|unconfirmed|ambiguous|error)\|(.*)$/);
    if (m) return { status: m[1] as ActStatus, detail: m[2] };
  }
  return { status: "error", detail: (stdout || "").trim().slice(0, 300) || "sem saida" };
}

// Decide entre o caminho foreground (Retorna "" -> o plugin usa ps.ts) e o
// caminho background. Background so com mode="background" ou window/hwnd —
// ressalva: mode="foreground" explicito forca o foreground mesmo com window/hwnd.
export function chooseActScript(
  name: "act_type" | "act_key",
  args: Record<string, unknown>,
): string {
  const explicitForeground = args.mode === "foreground";
  const bg =
    args.mode === "background" ||
    (!explicitForeground && (args.window !== undefined || args.hwnd !== undefined));
  if (name === "act_type") {
    if (!bg) return ""; // sinaliza foreground -> o plugin usa ps.ts
    return buildBackgroundTypeScript({
      text: String(args.text ?? ""),
      window: args.window === undefined ? undefined : String(args.window),
      hwnd: args.hwnd === undefined ? undefined : Number(args.hwnd),
    });
  }
  if (!bg) return "";
  return buildBackgroundKeyScript({
    keys: String(args.keys ?? ""),
    window: args.window === undefined ? undefined : String(args.window),
    hwnd: args.hwnd === undefined ? undefined : Number(args.hwnd),
  });
}

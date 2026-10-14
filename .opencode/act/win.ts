// Helpers puros das acoes Windows em segundo plano (background).
// NAO e arquivo de plugin (o loader so varre .opencode/plugins/*.ts), entao
// pode exportar varios helpers publicos.

import { encodeKeyChords, parseKeys } from "./keys.ts";

export type WinInfo = { hwnd: number; title: string; process: string };

// Escapa um valor para string 'single-quoted' do PowerShell.
function psQuote(v: string): string {
  return v.replace(/'/g, "''");
}

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
[DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint mapType);
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

export function buildBackgroundTypeScript(a: { text: string; window?: string; hwnd?: number; append?: boolean }): string {
  const text = psQuote(String(a.text ?? ""));
  const append = a.append === true;
  return `${WIN32_SNIPPET}${UIA_SETUP}${resolveBlock(String(a.window ?? ""), Number(a.hwnd ?? 0))}
$text = '${text}'
$append = ${append ? "$true" : "$false"}
# Injetamos via PostMessage WM_CHAR, que NAO ativa a janela. A UIA e usada
# apenas para LOCALIZAR o controle e VERIFICAR o resultado — nunca SetValue:
# medido no #9, ValuePattern.SetValue rouba o foco (FG muda no SetValue).
$job = Start-Job -ScriptBlock {
  param($hwnd, $text, $append)
  Add-Type -AssemblyName UIAutomationClient
  Add-Type -AssemblyName UIAutomationTypes
  Add-Type -Namespace W -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
'@
  $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
  $edit = $null
  foreach ($ct in @([System.Windows.Automation.ControlType]::Document, [System.Windows.Automation.ControlType]::Edit)) {
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, $ct)
    $cand = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if ($cand) { $edit = $cand; break }
  }
  # Handle nativo do controle de edicao (I3): o WM_CHAR vai nele, nao no topo.
  $native = 0
  if ($edit) { try { $native = [int64]$edit.Current.NativeWindowHandle } catch { $native = 0 } }
  $target = if ($native -gt 0) { [IntPtr]$native } else { [IntPtr]$hwnd }
  # Posiciona o caret antes de digitar (EM_SETSEL, nao rouba foco):
  #   append  -> caret no fim (-1,-1)
  #   default -> seleciona tudo (0,-1) para o WM_CHAR sobrescrever
  if ($append) { [void][W.Win]::PostMessageW($target, 0x00B1, [IntPtr](-1), [IntPtr](-1)) }
  else { [void][W.Win]::PostMessageW($target, 0x00B1, [IntPtr]::Zero, [IntPtr](-1)) }
  foreach ($ch in $text.ToCharArray()) { [void][W.Win]::PostMessageW($target, 0x0102, [IntPtr][int][char]$ch, [IntPtr]::Zero) }
  if (-not $edit) { return @('noset', $native) }
  # Deixa a fila de mensagens processar antes de reler (verificacao best-effort).
  Start-Sleep -Milliseconds 250
  try {
    $got = [string]$edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
    if ($text -and $got.Contains($text)) { return @('confirmed', $native) }
  } catch { }
  return @('set', $native)
} -ArgumentList ([int]$h), $text, $append
$done = Wait-Job $job -Timeout 5
if (-not $done) {
  Stop-Job $job -ErrorAction SilentlyContinue
  Remove-Job $job -Force -ErrorAction SilentlyContinue
  Write-Output 'JARVIS_RESULT=unconfirmed|UIA timeout (janela nao respondeu em 5s)'
  exit 0
}
$res = @(Receive-Job $job)
Remove-Job $job -Force -ErrorAction SilentlyContinue
$state = $res[0]
$native = if ($res.Count -gt 1) { [int64]$res[1] } else { 0 }
if ($state -eq 'confirmed') { Write-Output 'JARVIS_RESULT=confirmed|digitado' }
elseif ($state -eq 'set') { Write-Output 'JARVIS_RESULT=unconfirmed|sem confirmacao' }
else {
  Write-Output 'JARVIS_RESULT=unconfirmed|sem controle de edicao (WM_CHAR no topo)'
}
`;
}

export function buildBackgroundKeyScript(a: { keys: string; window?: string; hwnd?: number }): string {
  // Mesmo parser natural do foreground (keys.ts). O JSON vai dentro de um
  // here-string 'single-quoted': nao ha interpolacao nem aspas para escapar.
  const chords = parseKeys(String(a.keys ?? ""));
  const json = encodeKeyChords(chords);
  const hasWin = chords.some((c) => c.mods.includes("win"));
  return `${WIN32_SNIPPET}${UIA_SETUP}${resolveBlock(String(a.window ?? ""), Number(a.hwnd ?? 0))}
# Teclas via PostMessage WM_KEYDOWN/UP com lParam correto (scan code +
# extended). Mira o controle de edicao (mesmo padrao do act_type bg, I3);
# sem controle de edicao, cai no topo. Limites conhecidos e documentados:
# win+r e hotkey do sistema (nunca chega via PostMessage); combos com
# Ctrl/Alt sao best-effort (apps que consultam GetKeyState podem ignora-los).
# Teclas de caractere mandam SO keydown (down+up insere duas vezes em RichEdit).
$job = Start-Job -ScriptBlock {
  param($hwnd)
  Add-Type -AssemblyName UIAutomationClient
  Add-Type -AssemblyName UIAutomationTypes
  Add-Type -Namespace W -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
[DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint mapType);
'@
  $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
  $edit = $null
  foreach ($ct in @([System.Windows.Automation.ControlType]::Document, [System.Windows.Automation.ControlType]::Edit)) {
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, $ct)
    $cand = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if ($cand) { $edit = $cand; break }
  }
  $native = 0
  if ($edit) { try { $native = [int64]$edit.Current.NativeWindowHandle } catch { $native = 0 } }
  $h = if ($native -gt 0) { [IntPtr]$native } else { [IntPtr]$hwnd }
  $chords = @'
${json}
'@ | ConvertFrom-Json
  $MODS = @{ ctrl = 0x11; shift = 0x10; alt = 0x12; win = 0x5B }
  foreach ($c in @($chords)) {
    $mods = @($c.mods)
    $sc = [W.Win]::MapVirtualKey([uint32]$c.vk, 0x0001)
    $ex = $(if ($c.ex) { 0x1000000 } else { 0 })
    $lpDown = [IntPtr]([int64]($sc -shl 16) -bor $ex)
    $lpUp = [IntPtr]([int64]($sc -shl 16) -bor 0x8000 -bor $ex)
    foreach ($m in $mods) {
      $mvk = [uint32]$MODS[[string]$m]
      $msc = [W.Win]::MapVirtualKey($mvk, 0x0001)
      [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$mvk, [IntPtr]([int64]($msc -shl 16)))
    }
    $vk = [uint32]$c.vk
    if ($c.onlyDown) { [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$vk, [IntPtr]$lpDown) }
    else {
      [void][W.Win]::PostMessageW($h, 0x0100, [IntPtr]$vk, [IntPtr]$lpDown)
      [void][W.Win]::PostMessageW($h, 0x0101, [IntPtr]$vk, [IntPtr]$lpUp)
    }
    [array]::Reverse($mods)
    foreach ($m in $mods) {
      $mvk = [uint32]$MODS[[string]$m]
      $msc = [W.Win]::MapVirtualKey($mvk, 0x0001)
      [void][W.Win]::PostMessageW($h, 0x0101, [IntPtr]$mvk, [IntPtr]([int64]($msc -shl 16) -bor 0x8000))
    }
  }
  return $native
} -ArgumentList ([int]$h)
$done = Wait-Job $job -Timeout 5
if (-not $done) {
  Stop-Job $job -ErrorAction SilentlyContinue
  Remove-Job $job -Force -ErrorAction SilentlyContinue
  Write-Output 'JARVIS_RESULT=unconfirmed|timeout (janela nao respondeu em 5s)'
  exit 0
}
$res = @(Receive-Job $job)
Remove-Job $job -Force -ErrorAction SilentlyContinue
$native = if ($res.Count -gt 0) { [int64]$res[0] } else { 0 }
$alvo = if ($native -gt 0) { 'controle de edicao' } else { 'topo da janela (sem controle de edicao)' }
Write-Output ('JARVIS_RESULT=unconfirmed|teclas enviadas para ' + $alvo + '${hasWin ? " — win+r nao funciona em background" : ""}')
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
      append: args.append === true,
    });
  }
  if (!bg) return "";
  return buildBackgroundKeyScript({
    keys: String(args.keys ?? ""),
    window: args.window === undefined ? undefined : String(args.window),
    hwnd: args.hwnd === undefined ? undefined : Number(args.hwnd),
  });
}

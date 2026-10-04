"""Contexto do Windows em TEXTO para o agente (issue #6).

Em vez de tirar screenshot (custo de tokens), expõe janelas, árvore de
acessibilidade (UIA), clipboard e processos como texto. Reusa a descoberta de
janelas do `win_list` (mesmo P/Invoke do `.opencode/act/win.ts`).

O executor do PowerShell é injetável para os testes rodarem sem Windows.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class WinContextError(Exception):
    """Falha ao obter contexto do Windows."""


# P/Invoke minimo (equal ao WIN32_SNIPPET do win.ts) para enumerar janelas.
_WIN32 = r"""
Add-Type -Namespace W -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint procId);
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
"""


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    process: str


def parse_windows(stdout: str) -> list[Window]:
    """Extrai JSON-lines de janelas, ignorando ruido do PowerShell."""
    out: list[Window] = []
    for line in stdout.splitlines():
        t = line.strip()
        if not t.startswith("{"):
            continue
        try:
            o = json.loads(t)
        except ValueError:
            continue
        if isinstance(o.get("hwnd"), int) and isinstance(o.get("title"), str):
            out.append(Window(o["hwnd"], o["title"], str(o.get("process") or "")))
    return out


def format_windows(windows: list[Window]) -> str:
    """Texto compacto (uma linha por janela) — barato em tokens."""
    if not windows:
        return "(nenhuma janela visivel)"
    return "\n".join(f"{w.hwnd}\t{w.process}\t{w.title}".rstrip() for w in windows)


def _default_run(script: str) -> str:
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-EncodedCommand", _encode(script)],
            capture_output=True, text=True, errors="replace", timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WinContextError(f"falha ao rodar powershell.exe: {exc}") from exc
    if proc.returncode != 0:
        raise WinContextError(f"powershell falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}")
    return proc.stdout


def _encode(script: str) -> str:
    import base64
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def list_windows(run=_default_run) -> list[Window]:
    script = _WIN32 + "\n(Get-JarvisWindows | ForEach-Object { $_ | ConvertTo-Json -Compress })"
    return parse_windows(run(script))


def _tree_script(hwnd: int, max_nodes: int) -> str:
    return f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$h = [IntPtr]{int(hwnd)}
$root = [System.Windows.Automation.AutomationElement]::FromHandle($h)
""" + r"""
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$n = 0
foreach ($e in $all) {
  if ($n -ge __MAX__) { break }
  $ct = $e.Current.ControlType.ProgrammaticName -replace 'ControlType\.', ''
  $name = $e.Current.Name
  if ($name) { Write-Output ("$ct`t$name") } else { Write-Output $ct }
  $n++
}
""".replace("__MAX__", str(int(max_nodes)))


def format_tree(stdout: str) -> str:
    lines = [l.strip() for l in stdout.splitlines() if l.strip()]
    return "\n".join(lines) if lines else "(sem arvore de acessibilidade)"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "windows":
        print(format_windows(list_windows()))

"""Conversao de caminhos entre WSL e Windows.

Modulo folha (sem imports internos) para evitar acoplamento entre
capture e vision.
"""


def _wsl_to_windows(p: str) -> str:
    if p.startswith("/mnt/") and len(p) > 6 and p[5].isalpha():
        drive = p[5].upper()
        rest = p[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    return p


def _windows_to_wsl(p: str) -> str:
    if len(p) > 2 and p[1] == ":" and p[2] in "\\/":
        drive = p[0].lower()
        rest = p[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return p

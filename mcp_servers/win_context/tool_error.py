"""Formatacao unica de erros das tools do win_context (#26).

Espelho de `.opencode/lib/tool-error.ts` (os pacotes nao compartilham lib):
extrai a causa real (exit code + stderr/stdout), redige segredos e formata
`erro em <tool> (etapa: <step>): <causa>`. Nunca lanca: os call sites capturam
`WinContextError` e devolvem a string formatada.

Garantias:
- nunca ecoa conteudo sensivel: padroes de token (sk-/ghp_/AKIA/Bearer) e o
  blob de `-EncodedCommand` viram [REDACTADO];
- a causa e truncada (default 400) para nao dominar o contexto do modelo;
- `detail` e um resumo curto de comando/alvo (o chamador decide o conteudo).
"""

from __future__ import annotations

import re

LIMITE_CAUSA = 400
SUFIXO_TRUNCADO = " (truncado)"

# Padroes de credencial conhecidos. Ordem importa: Bearer antes de sk-/ghp_
# (um Bearer pode carregar qualquer token dentro).
_PADROES_SEGREDO: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(-EncodedCommand)\s+\S+", re.IGNORECASE), r"\1 [REDACTADO]"),
    (re.compile(r"(\bBearer)\s+\S+", re.IGNORECASE), r"\1 [REDACTADO]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{4,}"), "[REDACTADO]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{10,}"), "[REDACTADO]"),
    (re.compile(r"\bAKIA[A-Z0-9]{16}"), "[REDACTADO]"),
]

# Sequencias de escape ANSI (cores, cursor, etc.).
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def redact(text: str) -> str:
    """Troca padroes de token por [REDACTADO] (exportada para teste)."""
    out = text
    for padrao, sub in _PADROES_SEGREDO:
        out = padrao.sub(sub, out)
    return out


def truncate(text: str, limit: int = LIMITE_CAUSA) -> str:
    """Limita o tamanho com sufixo explicito (exportada para teste)."""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + SUFIXO_TRUNCADO


def _collapse(text: str) -> str:
    return " ".join(text.split())


# stderr do PowerShell 5.1 pode vir em CLIXML ("#< CLIXML <Objs...>"): markup
# XML + escapes _xHHHH_ escondem a mensagem real e fragmentos de progresso
# ("Preparando modulos para primeiro uso...") consomem o orcamento do
# truncamento. Extrai SO os fragmentos <S S="Error"> — concatenados, porque o
# PowerShell corta a mensagem no meio ("n" + "&#xE3;o") — desescapa _xHHHH_ e
# entidades, e sem fragmento de erro remove o preambulo.
_CLIXML_MARCADOR = "#< CLIXML"
_CLIXML_PREAMBULO = re.compile(r"#< CLIXML\r?\n?")
_CLIXML_FRAGMENTO_ERROR = re.compile(r'<S S="Error">(.*?)</S>', re.DOTALL)
_CLIXML_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{4})_")
_CLIXML_ENTIDADE_HEX = re.compile(r"&#x([0-9A-Fa-f]+);")
_CLIXML_ENTIDADE_DEC = re.compile(r"&#(\d+);")
_CLIXML_ENTIDADES_NOMEADAS = (
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&apos;", "'"),
    ("&amp;", "&"),
)


def _unescape_clixml(text: str) -> str:
    text = _CLIXML_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), text)
    text = _CLIXML_ENTIDADE_HEX.sub(lambda m: chr(int(m.group(1), 16)), text)
    text = _CLIXML_ENTIDADE_DEC.sub(lambda m: chr(int(m.group(1))), text)
    for entidade, char in _CLIXML_ENTIDADES_NOMEADAS:
        text = text.replace(entidade, char)
    return text


def _decode_clixml(text: str) -> str:
    inicio = text.find(_CLIXML_MARCADOR)
    if inicio < 0:
        return text
    # Preserva o que veio antes do CLIXML (ex.: "exit code 1: ").
    prefixo = text[:inicio]
    clixml = text[inicio:]
    fragmentos = [m.group(1) for m in _CLIXML_FRAGMENTO_ERROR.finditer(clixml)]
    if not fragmentos:
        return prefixo + _CLIXML_PREAMBULO.sub("", clixml)
    return prefixo + _unescape_clixml("".join(fragmentos))


def _limpa(text: str) -> str:
    return truncate(_collapse(redact(_ANSI.sub("", _decode_clixml(text)))))


def extract_cause(err: object) -> str:
    """Causa real: exit_code + stderr/stdout > message; redigida e truncada."""
    if isinstance(err, str):
        return _limpa(err) or "erro desconhecido"
    exit_code = getattr(err, "exit_code", None)
    stderr = getattr(err, "stderr", "") or ""
    stdout = getattr(err, "stdout", "") or ""
    corpo = stderr.strip() or stdout.strip()
    if exit_code is not None or corpo:
        if not corpo:
            return _limpa(f"exit code {exit_code}")
        if exit_code is not None:
            return _limpa(f"exit code {exit_code}: {corpo}")
        return _limpa(corpo)
    msg = "" if err is None else str(err)
    return _limpa(msg) if msg.strip() else "erro desconhecido"


def format_tool_error(
    tool: str,
    step: str,
    cause: object,
    detail: str | None = None,
    action: str | None = None,
) -> str:
    """Mensagem unica no formato `erro em <tool> (etapa: <step>): <causa>`."""
    detalhe = f"; {_collapse(redact(detail))}" if detail else ""
    acao = f" — {_collapse(redact(action))}" if action else ""
    return f"erro em {tool} (etapa: {step}{detalhe}): {extract_cause(cause)}{acao}"

import tool_error as te


class _Falha(Exception):
    def __init__(self, msg, exit_code=None, stderr="", stdout=""):
        super().__init__(msg)
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout


# redact: padroes de token viram [REDACTADO].
def test_redact_sk():
    assert te.redact("chave sk-abc123XYZ fim") == "chave [REDACTADO] fim"


def test_redact_ghp():
    assert te.redact("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!") == "token [REDACTADO]!"


def test_redact_akia():
    assert te.redact("AKIAIOSFODNN7EXAMPLE") == "[REDACTADO]"


def test_redact_bearer_preserva_esquema():
    assert (
        te.redact("Authorization: Bearer eyJhbGciOi.abc-123") == "Authorization: Bearer [REDACTADO]"
    )


def test_redact_encodedcommand_nao_vaza_base64():
    out = te.redact("powershell -EncodedCommand SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAKQA=")
    assert "SQBFAFgA" not in out
    assert "[REDACTADO]" in out


# truncate: corta em ~400 chars com sufixo explicito.
def test_truncate_curto_intacto():
    assert te.truncate("ok") == "ok"


def test_truncate_400_com_sufixo():
    assert te.truncate("a" * 600) == "a" * 400 + " (truncado)"


# extract_cause: causa real do erro, nunca so "exit code 1" cru.
def test_extract_cause_exit_code_stderr():
    assert (
        te.extract_cause(_Falha("x", exit_code=1, stderr="npm ERR! missing script\n"))
        == "exit code 1: npm ERR! missing script"
    )


def test_extract_cause_ansi_limpo():
    assert (
        te.extract_cause(_Falha("x", exit_code=2, stderr="\x1b[31mError: boom\x1b[0m\n"))
        == "exit code 2: Error: boom"
    )


def test_extract_cause_exit_sem_stderr():
    assert te.extract_cause(_Falha("x", exit_code=127)) == "exit code 127"


def test_extract_cause_usa_stdout_quando_stderr_vazio():
    assert (
        te.extract_cause(_Falha("x", exit_code=1, stdout="saida util")) == "exit code 1: saida util"
    )


def test_extract_cause_message():
    assert te.extract_cause(ValueError("falhou feio")) == "falhou feio"


def test_extract_cause_string():
    assert te.extract_cause("deu ruim") == "deu ruim"


def test_extract_cause_colapsa_whitespace():
    assert te.extract_cause(ValueError("linha1\n\n   linha2")) == "linha1 linha2"


def test_extract_cause_redige_segredo():
    out = te.extract_cause(ValueError("api key sk-abc123456789 invalida"))
    assert "sk-abc123456789" not in out
    assert "[REDACTADO]" in out


def test_extract_cause_trunca_stderr_gigante():
    out = te.extract_cause(_Falha("x", exit_code=1, stderr="x" * 1000))
    assert out.endswith("(truncado)")
    assert len(out) <= 400 + len(" (truncado)")


def test_extract_cause_fallback_desconhecido():
    assert te.extract_cause(None) == "erro desconhecido"


# format_tool_error: formato unico do pacote.
def test_format_tool_error_base():
    assert (
        te.format_tool_error("win_list_text", "powershell", ValueError("sem powershell"))
        == "erro em win_list_text (etapa: powershell): sem powershell"
    )


def test_format_tool_error_com_detail_e_action():
    out = te.format_tool_error(
        "win_tree_text",
        "powershell",
        _Falha("x", exit_code=1, stderr="boom"),
        detail="hwnd 123",
        action="confira a janela",
    )
    assert (
        out
        == "erro em win_tree_text (etapa: powershell; hwnd 123): exit code 1: boom — confira a janela"
    )


def test_format_tool_error_redige_detail_e_action():
    out = te.format_tool_error(
        "w",
        "s",
        ValueError("x"),
        detail="Authorization: Bearer abc.def",
        action="use sk-abc123456789?",
    )
    assert "Bearer abc.def" not in out
    assert "sk-abc123456789" not in out

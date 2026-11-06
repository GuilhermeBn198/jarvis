import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts" / "verify-linux.sh"


def test_linux_verifier_lists_local_regression_suites_without_claiming_hardware_coverage():
    result = subprocess.run(
        [str(VERIFY), "--list"], cwd=ROOT, capture_output=True, text=True, check=True
    )

    assert "voice/.venv/bin/python -m pytest -q voice/tests" in result.stdout
    assert "python -m pytest -q scripts/tests" in result.stdout
    assert "mcp_servers/win_context/tests" in result.stdout
    assert "mcp_servers/delegate_local/tests" in result.stdout
    assert "node --test gui/tests/*.test.mjs" in result.stdout
    assert "OpenCode" in result.stdout
    assert "cargo test" in result.stdout
    assert "áudio físico" in result.stdout
    assert "desktop real" in result.stdout

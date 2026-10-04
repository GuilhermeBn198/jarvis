import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_pyz_check_lista_modulos():
    out = subprocess.run(
        ["bash", str(ROOT / "scripts" / "build-pyz.sh"), "--check"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "empacotaria" in out
    for mod in ("loop.py", "capture.py", "config.py", "__main__.py"):
        assert mod in out


def test_pyz_importa_sem_dependencias_pesadas(tmp_path):
    """O zipap gera e o entrypoint importa `loop` (sem rodar voz/mic)."""
    out = tmp_path / "jarvis.pyz"
    import os
    env = dict(os.environ, OUT=str(out))
    subprocess.run(
        ["bash", str(ROOT / "scripts" / "build-pyz.sh")],
        capture_output=True, text=True, check=True, env=env,
    )
    assert out.exists() and out.stat().st_size > 0

    # `--list-mics` importa o loop e chama a captura; sem FFMPEG falha, mas o
    # que provamos aqui e que o zipapp e executavel e o import funciona.
    proc = subprocess.run(
        [sys.executable, str(out), "--list-mics"],
        capture_output=True, text=True, timeout=60,
    )
    combined = proc.stdout + proc.stderr
    assert "ModuleNotFoundError" not in combined
    assert "Traceback" not in combined or "ffmpeg" in combined.lower()

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


def test_pyz_outside_repo_extracts_project_resources(tmp_path):
    import os,json
    archive=tmp_path/'jarvis.pyz'
    unrelated=tmp_path/'unrelated';unrelated.mkdir()
    env=dict(os.environ,OUT=str(archive),XDG_CACHE_HOME=str(tmp_path/'cache'))
    env.pop('JARVIS_PROJECT_ROOT',None)
    subprocess.run(['bash',str(ROOT/'scripts/build-pyz.sh')],env=env,check=True,capture_output=True,text=True)
    result=subprocess.run([sys.executable,str(archive),'--doctor'],cwd=unrelated,env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    project=Path(report['project_root'])
    assert project.is_relative_to(tmp_path/'cache')
    assert (project/'voice/triggers.json').is_file()
    assert (project/'.opencode/plugins/act-tools.ts').is_file()
    assert (project/'opencode.json').is_file()
    assert os.access(project/'jarvis',os.X_OK)

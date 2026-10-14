import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_staged_launcher_works_from_arbitrary_directory(tmp_path):
    prefix=tmp_path/'meus apps ação'
    binary=tmp_path/'overlay'
    binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
    subprocess.run(['python3',str(ROOT/'scripts/stage-linux.py'),'--prefix',str(prefix),'--overlay',str(binary)],check=True,capture_output=True,text=True)
    proc=subprocess.run([str(prefix/'bin/jarvis'),'--doctor'],cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert proc.returncode==0,proc.stderr
    report=json.loads(proc.stdout)
    assert report['platform']=='linux'
    assert report['project_root']==str(prefix/'lib/jarvis')
    assert (prefix/'lib/jarvis/.opencode/plugins/act-tools.ts').is_file()
    assert (prefix/'lib/jarvis/voice/triggers.json').is_file()
    assert (prefix/'share/applications/com.jarvis.overlay.desktop').is_file()
    assert not (prefix/'lib/jarvis/voice/tests').exists()
    assert not (prefix/'lib/jarvis/voice/.venv').exists()
    unknown=subprocess.run([str(prefix/'bin/jarvis'),'--mcp','unknown'],capture_output=True,text=True,timeout=10)
    assert unknown.returncode!=0


def test_destdir_stage_keeps_target_prefix(tmp_path):
    binary=tmp_path/'overlay';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
    stage=tmp_path/'stage'
    subprocess.run(['python3',str(ROOT/'scripts/stage-linux.py'),'--prefix','/usr','--destdir',str(stage),'--overlay',str(binary)],check=True,capture_output=True,text=True)
    assert (stage/'usr/bin/jarvis').is_symlink()
    assert (stage/'usr/bin/jarvis-overlay').is_file()
    assert (stage/'usr/lib/jarvis/mcp_servers/win_context/server.py').is_file()

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


def test_packaged_python_directory_is_used_after_relocation(tmp_path):
    import shutil,os
    prefix=tmp_path/'build-prefix'
    binary=tmp_path/'overlay';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
    subprocess.run(['python3',str(ROOT/'scripts/stage-linux.py'),'--prefix',str(prefix),'--overlay',str(binary)],check=True,capture_output=True,text=True)
    python_directory=prefix/'lib/jarvis/python';python_directory.mkdir()
    (python_directory/'sitecustomize.py').write_text("from pathlib import Path\nPath(__file__).parent.parent.joinpath('runtime-used').write_text('yes')\n")
    relocated=tmp_path/'installed elsewhere ação'
    shutil.move(prefix,relocated)
    env=dict(os.environ);env.pop('JARVIS_PROJECT_ROOT',None);env.pop('JARVIS_PYTHON',None)
    result=subprocess.run([str(relocated/'bin/jarvis'),'--doctor'],env=env,cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert (relocated/'lib/jarvis/runtime-used').read_text()=='yes'
    assert json.loads(result.stdout)['project_root']==str(relocated/'lib/jarvis')


def test_private_runtime_does_not_write_bytecode_into_installed_tree(tmp_path):
    import os
    prefix=tmp_path/'installed'
    binary=tmp_path/'overlay';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
    subprocess.run(['python3',str(ROOT/'scripts/stage-linux.py'),'--prefix',str(prefix),'--overlay',str(binary)],check=True,capture_output=True,text=True)
    (prefix/'lib/jarvis/python').mkdir()
    env=dict(os.environ);env.pop('JARVIS_PROJECT_ROOT',None);env.pop('JARVIS_PYTHON',None)
    subprocess.run([str(prefix/'bin/jarvis'),'--doctor'],env=env,capture_output=True,text=True,check=True)
    assert not list((prefix/'lib/jarvis').rglob('__pycache__'))

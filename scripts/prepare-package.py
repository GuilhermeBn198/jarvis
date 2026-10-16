#!/usr/bin/env python3
"""Prepare a complete native package tree, with dependencies resolved at build."""
import argparse
import json
import os
import subprocess
import shutil
from pathlib import Path
from stage_linux_loader import stage

ROOT=Path(__file__).resolve().parents[1]


def bind_python(app: Path, interpreter: Path):
    """Bind native entrypoints to the wheel ABI, not the rolling default alias."""
    interpreter=interpreter.resolve(strict=True)
    if not interpreter.is_file() or not os.access(interpreter,os.X_OK):
        raise ValueError('interpretador do pacote nao e executavel')
    runtime_bin=app/'runtime/bin'
    runtime_bin.mkdir(parents=True,exist_ok=True)
    (runtime_bin/'python3').symlink_to(interpreter)
    for entry in (app/'python/bin').iterdir():
        if not entry.is_file():continue
        data=entry.read_bytes()
        if data.startswith(b'#!'):
            first,rest=data.split(b'\n',1)
            if b'python' in first:entry.write_bytes(b'#!'+os.fsencode(interpreter)+b'\n'+rest)


def prepare(prefix: str,destdir: str,overlay: str,python: str,opencode: str,wheelhouse: str | None=None):
    output=Path(destdir)/prefix.lstrip('/') if destdir else Path(prefix)
    app=output/'lib/jarvis'
    if (app/'python').exists():raise ValueError('staging contem runtime antigo; use diretorio de build limpo')
    stage(prefix,destdir,overlay,with_node_modules=True)
    (app/'bin').mkdir(exist_ok=True)
    shutil.copy2(opencode,app/'bin/opencode')
    (app/'bin/opencode').chmod(0o755)
    version_output=subprocess.check_output([str(app/'bin/opencode'),'--version'],text=True).strip()
    if version_output!='1.18.23':raise ValueError('versao do agente difere do manifesto fixado')
    runtime=app/'python'
    report=app/'python-build-report.json'
    argv=[python,'-m','pip','install','--disable-pip-version-check','--no-compile','--target',str(runtime),
          '--report',str(report),'-r',str(ROOT/'voice/requirements-linux.txt'),
          '-r',str(ROOT/'mcp_servers/win_context/requirements.txt'),
          '-r',str(ROOT/'mcp_servers/delegate_local/requirements.txt')]
    if wheelhouse:argv.extend(['--no-index','--find-links',wheelhouse])
    subprocess.run(argv,check=True)
    # Console entrypoints must use the package's declared system Python,
    # not a developer venv or a DESTDIR path.
    interpreter=Path(subprocess.check_output([python,'-c','import sys;print(sys.executable)'],text=True).strip()).resolve(strict=True)
    if interpreter.parent!=Path('/usr/bin'):
        raise ValueError('pacote nativo exige Python do alvo em /usr/bin; use ambiente da distro correspondente')
    bind_python(app,interpreter)
    version=subprocess.check_output([python,'-c','import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'],text=True).strip()
    files=sorted(str(path.relative_to(output)) for path in output.rglob('*') if path.is_file() or path.is_symlink())
    (app/'install-manifest.json').write_text(json.dumps({'prefix':prefix,'python_abi':version,'files':files},indent=2)+'\n')
    env=dict(os.environ,PATH=str(app/'bin')+os.pathsep+str(runtime/'bin')+os.pathsep+os.environ.get('PATH',''),PYTHONPATH=str(runtime),PYTHONDONTWRITEBYTECODE='1',JARVIS_PROJECT_ROOT=str(app),JARVIS_PLATFORM='linux')
    subprocess.run([python,str(app/'voice/loop.py'),'--doctor'],env=env,check=True)
    subprocess.run([python,'-c','import faster_whisper,piper,mcp,httpx,dbus_next;print("native runtime imports passed")'],env=env,check=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--prefix',default='/usr')
    parser.add_argument('--destdir',required=True)
    parser.add_argument('--overlay',required=True)
    parser.add_argument('--python',default='/usr/bin/python3')
    parser.add_argument('--opencode',required=True)
    parser.add_argument('--wheelhouse')
    args=parser.parse_args()
    prepare(args.prefix,args.destdir,args.overlay,args.python,args.opencode,args.wheelhouse)

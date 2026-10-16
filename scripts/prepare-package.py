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


def copy_python_environment(environment: Path, app: Path, python: str):
    """Copy local build-venv modules; distro dependencies stay package-managed."""
    probe='import json,sys,sysconfig\nfrom importlib import metadata\nsites=[sysconfig.get_path("purelib"),sysconfig.get_path("platlib")]\nscripts=[]\nif len(sys.argv)>1:\n    for distribution in metadata.distributions(path=set(sites)):\n        for entry in distribution.entry_points:\n            if entry.group=="console_scripts":scripts.append({"name":entry.name,"distribution":distribution.metadata["Name"]})\nprint(json.dumps({"prefix":sys.prefix,"abi":sysconfig.get_config_var("SOABI"),"sites":sites,"scripts":scripts}))\n'
    target=json.loads(subprocess.check_output([python,'-I','-c',probe],text=True))
    source=json.loads(subprocess.check_output([str(environment/'bin/python'),'-I','-c',probe,'local-scripts'],text=True))
    environment=environment.resolve(strict=True)
    if Path(source['prefix']).resolve()!=environment or source['abi']!=target['abi']:
        raise ValueError('ambiente Python preparado nao corresponde ao ABI do alvo')
    sites={Path(value).resolve(strict=True) for value in source['sites']}
    for site in sites:
        if not site.is_relative_to(environment):raise ValueError('site-packages fora do ambiente preparado')
        for entry in site.rglob('*'):
            if entry.is_symlink() or entry.suffix=='.egg-link':
                raise ValueError('runtime preparado contem links de build')
            if entry.suffix=='.pth' and any(line.strip() and not line.lstrip().startswith('#') for line in entry.read_text().splitlines()):
                raise ValueError('runtime preparado contem redirecionamento .pth')
    runtime=app/'python'
    if runtime.exists():raise ValueError('runtime preparado exige destino limpo')
    for site in sites:
        shutil.copytree(site,runtime,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    console=runtime/'bin';console.mkdir(exist_ok=True)
    for entry in (environment/'bin').iterdir():
        if entry.is_symlink() or not entry.is_file():continue
        with entry.open('rb') as stream:first=stream.readline(4096)
        if first.startswith(b'#!') and b'python' in first:
            shutil.copy2(entry,console/entry.name)
    for entry in source['scripts']:
        name=entry['name']
        if not name or name in ('.','..') or any(not (character.isascii() and (character.isalnum() or character in '-_.')) for character in name):
            raise ValueError('nome de console invalido no ambiente preparado')
        script=console/name
        script.write_text('#!/usr/bin/python3\nimport sys\nfrom importlib.metadata import distribution\nsys.exit(next(ep for ep in distribution('+repr(entry['distribution'])+').entry_points if ep.group == "console_scripts" and ep.name == '+repr(name)+').load()())\n')
        script.chmod(0o755)


def prepare(prefix: str,destdir: str,overlay: str,python: str,opencode: str,wheelhouse: str | None=None,python_environment: str | None=None,python_report: str | None=None):
    if python_environment and (wheelhouse or not python_report):
        raise ValueError('ambiente preparado exige relatorio pip e nao aceita wheelhouse')
    if python_report and not python_environment:raise ValueError('relatorio exige ambiente preparado')
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
    if python_environment:
        report_data=json.loads(Path(python_report).read_text())
        if not isinstance(report_data,dict) or not isinstance(report_data.get('install'),list):
            raise ValueError('relatorio pip do ambiente preparado invalido')
        copy_python_environment(Path(python_environment),app,python)
        report.write_text(json.dumps(report_data,indent=2)+'\n')
    else:
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
    parser.add_argument('--python-environment')
    parser.add_argument('--python-report')
    args=parser.parse_args()
    prepare(args.prefix,args.destdir,args.overlay,args.python,args.opencode,args.wheelhouse,args.python_environment,args.python_report)

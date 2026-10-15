#!/usr/bin/env python3
"""Resolve dependencies before an offline Flatpak build; record source hashes."""
import argparse
import hashlib
import json
import platform
import subprocess
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha256(path: Path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def write_manifest(source: Path,output: Path):
    digest=sha256(source)
    manifest=json.loads((ROOT/'packaging/flatpak/com.jarvis.overlay.yml').read_text())
    application=next(module for module in manifest['modules'] if module['name']=='jarvis')
    application['sources']=[{'type':'archive','path':str(source.resolve()),'sha256':digest}]
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(manifest,indent=2)+'\n')


def prepare(output: Path,resume: bool=False,wheelhouse: Path | None=None):
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    source=output/'source'
    if source.exists() and not resume:raise ValueError('preparacao existente; use --resume para continuar sem sobrescrever o checkout')
    archive=output/'checkout.tar.gz'
    if not source.exists():
        subprocess.run(['python3',str(ROOT/'scripts/source-archive.py'),'--output',str(archive)],check=True)
        source.mkdir()
        subprocess.run(['tar','-xzf',str(archive),'--strip-components=1','-C',str(source)],check=True)
    # Cargo validates each vendored crate against Cargo.lock.
    subprocess.run(['cargo','vendor','--locked','--manifest-path',str(source/'gui/src-tauri/Cargo.toml'),str(source/'cargo-vendor')],check=True)
    (source/'.cargo').mkdir(exist_ok=True)
    (source/'.cargo/config.toml').write_text('[source.crates-io]\nreplace-with="vendored-sources"\n[source.vendored-sources]\ndirectory="cargo-vendor"\n')
    subprocess.run(['npm','ci','--prefix',str(source/'.opencode'),'--ignore-scripts'],check=True)
    wheels=source/'wheels';wheels.mkdir(exist_ok=True)
    permissions=['--filesystem='+str(source)]
    offline=[]
    if wheelhouse:
        wheelhouse=wheelhouse.resolve()
        if not wheelhouse.is_dir():raise ValueError('wheelhouse ausente')
        permissions.append('--filesystem='+str(wheelhouse)+':ro')
        offline=['--no-index','--find-links',str(wheelhouse)]
    subprocess.run(['flatpak','run','--share=network',*permissions,'--command=python3','org.gnome.Sdk//49',
                    '-m','pip','download','--only-binary=:all:','--dest',str(wheels),
                    '-r',str(source/'voice/requirements-linux.txt'),'-r',str(source/'mcp_servers/win_context/requirements.txt'),
                    '-r',str(source/'mcp_servers/delegate_local/requirements.txt'),*offline],check=True)
    arch=platform.machine()
    if arch not in ('x86_64','aarch64'):raise ValueError('arquitetura nao suportada')
    subprocess.run(['python3',str(ROOT/'scripts/fetch-opencode.py'),'--target',arch+'-glibc','--output',str(source/'flatpak-agent')],check=True)
    hashes={str(path.relative_to(source)):sha256(path)
            for path in sorted(wheels.glob('*.whl'))}
    hashes['flatpak-agent']=sha256(source/'flatpak-agent')
    (source/'flatpak-dependencies.json').write_text(json.dumps(hashes,indent=2)+'\n')
    bundle=output/'jarvis-sources.tar.gz'
    with tarfile.open(bundle,'w:gz') as tar:tar.add(source,arcname='jarvis')
    write_manifest(bundle,output/'com.jarvis.overlay.json')
    print(output/'com.jarvis.overlay.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest-only',type=Path)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--wheelhouse',type=Path)
    args=parser.parse_args()
    if args.manifest_only:write_manifest(args.manifest_only,args.output/'com.jarvis.overlay.json')
    else:prepare(args.output,args.resume,args.wheelhouse)

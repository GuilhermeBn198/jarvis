#!/usr/bin/env python3
"""Create a Guix source archive with npm dependencies resolved from lockfiles."""
import argparse
import gzip
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','target','__pycache__','.pytest_cache','.superpowers','.worktrees'}


def archive_tree(source: Path, output: Path):
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as stream, gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for path in sorted(source.rglob('*')):
                relative=path.relative_to(source)
                if EXCLUDED.intersection(relative.parts):continue
                info=archive.gettarinfo(str(path),arcname=f'jarvis-0.1.0/{relative.as_posix()}')
                info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
                if info.isfile():
                    with path.open('rb') as content:archive.addfile(info,content)
                else:
                    archive.addfile(info)


def prepare(output: Path):
    for tool in ('npm','python3'):
        if not shutil.which(tool):raise RuntimeError(f'Guix source preparation requires {tool}')
    with tempfile.TemporaryDirectory(prefix='jarvis-guix-source-') as temporary:
        temporary=Path(temporary)
        base=temporary/'base.tar.gz'
        subprocess.run(['python3',str(ROOT/'scripts/source-archive.py'),'--output',str(base)],check=True,cwd=ROOT)
        with tarfile.open(base,'r:gz') as archive:archive.extractall(temporary)
        source=temporary/'jarvis-0.1.0'
        subprocess.run(['npm','ci','--ignore-scripts','--prefix',str(source/'.opencode')],check=True,cwd=source)
        archive_tree(source,output.resolve())
    print(output.resolve())


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    prepare(args.output)

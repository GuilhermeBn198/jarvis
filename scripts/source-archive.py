#!/usr/bin/env python3
"""Archive checkout build inputs; exclude local environments and user state."""
import argparse
import gzip
import io
import subprocess
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES={'voice','gui','mcp_servers','.opencode','scripts','packaging','docs'}
FILES={'LICENSE','README.md','jarvis','opencode.json'}
EXCLUDED={'.venv','node_modules','target','__pycache__','.pytest_cache','.superpowers','.worktrees'}


def build(output: Path):
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as stream, gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for name in sorted(set(paths)):
                if not name:continue
                path=Path(name)
                if path.parts[0] not in DIRECTORIES and name not in FILES:continue
                if EXCLUDED.intersection(path.parts) or path.name.startswith('.env') or path.suffix in ('.log','.onnx') or path.name in ('local.conf','settings.json','jarvis-config.json'):continue
                source=ROOT/path
                if not source.is_file() or source.is_symlink():continue
                data=source.read_bytes()
                member=tarfile.TarInfo('jarvis-0.1.0/'+name)
                member.size=len(data);member.mode=0o755 if source.stat().st_mode&0o111 else 0o644
                archive.addfile(member,io.BytesIO(data))
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    build(parser.parse_args().output)

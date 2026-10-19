#!/usr/bin/env python3
"""Fetch a pinned target-specific agent and verify its registry integrity."""
import argparse
import hashlib
import io
import json
import os
import tarfile
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def extract_verified(data: bytes,integrity: str,destination: Path):
    algorithm,expected=integrity.split(':',1)
    if algorithm!='sha256' or hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError('integridade SHA256 do agente incorreta')
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        member=archive.getmember('opencode')
        if not member.isfile():raise ValueError('agente nao e arquivo regular')
        binary=archive.extractfile(member).read()
    if not binary.startswith(b'\x7fELF'):raise ValueError('agente Linux nao e ELF')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+'.partial')
    try:
        temporary.write_bytes(binary);temporary.chmod(0o755);os.replace(temporary,destination)
    finally:temporary.unlink(missing_ok=True)


def fetch(target: str,destination: Path):
    manifest=json.loads((ROOT/'packaging/opencode-sources.json').read_text())
    item=manifest[target]
    with urllib.request.urlopen(item['url'],timeout=60) as response:data=response.read()
    extract_verified(data,item['integrity'],destination)
    return item


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',choices=['x86_64-glibc','aarch64-glibc','x86_64-musl','aarch64-musl'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=fetch(args.target,args.output)
    print(f"agente {result['version']} verificado para {args.target}")

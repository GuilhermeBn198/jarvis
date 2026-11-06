#!/usr/bin/env python3
"""Create a Solus package.yml with a checksummed local checkout archive."""
import argparse
import hashlib
from pathlib import Path
import re


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def render(template: Path, archive: Path, output: Path, release: int | None = None) -> None:
    if not archive.is_file():
        raise ValueError('Solus source archive does not exist')
    content = template.read_text()
    replacements = {
        '@JARVIS_SOURCE_URI@': archive.resolve().as_uri(),
        '@JARVIS_SOURCE_SHA256@': sha256(archive),
    }
    for placeholder, value in replacements.items():
        if content.count(placeholder) != 1:
            raise ValueError(f'expected exactly one {placeholder} placeholder')
        content = content.replace(placeholder, value)
    if release is not None:
        if release < 1:
            raise ValueError('Solus package release must be a positive integer')
        content, count = re.subn(r'(?m)^release\s*:\s*\d+\s*$', f'release    : {release}', content)
        if count != 1:
            raise ValueError(f'expected exactly one Solus release field, found {count}')
    if '@JARVIS_SOURCE_' in content:
        raise ValueError('unresolved Solus source placeholder')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('template', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--release', type=int)
    args = parser.parse_args()
    render(args.template, args.archive, args.output, args.release)


if __name__ == '__main__':
    main()

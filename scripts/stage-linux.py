#!/usr/bin/env python3
"""Build a common install tree for source, native packages and Flatpak."""
import argparse
import json
import os
import shutil
from resources import copy_application, copy_file as copy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def stage(prefix: str,destdir: str,overlay: str | None,with_node_modules: bool=False):
    if not Path(prefix).is_absolute():raise ValueError('prefix deve ser absoluto')
    output=Path(destdir)/prefix.lstrip('/') if destdir else Path(prefix)
    app=output/'lib/jarvis'
    if not overlay:raise ValueError('--overlay exige binario compilado; pacote deve incluir overlay')
    binary=Path(overlay)
    if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('overlay ausente ou nao executavel')
    (output/'bin').mkdir(parents=True,exist_ok=True)
    copy_application(ROOT,app,with_node_modules)
    launcher=output/'bin/jarvis'
    if launcher.exists() or launcher.is_symlink():launcher.unlink()
    launcher.symlink_to('../lib/jarvis/jarvis')
    copy(binary,output/'bin/jarvis-overlay')
    wrapped=binary.with_name(f'.{binary.name}-wrapped')
    if wrapped.is_file():
        copy(wrapped,output/'bin'/f'.{binary.name}-wrapped')
    (output/'bin/jarvis-overlay').chmod(0o755)
    copy(ROOT/'packaging/common/jarvis.desktop',output/'share/applications/com.jarvis.overlay.desktop')
    copy(ROOT/'gui/src-tauri/icons/icon.png',output/'share/icons/hicolor/128x128/apps/jarvis.png')
    copy(ROOT/'docs/linux.md',output/'share/doc/jarvis/linux.md')
    copy(ROOT/'LICENSE',output/'share/licenses/jarvis/LICENSE')
    copy(ROOT/'packaging/opencode/LICENSE',output/'share/licenses/jarvis/opencode-MIT.txt')
    files=sorted(str(path.relative_to(output)) for path in output.rglob('*') if path.is_file() or path.is_symlink())
    (app/'install-manifest.json').write_text(json.dumps({'prefix':prefix,'files':files},indent=2)+'\n')
    print(f'staged application at {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--prefix',required=True)
    parser.add_argument('--destdir',default='')
    parser.add_argument('--overlay',required=True)
    parser.add_argument('--with-node-modules',action='store_true')
    args=parser.parse_args()
    stage(args.prefix,args.destdir,args.overlay,args.with_node_modules)

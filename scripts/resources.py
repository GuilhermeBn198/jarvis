"""Application resources shared by native staging and the portable zipapp."""
import shutil
from pathlib import Path


def copy_file(source: Path,target: Path):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)


def copy_application(root: Path,destination: Path,with_node_modules: bool=False):
    destination.mkdir(parents=True,exist_ok=True)
    for source in (root/'voice').iterdir():
        if source.is_file() and (source.suffix=='.py' or source.name in ('triggers.json','requirements.txt','requirements-linux.txt')):
            copy_file(source,destination/'voice'/source.name)
    for server in ('win_context','delegate_local'):
        for source in (root/'mcp_servers'/server).iterdir():
            if source.is_file() and (source.suffix=='.py' or source.name=='requirements.txt'):
                copy_file(source,destination/'mcp_servers'/server/source.name)
    for source in (root/'.opencode').rglob('*.ts'):
        if '.test.' not in source.name and 'node_modules' not in source.parts:
            copy_file(source,destination/source.relative_to(root))
    for name in ('package.json','package-lock.json'):
        copy_file(root/'.opencode'/name,destination/'.opencode'/name)
    if with_node_modules:
        shutil.copytree(root/'.opencode/node_modules',destination/'.opencode/node_modules',dirs_exist_ok=True)
    for name in ('opencode.json','LICENSE'):copy_file(root/name,destination/name)
    copy_file(root/'packaging/common/launcher',destination/'jarvis')
    (destination/'jarvis').chmod(0o755)

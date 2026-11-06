"""Zipapp entrypoint: use nearby project or extract pinned application resources."""
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from platforms import xdg_path


def prepare_project():
    os.environ.setdefault("JARVIS_PYTHON",sys.executable)
    os.environ["PATH"]=str(Path(sys.executable).parent)+os.pathsep+os.environ.get("PATH","")
    if os.environ.get("JARVIS_PROJECT_ROOT"):return
    archive=Path(sys.argv[0]).resolve()
    for candidate in (archive.parent,archive.parent.parent,Path.cwd()):
        if (candidate/"opencode.json").is_file() and (candidate/"voice/triggers.json").is_file():
            os.environ["JARVIS_PROJECT_ROOT"]=str(candidate)
            return
    if not zipfile.is_zipfile(archive):return
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    cache=xdg_path("cache",os.environ)/"apps"
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    project=cache/digest[:24]
    if not (project/".jarvis-extracted").is_file():
        temporary=Path(tempfile.mkdtemp(prefix=".jarvis-extract-",dir=cache))
        try:
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    if not member.filename.startswith("jarvis_resources/"):continue
                    relative=PurePosixPath(member.filename).relative_to("jarvis_resources")
                    if relative.is_absolute() or ".." in relative.parts:raise ValueError("caminho invalido no zipapp")
                    target=temporary.joinpath(*relative.parts)
                    if member.is_dir():target.mkdir(parents=True,exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True,exist_ok=True)
                        target.write_bytes(bundle.read(member))
            (temporary/"jarvis").chmod(0o755)
            (temporary/".jarvis-extracted").write_text(digest)
            try:os.rename(temporary,project)
            except OSError:
                marker=project/".jarvis-extracted"
                if not marker.is_file() or marker.read_text()!=digest:raise
        finally:
            if temporary.exists():shutil.rmtree(temporary)
    os.environ["JARVIS_PROJECT_ROOT"]=str(project)


if __name__=="__main__":
    prepare_project()
    from loop import main
    raise SystemExit(main(sys.argv[1:]))

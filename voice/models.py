"""Pinned default voice downloads; no model file is replaced before verification."""
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from platforms import current_platform, xdg_path

REVISION='c10ece1aade47bb51c153c893d14e5bf8e5b7117'
BASE=f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/pt/pt_BR/faber/medium/'
FILES=(
    ('pt_BR-faber-medium.onnx','858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7',63201294),
    ('pt_BR-faber-medium.onnx.json','7e694de195ae3fc36dd732c445eb04fb49b649854893cb5506b978f0d50a1d6f',4855),
    ('MODEL_CARD','01f1a5bcfd0538782726059ae407eae9c2dd1b5b35f7298fd53a68de91afe563',279),
)


def file_hash(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str,destination: Path,sha256: str,size: int,fetch=None) -> Path:
    if urlparse(url).scheme!='https':raise ValueError('download exige HTTPS')
    if destination.is_file() and destination.stat().st_size==size and file_hash(destination)==sha256:return destination
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temporary=tempfile.mkstemp(prefix='.jarvis-model-',dir=destination.parent)
    try:
        digest=hashlib.sha256();total=0
        with os.fdopen(fd,'wb') as output:
            with (fetch or urllib.request.urlopen)(url,timeout=30) as response:
                if hasattr(response,'geturl') and urlparse(response.geturl()).scheme!='https':raise ValueError('redirect de download nao seguro')
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>size:raise ValueError('download excede tamanho anunciado')
                    digest.update(chunk);output.write(chunk)
        if total!=size:raise ValueError('tamanho de download incorreto')
        if digest.hexdigest()!=sha256:raise ValueError('checksum SHA256 de download incorreto')
        os.replace(temporary,destination)
        return destination
    finally:Path(temporary).unlink(missing_ok=True)


def download_default_voice(env: dict | None=None) -> str:
    env=os.environ if env is None else env
    if current_platform(env)!='linux':raise ValueError('--download-voice e especifico de Linux nativo')
    directory=xdg_path('data',env)/'voices'
    print('Voz pt_BR-faber-medium: 63,2 MB. O MODEL_CARD informa CC0 para o dataset; consulte os termos completos no arquivo.',flush=True)
    for name,sha256,size in FILES:download_file(BASE+name,directory/name,sha256,size)
    result=str(directory/FILES[0][0])
    print(f'Voz verificada e salva em {result}',flush=True)
    return result

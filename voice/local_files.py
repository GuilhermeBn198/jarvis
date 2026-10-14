"""Native file tools: explicit scope and no-follow traversal at syscall time."""
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path

CREDENTIALS={'.ssh','.aws','.gnupg','.git-credentials','.netrc','id_rsa','id_ed25519',
             'authorized_keys','known_hosts','credentials','.npmrc','.pypirc','shadow','sudoers'}
MAX_READ=64*1024


def parse_allowlist(raw: str) -> list[str]:
    if not raw.strip():return []
    roots=json.loads(raw)
    if not isinstance(roots,list) or not all(isinstance(root,str) and os.path.isabs(root) for root in roots):
        raise ValueError('JARVIS_ALLOW_WRITE deve ser lista JSON de diretorios absolutos')
    return list(dict.fromkeys(os.path.abspath(root) for root in roots))


def checked_path(path: str) -> Path:
    if not isinstance(path,str) or not os.path.isabs(path) or '\x00' in path:
        raise ValueError('caminho absoluto necessario')
    target=Path(os.path.abspath(path))
    for name in target.parts:
        if name.lower() in CREDENTIALS or name=='.env' or name.startswith('.env.'):
            raise ValueError('recusado: acesso a credencial/segredo')
    if target==Path('/'):raise ValueError('caminho deve apontar para arquivo')
    return target


@contextmanager
def parent_descriptor(target: Path,create: bool=False,root: Path=Path("/")):
    """Open every component without following a symlink, retaining only own fd."""
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for component in root.parts[1:]:
            child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        for component in target.relative_to(root).parts[:-1]:
            if create:
                try:os.mkdir(component,mode=0o700,dir_fd=fd)
                except FileExistsError:pass
            child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        yield fd
    finally:os.close(fd)


def read_text(path: str) -> str:
    target=checked_path(path)
    with parent_descriptor(target) as parent:
        fd=os.open(target.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=parent)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('somente arquivos regulares sem hardlinks')
            if info.st_size>MAX_READ:raise ValueError('leitura excede limite de 64 KiB')
            with os.fdopen(fd,'rb',closefd=False) as stream:data=stream.read(MAX_READ+1)
            if len(data)>MAX_READ:raise ValueError('arquivo cresceu alem do limite de 64 KiB')
            if b'\x00' in data:raise ValueError('arquivo binario nao e texto')
            return data.decode('utf-8')
        finally:os.close(fd)


def write_text(path: str,content: str,append: bool,confirm: bool,allowlist: list[str]) -> dict:
    if confirm is not True:raise ValueError('recusado: escrita exige confirm=true')
    if not isinstance(content,str) or len(content.encode('utf-8'))>256*1024:raise ValueError('conteudo invalido ou excede 256 KiB')
    if not isinstance(append,bool):raise ValueError('append deve ser booleano')
    target=checked_path(path)
    roots=parse_allowlist(json.dumps(allowlist))
    matching=[Path(root) for root in roots if target.is_relative_to(Path(root)) and target!=Path(root)]
    if not matching:
        raise ValueError('recusado: caminho fora da allowlist JARVIS_ALLOW_WRITE')
    # No O_TRUNC before validating the opened inode: links/special files stay intact.
    root=max(matching,key=lambda item:len(item.parts))
    with parent_descriptor(target,create=True,root=root) as parent:
        flags=os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC
        if append:flags|=os.O_APPEND
        fd=os.open(target.name,flags,0o600,dir_fd=parent)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                raise ValueError('recusado: destino especial ou com hardlinks')
            if not append:os.ftruncate(fd,0)
            with os.fdopen(fd,'w',encoding='utf-8',closefd=False) as stream:
                stream.write(content);stream.flush()
            os.fsync(fd)
        finally:os.close(fd)
    return {'status':'ok','detail':f'{"concatenado" if append else "escrito"}: {target}'}

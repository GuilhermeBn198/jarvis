"""Bounded Linux desktop context with accessibility isolated in a worker."""
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from platforms import desktop_session
from tts import VoiceError


class ContextError(VoiceError):
    def __init__(self,status,detail):self.status=status;super().__init__(detail)


def window_id(bus: str,path: str) -> str:
    return 'atspi:'+base64.urlsafe_b64encode(json.dumps([bus,path],separators=(',',':')).encode()).decode().rstrip('=')


def parse_window_id(identifier: str) -> tuple[str,str]:
    try:
        if not identifier.startswith('atspi:') or len(identifier)>2048:raise ValueError()
        encoded=identifier[6:]
        bus,path=json.loads(base64.b64decode(encoded+'='*(-len(encoded)%4),altchars=b'-_',validate=True))
        if not isinstance(bus,str) or not re.fullmatch(r':\d+\.\d+',bus):raise ValueError()
        if not isinstance(path,str) or not re.fullmatch(r'/[a-zA-Z0-9_/]+',path):raise ValueError()
        return bus,path
    except (ValueError,TypeError,KeyError) as exc:
        raise ValueError('identificador AT-SPI invalido') from exc


def object_id(node):return window_id(node.app.bus_name,node.path)


def walk_objects(root,max_nodes=200,max_depth=12):
    if not isinstance(max_nodes,int) or isinstance(max_nodes,bool) or not 1<=max_nodes<=2000:raise ValueError('max_nodes deve estar entre 1 e 2000')
    if not isinstance(max_depth,int) or not 0<=max_depth<=32:raise ValueError('max_depth deve estar entre 0 e 32')
    stack=[(root,0)];seen=set();count=0
    while stack and count<max_nodes:
        node,depth=stack.pop()
        try:key=object_id(node)
        except Exception:key=str(id(node))
        if key in seen:continue
        seen.add(key);count+=1
        yield node,depth
        if depth>=max_depth:continue
        try:
            children=min(node.get_child_count(),max_nodes-count)
            for index in reversed(range(children)):
                child=node.get_child_at_index(index)
                if child is not None:stack.append((child,depth+1))
        except Exception:continue


def flatten_accessibility(root,max_nodes=200,max_depth=12) -> list[dict]:
    rows=[]
    for node,depth in walk_objects(root,max_nodes,max_depth):
        try:
            role=node.get_role_name()
            protected='password' in role.lower()
            rows.append({'id':object_id(node),'depth':depth,'role':role[:80],
                         'name':'[protegido]' if protected else node.get_name()[:200]})
        except Exception:rows.append({'depth':depth,'role':'unavailable','name':'[elemento indisponivel]'})
    return rows


def accessibility_request(operation: str,args: dict,timeout_s: float=10) -> dict:
    if not 0<timeout_s<=30:raise ValueError("timeout deve estar entre 0 e 30 segundos")
    if desktop_session(os.environ)=='headless':raise ContextError('unsupported','AT-SPI exige sessao grafica')
    python=os.environ.get('JARVIS_ACCESSIBILITY_PYTHON')
    if not python:
        python=sys.executable if importlib.util.find_spec('gi') else '/usr/bin/python3'
    try:
        proc=subprocess.run([python,str(Path(__file__).with_name('atspi_worker.py'))],
            input=json.dumps({'operation':operation,'args':args}),capture_output=True,text=True,errors='replace',timeout=timeout_s)
        response=json.loads(proc.stdout)
        if response.get('status') not in ('ok','unconfirmed'):
            raise ContextError(response.get('status','error'),response.get('detail','AT-SPI indisponivel'))
        return response
    except (OSError,subprocess.SubprocessError,ValueError) as exc:
        raise ContextError('unavailable',f'AT-SPI indisponivel/timeout: {exc}') from exc


def list_windows() -> list[dict]:return accessibility_request('windows',{})['windows']


def accessibility_tree(window_id: str,max_nodes: int=200,timeout_s: float=10) -> str:
    if timeout_s<=0:raise ValueError('timeout deve ser positivo')
    rows=accessibility_request('tree',{'window':window_id,'max_nodes':max_nodes},timeout_s)['nodes']
    return '\n'.join(f"{row.get('id','')}\t{'  '*row['depth']}{row['role']}\t{row['name'].replace(chr(10),' ')}" for row in rows) or '(arvore vazia)'


def clipboard_text() -> str:
    session=desktop_session(os.environ)
    if session=='headless':raise ContextError('unsupported','clipboard exige sessao grafica')
    argv=['wl-paste','--no-newline'] if session=='wayland' else ['xclip','-selection','clipboard','-o']
    try:
        proc=subprocess.run(argv,capture_output=True,text=True,errors='replace',timeout=5)
        if proc.returncode:raise ContextError('unavailable',proc.stderr.strip()[-200:] or 'clipboard nao disponivel')
        return proc.stdout[:100000] or '(clipboard vazio)'
    except (OSError,subprocess.SubprocessError) as exc:raise ContextError('unavailable',f'clipboard: {exc}') from exc


def processes(name_filter: str='') -> str:
    if not isinstance(name_filter,str) or len(name_filter)>200:raise ValueError('filtro invalido')
    rows=[]
    for entry in sorted(Path('/proc').iterdir(),key=lambda p:int(p.name) if p.name.isdigit() else -1):
        if not entry.name.isdigit():continue
        try:
            name=(entry/'comm').read_text().strip()
            if name_filter.lower() in name.lower():rows.append(f'{name}\t{entry.name}')
        except OSError:continue
        if len(rows)>=500:break
    return '\n'.join(rows) or '(nenhum processo)'

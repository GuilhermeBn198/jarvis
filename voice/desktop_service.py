"""Per-user desktop service: private Unix socket, serialized portal operations."""
import asyncio
import fcntl
import json
import os
import signal
import socket
import stat
import struct
import time
from pathlib import Path
from platforms import desktop_session, xdg_path
from portal import PortalClient, PortalError
from linux_context import ContextError
from linux_input import WaylandInput, x11_action, open_target, validate_action, background_requested

MAX_REQUEST=512*1024


def socket_path(env: dict | None = None) -> Path:
    env=os.environ if env is None else env
    path=xdg_path('runtime',env)
    for directory in (path.parent,path):
        if directory==path and not directory.exists():
            directory.mkdir(mode=0o700)
        info=directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise ValueError(f'diretorio runtime precisa pertencer ao usuario com modo 0700: {directory}')
    return path/'desktop.sock'


def peer_is_owner(peer) -> bool:
    credentials=peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i'))
    _,uid,_=struct.unpack('3i',credentials)
    return uid==os.getuid()


class DesktopService:
    def __init__(self):
        self.session=desktop_session(os.environ)
        self.portal=PortalClient(persistent=True)
        self.wayland=WaylandInput(self.portal)
        self.lock=asyncio.Lock()
        self.last_activity=time.monotonic()

    async def execute(self,operation: str,args: dict) -> dict:
        self.last_activity=time.monotonic()
        if operation=='capabilities':
            return {'status':'ok','service_pid':os.getpid(),'session':self.session,'detail':'eventos de entrada exigem autorizacao; resultado depende do aplicativo',
                    'streams':[{ 'id':node, 'properties':{k:getattr(v,'value',v) for k,v in props.items()}}
                               for node,props in self.wayland.streams]}
        if operation=='authorize':
            if self.session!='wayland':return {'status':'unsupported','detail':'authorize e especifico do portal Wayland'}
            await self.wayland.ensure_session()
            return {'status':'ok','detail':'sessao de controle autorizada; nenhuma entrada enviada'}
        if operation in ('file_read','win_read','file_write','win_write'):
            from local_files import read_text, write_text, parse_allowlist
            if operation in ('file_read','win_read'):
                return {'status':'ok','detail':await asyncio.to_thread(read_text,args.get('path',''))}
            return await asyncio.to_thread(write_text,args.get('path',''),args.get('content',''),
                args.get('append',False),args.get('confirm',False),parse_allowlist(os.environ.get('JARVIS_ALLOW_WRITE','')))
        if operation in ('win_list','desktop_list','desktop_tree','desktop_clipboard','desktop_processes'):
            from linux_context import list_windows, accessibility_tree, clipboard_text, processes
            if operation in ('win_list','desktop_list'):
                windows=await asyncio.to_thread(list_windows)
                detail='\n'.join(f"{item['id']}\t{item['process']}\t{item['title']}" for item in windows) or '(nenhuma janela acessivel)'
            elif operation=='desktop_tree':detail=await asyncio.to_thread(accessibility_tree,args.get('window',''),args.get('max_nodes',200))
            elif operation=='desktop_clipboard':detail=await asyncio.to_thread(clipboard_text)
            else:detail=await asyncio.to_thread(processes,args.get('name_filter',''))
            return {'status':'ok','detail':detail}
        validate_action(operation,args)
        if background_requested(args):
            if args.get('hwnd') is not None:
                return {'status':'unsupported','detail':'hwnd e especifico de Windows; use window com ID AT-SPI'}
            from linux_context import accessibility_request
            return await asyncio.to_thread(accessibility_request,operation,args)
        if operation=='act_open':return await asyncio.to_thread(open_target,args)
        if self.session=='wayland':return await self.wayland.execute(operation,args)
        if self.session=='x11':return await asyncio.to_thread(x11_action,operation,args)
        return {'status':'unsupported','detail':'controle de entrada exige sessao grafica'}

    async def handle(self,reader,writer):
        try:
            peer=writer.get_extra_info('socket')
            if peer is None or not peer_is_owner(peer):
                result={'status':'denied','detail':'usuario do socket nao autorizado'}
            else:
                raw=await asyncio.wait_for(reader.readline(),5)
                if len(raw)>MAX_REQUEST or not raw.endswith(b'\n'):
                    raise ValueError('requisicao incompleta ou excede limite')
                request=json.loads(raw)
                if not isinstance(request,dict) or not isinstance(request.get('args',{}),dict):
                    raise ValueError('requisicao deve ser objeto JSON com args objeto')
                async with self.lock:
                    result=await self.execute(request.get('operation',''),request.get('args',{}))
        except ContextError as exc:result={"status":exc.status,"detail":str(exc)}
        except PortalError as exc:result={'status':exc.code,'detail':str(exc)}
        except (ValueError,TypeError,KeyError,asyncio.TimeoutError) as exc:result={'status':'error','detail':str(exc)}
        except Exception as exc:result={'status':'error','detail':f'falha no backend desktop: {exc}'}
        try:
            writer.write(json.dumps(result,ensure_ascii=False).encode()+b'\n')
            await writer.drain()
        except (ConnectionError,OSError):pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def close(self):await self.wayland.close()


async def serve(idle_timeout: float=300):
    path=socket_path()
    fd=os.open(path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    owned_socket=False
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise ValueError('lock desktop inseguro')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if path.exists():
            info=path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('caminho de socket inseguro')
            path.unlink()
        service=DesktopService()
        server=await asyncio.start_unix_server(service.handle,path=str(path),limit=MAX_REQUEST)
        owned_socket=True
        path.chmod(0o600)
        stop=asyncio.Event()
        loop=asyncio.get_running_loop()
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
        try:
            async with server:
                while not stop.is_set():
                    try:await asyncio.wait_for(stop.wait(),1)
                    except asyncio.TimeoutError:pass
                    if time.monotonic()-service.last_activity>idle_timeout and not service.lock.locked():break
        finally:
            await service.close()
    finally:
        if owned_socket:path.unlink(missing_ok=True)
        os.close(fd)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--idle-timeout',type=float,default=300)
    args=parser.parse_args()
    try:asyncio.run(serve(args.idle_timeout))
    except (OSError,ValueError) as exc:
        print(f'desktop service: {exc}',file=__import__('sys').stderr)
        raise SystemExit(1)

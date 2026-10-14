"""Linux input backends. Sending an event is never proof of app acceptance."""
import asyncio
import math
import re
import subprocess
import uuid
from portal import PortalError

REMOTE = 'org.freedesktop.portal.RemoteDesktop'
SCREENCAST = 'org.freedesktop.portal.ScreenCast'
UNCONFIRMED = {'status':'unconfirmed','detail':'entrada enviada; aplicativo nao confirmou o resultado'}
KEYS = {'ENTER':65293,'RETURN':65293,'TAB':65289,'ESC':65307,'ESCAPE':65307,
        'BACKSPACE':65288,'DELETE':65535,'HOME':65360,'END':65367,'LEFT':65361,
        'UP':65362,'RIGHT':65363,'DOWN':65364,'PAGEUP':65365,'PAGEDOWN':65366,
        'SPACE':32,**{f'F{i}':65469+i for i in range(1,25)}}
MODIFIERS={'CTRL':65507,'CONTROL':65507,'ALT':65513,'SHIFT':65505,'SUPER':65515,'META':65515}


def key_events(keys: str) -> list[tuple[int,int]]:
    if not isinstance(keys,str) or len(keys)>100:
        raise ValueError('atalho invalido')
    keys=keys.strip()
    prefixes=[]
    while keys and keys[0] in '^%+':
        prefixes.append({'^':'CTRL','%':'ALT','+':'SHIFT'}[keys[0]])
        keys=keys[1:]
    parts=prefixes+keys.strip('{}').split('+')
    if len(parts)>5 or not parts or not parts[-1]:
        raise ValueError('atalho invalido')
    modifiers=[]
    for name in parts[:-1]:
        if name.upper() not in MODIFIERS:
            raise ValueError('modificador invalido')
        value=MODIFIERS[name.upper()]
        if value not in modifiers: modifiers.append(value)
    key=parts[-1]
    symbol=KEYS.get(key.upper())
    if symbol is None:
        if len(key)!=1 or not key.isalnum(): raise ValueError('tecla invalida')
        symbol=ord(key.lower())
    pressed=[*modifiers,symbol]
    return [(value,1) for value in pressed]+[(value,0) for value in reversed(pressed)]


def background_requested(args: dict) -> bool:
    return args.get('mode')!='foreground' and (args.get('mode')=='background' or bool(args.get('window')) or args.get('hwnd') is not None)


def validate_action(operation: str, args: dict) -> None:
    if not isinstance(args,dict): raise ValueError('argumentos devem ser objeto')
    if args.get('mode','foreground') not in ('foreground','background'):
        raise ValueError('mode invalido')
    if operation=='act_type':
        text=args.get('text')
        if not isinstance(text,str) or len(text)>100000 or '\x00' in text:
            raise ValueError('texto invalido ou excede 100000 caracteres')
    elif operation=='act_key': key_events(args.get('keys',''))
    elif operation=='act_click':
        for key in ('x','y'):
            value=args.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError('coordenadas devem ser numeros finitos nao negativos')
        if args.get('button','left') not in ('left','right','middle'): raise ValueError('button invalido')
    elif operation=='act_open':
        target=args.get('target')
        if not isinstance(target,str) or not target.strip() or target.startswith('-') or '\x00' in target or len(target)>4096:
            raise ValueError('target invalido')
    else: raise ValueError(f'operacao desconhecida: {operation}')


def x11_action(operation: str, args: dict) -> dict:
    validate_action(operation,args)
    if background_requested(args):
        return {'status':'unsupported','detail':'background exige alvo acessivel AT-SPI; nenhuma janela foi ativada'}
    if operation=='act_type':
        argv=['xdotool','type','--clearmodifiers','--',args['text']]
    elif operation=='act_key':
        events=key_events(args['keys'])
        names=[]
        reverse={value:name for name,value in {**KEYS,**MODIFIERS}.items()}
        reverse.update({65507:'ctrl',65513:'alt',65505:'shift',65515:'super',65293:'Return',65307:'Escape'})
        for value,state in events:
            if state: names.append(reverse.get(value,chr(value)))
        argv=['xdotool','key','--clearmodifiers','+'.join(names)]
    elif operation=='act_click':
        from linux_screen import x11_dimensions
        import os
        width,height=x11_dimensions(os.environ.get('DISPLAY',''))
        if args['x']>=width or args['y']>=height: raise ValueError('coordenadas fora da tela X11')
        button={'left':'1','middle':'2','right':'3'}[args.get('button','left')]
        argv=['xdotool','mousemove','--sync',str(int(args['x'])),str(int(args['y'])),'click',button]
    else:
        return open_target(args)
    try:
        proc=subprocess.run(argv,capture_output=True,text=True,errors='replace',timeout=20)
        if proc.returncode: return {'status':'error','detail':proc.stderr.strip()[-300:] or 'xdotool falhou'}
        return dict(UNCONFIRMED)
    except (OSError,subprocess.SubprocessError) as exc:
        return {'status':'error','detail':f'xdotool indisponivel: {exc}'}


def open_target(args: dict) -> dict:
    import os
    import shutil
    from urllib.parse import urlparse
    validate_action('act_open',args)
    target=args['target']
    try:
        # Bare executable names are launched as a single argv, never shell text.
        executable=shutil.which(target) if not urlparse(target).scheme and not os.path.exists(target) else None
        if executable:
            subprocess.Popen([executable],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,start_new_session=True)
        else:
            proc=subprocess.run(['xdg-open',target],capture_output=True,text=True,errors='replace',timeout=20)
            if proc.returncode: return {'status':'error','detail':proc.stderr.strip()[-300:]}
        return {'status':'unconfirmed','detail':'abertura solicitada ao desktop; resultado nao verificado'}
    except (OSError,subprocess.SubprocessError) as exc:
        return {'status':'error','detail':f'falha ao abrir alvo: {exc}'}


class WaylandInput:
    def __init__(self, portal):
        self.portal=portal
        self.session=None
        self.devices=0
        self.streams=[]

    def revoked(self):
        self.session=None
        self.devices=0
        self.streams=[]

    async def ensure_session(self):
        if self.session: return
        result=await self.portal.request_async(REMOTE,'CreateSession',
                   ({'session_handle_token':'jarvis_'+uuid.uuid4().hex},),30)
        session=result.get('session_handle')
        if not isinstance(session,str) or not session.startswith('/'):
            raise PortalError('error','portal nao criou sessao')
        self.session=session
        try:
            await self.portal.watch_session(session,self.revoked)
            await self.portal.request_async(REMOTE,'SelectDevices',(session,{'types':3}),30)
            await self.portal.request_async(SCREENCAST,'SelectSources',
                                           (session,{'types':1,'multiple':True}),30)
            result=await self.portal.request_async(REMOTE,'Start',(session,'',{}),120)
            if self.session!=session: raise PortalError('denied','sessao revogada')
            self.devices=result.get('devices',0)
            self.streams=result.get('streams',[])
        except BaseException:
            try: await self.portal.call('org.freedesktop.portal.Session','Close','',[],path=session)
            except Exception: pass
            self.revoked()
            raise

    async def execute(self,operation: str,args: dict) -> dict:
        validate_action(operation,args)
        if background_requested(args):
            return {'status':'unsupported','detail':'background requer AT-SPI; foco preservado'}
        if operation=='act_open': return await asyncio.to_thread(open_target,args)
        try:
            await self.ensure_session()
            if operation in ('act_type','act_key'):
                if not self.devices & 1: raise PortalError('denied','teclado nao autorizado')
                if operation=='act_type':
                    events=[]
                    for char in args['text']:
                        symbol={'\n':65293,'\t':65289,'\r':65293}.get(char,ord(char) if ord(char)<=255 else 0x1000000+ord(char))
                        events.extend([(symbol,1),(symbol,0)])
                else: events=key_events(args['keys'])
                held=[]
                try:
                    for symbol,state in events:
                        if not self.session: raise PortalError('denied','sessao revogada')
                        await self.portal.call(REMOTE,'NotifyKeyboardKeysym','oa{sv}iu',[self.session,{},symbol,state])
                        if state: held.append(symbol)
                        elif symbol in held: held.remove(symbol)
                finally:
                    for symbol in reversed(held):
                        if self.session:
                            try: await self.portal.call(REMOTE,'NotifyKeyboardKeysym','oa{sv}iu',[self.session,{},symbol,0])
                            except Exception: pass
            else:
                if not self.devices & 2: raise PortalError('denied','ponteiro nao autorizado')
                if len(self.streams)!=1 and 'stream' not in args:
                    raise ValueError('selecione stream explicitamente para multiplos monitores')
                candidates=[stream for stream in self.streams if 'stream' not in args or stream[0]==args['stream']]
                if len(candidates)!=1: raise ValueError('stream invalido ou indisponivel')
                stream,props=candidates[0]
                # Pixel dimensions are not assumed to equal logical coordinates.
                size=props.get('logical_size',props.get('size'))
                size=getattr(size,'value',size)
                if not size: raise PortalError('unsupported','portal nao informou dimensoes no espaco do compositor; click recusado')
                if args['x']>=size[0] or args['y']>=size[1]: raise ValueError('coordenadas fora do stream')
                await self.portal.call(REMOTE,'NotifyPointerMotionAbsolute','oa{sv}udd',[self.session,{},stream,float(args['x']),float(args['y'])])
                button={'left':272,'right':273,'middle':274}[args.get('button','left')]
                try: await self.portal.call(REMOTE,'NotifyPointerButton','oa{sv}iu',[self.session,{},button,1])
                finally:
                    if self.session: await self.portal.call(REMOTE,'NotifyPointerButton','oa{sv}iu',[self.session,{},button,0])
            return dict(UNCONFIRMED)
        except PortalError as exc:
            if self.session:
                try: await self.portal.call('org.freedesktop.portal.Session','Close','',[],path=self.session)
                except Exception: pass
            self.revoked()
            return {'status':exc.code,'detail':str(exc)}

    async def close(self):
        if self.session:
            try: await self.portal.call('org.freedesktop.portal.Session','Close','',[],path=self.session)
            except Exception: pass
        self.revoked()
        await self.portal.close()

import pytest
import subprocess
from linux_input import key_events, x11_action, validate_action, WaylandInput
from portal import PortalError


def test_key_chords_release_in_reverse_order():
    assert key_events('CTRL+L')==[(65507,1),(108,1),(108,0),(65507,0)]
    assert key_events('^c')==[(65507,1),(99,1),(99,0),(65507,0)]
    assert key_events('{ENTER}')==[(65293,1),(65293,0)]
    with pytest.raises(ValueError): key_events('ctrl+invalid_key')


def test_x11_literal_unicode_is_single_argument(monkeypatch):
    calls=[]
    def run(argv,**kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(subprocess,'run',run)
    result=x11_action('act_type',{'text':'Olá; $(touch /tmp/no)'})
    assert result['status']=='unconfirmed'
    assert calls==[['xdotool','type','--clearmodifiers','--','Olá; $(touch /tmp/no)']]


def test_background_never_invokes_foreground(monkeypatch):
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw: pytest.fail('foreground was invoked'))
    assert x11_action('act_type',{'text':'x','window':'Editor'})['status']=='unsupported'
    assert x11_action('act_key',{'keys':'ENTER','mode':'background'})['status']=='unsupported'


@pytest.mark.parametrize('operation,args',[
    ('act_click',{'x':-1,'y':5}),('act_click',{'x':float('nan'),'y':0}),
    ('act_click',{'x':True,'y':0}),('act_click',{'x':1,'y':1,'button':'invalid'}),
    ('act_type',{'text':'a'*100001}),('act_key',{'keys':'bad;command'}),
    ('act_open',{'target':'-option'}),('act_type',{'text':'a','mode':'invalid'})])
def test_invalid_inputs_rejected_before_action(operation,args):
    with pytest.raises(ValueError): validate_action(operation,args)


def test_wayland_session_persists_and_revocation_stops_events():
    import asyncio
    class Portal:
        def __init__(self): self.calls=[]; self.revoked=False
        async def request_async(self,interface,method,args,timeout_s):
            self.calls.append(method)
            return {'CreateSession':{'session_handle':'/session/test'},'Start':{'devices':3,'streams':[(42,{'size':(100,100),'logical_size':(100,100)})]}}.get(method,{})
        async def watch_session(self,session,callback): self.callback=callback
        async def call(self,interface,method,signature,body,path=None):
            if self.revoked: raise PortalError('denied','revoked')
            self.calls.append((method,body))
        async def close(self): pass
    async def run():
        portal=Portal(); backend=WaylandInput(portal)
        assert (await backend.execute('act_type',{'text':'á'}))['status']=='unconfirmed'
        assert (await backend.execute('act_key',{'keys':'ENTER'}))['status']=='unconfirmed'
        assert portal.calls.count('CreateSession')==1
        assert ('NotifyKeyboardKeysym',['/session/test',{},225,1]) in portal.calls
        portal.revoked=True
        result=await backend.execute('act_type',{'text':'x'})
        assert result['status']=='denied'
        assert backend.session is None
    asyncio.run(run())


def test_wayland_click_rejects_out_of_stream_bounds():
    import asyncio
    backend=WaylandInput(None)
    backend.session='/session/test'; backend.devices=3
    backend.streams=[(42,{'logical_size':(100,100)})]
    with pytest.raises(ValueError):
        asyncio.run(backend.execute('act_click',{'x':101,'y':0}))


def test_wayland_compositor_size_is_logical_not_pixel_size():
    import asyncio
    class Portal:
        def __init__(self):self.calls=[]
        async def call(self,interface,method,signature,body,path=None):self.calls.append((method,body))
    async def run():
        portal=Portal();backend=WaylandInput(portal)
        backend.session='/session/test';backend.devices=3
        backend.streams=[(42,{'size':(100,50),'pixel_size':(200,100)})]
        assert (await backend.execute('act_click',{'x':75,'y':25}))['status']=='unconfirmed'
        assert portal.calls[0]==('NotifyPointerMotionAbsolute',['/session/test',{},42,75.0,25.0])
        assert portal.calls[1:]==[('NotifyPointerButton',['/session/test',{},272,1]),('NotifyPointerButton',['/session/test',{},272,0])]
    asyncio.run(run())

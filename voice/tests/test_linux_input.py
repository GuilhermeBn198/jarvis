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


def test_open_absolute_executable_launches_literal_path(tmp_path,monkeypatch):
    import sys,time
    from linux_input import open_target
    marker=tmp_path/'executed'
    executable=tmp_path/'programa ação $(literal)'
    executable.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("ran")\n')
    executable.chmod(0o755)
    # Prevent any desktop application from opening the script during RED.
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(subprocess,'run',run)
    result=open_target({'target':str(executable)})
    deadline=time.monotonic()+2
    while not marker.exists() and not calls and time.monotonic()<deadline:time.sleep(.01)
    assert not calls,'executable was incorrectly sent to document opener'
    assert marker.read_text()=='ran'
    assert result['status']=='unconfirmed'


def test_open_document_and_url_use_desktop_opener(tmp_path,monkeypatch):
    from linux_input import open_target
    document=tmp_path/'documento ação.txt';document.write_text('text')
    calls=[]
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**kw:pytest.fail('document executed'))
    def run(argv,**kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(subprocess,'run',run)
    for target in (str(document),'https://example.org/path?q=literal'):
        assert open_target({'target':target})['status']=='unconfirmed'
        assert calls[-1]==['xdg-open',target]


def _write_desktop_entry(root, relative_path, contents):
    path=root/'applications'/relative_path
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(contents,encoding='utf-8')
    return path


def _stub_linux_launchers(monkeypatch):
    import shutil
    launched=[]
    def which(name):
        return {'gtk-launch':'/usr/bin/gtk-launch','xdg-open':'/usr/bin/xdg-open'}.get(name)
    monkeypatch.setattr(shutil,'which',which)
    monkeypatch.setattr(subprocess,'Popen',lambda argv,**kwargs:launched.append((argv,kwargs)))
    monkeypatch.setattr(subprocess,'run',lambda argv,**kwargs:subprocess.CompletedProcess(argv,0,'',''))
    return launched


def test_open_desktop_app_by_localized_menu_name_and_id(tmp_path,monkeypatch):
    from linux_input import open_target
    data_home=tmp_path/'user-data'
    _write_desktop_entry(data_home,'kde/systemsettings.desktop',
        '[Desktop Entry]\nType=Application\nName=System Settings\nName[pt_BR]=Configurações do Sistema\nExec=systemsettings\n')
    monkeypatch.setenv('XDG_DATA_HOME',str(data_home))
    monkeypatch.setenv('XDG_DATA_DIRS',str(tmp_path/'system-data'))
    monkeypatch.setenv('LANGUAGE','pt_BR')
    launched=_stub_linux_launchers(monkeypatch)

    for target in ('Configurações do Sistema','kde-systemsettings'):
        result=open_target({'target':target})
        assert result['status']=='unconfirmed'
        assert launched[-1][0]==['/usr/bin/gtk-launch','kde-systemsettings']
        assert launched[-1][1].get('shell',False) is False


def test_open_desktop_app_matches_case_and_accents(tmp_path,monkeypatch):
    from linux_input import open_target
    data_home=tmp_path/'user-data'
    _write_desktop_entry(data_home,'org/example/Cafe.desktop',
        '[Desktop Entry]\nType=Application\nName=Café Editor\nExec=cafe-editor\n')
    monkeypatch.setenv('XDG_DATA_HOME',str(data_home))
    monkeypatch.setenv('XDG_DATA_DIRS',str(tmp_path/'system-data'))
    launched=_stub_linux_launchers(monkeypatch)

    result=open_target({'target':'cafe editor'})

    assert result['status']=='unconfirmed'
    assert launched[0][0]==['/usr/bin/gtk-launch','org-example-Cafe']


def test_open_desktop_app_uses_default_name_when_locale_name_missing(tmp_path,monkeypatch):
    from linux_input import open_target
    data_home=tmp_path/'user-data'
    _write_desktop_entry(data_home,'org/example/editor.desktop',
        '[Desktop Entry]\nType=Application\nName=Text Editor\nName[fr]=Éditeur de texte\nExec=editor\n')
    monkeypatch.setenv('XDG_DATA_HOME',str(data_home))
    monkeypatch.setenv('XDG_DATA_DIRS',str(tmp_path/'system-data'))
    monkeypatch.setenv('LANGUAGE','pt_BR')
    launched=_stub_linux_launchers(monkeypatch)

    result=open_target({'target':'Text Editor'})

    assert result['status']=='unconfirmed'
    assert launched[0][0]==['/usr/bin/gtk-launch','org-example-editor']


def test_open_desktop_app_uses_gio_with_desktop_file_path_as_fallback(tmp_path,monkeypatch):
    from linux_input import open_target
    import shutil
    data_home=tmp_path/'user-data'
    desktop_file=_write_desktop_entry(data_home,'org/example/editor.desktop',
        '[Desktop Entry]\nType=Application\nName=Text Editor\nExec=editor\n')
    monkeypatch.setenv('XDG_DATA_HOME',str(data_home))
    monkeypatch.setenv('XDG_DATA_DIRS',str(tmp_path/'system-data'))
    launched=[]
    monkeypatch.setattr(shutil,'which',lambda name:{'gio':'/usr/bin/gio'}.get(name))
    monkeypatch.setattr(subprocess,'Popen',lambda argv,**kwargs:launched.append((argv,kwargs)))

    result=open_target({'target':'Text Editor'})

    assert result['status']=='unconfirmed'
    assert launched[0][0]==['/usr/bin/gio','launch',str(desktop_file)]


def test_open_existing_path_command_keeps_literal_argv(monkeypatch):
    from linux_input import open_target
    import shutil
    launched=[]
    monkeypatch.setattr(shutil,'which',lambda name:'/opt/bin/systemsettings' if name=='systemsettings' else None)
    monkeypatch.setattr(subprocess,'Popen',lambda argv,**kwargs:launched.append((argv,kwargs)))

    result=open_target({'target':'systemsettings'})

    assert result['status']=='unconfirmed'
    assert launched[0][0]==['/opt/bin/systemsettings']
    assert launched[0][1].get('shell',False) is False


def test_open_desktop_app_reports_ambiguous_name(tmp_path,monkeypatch):
    from linux_input import open_target
    data_home=tmp_path/'user-data'
    _write_desktop_entry(data_home,'one/editor.desktop',
        '[Desktop Entry]\nType=Application\nName=Editor\nExec=editor-one\n')
    _write_desktop_entry(data_home,'two/editor.desktop',
        '[Desktop Entry]\nType=Application\nName=Editor\nExec=editor-two\n')
    monkeypatch.setenv('XDG_DATA_HOME',str(data_home))
    monkeypatch.setenv('XDG_DATA_DIRS',str(tmp_path/'system-data'))
    launched=_stub_linux_launchers(monkeypatch)

    result=open_target({'target':'Editor'})

    assert result['status']=='error'
    assert 'ambigu' in result['detail'].lower()
    assert launched==[]


def test_unknown_app_name_never_becomes_command_or_document_open(tmp_path,monkeypatch):
    from linux_input import open_target
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'user-data'))
    monkeypatch.setenv('XDG_DATA_DIRS',str(tmp_path/'system-data'))
    launched=_stub_linux_launchers(monkeypatch)
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:pytest.fail('unknown name reached xdg-open'))

    result=open_target({'target':'app-nao-instalado; touch pwned'})

    assert result['status']=='error'
    assert launched==[]

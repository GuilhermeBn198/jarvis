import pytest
from portal import PortalError, decode_response


def test_response_returns_values():
    assert decode_response(0,{'uri':'file:///a.png'})=={'uri':'file:///a.png'}


@pytest.mark.parametrize('code,status',[(1,'cancelled'),(2,'denied'),(9,'error')])
def test_response_errors_distinct(code,status):
    with pytest.raises(PortalError) as exc:
        decode_response(code,{})
    assert exc.value.code==status


@pytest.mark.parametrize('scenario', ['success','forged','cancelled','denied','timeout','missing','session-close'])
def test_private_dbus_request_lifecycle(scenario):
    import subprocess
    import sys
    from pathlib import Path
    pytest.importorskip('dbus_next')
    result = subprocess.run(['dbus-run-session', '--', sys.executable,
                             str(Path(__file__).with_name('portal_harness.py')), scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


def test_invalid_bus_address_is_diagnostic(monkeypatch):
    pytest.importorskip('dbus_next')
    from portal import PortalClient
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS','invalid-address')
    with pytest.raises(PortalError) as exc:
        PortalClient().request('org.freedesktop.portal.Screenshot','Screenshot',('',{}),0.2)
    assert exc.value.code == 'unavailable'


def test_persistent_portal_reuses_dbus_connection():
    import subprocess
    import sys
    from pathlib import Path
    pytest.importorskip('dbus_next')
    result=subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).with_name('portal_harness.py')),'persistent'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr


def test_revoked_session_removes_its_dbus_match_and_handler():
    import asyncio
    from types import SimpleNamespace
    from dbus_next import MessageType
    from portal import PortalClient

    class Bus:
        def __init__(self):self.handlers=[];self.members=[]
        def add_message_handler(self,handler):self.handlers.append(handler)
        def remove_message_handler(self,handler):self.handlers.remove(handler)
        async def call(self,message):
            self.members.append(message.member)
            return SimpleNamespace(message_type=MessageType.METHOD_RETURN)

    async def run():
        client=PortalClient(persistent=True)
        client.bus=Bus();client.owner=':1.42'
        revoked=[]
        session='/org/freedesktop/portal/desktop/session/test'
        await client.watch_session(session,lambda:revoked.append(session))
        signal=SimpleNamespace(message_type=MessageType.SIGNAL,sender=':1.42',path=session,
                               interface='org.freedesktop.portal.Session',member='Closed')
        client.bus.handlers[0](signal)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert revoked==[session]
        assert client.bus.handlers==[]
        assert client.bus.members==['AddMatch','RemoveMatch']

    asyncio.run(run())

import pytest
from portal import PortalError, decode_response


def test_response_returns_values():
    assert decode_response(0,{'uri':'file:///a.png'})=={'uri':'file:///a.png'}


@pytest.mark.parametrize('code,status',[(1,'cancelled'),(2,'denied'),(9,'error')])
def test_response_errors_distinct(code,status):
    with pytest.raises(PortalError) as exc:
        decode_response(code,{})
    assert exc.value.code==status


@pytest.mark.parametrize('scenario', ['success','forged','cancelled','denied','timeout','missing'])
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

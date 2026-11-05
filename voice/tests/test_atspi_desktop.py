"""Opt-in integration: opens only disposable test windows and edits their widget."""
import json
import os
import subprocess
import time
from pathlib import Path
import pytest
from linux_context import accessibility_request


def test_wait_for_sentinel_retries_an_empty_state_file(tmp_path):
    import threading
    from types import SimpleNamespace

    state=tmp_path/'state.json'
    state.write_text('')
    timer=threading.Timer(.02,lambda:state.write_text(
        json.dumps({'sentinel_active':True,'active':False})))
    timer.start()
    try:
        data=_wait_for_sentinel_state(state,SimpleNamespace(poll=lambda:None),
                                      attempts=100,interval=.005)
    finally:
        timer.join()
    assert data=={'sentinel_active':True,'active':False}


def _wait_for_sentinel_state(state,child,*,attempts=100,interval=.05):
    data={}
    for _ in range(attempts):
        try:
            data=json.loads(state.read_text())
        except (OSError,ValueError):
            data={}
        if data.get('sentinel_active') and not data.get('active'):
            return data
        if child.poll() is not None:
            pytest.fail('test widget did not start')
        time.sleep(interval)
    return data


@pytest.mark.skipif(os.environ.get('JARVIS_DESKTOP_TESTS')!='1',reason='requires authorized interactive Linux desktop')
def test_background_native_widget_preserves_focus_and_pointer(tmp_path):
    state=tmp_path/'state.json'
    child=subprocess.Popen(['/usr/bin/python3',str(Path(__file__).parent/'fixtures/gtk_input_probe.py'),str(state)],
        env=dict(os.environ,GDK_BACKEND='wayland',GTK_MODULES='atk-bridge'))
    try:
        data=_wait_for_sentinel_state(state,child)
        if not data.get('sentinel_active') or data.get('active'):pytest.skip('test sentinel did not receive focus; no mutation attempted')
        before=subprocess.run(['xdotool','getmouselocation','--shell'],capture_output=True,text=True,check=True).stdout
        result=accessibility_request('act_type',{'window':f'Jarvis Linux input probe {child.pid}','text':'Texto em segundo plano','mode':'background'})
        time.sleep(.2)
        after=subprocess.run(['xdotool','getmouselocation','--shell'],capture_output=True,text=True,check=True).stdout
        data=json.loads(state.read_text())
        assert result['status']=='ok'
        assert data['text']=='Texto em segundo plano'
        assert data['sentinel_active'] and not data['active'] and data['sentinel_text']==''
        assert before==after
    finally:
        child.terminate();child.wait(timeout=5)

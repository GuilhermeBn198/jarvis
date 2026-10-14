"""Opt-in integration: opens only disposable test windows and edits their widget."""
import json
import os
import subprocess
import time
from pathlib import Path
import pytest
from linux_context import accessibility_request


@pytest.mark.skipif(os.environ.get('JARVIS_DESKTOP_TESTS')!='1',reason='requires authorized interactive Linux desktop')
def test_background_native_widget_preserves_focus_and_pointer(tmp_path):
    state=tmp_path/'state.json'
    child=subprocess.Popen(['/usr/bin/python3',str(Path(__file__).parent/'fixtures/gtk_input_probe.py'),str(state)],
        env=dict(os.environ,GDK_BACKEND='wayland',GTK_MODULES='atk-bridge'))
    try:
        data={}
        for _ in range(100):
            if state.exists():
                try:data=json.loads(state.read_text())
                except ValueError:continue
                if data.get('sentinel_active') and not data.get('active'):break
            if child.poll() is not None:pytest.fail('test widget did not start')
            time.sleep(.05)
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

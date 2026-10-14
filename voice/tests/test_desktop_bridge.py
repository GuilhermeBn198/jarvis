import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest
from desktop_service import socket_path, peer_is_owner

VOICE=Path(__file__).resolve().parents[1]


def test_runtime_directory_rejects_symlink(tmp_path):
    root=tmp_path/'runtime';root.mkdir(mode=0o700)
    (root/'jarvis').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError): socket_path({'XDG_RUNTIME_DIR':str(root)})


def test_peer_uid_must_match():
    import struct
    class Peer:
        def getsockopt(self,*args):return struct.pack('3i',123,os.getuid()+1,1)
    assert peer_is_owner(Peer()) is False


def test_bridge_real_socket_lifecycle(tmp_path):
    root=tmp_path/'runtime';root.mkdir(mode=0o700)
    env=dict(os.environ,XDG_RUNTIME_DIR=str(root),XDG_SESSION_TYPE='headless',DISPLAY='',WAYLAND_DISPLAY='')
    proc=subprocess.Popen([sys.executable,str(VOICE/'desktop_service.py'),'--idle-timeout','20'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        path=root/'jarvis/desktop.sock'
        for _ in range(100):
            if path.exists():break
            if proc.poll() is not None: pytest.fail(proc.communicate()[1])
            time.sleep(.02)
        assert path.exists()
        def request(operation,args):
            result=subprocess.run([sys.executable,str(VOICE/'desktop_bridge.py')],input=json.dumps({'operation':operation,'args':args}),env=env,capture_output=True,text=True,timeout=10)
            return result,json.loads(result.stdout)
        result,response=request('capabilities',{})
        assert result.returncode==0
        assert response['session']=='headless'
        result,response=request('act_type',{'text':'x'})
        assert result.returncode!=0 and response['status']=='unsupported'
        result,response=request('act_type',{'text':'x','mode':'background'})
        assert response['status']=='unsupported'
        result,response=request('not-an-operation',{})
        assert response['status']=='error'
        second=subprocess.run([sys.executable,str(VOICE/'desktop_service.py')],env=env,capture_output=True,text=True,timeout=5)
        assert second.returncode!=0
        proc.terminate();proc.wait(timeout=5)
        assert not path.exists()
    finally:
        if proc.poll() is None:proc.kill();proc.wait()

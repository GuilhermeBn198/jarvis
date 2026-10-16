import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest
from desktop_service import socket_path, peer_is_owner

VOICE=Path(__file__).resolve().parents[1]


def wait_for_socket(path, process):
    # Cold imports can exceed two seconds on busy distro build hosts.
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if path.exists():return
        if process.poll() is not None:pytest.fail(process.communicate()[1])
        time.sleep(.02)
    pytest.fail('desktop service did not create its socket within 10 seconds')


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
        wait_for_socket(path,proc)
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


def test_service_exits_when_owning_brain_exits(tmp_path):
    runtime=tmp_path/'runtime';runtime.mkdir(mode=0o700)
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime))
    parent=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    service=subprocess.Popen([sys.executable,str(VOICE/'desktop_service.py'),'--idle-timeout','30'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        path=runtime/'jarvis/desktop.sock'
        wait_for_socket(path,service)
        result=subprocess.run([sys.executable,str(VOICE/'desktop_bridge.py')],input=json.dumps({'operation':'attach','args':{'pid':parent.pid}}),env=env,capture_output=True,text=True,timeout=5)
        assert result.returncode==0,result.stdout+result.stderr
        parent.terminate();parent.wait(timeout=5)
        service.wait(timeout=5)
        assert not path.exists()
    finally:
        for proc in (parent,service):
            if proc.poll() is None:proc.kill();proc.wait()


def test_service_shutdown_terminates_owned_worker():
    import asyncio
    from desktop_service import DesktopService
    async def run():
        service=DesktopService()
        worker=asyncio.create_task(asyncio.to_thread(service.run_child,[sys.executable,'-c','import time;time.sleep(30)'],capture_output=True,text=True,errors='replace',timeout=30))
        for _ in range(100):
            if service.children:break
            await asyncio.sleep(.01)
        assert service.children
        await service.close()
        result=await asyncio.wait_for(worker,2)
        assert result.returncode!=0
        assert not service.children
    asyncio.run(run())

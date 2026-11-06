"""JSON stdin/stdout bridge for the OpenCode tools. No shell interpolation."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from desktop_service import socket_path, MAX_REQUEST


def request(operation: str,args: dict,autostart: bool=True) -> dict:
    path=socket_path()
    payload=json.dumps({'operation':operation,'args':args},ensure_ascii=False).encode()+b'\n'
    if len(payload)>MAX_REQUEST:raise ValueError('requisicao excede limite')
    connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        connection.settimeout(150)
        try:connection.connect(str(path))
        except (FileNotFoundError,ConnectionRefusedError):
            if not autostart:raise
            child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('desktop_service.py'))],
                                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                   start_new_session=True)
            for _ in range(100):
                try:connection.connect(str(path));break
                except (FileNotFoundError,ConnectionRefusedError):time.sleep(.03)
            else:raise RuntimeError(f'servico desktop nao iniciou (exit={child.poll()})')
        connection.sendall(payload)
        with connection.makefile('rb') as reader:
            raw=reader.readline(MAX_REQUEST+1)
        if not raw.endswith(b'\n') or len(raw)>MAX_REQUEST:raise ValueError('resposta desktop invalida')
        result=json.loads(raw)
        if not isinstance(result,dict) or not isinstance(result.get('status'),str):raise ValueError('resposta desktop invalida')
        return result
    finally:connection.close()


def main() -> int:
    try:
        raw=sys.stdin.buffer.read(MAX_REQUEST+1)
        if len(raw)>MAX_REQUEST:raise ValueError('requisicao excede limite')
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get('args',{}),dict):raise ValueError('objeto JSON invalido')
        result=request(data.get('operation',''),data.get('args',{}))
    except Exception as exc:result={'status':'error','detail':str(exc)}
    sys.stdout.write(json.dumps(result,ensure_ascii=False)+'\n')
    return 0 if result['status'] in ('ok','unconfirmed') else 1


if __name__=='__main__':raise SystemExit(main())

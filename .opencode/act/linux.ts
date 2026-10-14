import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { beforeToolCall } from '../safety/hook.ts';

export async function runLinux(operation: string,args: Record<string,unknown>): Promise<string> {
  beforeToolCall(operation,args);
  const root=process.env.JARVIS_PROJECT_ROOT ?? fileURLToPath(new URL('../../',import.meta.url));
  const venv=join(root,'voice','.venv','bin','python');
  const python=process.env.JARVIS_PYTHON ?? (existsSync(venv)?venv:'python3');
  return new Promise((resolve,reject)=>{
    const child=spawn(python,[join(root,'voice','desktop_bridge.py')],{stdio:['pipe','pipe','pipe'],shell:false});
    let output='';let errors='';
    const timer=setTimeout(()=>{child.kill();reject(new Error('timeout no bridge desktop; nenhuma acao confirmada'));},155000);
    child.stdout.on('data',chunk=>{
      output+=chunk.toString();
      if(Buffer.byteLength(output)>512*1024){child.kill();reject(new Error('resposta desktop excede limite'));}
    });
    child.stderr.on('data',chunk=>{errors=(errors+chunk.toString()).slice(-4096);});
    child.on('error',error=>{clearTimeout(timer);reject(error);});
    child.stdin.on('error',error=>{clearTimeout(timer);reject(error);});
    child.on('close',()=>{
      clearTimeout(timer);
      try {
        const response=JSON.parse(output);
        if(typeof response.status!=='string' || typeof response.detail!=='string')throw new Error('resposta desktop invalida');
        resolve(`${response.status}: ${response.detail}`);
      } catch(error){reject(new Error(`falha no bridge desktop: ${errors || String(error)}`));}
    });
    child.stdin.end(JSON.stringify({operation,args}));
  });
}

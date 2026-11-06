import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { isNativeLinux } from './platform.ts';
import { runLinux } from './linux.ts';

test('platform override and WSL detection agree with Python', () => {
  assert.equal(isNativeLinux({},'generic','linux'),true);
  assert.equal(isNativeLinux({},'microsoft-standard-WSL2','linux'),false);
  assert.equal(isNativeLinux({JARVIS_PLATFORM:'linux'},'microsoft','linux'),true);
  assert.equal(isNativeLinux({JARVIS_PLATFORM:'wsl'},'generic','linux'),false);
  assert.throws(()=>isNativeLinux({JARVIS_PLATFORM:'bad'},'generic','linux'));
});

test('bridge transports text as JSON stdin, not executable shell code', async () => {
  const directory=mkdtempSync(join(tmpdir(),'jarvis unicode ação '));
  const interpreter=join(directory,'fake-python');
  writeFileSync(interpreter,`#!/usr/bin/env node\nlet input='';process.stdin.on('data',d=>input+=d);process.stdin.on('end',()=>{const request=JSON.parse(input);console.log(JSON.stringify({status:'unconfirmed',detail:request.args.text}));});`,{mode:0o700});
  const old=process.env.JARVIS_PYTHON;
  process.env.JARVIS_PYTHON=interpreter;
  try { assert.equal(await runLinux('act_type',{text:'Olá; $(touch test)'}),'unconfirmed: Olá; $(touch test)'); }
  finally { if(old===undefined)delete process.env.JARVIS_PYTHON;else process.env.JARVIS_PYTHON=old;rmSync(directory,{recursive:true}); }
});

test('SafetyGate denies dangerous action before spawning bridge',async()=>{
  await assert.rejects(()=>runLinux('act_type',{text:'rm -rf /'}),/SafetyGate/);
});

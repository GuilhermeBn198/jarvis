import { test } from 'node:test';
import assert from 'node:assert/strict';
import { resizeWindow } from '../src/window-layout.mjs';

class PhysicalSize {constructor(width,height){this.width=width;this.height=height;}}
class PhysicalPosition {constructor(x,y){this.x=x;this.y=y;}}
const dpi={PhysicalSize,PhysicalPosition};

test('Wayland without global positions still resizes menu',async()=>{
  let size;
  const win={scaleFactor:async()=>1.5,outerPosition:async()=>{throw new Error('unsupported');},innerSize:async()=>({width:120,height:120}),setSize:async value=>{size=value;},setPosition:async()=>assert.fail('position unavailable')};
  await resizeWindow(win,dpi,280,320);
  assert.deepEqual(size,new PhysicalSize(420,480));
});

test('X11 or Windows retain bottom-right anchor at display scale',async()=>{
  let position;let size;
  const win={scaleFactor:async()=>2,outerPosition:async()=>({x:600,y:400}),innerSize:async()=>({width:240,height:240}),setSize:async value=>{size=value;},setPosition:async value=>{position=value;}};
  await resizeWindow(win,dpi,280,320);
  assert.deepEqual(size,new PhysicalSize(560,640));
  assert.deepEqual(position,new PhysicalPosition(280,0));
});

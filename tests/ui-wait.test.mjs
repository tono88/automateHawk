import test from 'node:test';
import assert from 'node:assert/strict';
import {waitForRendered} from '../connector/ui-wait.mjs';
test('ready rendered controls incur no fixed delay',async()=>{
  let sleeps=0;
  await waitForRendered({observe:async()=>{}},async()=>true,{pause:async()=>{sleeps++;}});
  assert.equal(sleeps,0);
});
test('detached controls recover; a stalled screen times out with a bounded wait',async()=>{
  let now=0,calls=0;
  const options={timeoutMs:500,now:()=>now,pause:async ms=>{now+=ms;}};
  await waitForRendered({observe:async()=>{}},async()=>{if(++calls<3)throw Error('Detached');return true;},options);
  assert.equal(calls,3);assert.ok(now>0&&now<500);
  await assert.rejects(waitForRendered({observe:async()=>{}},async()=>false,options),/timeout/);
});

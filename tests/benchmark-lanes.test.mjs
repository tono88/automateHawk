import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
test('malformed benchmark input never echoes a supplied password',()=>{
 const marker='SYNTHETIC-PASSWORD-DO-NOT-LOG';
 const result=spawnSync(process.execPath,[fileURLToPath(new URL('../connector/benchmark-lanes.mjs',import.meta.url))],{input:'{"password":"'+marker+'",broken',encoding:'utf8'});
 assert.notEqual(result.status,0);assert.ok(!(result.stdout+result.stderr).includes(marker));
});

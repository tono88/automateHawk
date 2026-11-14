import test from 'node:test';
import assert from 'node:assert/strict';
import {repairable,onlyCallChanged,repairMissingTestCall} from '../connector/repair-test-call.mjs';
const before={fields:{test_date:'',test_call:'',cycle:'SYNTHETIC'},capabilities:{test_call:true}};
test('repair requires explicit authorization before touching Oracle',async()=>{
  await assert.rejects(repairMissingTestCall({},'SYNTHETIC'),/permission/);
});
test('missing fields, actual dates, existing calls and disabled controls prohibit repair',()=>{
  assert.equal(repairable(before),true);
  for(const detail of [{fields:{}},{...before,fields:{...before.fields,test_date:'2026-01-01'}},
    {...before,fields:{...before.fields,test_call:'Convocatoria ficticia'}},
    {...before,capabilities:{test_call:false}}])assert.equal(repairable(detail),false);
});
test('repair comparison rejects collateral edits, missing fields and fake dates',()=>{
  const after={fields:{...before.fields,test_call:'No Aplica'}};
  assert.equal(onlyCallChanged(before,after),true);
  for(const fields of [{...after.fields,cycle:'CHANGED'},{...after.fields,test_date:'2026-01-01'},
    {test_call:'No Aplica'},{...after.fields,unknown:'extra'}])assert.equal(onlyCallChanged(before,{fields}),false);
});

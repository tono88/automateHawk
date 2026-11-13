import test from 'node:test';
import assert from 'node:assert/strict';
import {validateObserved,equivalent,dateForOracle} from '../connector/oracle-write.mjs';
test('denies a write if Oracle control is not enabled',()=>{
  assert.throws(()=>validateObserved({field:'name',old_value:'Ficticio'},{fields:{name:'Ficticio'},capabilities:{name:false}}),/permission/);
  assert.throws(()=>validateObserved({field:'resolution'},{}),/permission/);
});
test('detects a change made outside the local mirror before any save',()=>{
  assert.throws(()=>validateObserved({field:'name',old_value:'Anterior ficticio'},{fields:{name:'Otro ficticio'},capabilities:{name:true}}),/conflict/);
});
test('normalizes observed dates and probabilities for conflict checks',()=>{
  assert.ok(equivalent('probability','75.0','75'));assert.ok(equivalent('close_date','13/11/26','2026-11-13'));
  assert.equal(dateForOracle('2026-12-01','13/11/26'),'01/12/26');
  assert.equal(dateForOracle('2026-12-01','13/11/2026'),'01/12/2026');
  assert.equal(dateForOracle('2026-12-01','2026-11-13'),'2026-12-01');
});

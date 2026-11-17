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
test('compares amounts, percentages and empty values by field kind',()=>{
  assert.ok(equivalent('amount','Q1,250.00','1250'));assert.ok(equivalent('financial_requested_1','50','50.0'));
  assert.ok(equivalent('test_date','',null));assert.ok(!equivalent('test_date','','2026-02-01'));
  assert.ok(!equivalent('test_call','No Aplica','Enero'));assert.equal(dateForOracle('','13/11/26'),'');
});
test('writer registry matches the hub catalogue',async()=>{
  const {readFileSync}=await import('node:fs');const {EDIT_FIELDS}=await import('../connector/edit-fields.mjs');
  const source=readFileSync(new URL('../app/catalog.py',import.meta.url),'utf8');
  const block=source.slice(source.indexOf('EDIT_KINDS={'),source.indexOf('}',source.indexOf('EDIT_KINDS={')));
  const keys=[...block.matchAll(/'([a-z_0-9]+)':'(text|choice|number|date|email|boolean)'/g)].map(m=>[m[1],m[2]]);
  assert.deepEqual(Object.fromEntries(keys),Object.fromEntries(Object.entries(EDIT_FIELDS).map(([k,v])=>[k,v.kind])));
});

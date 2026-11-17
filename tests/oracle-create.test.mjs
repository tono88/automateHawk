import test from 'node:test';
import assert from 'node:assert/strict';
import {validateCreation,oracleDate,contactName} from '../connector/oracle-create.mjs';

const base={name:'Oportunidad ficticia',close_date:'2026-12-01',stage:'01 - Interesado',probability:'',contact:{mode:'new',first_name:'Ana',last_name:'Ficticia'}};
test('creation requests are validated before touching Oracle',()=>{
  assert.equal(validateCreation(base),base);
  for(const bad of [{...base,name:' '},{...base,stage:'99 - Otra'},{...base,close_date:'01/12/26'},{...base,probability:'150'},{...base,contact:{mode:'existing',name:''}},{...base,contact:{mode:'otro'}}])
    assert.throws(()=>validateCreation(bad),/validation/);
});
test('dates and contact names use the forms observed in Oracle',()=>{
  assert.equal(oracleDate('2026-12-01'),'01/12/26');
  assert.equal(contactName({mode:'new',first_name:' Ana ',last_name:'Ficticia '}),'Ana Ficticia');
  assert.equal(contactName({mode:'existing',name:'Luis Prueba'}),'Luis Prueba');
});

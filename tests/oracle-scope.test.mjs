import test from 'node:test';
import assert from 'node:assert/strict';
import {validateQuery,oracleDate,normalizeOracleDate,dateEditOrder} from '../connector/oracle-scope.mjs';
test('scope includes all three observed Oracle states and only 2026',()=>{
  assert.deepEqual(validateQuery(),{from:'2026-01-01',to:'2026-12-31',states:['Abierta','Inscrito','Perdida']});
  for(const query of [{from:'2025-12-31'},{to:'2027-01-01'},{from:'2026-02-30'},
    {from:'2026-13-01'},{from:'2026-06-01',to:'2026-01-01'},{states:[]},{states:['Unknown']},{states:['Abierta','Abierta']}])assert.throws(()=>validateQuery(query));
});
test('Oracle date conversions preserve the requested calendar boundaries',()=>{
  assert.equal(oracleDate('2026-01-31'),'31/01/26');
  assert.equal(normalizeOracleDate('31/01/26'),'2026-01-31');
  assert.equal(normalizeOracleDate('1/2/2026'),'2026-02-01');
});

test('moving between intervals never puts the start after the end during editing',()=>{
 for(const [oldFrom,oldTo,from,to] of [
  ['2026-01-01','2026-01-31','2026-02-01','2026-02-28'],
  ['2026-12-01','2026-12-31','2026-01-01','2026-01-31'],
  ['2026-01-01','2026-01-31','2026-01-01','2026-01-16'],
  ['2026-01-01','2026-01-16','2026-01-17','2026-01-31']]){
  let left=oldFrom,right=oldTo;
  for(const [label,value] of dateEditOrder(oldTo,from,to)){
   if(label==='De Fecha de cierre')left=value;else right=value;
   assert.ok(left<=right);
  }
  assert.equal(left,from);assert.equal(right,to);
 }
});

import '../app/static/table-tools.js';
import '../app/static/workbook-views.js';
import test from 'node:test';
import assert from 'node:assert/strict';
const tools=globalThis.UnisTableTools, book=globalThis.UnisWorkbookViews;
const rows=[{opportunity_number:'SYNTHETIC-10',probability:'9',test_date:'03/11/26'},{opportunity_number:'SYNTHETIC-2',probability:'100',test_date:'15/02/2026'},{opportunity_number:'SYNTHETIC-3',probability:'',test_date:''}];
test('numeric/date sorting and missing values stay last in both directions',()=>{
 const get=(r,k)=>r[k];
 assert.deepEqual(tools.sort(rows,'probability','asc',get).map(r=>r.probability),['9','100','']);
 assert.deepEqual(tools.sort(rows,'probability','desc',get).map(r=>r.probability),['100','9','']);
 assert.equal(tools.sort(rows,'test_date','asc',get)[0].opportunity_number,'SYNTHETIC-2');
 assert.equal(tools.sort(rows,'opportunity_number','asc',get)[0].opportunity_number,'SYNTHETIC-2');
 assert.equal(rows[0].opportunity_number,'SYNTHETIC-10');
});
test('sorts full result before paging, clamps page and supports all',()=>{
 const data=Array.from({length:31},(_,i)=>({opportunity_number:'SYNTHETIC-'+i,probability:i}));
 assert.equal(tools.paginate(tools.sort(data,'probability','desc',(r,k)=>r[k]),12,1).rows[0].probability,30);
 assert.equal(tools.paginate(data,25,99).page,2);
 assert.equal(tools.paginate(data,'all',99).rows.length,31);
 assert.deepEqual([tools.paginate([],12,2).start,tools.paginate([],12,2).end],[0,0]);
});
test('all workbook views have labels and only explicit dates define cohorts',()=>{
 assert.equal(book.views.length,26);assert.equal(new Set(book.views.map(v=>v.name)).size,26);
 for(const view of book.views)for(const key of view.fields)assert.ok(book.fields[key],key);
 assert.equal(book.date('11 de noviembre de 2026'),'2026-11-11');
 assert.equal(book.date('11 noviembre'),'');
 assert.equal(book.filter([{test_date:''}],book.views.find(v=>v.name==='PDA 11Noviembre'),(r,k)=>r[k]||'').length,0);
});
test('commercial amount, interview indicator and stage do not create payment or attendance',()=>{
 const r={amount:'100',stage:'05 - Matriculado',interview:'Si',opportunity_number:'SYNTHETIC-1'};
 for(const key of ['payment_amount','attended_interview','attended_test','letter_delivered'])assert.equal(book.derive(r,key,(r,k)=>r[k]||'',{}),'');
 assert.equal(book.derive(r,'interview_date',(r,k)=>r[k]||'',{details:{'SYNTHETIC-1':{activities:{rows:[{type:'Tarea',subject:'entrevista',date:'2026-11-11'}]}}}}),'');
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeGrid,collectOpportunities,readOpportunityGrid} from '../connector/oracle-sync.mjs';
const grid=(number='SYNTHETIC-001')=>({headers:['Número de oportunidad','Nombre','Etapa de ventas','Correo electrónico de responsable'],rows:[[number,'Oportunidad ficticia','01 - Interesado','ficticio@example.invalid']]});
test('collector excludes fields outside the allowlist',()=>{
  const [row]=normalizeGrid(grid());
  assert.equal(row.opportunity_number,'SYNTHETIC-001');assert.equal(Object.keys(row).length,3);
  assert.ok(!JSON.stringify(row).includes('@'));
});
test('rejects an unrecognized layout and empty official IDs',()=>{
  assert.throws(()=>normalizeGrid({headers:[],rows:[]}));assert.equal(normalizeGrid(grid('')).length,0);
});
test('deduplicates virtual pages and declares a partial result',async()=>{
  let i=0;
  const adapter={ui:{evaluate:async()=>({headers:grid().headers,rows:[...grid('SYNTHETIC-001').rows,...grid('SYNTHETIC-'+i).rows]})},observe:async()=>{},scrollGrid:async()=>{i++;},maxRows:4};
  const result=await collectOpportunities(adapter);
  assert.equal(result.records.length,4);assert.equal(result.partial,true);
  assert.equal(new Set(result.records.map(r=>r.opportunity_number)).size,4);
});
test('does not publish a blank query as a successful refresh',async()=>{
  await assert.rejects(collectOpportunities({ui:{evaluate:async()=>({headers:grid().headers,rows:[]})},observe:async()=>{},scrollGrid:async()=>{}}),/empty/);
});

// ADF can retain the activity header before the active opportunities header.
test('uses the opportunity header when an earlier panel has another table',()=>{
  const table=(summary,rows)=>({getAttribute:()=>summary,rows:rows.map(r=>({cells:r.map(innerText=>({innerText}))}))});
  const tables=[table('Esta tabla contiene cabeceras',[['Actividad','Asunto']]),
    table('Esta tabla contiene cabeceras',[grid().headers]),table('Oportunidad',grid().rows)];
  const previous=globalThis.document;
  try {
    globalThis.document={querySelectorAll:()=>tables};
    assert.equal(normalizeGrid(readOpportunityGrid())[0].opportunity_number,'SYNTHETIC-001');
  } finally {globalThis.document=previous;}
});


import {decodeExport} from '../connector/export-codec.mjs';
test('keeps Spanish accents and symbols from UTF-8 and legacy export encodings',()=>{
 const text='<meta charset="utf-8"><p>Prueba sintética: Muñoz, María, §, 25 %</p>';
 assert.equal(decodeExport(Buffer.from(text,'utf8')),text);
 const legacy='<meta charset="windows-1252"><p>Muñoz y María</p>';
 assert.equal(decodeExport(Buffer.from(legacy,'latin1')),legacy);
 assert.equal(decodeExport(Buffer.from('Muñoz','latin1')),'Muñoz');
 assert.throws(()=>decodeExport(Buffer.from('<meta charset="utf-8">Muñoz','latin1')));
 assert.throws(()=>decodeExport(Buffer.from('<meta charset="unsupported">')));
});
import {openCachedDetail,readSummaryDetail,configureQuery} from '../connector/oracle-sync.mjs';
test('opens Summary explicitly when Oracle remembers the Contacts subtab',async()=>{
 let summarySelected=false;
 const locator={nth(){return this;},getByRole(){return this;},press:async()=>{}};
 const ui={evaluate:async(fn,arg)=>arg?{table:0,row:0}:fn===readSummaryDetail&&summarySelected?{fields:{}}:null,
 getByRole:(role,{name})=>name==='Resumen'?{count:async()=>1,click:async()=>{summarySelected=true;}}:role==='button'?{count:async()=>1}:locator};
 await openCachedDetail({ui,observe:async()=>{},scrollGrid:async()=>{}},'SYNTHETIC-001');
 assert.equal(summarySelected,true);
});
test('does not collapse an advanced search that is already expanded',async()=>{
 let toggles=0;
 const make=(role,name)=>({last(){return this;},count:async()=>name==='Cancelar'?0:1,click:async()=>{},fill:async()=>{}});
 const ui={getByRole:(role,{name})=>make(role,name),evaluate:async()=>grid()};
 await configureQuery({ui,observe:async()=>{},clickAdvanced:async()=>{toggles++;}});
 assert.equal(toggles,0);
});
import {readBlockingValidation,readValidationField} from '../connector/contact-reader.mjs';
test('detects rendered Oracle validation and reports only an allowed field key',()=>{
 const previous=globalThis.document;
 try{
  globalThis.document={activeElement:{id:'synthetic-control'},querySelectorAll:selector=>selector==='label'?[{htmlFor:'synthetic-control',innerText:'Convocatoria PA'}]:[{getClientRects:()=>[{}],closest:()=>({innerText:'Error: Se necesita una selección. Debe seleccionar al menos una opción.'})}]};
  assert.equal(readBlockingValidation(),true);assert.equal(readValidationField(),'test_call');
  globalThis.document.querySelectorAll=()=>[];
  assert.equal(readBlockingValidation(),false);assert.equal(readValidationField(),'');
 }finally{globalThis.document=previous;}
});

test('opens advanced filters even when an old hide label remains in the page',async()=>{
 let expanded=false,toggles=0;
 const make=(name)=>({last(){return this;},count:async()=>name==='Cancelar'?0:name==='Juego de registros'?(expanded?1:0):1,click:async()=>{},fill:async()=>{}});
 const ui={getByRole:(role,{name})=>make(name),evaluate:async()=>grid()};
 await configureQuery({ui,observe:async()=>{},clickAdvanced:async()=>{toggles++;expanded=true;}});
 assert.equal(toggles,1);assert.equal(expanded,true);
});

import {ensureAdvancedSearch} from '../connector/oracle-query.mjs';
test('opens the checkbox variant of Oracle advanced search',async()=>{
 let expanded=false,checked=0;
 const ui={getByRole:(role,{name})=>({first(){return this;},count:async()=>name==='Juego de registros'?(expanded?1:0):role==='checkbox'&&name==='Mostrar búsqueda avanzada'?1:0,check:async()=>{checked++;expanded=true;}})};
 await ensureAdvancedSearch(ui,async()=>{});
 assert.equal(checked,1);assert.equal(expanded,true);
});
test('leaves already available advanced filters unchanged',async()=>{
 const ui={getByRole:()=>({count:async()=>1})};
 await ensureAdvancedSearch(ui,async()=>{throw Error('Should not toggle');});
});

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

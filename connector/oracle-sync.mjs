import {collectRelatedContact,readBlockingValidation,readValidationField} from './contact-reader.mjs';
/** Browser UI collector. No Oracle HTTP calls, credentials, files or raw logs. */
export const SCOPE = 'Todos los registros que puedo ver · oportunidades abiertas · año actual';
const COLUMNS = {
  'Número de oportunidad':'opportunity_number',
  'Nombre de contacto principal':'first_name',
  'Apellido de contacto principal':'last_name',
  'Nombre':'name','Cuenta':'account','Fecha de cierre':'close_date',
  'Éxito (%)':'probability','Etapa de ventas':'stage','Estado':'status',
  'Segmento':'segment','Contacto principal':'contact_name','Responsable':'owner',
  'Teléfono':'phone','Fecha de creación de oportunidad':'created_at',
  'Última actualización de oportunidad':'updated_at'
};

// Runs only against the visible, rendered document. No application internals.
export function readOpportunityGrid() {
  const tables=Array.from(document.querySelectorAll('table'));
  const header=tables.find(t=>t.getAttribute('summary')?.startsWith('Esta tabla')&&Array.from(t.rows).some(r=>Array.from(r.cells).some(c=>c.innerText.trim()==='Número de oportunidad')));
  const bodies=tables.filter(t=>t.getAttribute('summary')==='Oportunidad');
  if(!header || !bodies.length) return null;
  const headerRows=Array.from(header.rows).map(r=>Array.from(r.cells).map(c=>c.innerText.trim()));
  const headers=headerRows.find(r=>r.includes('Número de oportunidad'));
  if(!headers) return null;
  return {headers, rows:bodies.flatMap(t=>Array.from(t.rows).map(r=>Array.from(r.cells).map(c=>c.innerText.trim())))};
}

export function normalizeGrid(grid) {
  if(!grid || !grid.headers.includes('Número de oportunidad')) throw Error('layout');
  return grid.rows.filter(row=>row.length===grid.headers.length).map(row=>{
    const out={};
    grid.headers.forEach((label,i)=>{if(COLUMNS[label]) out[COLUMNS[label]]=row[i];});
    return out;
  }).filter(r=>r.opportunity_number && /^[A-Za-z0-9_-]{1,80}$/.test(r.opportunity_number));
}

async function ready(adapter,predicate) {
  for(let attempt=0;attempt<40;attempt++) {
    await adapter.observe();
    try{if(await predicate())return;}catch{/* ADF may detach the old table while replacing it. */}
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  throw Error('timeout');
}

export async function openOpportunityQuery(adapter) {
  const {ui,observe}=adapter;
  const priorDetail=ui.getByRole('button',{name:'Cancelar',exact:true}).last();
  if(await priorDetail.count()) {
    await priorDetail.click();await observe();
    await ready(adapter,async()=>await ui.getByRole('button',{name:'Cancelar',exact:true}).count()===0);
  }
  if(!await ui.getByRole('tab',{name:'Ventas',exact:true}).count()) {
    const home=ui.getByRole('link',{name:'Página Inicial',exact:true});
    if(!await home.count()) throw Error('session');
    await home.click();await observe();
  }
  await ready(adapter,async()=>await ui.getByRole('tab',{name:'Ventas',exact:true}).count()>0);
  await ui.getByRole('tab',{name:'Ventas',exact:true}).click();
  await ui.getByRole('link',{name:'Oportunidades',exact:true}).click();await observe();
  await ready(adapter,async()=>await ui.getByRole('heading',{name:'Oportunidades',exact:true}).count()>0);
  const lateDetail=ui.getByRole('button',{name:'Cancelar',exact:true}).last();
  if(await lateDetail.count()){await lateDetail.click();await ready(adapter,async()=>await ui.getByRole('button',{name:'Cancelar',exact:true}).count()===0);}
  // ADF's checkbox is exposed inconsistently to DOM role locators; the adapter
  // performs its supported UI click using a fresh accessibility observation.
}

export async function collectOpportunities({ui,observe,scrollGrid,maxRows=240,maxScrolls=25,onProgress=()=>{}}) {
  const records=new Map();let unchanged=0;
  for(let step=0;step<=maxScrolls;step++) {
    await observe();
    const grid=await ui.evaluate(readOpportunityGrid);
    const rows=normalizeGrid(grid);
    const before=records.size;
    for(const row of rows) {
      if(records.size>=maxRows&&!records.has(row.opportunity_number)) break;
      records.set(row.opportunity_number,row);
    }
    onProgress(records.size);
    unchanged=records.size===before?unchanged+1:0;
    if(records.size>=maxRows || unchanged>=3 || step===maxScrolls) break;
    await scrollGrid();
  }
  if(!records.size) throw Error('empty');
  // No reliable total is exposed by this virtual table. Never claim complete.
  return {records:[...records.values()],scope:SCOPE,partial:true};
}

export async function localRequest(base,path,body,headers={}) {
  const url=new URL(path,base);
  if(url.protocol!=='http:' || !['127.0.0.1','localhost'].includes(url.hostname)) throw Error('local-target');
  const {request}=await import('node:http');
  return await new Promise((resolve,reject)=>{
    const data=body===undefined?'':JSON.stringify(body);
    const req=request(url,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data),...headers}},res=>{
      let response='';res.on('data',c=>response+=c);res.on('end',()=>{
        try {const parsed=JSON.parse(response);if(res.statusCode>=400)return reject(Error('local-import'));resolve(parsed);}
        catch{reject(Error('local-import'));}
      });
    });req.on('error',()=>reject(Error('local-unavailable')));req.end(data);
  });
}

export async function deliverToLocal(base,payload) {
  const {ticket}=await localRequest(base,'/api/oracle/ticket',{});
  return await localRequest(base,'/api/oracle/import',payload,{'X-Sync-Ticket':ticket});
}

/** In-app adapter: all Oracle interaction stays in the supported CUA API. */
export function inAppAdapter(tab) {
  return {
    ui:tab.playwright,
    observe:()=>tab.getAXState({emit:false}),
    clickAdvanced:async()=>{
      const state=await tab.getAXState({emit:false,disableDiffing:true});
      const match=state.match(/^\s*(\d+) checkbox Mostrar búsqueda avanzada(?:,.*)?\s*$/m);
      if(match) await tab.click(Number(match[1]));
      else if(!state.includes('Ocultar búsqueda avanzada')) throw Error('layout');
    },
    scrollGrid:async(direction='down',pages=4)=>{
      const state=await tab.getAXState({emit:false,disableDiffing:true});
      const matches=[...state.matchAll(/^\s*(\d+) table Oportunidad\s*$/gm)];
      if(!matches.length) throw Error('layout');
      await tab.scroll(Number(matches[matches.length-1][1]),direction,pages);
    }
  };
}

export async function configureQuery(adapter) {
  const {ui,observe,clickAdvanced}=adapter;
  adapter.phase='open_query';
  await openOpportunityQuery(adapter);
  adapter.phase='advanced_ready';
  await ready(adapter,async()=>await ui.getByRole('button',{name:'Mostrar búsqueda avanzada',exact:true}).count()>0||await ui.getByRole('button',{name:'Ocultar búsqueda avanzada',exact:true}).count()>0||await ui.getByRole('checkbox',{name:'Mostrar búsqueda avanzada',exact:true}).count()>0||await ui.getByRole('checkbox',{name:'Ocultar búsqueda avanzada',exact:true}).count()>0);
  adapter.phase='advanced_toggle';
  if(!await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).count())await clickAdvanced();
  await observe();
  adapter.phase='scope_ready';
  await ready(adapter,async()=>await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).count()>0);
  adapter.phase='scope_filter';await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).click();
  await ui.getByRole('option',{name:'Todos los registros que puedo ver',exact:true}).click();
  adapter.phase='period_filter';await ui.getByRole('combobox',{name:'Período de cierre',exact:true}).click();
  await ui.getByRole('option',{name:'Año actual',exact:true}).click();
  for(const label of ['Nombre','Número de oportunidad']) {
    const filter=ui.getByRole('textbox',{name:label,exact:true});
    if(await filter.count())await filter.fill('');
  }
  adapter.phase='run_search';await ui.getByRole('button',{name:'Buscar',exact:true}).last().click();await observe();
  await ready(adapter,async()=>{const grid=await ui.evaluate(readOpportunityGrid);return !!grid?.rows?.length;});
}

/** Starts a reusable local bridge. Status and data remain in process memory. */
export async function processOneJob(adapter,base,{maxRows=120}={}) {
  await localRequest(base,'/api/oracle/heartbeat',{});
  const {job}=await localRequest(base,'/api/oracle/claim',{});
  if(!job)return null;
  try {
    if(job.kind==='detail') {
      const payload=await collectOpportunityDetail(adapter,job.opportunity_number);
      const {ticket}=await localRequest(base,'/api/oracle/ticket',{});
      return await localRequest(base,'/api/oracle/details/import',payload,{'X-Sync-Ticket':ticket});
    }
    await configureQuery(adapter);
    if(job.kind==='details_batch') {
      while((await localRequest(base,'/api/oracle/batch')).pending.length)
        await processDetailSlice(adapter,base,{limit:3});
      return localRequest(base,'/api/oracle/status');
    }
    let payload=await collectOpportunities({...adapter,maxRows});
    const result=await deliverToLocal(base,payload);payload=null;
    return result;
  } catch(error) {
    const code=['empty','layout','session'].includes(error.message)?error.message:'timeout';
    const {ticket}=await localRequest(base,'/api/oracle/ticket',{});
    await localRequest(base,'/api/oracle/fail',{code},{'X-Sync-Ticket':ticket});
    // Deliberately do not surface diagnostic text, which may include row data.
    return {failed:true,code,phase:adapter.phase||'unknown'};
  }
}

export function readSummaryDetail() {
  const root=Array.from(document.querySelectorAll('div')).find(d=>d.id.endsWith(':OpportunitySummaryPgl1')&&d.getClientRects().length);
  if(!root)return null;
  const labels={
    'Ciclo de Ingreso':'cycle','Año':'year','Estado Proceso Admision':'admission_status',
    'Convocatoria PA':'test_call','Prueba de Admisión':'test_type','Fecha PA':'test_date',
    'Tipo de Prueba':'test_route','Proceso PAA':'paa_process','Convenio PA':'agreement',
    'Resolución':'resolution','Entrevista':'interview','Asistencia Economica':'financial_aid',
    'Tipo Asistencia Economica 1':'financial_type_1','Porcentaje Solicitado AE1':'financial_requested_1',
    'Porcentaje Otorgado AE1':'financial_granted_1','Estatus':'financial_status',
    'Fecha limite entrega papeleria':'documents_due','Razon Retraso Pago de Matricula':'tuition_delay_reason',
    'Cierre Reserva de cupo':'reservation_close','Importe':'amount','Origen':'origin',
    'Nombre':'name','Responsable':'owner','Etapa de ventas':'stage',
    'Probabilidad de ganar (%)':'probability','Fecha de cierre':'close_date',
    'Puntaje Global':'global_score','Puntaje PAA':'paa_score','Promedio':'grade_average','Puntaje Requerido':'required_score','Tipo Asistencia Economica 2':'financial_type_2','Porcentaje Solicitado AE 2':'financial_requested_2','Porcentaje Otorgado AE 2':'financial_granted_2','Aceptacion':'financial_acceptance','Comentarios Asistencia Economica':'financial_comments'
  };
  const fields={},capabilities={},priority={};
  for(const label of root.querySelectorAll('label')) {
    const key=labels[label.innerText.trim()];if(!key)continue;
    const control=label.htmlFor?document.getElementById(label.htmlFor):null;
    let value='';let editable=false;
    if(control?.matches('input,textarea,select')) {
      value=control.value??'';
      editable=!control.disabled&&control.getAttribute('aria-disabled')!=='true'&&(!control.readOnly||control.getAttribute('role')==='combobox');
    } else {
      const row=label.closest('tr');const cell=row?.cells[row.cells.length-1];
      if(cell&&!cell.contains(label))value=cell.innerText.trim();
    }
    const rank=control?.matches('input,textarea,select')?2:1;
    if(!(key in fields)||(priority[key]||0)<rank){fields[key]=value.trim();priority[key]=rank;}
    capabilities[key]=!!(capabilities[key]||editable);
  }
  return {fields,capabilities};
}

export function readLinkedActivities() {
  const table=Array.from(document.querySelectorAll('table')).find(t=>t.getAttribute('summary')==='Resumen');
  if(!table)return {queried:false,rows:[]};
  const keys=['activity','subject','date','owner',null,'type','priority'];
  const rows=Array.from(table.rows).slice(0,100).filter(r=>r.cells.length===7).map(r=>{
    const out={};Array.from(r.cells).forEach((cell,i)=>{if(keys[i])out[keys[i]]=cell.innerText.trim();});return out;
  });return {queried:true,rows};
}

export async function collectOpportunityDetail(adapter,number,{reuseQuery=false}={}) {
  if(!reuseQuery)await configureQuery(adapter);
  adapter.phase='select_record';await selectOpportunityByNumber(adapter,number);
  adapter.phase='open_detail';await openCachedDetail(adapter,number);
  adapter.phase='capture_detail';const payload=await captureOpenDetail(adapter,number);
  try {
    if(!payload.pending_modules?.includes('contact')){
      adapter.phase='linked_contact';const contact=await collectRelatedContact(adapter);
      Object.assign(payload.fields,contact.fields);Object.assign(payload.capabilities,contact.capabilities);
      if(contact.pending){payload.pending_modules=[...(payload.pending_modules||[]),'contact'];payload.module_reason='validation';payload.validation_field=contact.validation_field||'';}
    }
    payload.schema_version=2;
  } finally {
    adapter.phase='close_detail';
    try{await closeCachedDetail(adapter);}catch{adapter.discardPage=true;}
  }
  return payload;
}

export async function selectOpportunityByNumber(adapter,number) {
  const filter=adapter.ui.getByRole('textbox',{name:'Número de oportunidad',exact:true});
  if(!await filter.count()) {
    await adapter.ui.getByRole('button',{name:'Agregar',exact:true}).click();
    await adapter.observe();
    await adapter.ui.getByRole('menuitem',{name:'Número de oportunidad',exact:true}).click();
    await ready(adapter,async()=>await filter.count()>0);
  }
  await adapter.ui.getByRole('textbox',{name:'Nombre',exact:true}).fill('');
  await filter.fill(number);
  await adapter.ui.getByRole('button',{name:'Buscar',exact:true}).last().press('Enter');
  await ready(adapter,async()=>{const grid=await adapter.ui.evaluate(readOpportunityGrid);return !!grid?.rows.some(r=>r[0]?.trim()===number);});
}

export function startWorker(adapter,base,{maxRows=120,pollMs=2500}={}) {
  let stopping=false;
  const finished=(async()=>{
    while(!stopping) {
      try {
        await processOneJob(adapter,base,{maxRows});
      } catch { /* Retry local availability only; never log raw exceptions. */ }
      await new Promise(resolve=>setTimeout(resolve,pollMs));
    }
  })();
  return {stop:()=>{stopping=true;},finished};
}

/** Reuses the list between records; Enter opens off-screen ADF links reliably. */
export async function openCachedDetail(adapter,number) {
  const {ui}=adapter;
  let match;
  for(let step=0;step<30;step++) {
    match=await ui.evaluate(number=>{
      const tables=Array.from(document.querySelectorAll('table')).filter(t=>t.getAttribute('summary')==='Oportunidad');
      for(let table=0;table<tables.length;table++)for(let row=0;row<tables[table].rows.length;row++)
        if(tables[table].rows[row].cells[0]?.innerText.trim()===number)return {table,row};
      return null;
    },number);
    if(match)break;
    await adapter.scrollGrid('down',2);await adapter.observe();
  }
  if(!match)throw Error('record-not-in-query');
  await ui.getByRole('table',{name:'Oportunidad',exact:true}).nth(match.table).getByRole('row').nth(match.row).getByRole('cell').nth(3).getByRole('link').press('Enter');
  await ready(adapter,async()=>await ui.getByRole('button',{name:'Guardar y Cerrar',exact:true}).count()>0);
  // Oracle remembers the last subtab (for example Contacts) between records.
  // Always open Summary before reading, instead of waiting on a hidden panel.
  const summary=ui.getByRole('link',{name:'Resumen',exact:true});
  await ready(adapter,async()=>await summary.count()>0);
  if(!await ui.evaluate(readSummaryDetail)){await summary.click();await ready(adapter,async()=>!!await ui.evaluate(readSummaryDetail));}
}

export async function captureOpenDetail(adapter,number,{activities=true}={}) {
  const {ui}=adapter;
  for(const [expand,collapse] of [['Ampliar Asistencia Economica','Reducir Asistencia Economica'],['Ampliar Información Adicional','Reducir Información Adicional']]) {
    const button=ui.getByRole('button',{name:expand,exact:true});
    if(await button.count()) {
      await button.click();
      await ready(adapter,async()=>await ui.getByRole('button',{name:collapse,exact:true}).count()>0);
    }
  }
  await ready(adapter,async()=>!!await ui.evaluate(readSummaryDetail));
  const detail=await ui.evaluate(readSummaryDetail);
  let linked={queried:false,rows:[]};
  if(activities) {
    const link=ui.getByRole('link',{name:'Actividades',exact:true});
    if(await link.count()) {
      await link.click();
      await ready(adapter,async()=>await ui.getByRole('combobox',{name:'Mostrar',exact:true}).count()>0||await ui.evaluate(readBlockingValidation));
      if(!await ui.getByRole('combobox',{name:'Mostrar',exact:true}).count()&&await ui.evaluate(readBlockingValidation))return {opportunity_number:number,...detail,activities:linked,pending_modules:['activities','contact'],module_reason:'validation',validation_field:await ui.evaluate(readValidationField)};
      const filter=ui.getByRole('combobox',{name:'Mostrar',exact:true});
      const current=await filter.evaluate(e=>e.value);
      if(current!=='Todas las actividades') {
        await filter.click();
        await ui.getByRole('option',{name:'Todas las actividades',exact:true}).click();
        await ui.getByRole('button',{name:'Buscar',exact:true}).last().press('Enter');
      }
      await adapter.observe();await adapter.observe();
      linked=await ui.evaluate(readLinkedActivities);
    }
  }
  return {opportunity_number:number,...detail,activities:linked};
}

export async function closeCachedDetail(adapter) {
  const cancel=adapter.ui.getByRole('button',{name:'Cancelar',exact:true}).last();
  if(await cancel.count()) {
    await cancel.click();
    await ready(adapter,async()=>await adapter.ui.getByRole('button',{name:'Cancelar',exact:true}).count()===0);
  }
}

export function domAdapter(tab) {
  return {
    ui:tab.playwright,
    observe:()=>tab.playwright.domSnapshot(),
    scrollGrid:async(direction='down')=>{
      const table=tab.playwright.getByRole('table',{name:'Oportunidad',exact:true}).last();
      const lastLink=table.getByRole('row').last().getByRole('link').last();
      await lastLink.press(direction==='up'?'PageUp':'PageDown');
    }
  };
}

export async function deliverDetail(base,payload) {
  const {ticket}=await localRequest(base,'/api/oracle/ticket',{});
  return localRequest(base,'/api/oracle/details/import',payload,{'X-Sync-Ticket':ticket});
}

export async function processDetailSlice(adapter,base,{limit=3,maxMillis=35000}={}) {
  const started=Date.now();let completed=0;
  let queue=await localRequest(base,'/api/oracle/batch');
  for(let index=0;index<limit;index++) {
    if(Date.now()-started>maxMillis)break;
    queue=await localRequest(base,'/api/oracle/batch');
    if(!queue.pending.length)break;
    const rendered=await adapter.ui.evaluate(()=>Array.from(document.querySelectorAll('table')).filter(t=>t.getAttribute('summary')==='Oportunidad').flatMap(t=>Array.from(t.rows).map(r=>r.cells[0]?.innerText.trim())));
    let number=queue.pending.find(n=>rendered.includes(n));
    if(!number) {
      number=queue.pending[0];
      await selectOpportunityByNumber(adapter,number);
    }
    await openCachedDetail(adapter,number);
    let payload=await captureOpenDetail(adapter,number);
    await deliverDetail(base,payload);payload=null;
    await closeCachedDetail(adapter);
    completed++;
  }
  return {completed,pending:(await localRequest(base,'/api/oracle/batch')).pending.length};
}

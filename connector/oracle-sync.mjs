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
  const header=tables.find(t=>t.getAttribute('summary')?.startsWith('Esta tabla'));
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
  for(let attempt=0;attempt<10;attempt++) {
    await adapter.observe();
    try{if(await predicate())return;}catch{/* ADF may detach the old table while replacing it. */}
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
  adapter.phase='advanced_search';await clickAdvanced();await observe();
  await ready(adapter,async()=>await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).count()>0);
  adapter.phase='scope_filter';await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).click();
  await ui.getByRole('option',{name:'Todos los registros que puedo ver',exact:true}).click();
  adapter.phase='period_filter';await ui.getByRole('combobox',{name:'Período de cierre',exact:true}).click();
  await ui.getByRole('option',{name:'Año actual',exact:true}).click();
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
  const root=Array.from(document.querySelectorAll('div')).find(d=>d.id.endsWith(':OpportunitySummaryPgl1'));
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
    'Probabilidad de ganar (%)':'probability','Fecha de cierre':'close_date'
  };
  const fields={},capabilities={},priority={};
  for(const label of root.querySelectorAll('label')) {
    const key=labels[label.innerText.trim()];if(!key)continue;
    const control=label.htmlFor?document.getElementById(label.htmlFor):null;
    let value='';let editable=false;
    if(control?.matches('input,textarea,select')) {
      value=control.value||control.getAttribute('title')||'';
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

export async function collectOpportunityDetail(adapter,number) {
  const {ui,observe,scrollGrid}=adapter;
  await configureQuery(adapter);
  adapter.phase='find_record';
  let match=null;
  for(let step=0;step<25;step++) {
    await observe();
    match=await ui.evaluate(number=>{
      const tables=Array.from(document.querySelectorAll('table')).filter(t=>t.getAttribute('summary')==='Oportunidad');
      for(let table=0;table<tables.length;table++)for(let row=0;row<tables[table].rows.length;row++)
        if(tables[table].rows[row].cells[0]?.innerText.trim()===number){
          const bounds=tables[table].rows[row].getBoundingClientRect(),clip=tables[table].parentElement.getBoundingClientRect();
          const top=Math.max(clip.top,0),bottom=Math.min(clip.bottom,window.innerHeight);
          if(bounds.top>=top&&bounds.bottom<=bottom)return {table,row};
          return {offscreen:true,direction:bounds.top<top?'up':'down'};
        }
      return null;
    },number);
    if(match&&!match.offscreen)break;
    await scrollGrid(match?.direction||'down',1);match=null;
  }
  if(!match)throw Error('empty');
  adapter.phase='open_record';await ui.getByRole('table',{name:'Oportunidad',exact:true}).nth(match.table).getByRole('row').nth(match.row).getByRole('cell').nth(3).getByRole('link').click();
  await observe();
  await ready(adapter,async()=>await ui.getByRole('button',{name:'Guardar y Cerrar',exact:true}).count()>0);
  adapter.phase='expand_modules';for(const title of ['Ampliar Asistencia Economica','Ampliar Información Adicional']) {
    const button=ui.getByRole('button',{name:title,exact:true});if(await button.count()){await button.click();await observe();}
  }
  await observe();
  adapter.phase='read_fields';const detail=await ui.evaluate(readSummaryDetail);if(!detail)throw Error('layout');
  let activities={queried:false,rows:[]};
  const activityLink=ui.getByRole('link',{name:'Actividades',exact:true});
  if(await activityLink.count()) {
    adapter.phase='open_activities';await activityLink.click();await observe();
    const filter=ui.getByRole('combobox',{name:'Mostrar',exact:true});
    if(await filter.count()) {
      adapter.phase='activities_filter';await filter.click();await ui.getByRole('option',{name:'Todas las actividades',exact:true}).click();
      await ui.getByRole('button',{name:'Buscar',exact:true}).last().click();await observe();
    }
    adapter.phase='read_activities';await observe();activities=await ui.evaluate(readLinkedActivities);
  }
  adapter.phase='close_detail';const close=ui.getByRole('button',{name:'Cancelar',exact:true}).last();
  await close.click();await ready(adapter,async()=>await ui.getByRole('button',{name:'Cancelar',exact:true}).count()===0);
  return {opportunity_number:number,...detail,activities};
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

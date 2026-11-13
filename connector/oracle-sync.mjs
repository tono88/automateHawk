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

export async function openOpportunityQuery({ui,observe}) {
  if(!await ui.getByRole('tab',{name:'Ventas',exact:true}).count()) {
    const home=ui.getByRole('link',{name:'Página Inicial',exact:true});
    if(!await home.count()) throw Error('session');
    await home.click();await observe();
  }
  await ui.getByRole('tab',{name:'Ventas',exact:true}).waitFor({state:'visible',timeoutMs:20000});
  await ui.getByRole('tab',{name:'Ventas',exact:true}).click();
  await ui.getByRole('link',{name:'Oportunidades',exact:true}).click();await observe();
  await ui.getByRole('heading',{name:'Oportunidades',exact:true}).waitFor({state:'visible',timeoutMs:20000});
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
    const data=JSON.stringify(body);
    const req=request(url,{method:'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data),...headers}},res=>{
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
    scrollGrid:async()=>{
      const state=await tab.getAXState({emit:false,disableDiffing:true});
      const matches=[...state.matchAll(/^\s*(\d+) table Oportunidad\s*$/gm)];
      if(!matches.length) throw Error('layout');
      await tab.scroll(Number(matches[matches.length-1][1]),'down',4);
    }
  };
}

export async function configureQuery(adapter) {
  const {ui,observe,clickAdvanced}=adapter;
  await openOpportunityQuery(adapter);
  await clickAdvanced();await observe();
  await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).waitFor({state:'visible',timeoutMs:20000});
  await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).click();
  await ui.getByRole('option',{name:'Todos los registros que puedo ver',exact:true}).click();
  await ui.getByRole('combobox',{name:'Período de cierre',exact:true}).click();
  await ui.getByRole('option',{name:'Año actual',exact:true}).click();
  await ui.getByRole('button',{name:'Buscar',exact:true}).last().click();await observe();
  await ui.getByRole('table',{name:'Oportunidad',exact:true}).first().getByRole('row').first().waitFor({state:'visible',timeoutMs:20000});
}

/** Starts a reusable local bridge. Status and data remain in process memory. */
export async function processOneJob(adapter,base,{maxRows=120}={}) {
  await localRequest(base,'/api/oracle/heartbeat',{});
  const {job}=await localRequest(base,'/api/oracle/claim',{});
  if(!job)return null;
  try {
    await configureQuery(adapter);
    let payload=await collectOpportunities({...adapter,maxRows});
    const result=await deliverToLocal(base,payload);payload=null;
    return result;
  } catch(error) {
    const code=['empty','layout','session'].includes(error.message)?error.message:'timeout';
    const {ticket}=await localRequest(base,'/api/oracle/ticket',{});
    await localRequest(base,'/api/oracle/fail',{code},{'X-Sync-Ticket':ticket});
    // Deliberately do not surface diagnostic text, which may include row data.
    return {failed:true,code};
  }
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

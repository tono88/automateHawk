import {waitForRendered} from './ui-wait.mjs';
export const QUERY_YEAR=2026;
export const OPPORTUNITY_STATES=['Abierta','Inscrito','Perdida'];
export function validateQuery(query={}){
  const from=query.from||`${QUERY_YEAR}-01-01`,to=query.to||`${QUERY_YEAR}-12-31`;
  const valid=s=>typeof s==='string'&&/^2026-\d{2}-\d{2}$/.test(s)&&Number.isFinite(new Date(s+'T00:00:00Z').getTime())&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
  const states=query.states||OPPORTUNITY_STATES;
  if(!valid(from)||!valid(to)||from>to||!Array.isArray(states)||!states.length||states.length>3||new Set(states).size!==states.length||states.some(s=>!OPPORTUNITY_STATES.includes(s)))throw Error('scope');
  return {from,to,states};
}
export function oracleDate(iso){const [y,m,d]=iso.split('-');return `${d}/${m}/${y.slice(2)}`;}
export function normalizeOracleDate(value){
  const m=value.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})$/);
  return m?`${m[3].length===2?'20'+m[3]:m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`:value;
}
export async function applyOpportunityScope(adapter,query){
  const {ui}=adapter,{from,to,states}=validateQuery(query);
  adapter.scopeDiagnostic={requested:{from,to,states}};
  const settle=async()=>{if(adapter.settleFilters)await adapter.settleFilters();else await adapter.observe();};
  const choose=async(name,value)=>{
    const control=ui.getByRole('combobox',{name,exact:true});
    if(await control.evaluate(e=>e.value)!==value){const arrow=ui.locator('span[id$="::cntrl"]').filter({has:control}).locator('a[id$="::drop"]');
      if(await arrow.count()===1)await arrow.click();else await control.click();await ui.getByRole('option',{name:value,exact:true}).click();await settle();}
  };
  adapter.phase='scope_states';
  await choose('Estado Operador','Igual que');
  await ui.getByRole('textbox',{name:'Estado',exact:true}).click();
  await waitForRendered(adapter,async()=>await ui.getByRole('checkbox',{name:'Abierta',exact:true}).count()>0);
  for(const state of states)await ui.getByRole('checkbox',{name:state,exact:true}).check();
  for(const state of OPPORTUNITY_STATES.filter(s=>!states.includes(s)))await ui.getByRole('checkbox',{name:state,exact:true}).uncheck();
  await ui.getByRole('textbox',{name:'Estado',exact:true}).press('Tab');await settle();
  adapter.phase='scope_period';
  await choose('Período de cierre','Todo');
  adapter.phase='scope_date_operator';
  await choose('Fecha de cierre Operador','Entre');
  let verified=false;
  for(let attempt=0;attempt<3&&!verified;attempt++){
    const currentTo=normalizeOracleDate(await ui.getByRole('textbox',{name:'Para Fecha de cierre',exact:true}).evaluate(e=>e.value));
    for(const [label,value] of dateEditOrder(currentTo,from,to)){
      adapter.phase=label.startsWith('De ')?'scope_date_from':'scope_date_to';
      const field=ui.getByRole('textbox',{name:label,exact:true});
      await field.fill(oracleDate(value));await field.press('Tab');await settle();
    }
    adapter.phase='scope_search';
    await ui.getByRole('button',{name:'Buscar',exact:true}).last().press('Enter');await settle();
    adapter.phase='scope_verify_dates';
    const observedFrom=await ui.getByRole('textbox',{name:'De Fecha de cierre',exact:true}).evaluate(e=>e.value);
    const observedTo=await ui.getByRole('textbox',{name:'Para Fecha de cierre',exact:true}).evaluate(e=>e.value);
    adapter.scopeDiagnostic={requested:{from,to,states},observed:{from:observedFrom,to:observedTo},attempt:attempt+1};
    verified=normalizeOracleDate(observedFrom)===from&&normalizeOracleDate(observedTo)===to;
  }
  if(!verified)throw Error('scope');
  const observedStates=await ui.getByRole('textbox',{name:'Estado',exact:true}).evaluate(e=>e.value);
  const selected=observedStates==='Todo'?OPPORTUNITY_STATES:observedStates.split(';').map(s=>s.trim());
  if(selected.length!==states.length||states.some(s=>!selected.includes(s)))throw Error('scope');
}

/** Keep the intermediate interval valid when moving to a later month. */
export function dateEditOrder(currentTo,from,to){
  const start=['De Fecha de cierre',from],end=['Para Fecha de cierre',to];
  return from>currentTo?[end,start]:[start,end];
}

/** Explicit user-requested scalar changes only. Never retries an uncertain save. */
import {configureQuery,selectOpportunityByNumber,openCachedDetail,captureOpenDetail,closeCachedDetail} from './oracle-sync.mjs';
const labels={name:'Nombre',stage:'Etapa de ventas',probability:'Probabilidad de ganar (%)',close_date:'Fecha de cierre'};
export function equivalent(field,a,b){
  if(a==null&&b==null)return true;
  if(field==='probability')return Number(a)===Number(b);
  if(field==='close_date'){
    const normalize=v=>{const m=String(v).match(/^(\d{2})\/(\d{2})\/(\d{2,4})$/);return m?`${m[3].length===2?'20'+m[3]:m[3]}-${m[2]}-${m[1]}`:v;};
    return normalize(a)===normalize(b);
  }return a===b;
}
export function validateObserved(change,detail){
  if(!labels[change.field]||!detail?.capabilities?.[change.field])throw Error('permission');
  if(!equivalent(change.field,detail.fields[change.field],change.old_value))throw Error('conflict');
}
export function dateForOracle(iso,current){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))throw Error('validation');
  if(/^\d{4}-\d{2}-\d{2}$/.test(current))return iso;
  const [y,m,d]=iso.split('-');return `${d}/${m}/${/\/\d{2}$/.test(current)?y.slice(-2):y}`;
}
export async function applyScalarChange(adapter,change){
  let saving=false;
  try{
    await configureQuery(adapter);await selectOpportunityByNumber(adapter,change.opportunity_number);
    await openCachedDetail(adapter,change.opportunity_number);
    const before=await captureOpenDetail(adapter,change.opportunity_number,{activities:false});validateObserved(change,before);
    const control=adapter.ui.getByLabel(labels[change.field],{exact:true});
    if(await control.count()!==1||!await control.isEnabled())throw Error('permission');
    if(change.field==='stage'){
      await control.click();await adapter.ui.getByRole('option',{name:change.new_value,exact:true}).click();
    }else{
      await control.fill(change.field==='close_date'?dateForOracle(change.new_value,before.fields.close_date):change.new_value);
      await control.press('Tab');
    }
    await adapter.observe();
    const proposed=await captureOpenDetail(adapter,change.opportunity_number,{activities:false});
    if(!equivalent(change.field,proposed.fields[change.field],change.new_value))throw Error('validation');
    for(const key of Object.keys(labels))if(key!==change.field&&!equivalent(key,before.fields[key],proposed.fields[key]))throw Error('side-effects');
    if(!proposed.capabilities[change.field])throw Error('permission');
    saving=true;
    await adapter.ui.getByRole('button',{name:'Guardar y Cerrar',exact:true}).click();
    await adapter.ui.getByRole('button',{name:'Guardar y Cerrar',exact:true}).waitFor({state:'hidden',timeout:20000});
    await selectOpportunityByNumber(adapter,change.opportunity_number);await openCachedDetail(adapter,change.opportunity_number);
    const verified=await captureOpenDetail(adapter,change.opportunity_number,{activities:false});
    if(!equivalent(change.field,verified.fields[change.field],change.new_value))throw Error('uncertain');
    return {verified:true,detail:verified};
  }catch(error){throw Error(saving?'uncertain':(['permission','conflict','validation','side-effects'].includes(error.message)?error.message:'write-not-started'));}
  finally{await closeCachedDetail(adapter).catch(()=>{});}
}

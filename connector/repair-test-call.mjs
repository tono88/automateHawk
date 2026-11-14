/** Operator-only repair. Deliberately not imported by the read worker.
 * Requires explicit authorization and a fresh observation of both blank fields.
 * A save is issued once; uncertain saves are never retried here.
 */
import {openCachedDetail,closeCachedDetail,selectOpportunityByNumber,
  captureOpenDetail,readSummaryDetail,readDetailIdentity} from './oracle-sync.mjs';
import {waitForRendered} from './ui-wait.mjs';

export function repairable(detail){
  return detail?.fields?.test_date==='' && detail?.fields?.test_call===''
    && detail?.capabilities?.test_call===true;
}

export function onlyCallChanged(before,after){
  const keys=Object.keys(before.fields);
  return Object.keys(after.fields).length===keys.length
    && after.fields.test_call==='No Aplica'
    && keys.every(k=>k==='test_call'||before.fields[k]===after.fields[k]);
}

export async function repairMissingTestCall(adapter,number,{authorized=false}={}){
  if(authorized!==true)throw Error('permission');
  const ui=adapter.ui;let saved=false;
  adapter.lastRepairCheck={phase:'open'};
  await selectOpportunityByNumber(adapter,number);
  await openCachedDetail(adapter,number);
  try{
    if(await ui.evaluate(readDetailIdentity)!==number)throw Error('identity');
    const before=await captureOpenDetail(adapter,number,{activities:false});
    if(!repairable(before))return {changed:false,reason:'preconditions-changed'};
    const combo=ui.getByRole('combobox',{name:'Convocatoria PA',exact:true});
    await combo.click();
    await ui.getByRole('option',{name:'No Aplica',exact:true}).click();
    await combo.press('Tab');
    if(!onlyCallChanged(before,await ui.evaluate(readSummaryDetail)))throw Error('unexpected-edit');
    adapter.lastRepairCheck={phase:'save',pre_save_only_call_changed:true};
    saved=true;
    await ui.getByRole('button',{name:'Guardar y Cerrar',exact:true}).click();
    await waitForRendered(adapter,async()=>await ui.getByRole('button',{name:'Guardar y Cerrar',exact:true}).count()===0);
    adapter.lastRepairCheck.phase='reopen';
    await selectOpportunityByNumber(adapter,number);
    await openCachedDetail(adapter,number);
    const after=await captureOpenDetail(adapter,number,{activities:false});
    adapter.lastRepairCheck={...adapter.lastRepairCheck,phase:'verify',
      changed_other_field_keys:Object.keys(before.fields).filter(k=>k!=='test_call'&&before.fields[k]!==after.fields[k]),
      same_field_count:Object.keys(before.fields).length===Object.keys(after.fields).length};
    if(await ui.evaluate(readDetailIdentity)!==number||!onlyCallChanged(before,after))throw Error('uncertain');
    return {changed:true,verified:true,only_test_call_changed:true,post_save_fields_verified:true};
  }catch(error){
    if(saved)throw Error('uncertain');
    throw error;
  }finally{await closeCachedDetail(adapter);}
}

/** Explicit user-requested scalar changes only. Never retries an uncertain save. */
import {configureQuery,selectOpportunityByNumber,openCachedDetail,captureOpenDetail,closeCachedDetail} from './oracle-sync.mjs';
import {EDIT_FIELDS} from './edit-fields.mjs';

const kindOf=field=>EDIT_FIELDS[field]?.kind||'text';
const isoDate=v=>{const m=String(v??'').trim().match(/^(\d{2})\/(\d{2})\/(\d{2,4})$/);return m?`${m[3].length===2?'20'+m[3]:m[3]}-${m[2]}-${m[1]}`:String(v??'').trim();};
const number=v=>{const cleaned=String(v??'').replace(/,/g,'').replace(/[^0-9.\-]/g,'');return cleaned===''||cleaned==='-'||cleaned==='.'?null:Number(cleaned);};

export function equivalent(field,a,b){
  const x=String(a??'').trim(),y=String(b??'').trim();
  if(x===y)return true;
  if(!x||!y)return false;
  const kind=kindOf(field);
  if(kind==='number'){const p=number(x),q=number(y);if(p!==null&&q!==null&&!Number.isNaN(p)&&!Number.isNaN(q))return p===q;}
  if(kind==='date')return isoDate(x)===isoDate(y);
  return false;
}
export function validateObserved(change,detail){
  if(!EDIT_FIELDS[change.field]||!detail?.capabilities?.[change.field])throw Error('permission');
  if(!equivalent(change.field,detail.fields?.[change.field],change.old_value))throw Error('conflict');
}
export function dateForOracle(iso,current){
  if(iso==='')return '';
  if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))throw Error('validation');
  if(/^\d{4}-\d{2}-\d{2}$/.test(current||''))return iso;
  const [y,m,d]=iso.split('-');return `${d}/${m}/${/\/\d{2}$/.test(current||'')?y.slice(-2):y}`;
}

/** Locates the single form control bound to a visible label inside the Summary panel. */
export function findSummaryControl(label){
  const root=Array.from(document.querySelectorAll('div')).find(d=>d.id.endsWith(':OpportunitySummaryPgl1')&&d.getClientRects().length);
  if(!root)return null;
  const matches=Array.from(root.querySelectorAll('label')).filter(l=>l.innerText.trim()===label&&l.htmlFor)
    .map(l=>document.getElementById(l.htmlFor)).filter(c=>c&&c.matches('input,textarea,select'));
  if(matches.length!==1)return null;
  const c=matches[0];
  return {id:c.id,tag:c.tagName.toLowerCase(),role:c.getAttribute('role')||'',
    options:c.tagName==='SELECT'?Array.from(c.options).map(o=>o.text.trim()):[]};
}

async function setValue(adapter,change,before){
  const {ui}=adapter,field=EDIT_FIELDS[change.field];
  const info=await ui.evaluate(findSummaryControl,field.label);
  if(!info)throw Error('permission');
  const control=ui.locator(`[id="${info.id.replace(/["\\]/g,'\\$&')}"]`);
  if(await control.count()!==1||!await control.isEnabled())throw Error('permission');
  const target=field.kind==='date'?dateForOracle(change.new_value,before.fields[change.field]):change.new_value;
  if(info.tag==='select'){
    const index=info.options.findIndex(text=>text===target);
    if(index<0)throw Error('validation');
    await control.selectOption({index});
  }else if((field.kind==='choice'||info.role==='combobox')&&target!==''){
    await control.click();
    const option=ui.getByRole('option',{name:target,exact:true});
    if(await option.count()===1)await option.click();
    else{await control.fill(target);await control.press('Tab');}
  }else{
    await control.fill(target);await control.press('Tab');
  }
}

export async function applyScalarChange(adapter,change){
  let saving=false;
  try{
    if(!EDIT_FIELDS[change.field])throw Error('permission');
    await configureQuery(adapter);await selectOpportunityByNumber(adapter,change.opportunity_number);
    await openCachedDetail(adapter,change.opportunity_number);
    const before=await captureOpenDetail(adapter,change.opportunity_number,{activities:false});validateObserved(change,before);
    await setValue(adapter,change,before);
    await adapter.observe();
    const proposed=await captureOpenDetail(adapter,change.opportunity_number,{activities:false});
    if(!equivalent(change.field,proposed.fields[change.field],change.new_value))throw Error('validation');
    // Any other field moved by Oracle (defaults, dependent lists) stops the save for review.
    for(const key of Object.keys(before.fields))if(key!==change.field&&!equivalent(key,before.fields[key],proposed.fields[key]))throw Error('side-effects');
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

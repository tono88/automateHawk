/** Explicit user-requested scalar changes only. Never retries an uncertain save. */
import {configureQuery,selectOpportunityByNumber,openCachedDetail,captureOpenDetail,closeCachedDetail} from './oracle-sync.mjs';
import {EDIT_FIELDS} from './edit-fields.mjs';
import {collectRelatedContact,readContactProfile,readContactAccessFailure} from './contact-reader.mjs';
import {waitForRendered} from './ui-wait.mjs';

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
  if(kind==='email')return x.toLowerCase()===y.toLowerCase();
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

/** Same profile root as readContactProfile; returns the control bound to one normalised label. */
export function findContactControl(label){
  const norm=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();
  const all=Array.from(document.querySelectorAll('label')).filter(l=>l.getClientRects().length);
  const anchor=all.filter(l=>norm(l.innerText)==='id campus').at(-1);
  if(!anchor)return null;
  let root=anchor.parentElement,found=false;
  for(let i=0;root&&i<25;i++,root=root.parentElement){
    const texts=Array.from(root.querySelectorAll('label')).map(l=>norm(l.innerText));
    if(texts.includes('nombre')&&texts.includes('estado en campus')){found=true;break;}
  }
  if(!found)return null;
  const matches=Array.from(root.querySelectorAll('label')).filter(l=>l.getClientRects().length&&norm(l.innerText)===label&&l.htmlFor)
    .map(l=>document.getElementById(l.htmlFor)).filter(c=>c&&c.matches('input,textarea,select'));
  if(matches.length!==1)return null;
  const c=matches[0];
  return {id:c.id,tag:c.tagName.toLowerCase(),role:c.getAttribute('role')||'',type:c.type||'',
    options:c.tagName==='SELECT'?Array.from(c.options).map(o=>o.text.trim()):[]};
}

async function setValue(adapter,change,before,finder=findSummaryControl){
  const {ui}=adapter,field=EDIT_FIELDS[change.field];
  const info=await ui.evaluate(finder,field.label);
  if(!info)throw Error('permission');
  const control=ui.locator(`[id="${info.id.replace(/["\\]/g,'\\$&')}"]`);
  if(await control.count()!==1||!await control.isEnabled())throw Error('permission');
  const target=field.kind==='date'?dateForOracle(change.new_value,before.fields[change.field]):change.new_value;
  if(info.type==='checkbox'){
    if(!['Sí','No'].includes(target))throw Error('validation');
    await control.setChecked(target==='Sí');
  }else if(info.tag==='select'){
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

const wait=(adapter,predicate)=>waitForRendered(adapter,predicate);
const SAVE_AND_CLOSE=/^Guardar y [Cc]errar$/;

/** From an open opportunity: Contactos → primary contact → Perfil, expanded. */
async function openContactProfile(adapter){
  const {ui}=adapter,contacts=ui.getByRole('link',{name:'Contactos',exact:true});
  if(!await contacts.count())throw Error('permission');
  await contacts.click();
  await wait(adapter,async()=>await ui.getByRole('table',{name:'Contactos',exact:true}).count()>0);
  const principal=await ui.getByRole('table',{name:'Contactos',exact:true}).evaluate(t=>{
    const rows=Array.from(t.rows).map((r,index)=>({r,index})).filter(({r})=>Array.from(r.cells[0]?.querySelectorAll('img')||[]).some(i=>i.alt==='Principal'));
    return rows.length===1?rows[0].index:null;
  });
  if(principal===null)throw Error('permission');
  const marks={cancel:await ui.getByRole('button',{name:'Cancelar',exact:true}).count(),save:await ui.getByRole('button',{name:SAVE_AND_CLOSE}).count()};
  await ui.getByRole('table',{name:'Contactos',exact:true}).getByRole('row').nth(principal).getByRole('cell').nth(1).getByRole('link').click();
  await wait(adapter,async()=>await ui.getByRole('link',{name:'Perfil',exact:true}).count()>0||await ui.evaluate(readContactAccessFailure));
  if(await ui.evaluate(readContactAccessFailure))throw Error('permission');
  await ui.getByRole('link',{name:'Perfil',exact:true}).click();
  await wait(adapter,async()=>await ui.getByRole('button',{name:'Ampliar Información Adicional',exact:true}).count()>0||await ui.getByRole('button',{name:'Reducir Información Adicional',exact:true}).count()>0);
  const more=ui.getByRole('button',{name:'Ampliar Información Adicional',exact:true}).last();
  if(await more.count()){await more.click();await adapter.observe();}
  await wait(adapter,async()=>!!await ui.evaluate(readContactProfile));
  return marks;
}

async function leaveContact(adapter,marks){
  const cancel=adapter.ui.getByRole('button',{name:'Cancelar',exact:true});
  if(await cancel.count()>marks.cancel){await cancel.last().click();await wait(adapter,async()=>await cancel.count()===marks.cancel);}
}

/** Changes one field of the linked primary contact, saves it and re-reads it. */
async function applyContactChange(adapter,change){
  const {ui}=adapter;let saving=false,marks=null;
  try{
    await configureQuery(adapter);await selectOpportunityByNumber(adapter,change.opportunity_number);
    await openCachedDetail(adapter,change.opportunity_number);
    marks=await openContactProfile(adapter);
    const before=await ui.evaluate(readContactProfile);validateObserved(change,before);
    await setValue(adapter,change,before,findContactControl);
    await adapter.observe();
    const proposed=await ui.evaluate(readContactProfile);
    if(!equivalent(change.field,proposed?.fields[change.field],change.new_value))throw Error('validation');
    for(const key of Object.keys(before.fields))if(key!==change.field&&!equivalent(key,before.fields[key],proposed.fields[key]))throw Error('side-effects');
    const save=ui.getByRole('button',{name:SAVE_AND_CLOSE});
    if(await save.count()<=marks.save)throw Error('write-not-started');
    saving=true;
    await save.last().click();
    await wait(adapter,async()=>await ui.getByRole('button',{name:'Cancelar',exact:true}).count()<=marks.cancel);
    marks=null;
    const contact=await collectRelatedContact(adapter);
    if(!equivalent(change.field,contact.fields?.[change.field],change.new_value))throw Error('uncertain');
    const summary=await captureOpenDetail(adapter,change.opportunity_number,{activities:false});
    return {verified:true,detail:{opportunity_number:change.opportunity_number,fields:{...summary.fields,...contact.fields},capabilities:{...summary.capabilities,...contact.capabilities},activities:{queried:false,rows:[]}}};
  }catch(error){throw Error(saving?'uncertain':(['permission','conflict','validation','side-effects'].includes(error.message)?error.message:'write-not-started'));}
  finally{if(marks)await leaveContact(adapter,marks).catch(()=>{});await closeCachedDetail(adapter).catch(()=>{});}
}

export async function applyScalarChange(adapter,change){
  if(EDIT_FIELDS[change.field]?.section==='contact')return applyContactChange(adapter,change);
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

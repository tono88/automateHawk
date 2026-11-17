/** Creates an opportunity (and, if requested, its primary contact) through Oracle's own
 * "Crear contacto" / "Crear oportunidad" screens, then identifies and reads it back.
 * Never retries after a save was clicked: an unknown outcome is reported as uncertain. */
import {openOpportunityQuery,readDetailIdentity,readOpportunityGrid,normalizeGrid,captureOpenDetail,closeCachedDetail} from './oracle-sync.mjs';
import {waitForRendered} from './ui-wait.mjs';

const STAGES=['01 - Interesado','02 - Inscrito a prueba','03 - Presente a prueba: resolución','04 - Perdida','05 - Matriculado','06 - Inscrito'];
const wait=(adapter,predicate,timeoutMs=20000)=>waitForRendered(adapter,predicate,{timeoutMs});
const SAVE_CLOSE=/^Guardar y [Cc]errar$/,SAVE_CONTINUE=/^Guardar y [Cc]ontinuar$/;

export function validateCreation(r){
  const text=(v,max=240)=>typeof v==='string'&&v.trim().length>0&&v.length<=max;
  if(!r||!text(r.name)||!/^\d{4}-\d{2}-\d{2}$/.test(r.close_date||'')||!STAGES.includes(r.stage))throw Error('validation');
  if(r.probability&&!(Number(r.probability)>=0&&Number(r.probability)<=100))throw Error('validation');
  const c=r.contact||{};
  if(c.mode==='existing'&&!text(c.name))throw Error('validation');
  if(c.mode==='new'&&!(text(c.first_name,150)&&text(c.last_name,150)))throw Error('validation');
  if(!['existing','new','none'].includes(c.mode))throw Error('validation');
  return r;
}
/** Oracle shows dates as dd/mm/yy in this tenant's forms. */
export const oracleDate=iso=>{const [y,m,d]=iso.split('-');return `${d}/${m}/${y.slice(2)}`;};
export const contactName=c=>c.mode==='existing'?c.name.trim():`${c.first_name.trim()} ${c.last_name.trim()}`;

/** Single visible form control by its label text (the create dialogs have no summary panel). */
export function findFormControl(label){
  const matches=Array.from(document.querySelectorAll('label')).filter(l=>l.getClientRects().length&&l.innerText.trim().replace(/^\*\s*/,'')===label&&l.htmlFor)
    .map(l=>document.getElementById(l.htmlFor)).filter(c=>c&&c.matches('input,textarea,select')&&c.getClientRects().length);
  if(matches.length!==1)return null;
  const c=matches[0];return {id:c.id,tag:c.tagName.toLowerCase(),role:c.getAttribute('role')||''};
}
async function control(adapter,label,{required=true}={}){
  const info=await adapter.ui.evaluate(findFormControl,label);
  if(!info){if(required)throw Error('layout');return null;}
  return {info,locator:adapter.ui.locator(`[id="${info.id.replace(/["\\]/g,'\\$&')}"]`)};
}
async function fillText(adapter,label,value,options){
  if(!value)return;const c=await control(adapter,label,options);if(!c)return;
  await c.locator.fill(value);await c.locator.press('Tab');await adapter.observe();
}
async function choose(adapter,label,value){
  const c=await control(adapter,label);
  if(c.info.tag==='select'){await c.locator.selectOption({label:value});return;}
  await c.locator.click();
  const option=adapter.ui.getByRole('option',{name:value,exact:true});
  if(await option.count()===1){await option.click();return;}
  await c.locator.fill(value);await c.locator.press('Tab');await adapter.observe();
}
/** Contact search fields: type the name, then require exactly one exact suggestion. */
async function pickContact(adapter,label,name){
  const c=await control(adapter,label);
  await c.locator.fill(name);await adapter.observe();
  await wait(adapter,async()=>await adapter.ui.getByRole('option',{name,exact:true}).count()>0||await adapter.ui.getByRole('row',{name}).count()>0,10000).catch(()=>{});
  const options=adapter.ui.getByRole('option',{name,exact:true});
  const count=await options.count();
  if(count>1)throw Error('ambiguous-contact');
  if(count===1)await options.click();else await c.locator.press('Tab');
  await adapter.observe();
  const value=await c.locator.evaluate(e=>e.value);
  if(value.trim().toLowerCase()!==name.toLowerCase())throw Error('contact-not-found');
}
async function openSalesTask(adapter,name){
  const {ui}=adapter;
  await openOpportunityQuery(adapter);
  const link=ui.getByRole('link',{name,exact:true}),button=ui.getByRole('button',{name,exact:true});
  if(await button.count())await button.first().click();
  else{
    if(!await link.count()){await ui.getByRole('tab',{name:'Ventas',exact:true}).click();await adapter.observe();}
    await wait(adapter,async()=>await link.count()>0);
    await link.first().click();
  }
  await wait(adapter,async()=>await ui.getByRole('button',{name:SAVE_CLOSE}).count()>0);
}
async function readValue(adapter,label){const c=await control(adapter,label,{required:false});return c?await c.locator.evaluate(e=>e.value.trim()):null;}

async function createContact(adapter,c){
  const {ui}=adapter;
  await openSalesTask(adapter,'Crear contacto');
  await fillText(adapter,'Nombre',c.first_name.trim());
  await fillText(adapter,'Apellidos',c.last_name.trim());
  await fillText(adapter,'Correo electrónico',c.email,{required:false});
  await fillText(adapter,'Teléfono móvil',c.phone,{required:false});
  if(await readValue(adapter,'Nombre')!==c.first_name.trim()||await readValue(adapter,'Apellidos')!==c.last_name.trim())throw Error('validation');
  await ui.getByRole('button',{name:SAVE_CLOSE}).last().click();
  // A duplicate-contact warning or a validation error keeps the dialog open.
  await wait(adapter,async()=>await ui.getByRole('button',{name:SAVE_CLOSE}).count()===0,30000).catch(()=>{throw Error('contact-uncertain');});
}

async function findCreatedByName(adapter,name){
  const {ui}=adapter;
  for(let attempt=0;attempt<3;attempt++){
    await openOpportunityQuery(adapter);
    if(!await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).count())await adapter.clickAdvanced();
    await wait(adapter,async()=>await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).count()>0);
    await ui.getByRole('combobox',{name:'Juego de registros',exact:true}).click();
    await ui.getByRole('option',{name:'Todos los registros que puedo ver',exact:true}).click();
    await ui.getByRole('combobox',{name:'Período de cierre',exact:true}).click();
    await ui.getByRole('option',{name:'Año actual',exact:true}).click();
    await ui.getByRole('textbox',{name:'Nombre',exact:true}).fill(name);
    await ui.getByRole('button',{name:'Buscar',exact:true}).last().click();
    try{
      await wait(adapter,async()=>{const g=await ui.evaluate(readOpportunityGrid);return !!g&&normalizeGrid(g).some(r=>r.name===name);},15000);
      const rows=normalizeGrid(await ui.evaluate(readOpportunityGrid)).filter(r=>r.name===name);
      if(rows.length>1)throw Error('duplicate');
      return rows[0];
    }catch(error){if(error.message==='duplicate')throw error;}
  }
  return null;
}

export async function createOpportunity(adapter,request){
  const r=validateCreation(request);const {ui}=adapter;
  let contactCreated=!!r.contact_created,saving=false;
  try{
    if(r.contact.mode==='new'&&!contactCreated){
      try{await createContact(adapter,r.contact);}
      catch(error){if(error.message==='contact-uncertain')throw Error('contact-created');throw error;}
      contactCreated=true;
    }
    await openSalesTask(adapter,'Crear oportunidad');
    await fillText(adapter,'Nombre',r.name.trim());
    if(r.contact.mode!=='none')await pickContact(adapter,'Contacto principal',contactName(r.contact));
    await fillText(adapter,'Fecha de cierre',oracleDate(r.close_date));
    if(r.probability)await fillText(adapter,'Probabilidad de ganar',String(r.probability),{required:false});
    await choose(adapter,'Etapa de ventas',r.stage);
    if(await readValue(adapter,'Nombre')!==r.name.trim())throw Error('validation');
    const continueButton=ui.getByRole('button',{name:SAVE_CONTINUE});
    saving=true;
    let number=null,row=null,detail=null;
    if(await continueButton.count()){
      await continueButton.last().click();
      await wait(adapter,async()=>!!await ui.evaluate(readDetailIdentity),45000).catch(()=>{});
      number=await ui.evaluate(readDetailIdentity);
      if(number){
        try{detail=await captureOpenDetail(adapter,number,{activities:false});detail.schema_version=2;}catch{detail=null;}
        await closeCachedDetail(adapter).catch(()=>{});
      }
    }else{
      await ui.getByRole('button',{name:SAVE_CLOSE}).last().click();
      await wait(adapter,async()=>await ui.getByRole('button',{name:SAVE_CLOSE}).count()===0,45000).catch(()=>{throw Error('uncertain');});
    }
    row=await findCreatedByName(adapter,r.name.trim());
    if(!row||number&&row.opportunity_number!==number)throw Error('uncertain');
    return {created:true,opportunity_number:row.opportunity_number,row,detail,contact_created:contactCreated};
  }catch(error){
    const known=['validation','layout','ambiguous-contact','contact-not-found','duplicate','contact-created','permission'];
    if(saving)throw Error('uncertain');
    if(contactCreated&&error.message!=='contact-created')throw Error('contact-created');
    throw Error(known.includes(error.message)?error.message:'write-not-started');
  }finally{
    const cancel=ui.getByRole('button',{name:'Cancelar',exact:true});
    if(!saving&&await cancel.count().catch(()=>0))await cancel.last().click().catch(()=>{});
  }
}

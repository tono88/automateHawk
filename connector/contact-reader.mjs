/** Reads the explicitly linked primary contact. Never joins people by names. */
export function readContactProfile(){
  const norm=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();
  const labels={
    'id campus':'campus_id','estado en campus':'campus_status','id scala':'scala_id',
    'nombre':'contact_first_name','segundo nombre':'contact_middle_name','apellidos':'contact_last_name','segundo apellido':'contact_second_last_name',
    'fecha de nacimiento':'birth_date','numero del documento de identidad':'document_id',
    'correo electronico':'contact_email','telefono movil':'contact_phone','cuenta':'contact_account',
    'carrera de interes':'career','facultad':'faculty','estatus lead':'lead_status',
    'mes de prueba':'test_month','tipo de prueba':'contact_test_type','talla sudadero':'hoodie_size',
    'estatus papeleria':'document_status','interes asistencia economica':'financial_interest',
    'ano de graduacion colegio':'graduation_school_year','homeschool':'homeschool'
  };
  const all=Array.from(document.querySelectorAll('label')).filter(l=>l.getClientRects().length);
  const anchor=all.filter(l=>norm(l.innerText)==='id campus').at(-1);
  if(!anchor)return null;
  let root=anchor.parentElement,found=false;
  for(let i=0;root&&i<25;i++,root=root.parentElement){
    const texts=Array.from(root.querySelectorAll('label')).map(l=>norm(l.innerText));
    const section=Array.from(root.querySelectorAll('[role=button],button,a')).some(e=>/^(ampliar|reducir) informacion adicional$/.test(norm(e.getAttribute('title')||e.getAttribute('aria-label')||e.innerText||'')));
    if(texts.includes('nombre')&&texts.includes('estado en campus')&&section){found=true;break;}
  }
  if(!found)return null;
  const fields={},capabilities={},priority={};
  for(const label of root.querySelectorAll('label')){
    if(!label.getClientRects().length)continue;
    const key=labels[norm(label.innerText)];if(!key)continue;
    const control=label.htmlFor?document.getElementById(label.htmlFor):null;
    let value='',rank=0,editable=false;
    if(control?.matches('input,textarea,select')){
      value=control.type==='checkbox'?(control.checked?'Sí':'No'):(control.value??'');rank=2;
      editable=!control.disabled&&control.getAttribute('aria-disabled')!=='true'&&(!control.readOnly||control.getAttribute('role')==='combobox');
    }else{
      const row=label.closest('tr'),cell=row?.cells[row.cells.length-1];
      if(cell&&!cell.contains(label)){value=cell.innerText.trim();rank=1;}
    }
    if(rank&&(!(key in fields)||rank>(priority[key]||0))){fields[key]=value.trim();capabilities[key]=editable;priority[key]=rank;}
  }
  return {fields,capabilities};
}
async function wait(adapter,predicate){for(let i=0;i<40;i++){await adapter.observe();if(await predicate())return;await new Promise(r=>setTimeout(r,200));}throw Error('timeout');}
export async function collectRelatedContact(adapter){
  const ui=adapter.ui,contacts=ui.getByRole('link',{name:'Contactos',exact:true});
  if(!await contacts.count())return {fields:{contact_link_status:'Sin acceso al módulo de contactos'},capabilities:{}};
  await contacts.click();
  await wait(adapter,async()=>await ui.getByRole('table',{name:'Contactos',exact:true}).count()>0);
  const principal=await ui.getByRole('table',{name:'Contactos',exact:true}).evaluate(t=>{
    const rows=Array.from(t.rows).map((r,index)=>({r,index})).filter(({r})=>Array.from(r.cells[0]?.querySelectorAll('img')||[]).some(i=>i.alt==='Principal'));
    return rows.length===1?rows[0].index:null;
  });
  if(principal===null)return {fields:{contact_link_status:'No hay un contacto principal único en la relación'},capabilities:{}};
  const before=await ui.getByRole('button',{name:'Cancelar',exact:true}).count();
  await ui.getByRole('table',{name:'Contactos',exact:true}).getByRole('row').nth(principal).getByRole('cell').nth(1).getByRole('link').click();
  await wait(adapter,async()=>await ui.getByRole('link',{name:'Perfil',exact:true}).count()>0);
  try{
    await ui.getByRole('link',{name:'Perfil',exact:true}).click();
    await wait(adapter,async()=>await ui.getByRole('button',{name:'Ampliar Información Adicional',exact:true}).count()>0||await ui.getByRole('button',{name:'Reducir Información Adicional',exact:true}).count()>0);
    const more=ui.getByRole('button',{name:'Ampliar Información Adicional',exact:true}).last();
    if(await more.count()){await more.click();await adapter.observe();}
    await wait(adapter,async()=>{const d=await ui.evaluate(readContactProfile);return !!d&&('career' in d.fields||'faculty' in d.fields);});
    const result=await ui.evaluate(readContactProfile);
    return {fields:{...result.fields,contact_link_status:'Contacto principal verificado desde la oportunidad'},capabilities:result.capabilities};
  }finally{
    if(await ui.getByRole('button',{name:'Cancelar',exact:true}).count()>before){await ui.getByRole('button',{name:'Cancelar',exact:true}).last().click();await wait(adapter,async()=>await ui.getByRole('button',{name:'Cancelar',exact:true}).count()===before);}
  }
}

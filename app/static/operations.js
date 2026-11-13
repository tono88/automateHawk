'use strict';
window.UnisOracleLive = (() => {
  let state, catalog, changes = [], root, view = 'base', query = '', cycle = '', advisor = '',
    stage = '', testDate = '', page = 1, selected = null, module = 'general',
    inline = null, error = '', activities = [], activitySchemas = {};
  const labels = {name:'Nombre de oportunidad',owner:'Asesor',stage:'Etapa',probability:'Probabilidad',close_date:'Fecha de cierre'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time = value => value ? new Date(value).toLocaleString('es-GT', {timeZone:'America/Guatemala'}) : 'Sin consultar';
  const value = (row, key) => row[key] || state.details?.[row.opportunity_number]?.fields?.[key] || '';
  function fieldHint(row,key) {
    if(key in row || key in (state.details?.[row.opportunity_number]?.fields||{}))return 'Sin valor registrado en Oracle';
    return state.details?.[row.opportunity_number]?'Campo no disponible en la pantalla de este registro':'Detalle pendiente de actualización';
  }
  const options = (values, current, all) => `<option value="">${all}</option>${[...new Set(values.filter(Boolean))].sort().map(v => `<option value="${esc(v)}" ${v===current?'selected':''}>${esc(v)}</option>`).join('')}`;
  const badge = (text, kind='gray') => `<span class="badge ${kind}">${esc(text)}</span>`;
  const pending = (number, key) => changes.find(c => c.opportunity_number===number && c.field===key && ['pending_validation','approved','applying'].includes(c.state));
  async function request(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'No se pudo completar la operación.');
    return data;
  }
  async function refresh() {
    const [snapshot, queue, local] = await Promise.all([request('/api/oracle/snapshot'), request('/api/oracle/changes'),request('/api/oracle/activities')]);
    state = snapshot; changes = queue.changes; activities=local.activities;activitySchemas=local.schemas;
    if (!catalog) catalog = await request('/api/oracle/catalog');
  }
  async function render(target) {
    root=target;
    try {await refresh(); draw();} catch {target.innerHTML='<div class="empty">No se pudo leer la copia local. Comprueba PostgreSQL y el servidor.</div>';}
  }
  function rows() {
    const term=query.toLocaleLowerCase('es');
    return state.records.filter(row => {
      if(term && ![row.opportunity_number,row.name,row.first_name,row.last_name,row.owner,row.account].join(' ').toLocaleLowerCase('es').includes(term)) return false;
      if(cycle && value(row,'cycle')!==cycle || advisor && row.owner!==advisor || stage && row.stage!==stage || testDate && value(row,'test_date')!==testDate) return false;
      if(view==='enrollment' && !/^(05|06)\s*-/.test(row.stage)) return false;
      return true;
    });
  }
  function draw() {
    if(!root || !document.querySelector('[data-mode="live"].active')) return;
    const filtered=rows(), busy=['pending','running'].includes(state.job?.state);
    const outstanding=changes.filter(c=>['pending_validation','approved','applying'].includes(c.state)).length;
    root.innerHTML=`<div class="page-heading"><div><span class="eyebrow">AUTOMATEHAWK · OPERACIÓN DE ADMISIONES</span><h1>La cartera, conectada.</h1><p>Consulta local, detalle por módulo y propuestas de cambio con trazabilidad.</p></div><button class="primary" id="op-sync" ${!state.worker_online||busy?'disabled':''}>${busy?'Consulta en curso…':'Actualizar desde Oracle'}</button></div>
      <div class="source-strip"><span>${badge(state.storage==='postgresql'?'PostgreSQL · copia persistente':'Copia en memoria',state.storage==='postgresql'?'green':'orange')}</span><span>Última carga: ${esc(time(state.loaded_at))}</span><span>${state.worker_online?'Trabajador conectado':'Trabajador desconectado'}</span><span>Perfil local: ${esc(state.role)}</span></div>
      <p class="subtle">Consulta parcial · ${esc(state.scope)}. Los datos disponibles se muestran completos. Una raya indica un campo sin valor o pendiente de actualización; su descripción distingue cada caso.</p>
      <div class="metrics ops-metrics"><div class="metric accent"><div class="metric-label">Oportunidades en copia local</div><strong>${state.records.length}</strong><small>Identificadas por número oficial</small></div><div class="metric"><div class="metric-label">Detalles consultados</div><strong>${state.detail_count}</strong><small>Cobertura de campos ampliados</small></div><div class="metric"><div class="metric-label">Propuestas pendientes</div><strong>${outstanding}</strong><small>Aún no confirmadas en Oracle</small></div><div class="metric"><div class="metric-label">Versiones observadas</div><strong>${state.database?.historical_versions ?? '—'}</strong><small>Historia de la copia local</small></div></div>
      <div class="detail-progress"><span>${esc(state.job?.message||'Los datos se muestran tal como se recuperaron de Oracle.')}</span><button id="op-enrich" class="tiny-button" ${!state.worker_online||busy?'disabled':''}>Completar datos de la cartera</button></div>
      <div class="ops-tabs" aria-label="Vistas de admisiones">${[...catalog.views,{id:'local-activities',title:'Seguimientos y citas locales'}].map(v=>`<button data-view="${v.id}" class="${view===v.id?'selected':''}">${esc(v.title)}</button>`).join('')}</div>
      ${error?`<div class="notice" role="alert">${esc(error)}</div>`:''}
      ${view==='local-activities'?localActivityView(filtered):view==='changes'?queueView():view==='sync'?syncView():view==='roadmap'?roadmapView():view==='summary'?summaryView(filtered):tableView(filtered)}`;
    root.querySelector('#op-sync').onclick=()=>enqueue('opportunities');
    root.querySelector('#op-enrich').onclick=()=>enqueue('details_batch');
    root.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{view=button.dataset.view;page=1;inline=null;error='';draw();});
    bindTable();
    bindActivities(root);
    root.querySelectorAll('[data-cancel-change]').forEach(button=>button.onclick=async()=>{
      try {await request('/api/oracle/changes/cancel',{id:button.dataset.cancelChange});await refresh();draw();} catch(e){error=e.message;draw();}
    });
    const settings=root.querySelector('#sync-form');
    if(settings)settings.onsubmit=async event=>{
      event.preventDefault();
      try {await request('/api/oracle/settings',{enabled:settings.elements.enabled.checked,interval_minutes:Number(settings.elements.interval.value)});await refresh();error='Configuración guardada. Se consulta solo mientras el trabajador esté conectado.';draw();} catch(e){error=e.message;draw();}
    };
  }
  function filters() {
    return `<div class="filters"><input id="op-search" aria-label="Buscar en cartera" placeholder="Buscar por nombre, número, cuenta o asesor…" value="${esc(query)}"><select id="op-cycle" aria-label="Ciclo de ingreso">${options(state.records.map(r=>value(r,'cycle')),cycle,'Todos los ciclos disponibles')}</select><select id="op-advisor" aria-label="Asesor asignado">${options(state.records.map(r=>r.owner),advisor,'Todos los asesores')}</select><select id="op-stage" aria-label="Etapa comercial">${options(state.records.map(r=>r.stage),stage,'Todas las etapas')}</select>${view==='tests'?`<select id="op-test-date" aria-label="Fecha de prueba">${options(state.records.map(r=>value(r,'test_date')),testDate,'Todas las fechas disponibles')}</select>`:''}<button id="op-clear">Limpiar</button></div>`;
  }
  const columns = {
    base:[['name','Nombre de oportunidad','general'],['owner','Asesor','advisor'],['stage','Etapa comercial','general'],['probability','Probabilidad','general'],['close_date','Cierre comercial','general'],['cycle','Ciclo','general'],['admission_status','Proceso de admisión','general'],['test_date','Fecha de prueba','tests'],['interview','Entrevista','interviews'],['activities','Citas y tareas','activities']],
    tests:[['cycle','Ciclo','general'],['test_call','Convocatoria','tests'],['test_date','Fecha PA','tests'],['test_type','Prueba de admisión','tests'],['test_route','Tipo de prueba','tests'],['agreement','Convenio PA','tests'],['resolution','Resolución','tests']],
    interviews:[['owner','Asesor','advisor'],['cycle','Ciclo','general'],['interview','Indicador de entrevista','interviews'],['activities','Citas y tareas vinculadas','activities'],['resolution','Resolución','tests']],
    payments:[['owner','Asesor','advisor'],['stage','Etapa','general'],['amount','Importe de oportunidad','payments'],['reservation_close','Reserva de cupo','payments'],['tuition_delay_reason','Retraso de matrícula','payments']],
    financial:[['cycle','Ciclo','general'],['financial_aid','Asistencia económica','financial'],['financial_type_1','Tipo de ayuda','financial'],['financial_requested_1','% solicitado','financial'],['financial_granted_1','% otorgado','financial'],['financial_status','Estatus','financial'],['documents_due','Límite de papelería','financial']],
    enrollment:[['owner','Asesor','advisor'],['stage','Etapa comercial','general'],['cycle','Ciclo','general'],['resolution','Resolución','tests'],['reservation_close','Reserva de cupo','payments'],['close_date','Cierre comercial','general']]
  };
  function canEdit(row,key) {
    return state.can_propose && catalog.edit_fields.includes(key) && state.details?.[row.opportunity_number]?.capabilities?.[key]===true;
  }
  function cell(row,key,section) {
    const number=row.opportunity_number;
    if(inline?.number===number&&inline.key===key) {
      const current=value(row,key), type=key==='probability'?'number':key==='close_date'?'date':'text';
      const control=key==='stage'?`<select name="value" aria-label="Nuevo valor de Etapa">${['01 - Interesado','02 - Inscrito a prueba','03 - Presente a prueba: resolución','04 - Perdida','05 - Matriculado','06 - Inscrito'].map(s=>`<option ${s===current?'selected':''}>${s}</option>`).join('')}</select>`:`<input name="value" aria-label="Nuevo valor de ${labels[key]}" type="${type}" value="${esc(type==='date'?isoDate(current):current)}" required>`;
      return `<form class="inline-editor" data-inline-form="${esc(number)}" data-field="${key}">${control}<button class="primary tiny-button">Proponer</button><button type="button" data-inline-cancel class="tiny-button">×</button></form>`;
    }
    let text=value(row,key)||'—';
    if(key==='activities'){const d=state.details?.[number];text=d?.activities?.queried?`${d.activities.rows.length} actividades visibles`:'—';}
    const change=pending(number,key);
    return `<button class="cell-link" title="${esc(value(row,key)?'Valor recuperado de Oracle':fieldHint(row,key))}" data-detail="${esc(number)}" data-module="${section}">${esc(text)}</button>${canEdit(row,key)?`<button class="pencil" aria-label="Editar ${labels[key]} en la lista" data-inline="${esc(number)}" data-field="${key}">✎</button>`:''}${change?`<span class="record-id pending-label">Propuesta: ${esc(change.new_value)}</span>`:''}`;
  }
  function isoDate(raw) {
    if(/^\d{4}-\d{2}-\d{2}$/.test(raw))return raw;
    const m=raw.match(/^(\d{2})\/(\d{2})\/(\d{2,4})$/);return m?`${m[3].length===2?'20'+m[3]:m[3]}-${m[2]}-${m[1]}`:'';
  }
  function tableView(filtered) {
    const cols=columns[view]||columns.base, pages=Math.max(1,Math.ceil(filtered.length/12));page=Math.min(page,pages);
    const caption=catalog.views.find(v=>v.id===view);
    return `<section class="table-panel"><div class="table-toolbar"><div><h2>${esc(caption.title)}</h2><span class="count-pill">${filtered.length}</span></div><span class="subtle">Haz clic en un dato para abrir su módulo</span></div><p class="view-caption">${esc(caption.description)} ${view==='payments'?'Un importe comercial no demuestra que exista un pago confirmado.':''}</p>${filters()}<div class="table-wrap"><table><thead><tr><th>ASPIRANTE / OPORTUNIDAD</th>${cols.map(c=>`<th>${c[1]}</th>`).join('')}<th>ACTIVIDADES LOCALES</th><th>ÚLTIMA OBSERVACIÓN</th></tr></thead><tbody>${filtered.slice((page-1)*12,page*12).map(row=>`<tr><td><button class="name-button" data-detail="${esc(row.opportunity_number)}" data-module="general">${esc([row.first_name,row.last_name].filter(Boolean).join(' ')||row.name)}</button><span class="record-id">${esc(row.opportunity_number)}</span></td>${cols.map(([key,,section])=>`<td>${cell(row,key,section)}</td>`).join('')}<td>${activityActions(row.opportunity_number)}<span class="record-id">${activities.filter(a=>a.opportunity_number===row.opportunity_number).length} registros locales</span></td><td>${esc(time(row._last_seen||state.loaded_at))}<span class="record-id">${state.details?.[row.opportunity_number]?'Detalle disponible':'Detalle pendiente'}</span></td></tr>`).join('')||`<tr><td class="empty" colspan="${cols.length+3}">No hay registros con estos filtros.</td></tr>`}</tbody></table></div><div class="pagination"><span>Valores confirmados de la copia local. Las propuestas no sustituyen los datos de Oracle.</span><div><button id="op-prev" ${page===1?'disabled':''}>‹</button> ${page}/${pages}<button id="op-next" ${page===pages?'disabled':''}>›</button></div></div></section>`;
  }
  function bindTable() {
    const search=root.querySelector('#op-search');
    if(search)search.oninput=event=>{query=event.target.value;const pos=event.target.selectionStart;page=1;draw();const target=root.querySelector('#op-search');target.focus();target.setSelectionRange(pos,pos);};
    for(const [id,set] of [['op-cycle',v=>cycle=v],['op-advisor',v=>advisor=v],['op-stage',v=>stage=v],['op-test-date',v=>testDate=v]]){
      const element=root.querySelector('#'+id);if(element)element.onchange=e=>{set(e.target.value);page=1;draw();};
    }
    const clear=root.querySelector('#op-clear');if(clear)clear.onclick=()=>{query=cycle=advisor=stage=testDate='';page=1;draw();};
    const prev=root.querySelector('#op-prev'),next=root.querySelector('#op-next');if(prev)prev.onclick=()=>{page--;draw();};if(next)next.onclick=()=>{page++;draw();};
    root.querySelectorAll('[data-detail]').forEach(button=>button.onclick=()=>openDetail(button.dataset.detail,button.dataset.module));
    root.querySelectorAll('[data-inline]').forEach(button=>button.onclick=()=>{inline={number:button.dataset.inline,key:button.dataset.field};error='';draw();});
    root.querySelectorAll('[data-inline-cancel]').forEach(button=>button.onclick=()=>{inline=null;draw();});
    root.querySelectorAll('[data-inline-form]').forEach(form=>form.onsubmit=async event=>{
      event.preventDefault();const row=state.records.find(r=>r.opportunity_number===form.dataset.inlineForm);
      try {await request('/api/oracle/changes',{opportunity_number:row.opportunity_number,field:form.dataset.field,value:form.elements.value.value,version:row._version});inline=null;await refresh();error='Propuesta guardada. Pendiente de validar y aplicar en Oracle.';draw();}catch(e){error=e.message;draw();}
    });
  }
  function ensureDrawer() {
    let dialog=document.querySelector('#crm-detail');if(dialog)return dialog;
    dialog=document.createElement('dialog');dialog.id='crm-detail';dialog.className='crm-drawer';document.body.append(dialog);return dialog;
  }
  function openDetail(number,section='general') {
    selected=number;module=section;drawDetail();const dialog=ensureDrawer();if(!dialog.open)dialog.showModal();
  }
  function drawDetail() {
    const row=state.records.find(r=>r.opportunity_number===selected),detail=state.details?.[selected];if(!row)return;
    const dialog=ensureDrawer(), tabs=[['general','Resumen'],['advisor','Asesor'],['tests','Pruebas'],['interviews','Entrevista'],['activities','Citas y tareas'],['payments','Pagos'],['financial','Ayuda económica']];
    const fields=Object.entries(catalog.fields).filter(([,definition])=>definition.module===module);
    const currentJob=state.job,busy=['pending','running'].includes(currentJob?.state);
    dialog.innerHTML=`<div class="dialog-head"><div><span class="eyebrow">DETALLE DE ORACLE · COPIA LOCAL</span><h2>${esc([row.first_name,row.last_name].filter(Boolean).join(' ')||row.name)}</h2><p class="subtle">${esc(selected)} · ${esc(time(detail?.loaded_at))}</p></div><button id="crm-close" class="icon-button" aria-label="Cerrar detalle">×</button></div><div class="ops-tabs">${tabs.map(([id,title])=>`<button data-section="${id}" class="${id===module?'selected':''}">${title}</button>`).join('')}</div><div class="notice">${detail?'Permisos y valores observados en la cuenta del trabajador.':'Aún no se ha consultado el detalle de esta oportunidad.'} Los cambios propuestos quedan separados del valor confirmado.</div>
      ${module==='activities'?activityPanel(detail)+localActivityPanel(selected):`<div class="detail-grid">${fields.map(([key,definition])=>{
        const available=key in row||key in (detail?.fields||{});let text=available?(value(row,key)||'Sin valor registrado en Oracle'):fieldHint(row,key);
        const permission=detail?.capabilities?.[key];return `<div class="detail-field"><span>${esc(key==='name'?'Nombre de la oportunidad':definition.label)}</span><strong>${esc(text)}</strong><small>${permission===true?'Control habilitado en la consulta de Oracle':permission===false?'Solo lectura en Oracle':'Permiso pendiente de validación'}</small></div>`;
      }).join('')||'<p class="subtle">Este módulo todavía no tiene campos mapeados.</p>'}</div>`}
      ${module==='payments'?'<p class="notice">Importe, reserva de cupo y razón de retraso no acreditan un pago. El recibo, transacción y confirmación de pago aún requieren un mapeo específico.</p>':''}
      ${module==='advisor'?'<p class="subtle">Se muestra la asignación observada. El perfil, equipo y permisos del asesor se ampliarán al validar su módulo específico.</p>':''}
      <div class="dialog-actions"><span></span><button id="crm-reload" class="primary" ${!state.worker_online||busy?'disabled':''}>Consultar detalle en Oracle</button></div>`;
    bindActivities(dialog);
    dialog.querySelector('#crm-close').onclick=()=>dialog.close();
    dialog.querySelectorAll('[data-section]').forEach(button=>button.onclick=()=>{module=button.dataset.section;drawDetail();});
    dialog.querySelector('#crm-reload').onclick=()=>enqueue('detail',selected);
  }
  function activityPanel(detail) {
    if(!detail?.activities?.queried)return '<div class="empty">Actualiza este detalle para cargar las citas y tareas vinculadas.</div>';
    if(!detail.activities.rows.length)return '<div class="empty">No se encontraron actividades en la consulta visible de esta oportunidad.</div>';
    return `<div class="activity-cards">${detail.activities.rows.map(activity=>`<article class="panel"><span class="eyebrow">${esc(activity.activity||activity.type||'Actividad')}</span><h2>${esc(activity.subject)}</h2><p>${esc(activity.date)} · ${esc(activity.owner)}</p><p class="subtle">Prioridad: ${esc(activity.priority||'Sin dato')}</p></article>`).join('')}</div>`;
  }
  function activityActions(number) {
    if(!state.can_propose)return '';
    return `<div class="local-actions"><button class="row-action" data-activity-new="tasks" data-number="${esc(number)}">+ Seguimiento</button><button class="row-action" data-activity-new="appointments" data-number="${esc(number)}">+ Cita</button><button class="row-action" data-activity-new="interactions" data-number="${esc(number)}">+ Informe</button></div>`;
  }
  function localCards(list) {
    return list.map(a=>`<article class="panel local-activity-card"><div class="local-card-head"><span class="eyebrow">${esc(activitySchemas[a.kind].title)}</span>${badge(a.data.local_status,a.data.local_status==='Completado'?'green':'gray')}</div><h2>${esc(a.data.subject)}</h2><p>${esc(a.data.owner)} · ${esc(a.data.followup_date||a.data.start_date||'Sin fecha')} ${esc(a.data.start_time||'')}</p><p class="subtle">${esc(a.data.timezone||'America/Guatemala')}${a.data.location?' · '+esc(a.data.location):''}</p><p class="pending-label">Solo local · sin enviar a Oracle</p><button class="tiny-button" data-activity-edit="${esc(a.id)}">${state.can_propose?'Ver / editar':'Ver detalle'}</button></article>`).join('');
  }
  function localActivityPanel(number) {
    const list=activities.filter(a=>a.opportunity_number===number);
    return `<section class="local-activity-section"><h2>Seguimientos y citas locales</h2><p class="subtle">Se conservan en este portal y no modifican las actividades de Oracle. Los recordatorios no envían avisos todavía.</p>${activityActions(number)}<div class="activity-cards">${localCards(list)||'<p class="subtle">Aún no hay actividades locales para esta oportunidad.</p>'}</div></section>`;
  }
  function localActivityView(filtered) {
    const numbers=new Set(filtered.map(r=>r.opportunity_number)),list=activities.filter(a=>numbers.has(a.opportunity_number));
    return `<section class="table-panel"><div class="table-toolbar"><h2>Seguimientos y citas locales</h2><span class="count-pill">${list.length} registros locales</span></div><p class="view-caption">Formularios de trabajo vinculados a la cartera. No se envían a Oracle ni generan notificaciones.</p>${filters()}${state.can_propose?`<div class="local-create-toolbar">${Object.entries(activitySchemas).map(([kind,definition])=>`<button data-activity-new="${kind}">+ ${esc(definition.title)}</button>`).join('')}</div>`:''}<div class="local-activity-list">${list.map(a=>{const r=state.records.find(r=>r.opportunity_number===a.opportunity_number);return `<section><p class="subtle">${esc([r?.first_name,r?.last_name].filter(Boolean).join(' ')||r?.name)} · ${esc(a.opportunity_number)}</p>${localCards([a])}</section>`;}).join('')||'<div class="empty">Aún no hay actividades locales con estos filtros.</div>'}</div></section>`;
  }
  function bindActivities(container) {
    container.querySelectorAll('[data-activity-new]').forEach(b=>b.onclick=()=>openActivity(b.dataset.activityNew,b.dataset.number));
    container.querySelectorAll('[data-activity-edit]').forEach(b=>{const a=activities.find(a=>a.id===b.dataset.activityEdit);openActivity(a.kind,a.opportunity_number,a);});
  }
  function openActivity(kind,number,existing) {
    let dialog=document.querySelector('#local-activity-form');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='local-activity-form';document.body.append(dialog);}
    const schema=activitySchemas[kind], row=state.records.find(r=>r.opportunity_number===number),editable=state.can_propose;
    const data=existing?.data||{owner:row?.owner||'',account:row?.account||'',contact_reference:row?.contact_name||'',timezone:'America/Guatemala',local_status:'Pendiente'};
    const identifier=existing?.id||crypto.randomUUID();
    dialog.innerHTML=`<div class="dialog-head"><div><span class="eyebrow">ACTIVIDAD LOCAL</span><h2>${existing?'Detalle de':'Crear'} ${esc(schema.title.toLocaleLowerCase('es'))}</h2></div><button class="icon-button" id="activity-close" aria-label="Cerrar formulario">×</button></div><p class="notice">Solo local · sin enviar a Oracle. Guardar no crea registros en Oracle ni envía invitaciones o recordatorios.</p><details class="oracle-preflight"><summary>Preparación de la prueba oficial en Oracle</summary><p>Formulario destino: <strong>${esc(schema.oracle_form)}</strong>. Acceso y etiquetas verificados; guardado real todavía sin validar.</p><p>Antes del envío: confirmar el contacto y la oportunidad por sus identificadores oficiales, resolver los catálogos y el responsable con permisos vigentes, revisar fechas y notificaciones con los responsables y autorizar el caso de prueba. Después de guardar se deberá releer el registro y comprobar que no se duplicó.</p><p>${kind==='tasks'?'El formulario de tarea observado vincula Contacto principal y Cuenta; el vínculo directo a oportunidad requiere validación.':'El responsable local no equivale a un campo Responsable en este formulario de Oracle. Deben validarse organizador y participantes.'}</p></details><form id="activity-fields"><div class="fields"><label class="full">Oportunidad vinculada<select name="opportunity_number" required ${existing?'disabled':''}><option value="">Selecciona una oportunidad</option>${state.records.map(r=>`<option value="${esc(r.opportunity_number)}" ${number===r.opportunity_number?'selected':''}>${esc([r.first_name,r.last_name].filter(Boolean).join(' ')||r.name)} · ${esc(r.opportunity_number)}</option>`).join('')}</select></label>${schema.fields.map(f=>`<label class="${f.kind==='textarea'?'full':''}">${esc(f.label)}${f.required?' *':''}${f.kind==='select'?`<select name="${f.key}" ${f.required?'required':''} ${!editable?'disabled':''}>${!f.required?'<option value="">Sin especificar</option>':''}${f.options.map(v=>`<option ${data[f.key]===v?'selected':''}>${esc(v)}</option>`).join('')}</select>`:f.kind==='textarea'?`<textarea name="${f.key}" ${!editable?'disabled':''} maxlength="6000">${esc(data[f.key]||'')}</textarea>`:`<input name="${f.key}" type="${f.kind==='text'?'text':f.kind}" value="${esc(data[f.key]||'')}" ${f.required?'required':''} maxlength="500" ${!editable?'disabled':''}>`}</label>`).join('')}</div><p id="activity-error" class="error" role="alert"></p><div class="dialog-actions"><button type="button" id="activity-cancel">Cerrar</button><span></span>${editable?'<button class="primary" type="submit">Guardar en el portal</button>':''}</div></form>`;
    const close=()=>dialog.close();dialog.querySelector('#activity-close').onclick=close;dialog.querySelector('#activity-cancel').onclick=close;
    const form=dialog.querySelector('form');
    form.elements.opportunity_number.onchange=()=>{const r=state.records.find(r=>r.opportunity_number===form.elements.opportunity_number.value);for(const key of ['owner','account'])if(form.elements[key])form.elements[key].value=r?.[key]||'';if(form.elements.contact_reference)form.elements.contact_reference.value=r?.contact_name||'';};
    form.onsubmit=async event=>{
      event.preventDefault();if(!editable)return;
      const button=form.querySelector('[type=submit]');if(button.disabled)return;button.disabled=true;
      const payload=Object.fromEntries(schema.fields.map(f=>[f.key,form.elements[f.key].value]));
      try {await request('/api/oracle/activities',{id:identifier,kind,opportunity_number:existing?.opportunity_number||form.elements.opportunity_number.value,data:payload,version:existing?.version??null});await refresh();dialog.close();error='Actividad guardada en el portal. No se envió a Oracle.';draw();if(ensureDrawer().open)drawDetail();}
      catch(e){dialog.querySelector('#activity-error').textContent=e.message;button.disabled=false;}
    };
    dialog.showModal();
  }
  async function enqueue(kind,number) {
    try {await request('/api/oracle/jobs',{kind,opportunity_number:number});await refresh();error='Consulta solicitada; se procesará cuando el trabajador esté activo.';draw();if(ensureDrawer().open)drawDetail();}catch(e){error=e.message;draw();}
  }
  function queueView() {
    return `<section class="table-panel"><div class="table-toolbar"><h2>Propuestas de cambio</h2></div><div class="notice">El valor de Oracle se conserva. Esta versión registra y controla propuestas; el envío de escrituras reales aún requiere validar el conector y volver a comprobar los permisos.</div><div class="table-wrap"><table><thead><tr><th>OPORTUNIDAD</th><th>CAMPO</th><th>VALOR CONFIRMADO</th><th>PROPUESTA</th><th>ESTADO</th><th>ACCIÓN</th></tr></thead><tbody>${changes.map(c=>`<tr><td>${esc(c.opportunity_number)}</td><td>${esc(labels[c.field]||c.field)}</td><td>${esc(c.old_value)}</td><td>${esc(c.new_value)}</td><td>${badge(({pending_validation:'Pendiente de validar',conflict:'Conflicto: Oracle cambió',cancelled:'Cancelada',confirmed:'Confirmada'})[c.state]||c.state,c.state==='conflict'?'orange':'gray')}</td><td>${state.can_propose&&['pending_validation','conflict'].includes(c.state)?`<button class="tiny-button" data-cancel-change="${esc(c.id)}">Cancelar propuesta</button>`:''}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">No hay propuestas de cambio.</td></tr>'}</tbody></table></div></section>`;
  }
  function syncView() {
    const config=state.settings;
    return `<div class="guide-grid"><section class="panel"><h2>Sincronización híbrida</h2><p>La navegación usa PostgreSQL. Oracle se consulta por solicitud, por intervalo y para volver a verificar cambios.</p><form id="sync-form" class="settings-form"><label><input name="enabled" type="checkbox" ${config.enabled?'checked':''} ${state.can_propose?'':'disabled'}> Activar consulta periódica mientras el trabajador esté conectado</label><label>Intervalo en minutos<input name="interval" type="number" min="5" max="240" value="${config.interval_minutes}" ${state.can_propose?'':'disabled'}></label><button class="primary" ${state.can_propose?'':'disabled'}>Guardar frecuencia</button></form><p class="subtle">15 minutos es el punto de partida del piloto. Se ajustará según volumen, duración y estabilidad de Oracle. No se consulta por cada clic.</p></section><section class="panel"><h2>Estado de la copia</h2><div class="detail-grid"><div class="detail-field"><span>Almacenamiento</span><strong>${state.storage==='postgresql'?'PostgreSQL persistente':'Memoria'}</strong></div><div class="detail-field"><span>Registros</span><strong>${state.database?.records??state.records.length}</strong></div><div class="detail-field"><span>Cargas registradas</span><strong>${state.database?.sync_runs??'—'}</strong></div><div class="detail-field"><span>Última carga</span><strong>${esc(time(state.loaded_at))}</strong></div></div><p class="notice">La copia local y sus respaldos no sustituyen a Oracle ni constituyen alta disponibilidad. La sincronización completa y la confirmación de pagos siguen pendientes.</p><p>${esc(state.job?.message||'Sin trabajo pendiente.')}</p></section></div>`;
  }
  function summaryView(filtered) {
    const groups=new Map();filtered.forEach(row=>groups.set(row.stage,(groups.get(row.stage)||0)+1));
    const dates=[...new Set(filtered.map(row=>value(row,'test_date')).filter(Boolean))];
    return `<div class="guide-grid"><section class="panel"><h2>Distribución comercial</h2>${[...groups].map(([key,count])=>`<div class="attention"><span>${esc(key||'Sin etapa')}</span><b>${count}</b></div>`).join('')}</section><section class="panel"><h2>Cobertura de información</h2><p>${state.detail_count} detalles consultados de ${state.records.length} oportunidades locales.</p><p>${dates.length} fechas de prueba observadas. Las vistas por fecha se generan desde los datos consultados.</p><p class="subtle">Este resumen operativo usa estados actuales. Conversión histórica, cohortes y analítica predictiva permanecen en el roadmap.</p></section></div>`;
  }
  function roadmapView() {
    const phases=[['01','Base persistente','Implementado','PostgreSQL, copia local, historial por cambios y respaldo verificable.'],['02','Vistas del equipo','Piloto en curso','Cartera, pruebas por fecha, entrevistas, pagos, ayuda y matrícula; extracción de detalle por oportunidad.'],['03','Gestión sobre Oracle','Siguiente','Escritores por operación, revalidación de permisos, aprobación, idempotencia y confirmación posterior.'],['04','Sincronización confiable','En evolución','Intervalos, prioridades, detección de cambios, colas, reconciliación y cobertura completa.'],['05','Operación institucional','Pendiente','SSO, permisos por cartera, ambientes, observabilidad, soporte y recuperación.'],['06','Inteligencia de negocio','Roadmap','Modelo analítico, cohortes, conversiones, tiempos por etapa y tableros con gobierno del dato.']];
    return `<div class="roadmap-list">${phases.map(([n,title,status,description])=>`<article class="panel roadmap-card"><span class="roadmap-number">${n}</span><div>${badge(status,n==='01'?'green':'gray')}<h2>${title}</h2><p>${description}</p></div></article>`).join('')}</div>`;
  }
  setInterval(async()=>{
    if(!root||!document.querySelector('[data-mode="live"].active')||inline||document.querySelector('#local-activity-form[open]'))return;
    try {const signature=JSON.stringify([state?.loaded_at,state?.detail_count,state?.job,state?.worker_online,activities]);await refresh();
      if(signature!==JSON.stringify([state.loaded_at,state.detail_count,state.job,state.worker_online,activities])){draw();if(selected&&ensureDrawer().open)drawDetail();}}
    catch { /* Retain the last successful view during brief local outages. */ }
  },3000);
  return {render};
})();

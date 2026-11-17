'use strict';
/** Traceability dashboard: cross-tabs, consistency checks, activity and per-record timeline. */
window.UnisTrace=(()=>{
  let data=null,root=null,rowDim='stage',colDim='owner',onlyDetail=false,selection=null,timeline=null,timelineError='',loading=false;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const EMPTY='Sin dato',MAX_COLS=14;
  const time=v=>v?new Date(v).toLocaleString('es-GT',{timeZone:'America/Guatemala'}):'—';
  const pct=(n,d)=>d?Math.round(100*n/d):0;
  const fmt=n=>Number(n).toLocaleString('es-GT');
  const states={pending_validation:'Pendiente',queued:'En cola',applying:'Guardando en Oracle',uncertain:'Verificación requerida',failed:'No aplicado',conflict:'Conflicto',cancelled:'Cancelado',confirmed:'Confirmado en Oracle'};
  const fieldName=f=>data?.field_labels?.[f]||f;
  const actions={propose_change:'Cambio solicitado',cancel_change:'Cambio cancelado',oracle_write_verified:'Cambio confirmado en Oracle',create_opportunity_requested:'Creación solicitada',oracle_create_verified:'Oportunidad creada en Oracle',save_local_activity:'Actividad local guardada'};
  async function request(path){
    const generation=window.HubAuth.generation;const r=await fetch(path);const d=await r.json();
    if(generation!==window.HubAuth.generation)throw Error('La sesión cambió.');
    if(r.status===401)window.HubAuth.expired();if(!r.ok)throw Error(d.error||'No se pudo consultar la trazabilidad.');return d;
  }
  async function render(target){
    root=target;if(loading)return;loading=true;
    if(!data)root.innerHTML='<div class="loading" role="status">Calculando cruces…</div>';
    try{data=await request('/api/oracle/trace');draw();}
    catch(e){if(window.HubAuth.isAuthenticated())root.innerHTML=`<div class="empty">${esc(e.message)}</div>`;}
    finally{loading=false;}
  }
  const active=()=>root&&document.querySelector('[data-mode="trace"].active');
  const label=key=>data.dimensions.find(d=>d.key===key)?.label||key;
  const rows=()=>onlyDetail?data.rows.filter(r=>r.detail_state==='Detalle disponible'):data.rows;
  function order(key,values){
    if(key==='stage'){const known=data.stage_order.filter(s=>values.includes(s));return [...known,...values.filter(v=>!known.includes(v)).sort()];}
    if(key.endsWith('_month'))return values.slice().sort();
    return values;
  }
  /** Rows by count desc; columns capped, the remainder folds into "Otros". */
  function crossTab(list){
    const rCount=new Map(),cCount=new Map(),cells=new Map();
    for(const r of list){
      const a=r[rowDim]||EMPTY,b=r[colDim]||EMPTY;
      rCount.set(a,(rCount.get(a)||0)+1);cCount.set(b,(cCount.get(b)||0)+1);
    }
    let cols=order(colDim,[...cCount.keys()].sort((x,y)=>cCount.get(y)-cCount.get(x)));
    let other=[];if(cols.length>MAX_COLS){other=cols.slice(MAX_COLS-1);cols=[...cols.slice(0,MAX_COLS-1),'Otros'];}
    const otherSet=new Set(other);
    for(const r of list){
      const a=r[rowDim]||EMPTY,raw=r[colDim]||EMPTY,b=otherSet.has(raw)?'Otros':raw,k=a+'\u0000'+b;
      if(!cells.has(k))cells.set(k,[]);cells.get(k).push(r);
    }
    const rowsOrdered=order(rowDim,[...rCount.keys()].sort((x,y)=>rCount.get(y)-rCount.get(x)));
    const max=Math.max(1,...[...cells.values()].map(v=>v.length));
    return {rows:rowsOrdered,cols,cells,rCount,cCount:new Map(cols.map(c=>[c,c==='Otros'?other.reduce((s,o)=>s+cCount.get(o),0):cCount.get(c)])),max,otherSet};
  }
  function heat(n,max){
    if(!n)return '';
    const share=12+Math.round(78*Math.sqrt(n/max));
    return `data-heat="${share}"`;
  }
  function bars(items,total,{color='var(--wine)'}={}){
    const max=Math.max(1,...items.map(i=>i.count));
    return `<div class="trace-bars">${items.map(i=>`<div class="trace-bar" title="${esc(i.label)}: ${fmt(i.count)} (${pct(i.count,total)}%)"><span class="trace-bar-label">${esc(i.label)}</span><span class="trace-bar-track"><span class="trace-bar-fill" data-width="${Math.max(1,100*i.count/max)}" data-color="${color}"></span></span><b>${fmt(i.count)}</b><small>${pct(i.count,total)}%</small></div>`).join('')}</div>`;
  }
  function activityChart(days){
    if(!days.length)return '<p class="subtle">Sin cambios observados ni acciones del portal en los últimos 30 días.</p>';
    const max=Math.max(1,...days.map(d=>Math.max(d.oracle_changes,d.portal_actions)));
    return `<div class="trace-legend"><span><i class="swatch oracle"></i>Cambios observados en Oracle</span><span><i class="swatch portal"></i>Acciones desde el portal</span></div>
      <div class="trace-columns" role="img" aria-label="Actividad diaria de los últimos 30 días">${days.map(d=>`<div class="trace-day" title="${esc(d.day)} · Oracle: ${d.oracle_changes} · Portal: ${d.portal_actions}"><div class="trace-day-bars"><span class="oracle" data-height="${100*d.oracle_changes/max}"></span><span class="portal" data-height="${100*d.portal_actions/max}"></span></div><small>${esc(d.day.slice(8))}</small></div>`).join('')}</div>
      <details class="field-coverage"><summary>Ver como tabla</summary><div class="table-wrap"><table><thead><tr><th>Día</th><th>Cambios en Oracle</th><th>Acciones en el portal</th></tr></thead><tbody>${days.map(d=>`<tr><td>${esc(d.day)}</td><td>${d.oracle_changes}</td><td>${d.portal_actions}</td></tr>`).join('')}</tbody></table></div></details>`;
  }
  function selectionList(){
    if(!selection)return '';
    const list=selection.rows.slice(0,300);
    return `<section class="table-panel trace-selection"><div class="table-toolbar"><div><h2>${esc(selection.title)}</h2><span class="count-pill">${fmt(selection.rows.length)}</span></div><button class="tiny-button" data-clear-selection>Cerrar</button></div>
      <div class="table-wrap"><table><thead><tr><th>OPORTUNIDAD</th><th>ETAPA</th><th>ASESOR</th><th>CICLO</th><th>CONVOCATORIA</th><th>RESOLUCIÓN</th><th>EXTRACCIÓN</th><th>ACCIONES</th></tr></thead><tbody>${list.map(r=>`<tr><td><button class="name-button" data-open="${esc(r.number)}">${esc(r.name)}</button><span class="record-id">${esc(r.number)}</span></td><td>${esc(r.stage||'—')}</td><td>${esc(r.owner||'—')}</td><td>${esc(r.cycle||'—')}</td><td>${esc(r.test_call||'—')}</td><td>${esc(r.resolution||'—')}</td><td>${esc(r.detail_state)}</td><td><button class="row-action" data-timeline="${esc(r.number)}">Trazabilidad</button><button class="row-action" data-open="${esc(r.number)}">Abrir / editar</button></td></tr>`).join('')}</tbody></table></div>${selection.rows.length>list.length?`<p class="view-caption">Se muestran las primeras ${list.length}. Usa los filtros de Admisiones para el resto.</p>`:''}</section>`;
  }
  function timelinePanel(){
    const t=timeline;
    const head=`<section class="panel trace-timeline" id="trace-timeline"><div class="panel-title"><h2>Trazabilidad de una oportunidad</h2></div><form id="trace-search" class="trace-search"><input name="number" placeholder="Número oficial de la oportunidad" value="${esc(t?.number||'')}" aria-label="Número oficial"><button class="primary">Ver historial</button></form>${timelineError?`<p class="error">${esc(timelineError)}</p>`:''}`;
    if(!t)return head+'<p class="subtle">Muestra cada versión observada en Oracle, los cambios solicitados desde el portal, quién los hizo y su confirmación.</p></section>';
    const events=[
      ...(t.first_seen?[{at:t.first_seen,kind:'Primera observación en Oracle',detail:''}]:[]),
      ...t.timeline.filter(v=>v.kind==='oracle_change').map(v=>({at:v.at,kind:`Cambio observado en Oracle · versión ${v.version}`,detail:v.changes.map(c=>`${fieldName(c.field)}: «${c.before||'vacío'}» → «${c.after||'vacío'}»`).join(' · ')})),
      ...t.events.map(e=>({at:e.at,kind:actions[e.action]||e.action,detail:[fieldName(e.field),e.actor].filter(Boolean).join(' · ')})),
      ...(t.detail?.loaded_at?[{at:t.detail.loaded_at,kind:'Detalle leído de Oracle',detail:t.read_state?.state?`Estado: ${t.read_state.state}`:''}]:[])
    ].sort((a,b)=>String(b.at).localeCompare(String(a.at)));
    return head+`<p><strong>${esc([t.record.first_name,t.record.last_name].filter(Boolean).join(' ')||t.record.name)}</strong> · ${esc(t.number)} · ${esc(t.record.stage||'')} · ${esc(t.record.owner||'')} <button class="row-action" data-open="${esc(t.number)}">Abrir / editar</button></p>
      ${t.changes.length?`<div class="table-wrap"><table><thead><tr><th>CAMPO</th><th>ANTES</th><th>SOLICITADO</th><th>ESTADO</th><th>ACTUALIZADO</th></tr></thead><tbody>${t.changes.map(c=>`<tr><td>${esc(fieldName(c.field))}</td><td>${esc(c.old_value||'—')}</td><td>${esc(c.new_value||'—')}</td><td>${esc(states[c.state]||c.state)}</td><td>${esc(time(c.updated_at))}</td></tr>`).join('')}</tbody></table></div>`:''}
      <ol class="trace-events">${events.map(e=>`<li><time>${esc(time(e.at))}</time><strong>${esc(e.kind)}</strong>${e.detail?`<span>${esc(e.detail)}</span>`:''}</li>`).join('')||'<li>Sin eventos registrados.</li>'}</ol></section>`;
  }
  function draw(){
    if(!active()||!data)return;
    const list=rows(),k=data.kpis,ct=crossTab(list),dims=data.dimensions;
    const dimSelect=(id,current)=>`<select id="${id}">${dims.map(d=>`<option value="${d.key}" ${d.key===current?'selected':''}>${esc(d.label)}</option>`).join('')}</select>`;
    root.innerHTML=`<div class="page-heading"><div><span class="eyebrow">TRAZABILIDAD · COPIA LOCAL DE ORACLE</span><h1>Cruces y trazabilidad de oportunidades.</h1><p>Calculado sobre las oportunidades y campos que tus permisos de Oracle permiten ver. Última carga: ${esc(time(data.loaded_at))}${['pending','running'].includes(data.job?.state)?' · sincronización en curso':''}${k.unconfirmed?` · ${fmt(k.unconfirmed)} de la última copia por reconfirmar con Oracle`:''}</p></div><button id="trace-refresh">Actualizar</button></div>
      <div class="metrics">
        <div class="metric accent"><div class="metric-label">Oportunidades visibles</div><strong>${fmt(k.opportunities)}</strong><small>Inventario consultado</small></div>
        <div class="metric"><div class="metric-label">Con detalle extraído</div><strong>${pct(k.with_detail,k.opportunities)}%</strong><small>${fmt(k.with_detail)} fichas con pruebas, ayuda y matrícula</small></div>
        <div class="metric"><div class="metric-label">Asesores</div><strong>${fmt(k.owners)}</strong><small>Responsables con cartera</small></div>
        <div class="metric"><div class="metric-label">Cambios confirmados</div><strong>${fmt(k.changes_confirmed)}</strong><small>Guardados y releídos en Oracle</small></div>
        <div class="metric"><div class="metric-label">Cambios abiertos</div><strong>${fmt(k.changes_open)}</strong><small>En cola, inciertos o en conflicto</small></div>
      </div>
      <div class="panels"><section class="panel"><div class="panel-title"><h2>Embudo por etapa comercial</h2><span class="subtle">${fmt(list.length)} oportunidades</span></div>${bars(data.funnel,k.opportunities)}</section>
      <section class="panel"><div class="panel-title"><h2>Frescura de la copia</h2><span class="subtle">Última observación en Oracle</span></div>${bars(data.freshness,k.opportunities,{color:'#5b7f95'})}</section></div>
      <section class="table-panel trace-cross"><div class="table-toolbar"><div><h2>Cruce de datos</h2><span class="count-pill">${fmt(list.length)}</span></div><span class="subtle">Haz clic en una celda para ver sus oportunidades</span></div>
        <div class="filters"><label>Filas ${dimSelect('trace-row',rowDim)}</label><label>Columnas ${dimSelect('trace-col',colDim)}</label><label class="trace-check"><input type="checkbox" id="trace-detail" ${onlyDetail?'checked':''}> Solo con detalle extraído</label><button id="trace-swap">Intercambiar ⇄</button></div>
        <div class="table-wrap"><table class="trace-matrix"><thead><tr><th>${esc(label(rowDim))} \\ ${esc(label(colDim))}</th>${ct.cols.map(c=>`<th title="${esc(c)}">${esc(c)}</th>`).join('')}<th>TOTAL</th></tr></thead><tbody>
        ${ct.rows.map(r=>`<tr><td><strong>${esc(r)}</strong></td>${ct.cols.map(c=>{const n=(ct.cells.get(r+'\u0000'+c)||[]).length;return `<td class="trace-cell" ${heat(n,ct.max)}>${n?`<button data-cell-row="${esc(r)}" data-cell-col="${esc(c)}" title="${esc(r)} × ${esc(c)}: ${n}">${fmt(n)}</button>`:'<span class="trace-zero">·</span>'}</td>`;}).join('')}<td><button class="trace-total" data-cell-row="${esc(r)}">${fmt(ct.rCount.get(r))}</button></td></tr>`).join('')||`<tr><td colspan="${ct.cols.length+2}" class="empty">Sin oportunidades.</td></tr>`}
        </tbody><tfoot><tr><td><strong>Total</strong></td>${ct.cols.map(c=>`<td><button class="trace-total" data-cell-col="${esc(c)}">${fmt(ct.cCount.get(c)||0)}</button></td>`).join('')}<td><strong>${fmt(list.length)}</strong></td></tr></tfoot></table></div>
        <p class="view-caption">"Sin dato" agrupa campos vacíos o aún no extraídos; no equivale a que Oracle carezca del valor. ${onlyDetail?'':'Activa «Solo con detalle extraído» para cruces de pruebas, resolución y ayuda económica.'}</p></section>
      ${selectionList()}
      <div class="panels trace-lower"><section class="panel"><div class="panel-title"><h2>Controles de consistencia</h2><span class="subtle">Clic para ver los casos</span></div>${data.checks.map(c=>`<button class="trace-check-row" data-check="${c.id}" ${c.count?'':'disabled'}><span><strong>${esc(c.title)}</strong><small>${esc(c.description)}</small></span><b class="${c.count?'warn':''}">${fmt(c.count)}</b></button>`).join('')}</section>
      <section class="panel"><div class="panel-title"><h2>Actividad de los últimos 30 días</h2></div>${activityChart(data.activity.by_day)}
        <h2 class="trace-subtitle">Últimas acciones</h2><div class="trace-recent">${data.activity.recent.slice(0,15).map(e=>`<div class="audit-row"><span>${esc(time(e.at))}</span><strong>${esc(actions[e.action]||e.action)}</strong><span><button class="row-action" data-timeline="${esc(e.opportunity_number)}">${esc(e.opportunity_number)}</button> ${esc(e.field?fieldName(e.field):'')}<span class="record-id">${esc(e.actor)}</span></span></div>`).join('')||'<p class="subtle">Sin acciones registradas.</p>'}</div></section></div>
      ${timelinePanel()}`;
    bind();
  }
  /** The CSP forbids inline style attributes; sizes and shades are applied through CSSOM. */
  function applyStyles(){
    root.querySelectorAll('[data-width]').forEach(e=>{e.style.width=e.dataset.width+'%';e.style.background=e.dataset.color;});
    root.querySelectorAll('[data-height]').forEach(e=>{e.style.height=e.dataset.height+'%';});
    root.querySelectorAll('[data-heat]').forEach(e=>{const n=Number(e.dataset.heat);e.style.background=`color-mix(in srgb,var(--wine) ${n}%,white)`;e.style.color=n>52?'#fff':'#2b2f36';});
  }
  function bind(){
    applyStyles();
    root.querySelector('#trace-refresh').onclick=()=>render(root);
    root.querySelector('#trace-row').onchange=e=>{rowDim=e.target.value;selection=null;draw();};
    root.querySelector('#trace-col').onchange=e=>{colDim=e.target.value;selection=null;draw();};
    root.querySelector('#trace-detail').onchange=e=>{onlyDetail=e.target.checked;selection=null;draw();};
    root.querySelector('#trace-swap').onclick=()=>{[rowDim,colDim]=[colDim,rowDim];selection=null;draw();};
    root.querySelectorAll('[data-cell-row],[data-cell-col]').forEach(b=>b.onclick=()=>{
      const r=b.dataset.cellRow,c=b.dataset.cellCol,ct=crossTab(rows());
      const match=row=>(r===undefined||(row[rowDim]||EMPTY)===r)&&(c===undefined||(c==='Otros'?ct.otherSet.has(row[colDim]||EMPTY):(row[colDim]||EMPTY)===c));
      selection={title:[r!==undefined?`${label(rowDim)}: ${r}`:'',c!==undefined?`${label(colDim)}: ${c}`:''].filter(Boolean).join(' × '),rows:rows().filter(match)};
      draw();root.querySelector('.trace-selection')?.scrollIntoView({behavior:'smooth',block:'start'});
    });
    root.querySelectorAll('[data-check]').forEach(b=>b.onclick=()=>{
      const check=data.checks.find(c=>c.id===b.dataset.check),set=new Set(check.numbers);
      selection={title:check.title,rows:data.rows.filter(r=>set.has(r.number))};draw();root.querySelector('.trace-selection')?.scrollIntoView({behavior:'smooth',block:'start'});
    });
    root.querySelector('[data-clear-selection]')?.addEventListener('click',()=>{selection=null;draw();});
    root.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>window.UnisOracleLive.openRecord(b.dataset.open));
    root.querySelectorAll('[data-timeline]').forEach(b=>b.onclick=()=>openTimeline(b.dataset.timeline));
    root.querySelector('#trace-search').onsubmit=e=>{e.preventDefault();openTimeline(e.target.elements.number.value.trim());};
  }
  async function openTimeline(number){
    if(!number)return;timelineError='';
    try{timeline=await request('/api/oracle/trace/opportunity?number='+encodeURIComponent(number));}
    catch(e){timeline=null;timelineError=e.message;}
    draw();root.querySelector('#trace-timeline')?.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function reset(){data=null;selection=null;timeline=null;timelineError='';}
  document.addEventListener('hub-session-expired',reset);
  return {render,reset};
})();

"use strict";
window.HubAuth=(()=>{
  let ready=false,startApp,lastTouch=0,idleTimer,generation=0;
  const escape=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function lock(message=''){
    ready=false;generation++;window.UnisOracleLive?.reset();clearTimeout(idleTimer);document.body.classList.add('auth-locked');
    document.querySelectorAll('dialog[open]').forEach(d=>d.close());
    document.querySelector('#auth-logout').hidden=true;
    document.querySelector('#main').innerHTML=`<section class="login-card"><div class="login-brand"><img class="unis-crest" src="/unis-crest.png" alt="Universidad del Istmo" width="72" height="72"><span>UNIS<small>INTELLIGENT PROCESS HUB</small></span></div><span class="eyebrow">ACCESO A ADMISIONES</span><h1>Tu espacio de trabajo.</h1><p>Ingresa con tu usuario de Oracle. Consultaremos los datos con los permisos de tu sesión.</p><form id="login-form"><label>Usuario de Oracle<input name="username" autocomplete="username" required maxlength="150" autocapitalize="none" spellcheck="false"></label><label>Contraseña<input name="password" type="password" autocomplete="off" required maxlength="512"></label><p class="error" id="login-error" role="alert">${escape(message)}</p><button class="primary" type="submit">Iniciar sesión</button></form><p class="login-note">Tu contraseña se usa una vez para abrir la pantalla de Oracle y no se guarda. La sesión vence tras 15 minutos de inactividad. Si Oracle solicita una verificación adicional, el acceso no se completará automáticamente.</p></section>`;
    const form=document.querySelector('#login-form');form.onsubmit=async e=>{
      e.preventDefault();const button=form.querySelector('button');if(button.disabled)return;button.disabled=true;button.textContent='Verificando en Oracle…';
      const username=form.elements.username.value,password=form.elements.password.value;form.elements.password.value='';
      try{const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});const data=await r.json();if(!r.ok)throw Error(data.error);await unlock(data);}
      catch(error){document.querySelector('#login-error').textContent=error.message||'No se pudo conectar con Oracle.';button.disabled=false;button.textContent='Iniciar sesión';}
    };
  }
  function arm(){clearTimeout(idleTimer);idleTimer=setTimeout(()=>logout('La sesión terminó por inactividad.'),900000);}
  async function unlock(data){
    generation++;window.UnisOracleLive?.reset();ready=true;document.body.classList.remove('auth-locked');document.querySelector('#auth-logout').hidden=data.mode==='local';
    document.querySelector('#session-identity').textContent=data.display||'Operador local';
    arm();await startApp();
  }
  async function logout(message=''){ready=false;await fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>{});location.replace('/');}
  async function start(callback){startApp=callback;try{const r=await fetch('/api/auth/session');const data=await r.json();if(data.authenticated)await unlock(data);else lock();}catch{lock('No se pudo comprobar el acceso al portal.');}}
  document.addEventListener('hub-session-expired',()=>{if(ready)lock('Tu sesión terminó. Inicia sesión de nuevo.');});
  for(const event of ['pointerdown','keydown'])document.addEventListener(event,()=>{if(!ready)return;arm();if(Date.now()-lastTouch<30000)return;lastTouch=Date.now();fetch('/api/auth/touch',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>{});});
  document.addEventListener('DOMContentLoaded',()=>{document.querySelector('#auth-logout').onclick=()=>logout();});
  return {start,get generation(){return generation;},isAuthenticated:()=>ready,expired:()=>document.dispatchEvent(new Event('hub-session-expired'))};
})();

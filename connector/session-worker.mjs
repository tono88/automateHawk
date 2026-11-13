/** Oracle screen gateway: no Oracle APIs, persistent profiles, recordings or raw logs. */
import {applyScalarChange} from './oracle-write.mjs';
import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
import {randomBytes,timingSafeEqual} from 'node:crypto';
import {chromium} from 'playwright';
import {configureQuery,collectOpportunities,collectOpportunityDetail,openCachedDetail,captureOpenDetail,closeCachedDetail} from './oracle-sync.mjs';
const secret=readFileSync(process.env.HUB_WORKER_SECRET_FILE,'utf8').trim();
const target=new URL(process.env.ORACLE_URL);
if(target.protocol!=='https:'||!target.hostname.endsWith('.oraclecloud.com')||target.username||target.password||target.search)throw Error('configuration');
const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
const loginOrigin=new URL(process.env.ORACLE_LOGIN_ORIGIN).origin;
if(!loginOrigin.startsWith('https://')||!loginOrigin.endsWith('.identity.oraclecloud.com'))throw Error('configuration');
const sessions=new Map();let active=0,pendingLogins=0;const waiters=[];
const LIMIT=2,MAX_SESSIONS=8,IDLE=15*60*1000,MAX_AGE=8*60*60*1000;
async function slot(fn){if(active>=LIMIT)await new Promise(r=>waiters.push(r));else active++;try{return await fn();}finally{const next=waiters.shift();if(next)next();else active--;}}
async function remove(id){const s=sessions.get(id);sessions.delete(id);if(s)await s.context.close().catch(()=>{});}
function alive(s){return s&&Date.now()-s.seen<IDLE&&Date.now()-s.created<MAX_AGE;}
function trusted(page){return new URL(page.url()).origin===target.origin;}
async function authenticated(page){return trusted(page)&&await page.getByRole('link',{name:'PÃ¡gina Inicial',exact:true}).count()>0;}
function adapter(page){return {ui:page,observe:async()=>{await page.locator('body').waitFor({state:'visible'});await page.waitForTimeout(300);},clickAdvanced:async()=>{const b=page.getByRole('button',{name:'Mostrar bÃºsqueda avanzada',exact:true});if(await b.count())await b.click();else if(!await page.getByRole('button',{name:'Ocultar bÃºsqueda avanzada',exact:true}).count())throw Error('layout');},scrollGrid:async(direction='down')=>{const fingerprint=()=>Array.from(document.querySelectorAll('table')).filter(t=>t.getAttribute('summary')==='Oportunidad').map(t=>t.getAttribute('_startrow')+':'+t.rows.length).join('|');const before=await page.evaluate(fingerprint);const scroller=page.locator('div[id$="::scroller"]:visible').last();if(await scroller.count()){await scroller.hover();await page.mouse.wheel(0,direction==='up'?-650:650);}else{const t=page.getByRole('table',{name:'Oportunidad',exact:true}).last();await t.getByRole('row').last().getByRole('link').last().press(direction==='up'?'PageUp':'PageDown');}await page.waitForFunction(prior=>Array.from(document.querySelectorAll('table')).filter(t=>t.getAttribute('summary')==='Oportunidad').map(t=>t.getAttribute('_startrow')+':'+t.rows.length).join('|')!==prior,before,{timeout:10000}).catch(()=>{});}};}
async function login(body){
  if(sessions.size+pendingLogins>=MAX_SESSIONS)throw Error('capacity');
  pendingLogins++;let context,page;
  try{
  context=await browser.newContext({acceptDownloads:true,locale:'es-GT'});
  // Only this institutional tenant may receive a form submission.
  await context.route('**/*',async route=>{const u=new URL(route.request().url());if(route.request().method()==='POST'&&u.origin!==target.origin&&u.origin!==loginOrigin)return route.abort();return route.continue();});
    page=await context.newPage();await page.goto(target.href,{waitUntil:'domcontentloaded',timeout:45000});
    if(!trusted(page)&&new URL(page.url()).origin!==loginOrigin)throw Error('login-destination');
    const user=page.locator('#userid,[id="idcs-signin-basic-signin-form-username|input"]'),password=page.locator('input[type="password"]');
    await user.first().waitFor({state:'visible',timeout:20000}).catch(()=>{});
    if(await user.count()!==1||await password.count()!==1)throw Error('login-layout');
    await user.fill(body.username);await password.fill(body.password);
    body.password='';
    const submit=page.getByRole('button',{name:/^(Sign In|Iniciar sesión|Iniciar sesión segura|Acceder)$/i});
    if(await submit.count())await submit.click();else await password.press('Enter');
    try{await page.getByRole('link',{name:'PÃ¡gina Inicial',exact:true}).waitFor({state:'visible',timeout:45000});}catch{throw Error('credentials-or-challenge');}
    if(!await authenticated(page))throw Error('session');
    const identity=await page.locator('h1').first().innerText().catch(()=>'Cuenta de Oracle');
    const id=randomBytes(32).toString('base64url'),now=Date.now();
    sessions.set(id,{context,seen:now,created:now,busy:false});await page.close();
    return {id,principal:body.username.trim().toLocaleLowerCase('en'),display:identity.slice(0,180)};
  }catch(error){if(context)await context.close();throw error;}finally{pendingLogins--;body.password='';}
}
async function run(body){
  const s=sessions.get(body.id);if(!alive(s))throw Error('session');
  if(s.busy)throw Error('busy');s.busy=true;s.seen=Date.now();let page;
  try{
    page=await s.context.newPage();await page.goto(target.href,{waitUntil:'domcontentloaded',timeout:45000});
    await page.getByRole('link',{name:'PÃ¡gina Inicial',exact:true}).waitFor({state:'visible',timeout:30000}).catch(()=>{throw Error('session');});
    if(!await authenticated(page))throw Error('session');
    const a=adapter(page);let result;
    if(body.kind==='write')result=await applyScalarChange(a,body.change);
    else if(body.kind==='detail')result=await collectOpportunityDetail(a,body.number);
    else {
      await configureQuery(a);
      await page.getByRole('button',{name:'Acciones',exact:true}).click();
      await page.getByRole('menuitem',{name:'Exportar',exact:true}).waitFor({state:'visible',timeout:10000});
      const [download]=await Promise.all([page.waitForEvent('download',{timeout:65000}),page.getByRole('menuitem',{name:'Exportar',exact:true}).click()]);
      let bytes=0;const chunks=[];
      try {
        const stream=await download.createReadStream();
        for await(const chunk of stream){bytes+=chunk.length;if(bytes>10_000_000)throw Error('export-limit');chunks.push(chunk);}
        result={export_html:Buffer.concat(chunks).toString('utf8'),scope:'Todos los registros que puedo ver · oportunidades abiertas · año actual · exportación de Oracle'};
      } finally {await download.delete().catch(()=>{});}
    }
    s.seen=Date.now();return result;
  }finally{s.busy=false;if(page)await page.close().catch(()=>{});}
}
const safe=new Set(['session','busy','capacity','login-layout','login-destination','credentials-or-challenge','layout','empty','permission','conflict','validation','side-effects','uncertain','write-not-started']);
const http=createServer(async(req,res)=>{
  const respond=(code,data)=>{res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
  const supplied=Buffer.from(req.headers['x-worker-secret']||''),expected=Buffer.from(secret);
  if(supplied.length!==expected.length||!timingSafeEqual(supplied,expected))return respond(403,{code:'forbidden'});
  if(req.method!=='POST')return respond(405,{code:'method'});
  let raw='',body;
  try{
    for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>16384)throw Error('invalid');}
    body=JSON.parse(raw);raw='';
    if(req.url==='/login')return respond(200,await slot(()=>login(body)));
    if(req.url==='/logout'){await remove(body.id);return respond(200,{ok:true});}
    if(req.url==='/alive'){const s=sessions.get(body.id);if(!alive(s)){await remove(body.id);throw Error('session');}s.seen=Date.now();return respond(200,{ok:true});}
    if(req.url==='/run')return respond(200,await slot(()=>run(body)));
    return respond(404,{code:'missing'});
  }catch(error){return respond(400,{code:safe.has(error.message)?error.message:'unavailable'});}finally{if(body)body.password='';raw='';}
});
http.requestTimeout=15000;
http.listen(8767,'0.0.0.0');
setInterval(()=>{for(const [id,s]of sessions)if(!s.busy&&!alive(s))remove(id);},30000).unref();
process.on('SIGTERM',async()=>{http.close();await browser.close();process.exit(0);});

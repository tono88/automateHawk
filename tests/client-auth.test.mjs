import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

async function client(){
  const elements=new Map(),events={},requests=[];let timer,navigations=0;
  const document={body:{classList:{add(){},remove(){}}},
    querySelector(selector){if(!elements.has(selector))elements.set(selector,{});return elements.get(selector);},
    querySelectorAll(){return [];},addEventListener(name,fn){events[name]=fn;}};
  const context={window:{},document,location:{replace(){navigations++;}},Date,clearTimeout(){},setTimeout(fn){timer=fn;},
    fetch:async path=>{requests.push(path);return {json:async()=>({authenticated:true,mode:'screen',display:'Sintético'})};}};
  vm.runInNewContext(readFileSync(new URL('../app/static/auth.js',import.meta.url),'utf8'),context);
  await context.window.HubAuth.start(async()=>{});
  return {context,elements,requests,events,idle:()=>timer(),navigations:()=>navigations};
}
test('idle locks the client without revoking an authorized background read',async()=>{
  const c=await client();assert.equal(c.context.window.HubAuth.isAuthenticated(),true);
  c.idle();assert.equal(c.context.window.HubAuth.isAuthenticated(),false);
  assert.match(c.elements.get('#main').innerHTML,/id="login-form"/);
  assert.equal(c.requests.includes('/api/auth/logout'),false);assert.equal(c.navigations(),0);
});
test('explicit logout still revokes the server session',async()=>{
  const c=await client();c.events.DOMContentLoaded();await c.elements.get('#auth-logout').onclick();
  assert.equal(c.requests.includes('/api/auth/logout'),true);assert.equal(c.navigations(),1);
});
test('a synchronisation in progress keeps the portal open past the idle timeout',async()=>{
  const c=await client();let syncing=true;c.context.window.UnisOracleLive={reset(){},syncActive:()=>syncing};
  c.idle();assert.equal(c.context.window.HubAuth.isAuthenticated(),true);
  syncing=false;c.idle();assert.equal(c.context.window.HubAuth.isAuthenticated(),false);
});

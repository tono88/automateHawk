import test from 'node:test';
import assert from 'node:assert/strict';
import {ensureReadPage} from '../connector/read-page-auth.mjs';
const tenant='https://tenant.oraclecloud.com';
function page({ready=false,closed=false,origin=tenant,login=false}={}){return{url:()=>origin+'/screen',isClosed:()=>closed,getByRole:()=>({waitFor:async()=>{if(!ready)throw Error('timeout');}}),locator:()=>({count:async()=>login?1:0})};}
test('slow trusted pages are retryable and do not revoke the whole login',async()=>{
 await assert.rejects(()=>ensureReadPage(page(),tenant),/unavailable/);
 await assert.rejects(()=>ensureReadPage(page({closed:true}),tenant),/unavailable/);
});
test('real login forms and redirects require reauthentication; trusted ready pages pass',async()=>{
 await assert.rejects(()=>ensureReadPage(page({login:true}),tenant),/session/);
 await assert.rejects(()=>ensureReadPage(page({origin:'https://idcs.example.invalid'}),tenant),/session/);
 await assert.rejects(()=>ensureReadPage(page({ready:true,origin:'https://idcs.example.invalid'}),tenant),/session/);
 await ensureReadPage(page({ready:true}),tenant);
});

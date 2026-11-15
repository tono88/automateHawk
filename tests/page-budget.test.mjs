import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {PageBudget} from '../connector/page-budget.mjs';
class Page extends EventEmitter{closed=false;isClosed(){return this.closed;}async close(){this.closed=true;this.emit('close');}}
const context=()=>({newPage:async()=>new Page()});
test('global budget evicts only an idle page and preserves active user pages',async()=>{
 const idle=[],budget=new PageBudget(2,()=>idle.shift()),c=context();
 const active=await budget.create(c),cached=await budget.create(c);idle.push(cached);
 const next=await budget.create(c);assert.ok(cached.isClosed());assert.ok(!active.isClosed());assert.ok(!next.isClosed());assert.equal(budget.pages.size,2);
 await assert.rejects(()=>budget.create(c),/busy/);await active.close();assert.equal(budget.pages.size,1);
});
test('parallel creation reservations prevent capacity oversubscription',async()=>{
 const budget=new PageBudget(1,()=>null);let release;
 const first=budget.create({newPage:()=>new Promise(r=>{release=r;})});
 await assert.rejects(()=>budget.create(context()),/busy/);release(new Page());await first;
 assert.equal(budget.pages.size,1);assert.equal(budget.reserved,0);
});
test('failed page creation and failed eviction restore budget accounting',async()=>{
 const budget=new PageBudget(1,()=>null);
 await assert.rejects(()=>budget.create({newPage:async()=>{throw Error('session');}}));assert.equal(budget.reserved,0);
 const page=await budget.create(context());page.close=async()=>{throw Error('busy');};budget.takeIdle=()=>page;
 await assert.rejects(()=>budget.create(context()),/busy/);assert.equal(budget.pages.size,1);assert.equal(budget.reserved,0);
});

test('an unrelated idle page cannot increase the managed page allowance',async()=>{
 const foreign=new Page(),budget=new PageBudget(1,()=>foreign),active=await budget.create(context());
 await assert.rejects(()=>budget.create(context()),/busy/);assert.equal(budget.pages.size,1);assert.ok(!active.isClosed());
});

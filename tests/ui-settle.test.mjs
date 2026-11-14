import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {uiSettler} from '../connector/ui-settle.mjs';
const request=(method='POST')=>({method:()=>method,url:()=>'https://tenant.oraclecloud.com/crmUI/visible-page'});
function harness(){const page=new EventEmitter();let time=0;const jobs=[];
 const settle=uiSettler(page,'https://tenant.oraclecloud.com',{quietMs:200,timeoutMs:1000,now:()=>time,pause:async ms=>{time+=ms;while(jobs.length&&jobs[0][0]<=time)jobs.shift()[1]();}});
 return {page,settle,jobs,now:()=>time};}
test('persistent GET does not block a completed UI POST and observers are reused',async()=>{
 const h=harness(),post=request();h.page.emit('request',request('GET'));h.page.emit('request',post);
 h.jobs.push([400,()=>h.page.emit('requestfinished',post)]);
 await h.settle();assert.equal(h.now(),600);
 assert.equal(uiSettler(h.page,'https://tenant.oraclecloud.com'),h.settle);assert.equal(h.page.listenerCount('request'),1);
 h.page.emit('close');assert.equal(h.page.listenerCount('request'),0);
});
test('late queued POST resets quiet time; failed requests release it; stalled updates time out',async()=>{
 const h=harness(),post=request();h.jobs.push([100,()=>h.page.emit('request',post)],[400,()=>h.page.emit('requestfailed',post)]);
 await h.settle();assert.equal(h.now(),600);
 const stuck=harness();stuck.page.emit('request',request());await assert.rejects(()=>stuck.settle(),/timeout/);assert.equal(stuck.now(),1000);
});

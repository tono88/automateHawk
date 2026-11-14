/** Wait for user-triggered POST updates; ignore Oracle's persistent GET channel.
 * Observes lifecycle only; diagnostics omit query values, bodies and headers.
 */
const waiters=new WeakMap();
export function uiSettler(page,origin,{quietMs=600,timeoutMs=20000,now=()=>performance.now(),pause=ms=>page.waitForTimeout(ms)}={}){
  if(waiters.has(page))return waiters.get(page);
  const pending=new Set();let changed=now();
  const began=request=>{
    if(request.method()==='POST'&&new URL(request.url()).origin===origin){pending.add(request);changed=now();}
  };
  const ended=request=>{if(pending.delete(request))changed=now();};
  page.on('request',began);page.on('requestfinished',ended);page.on('requestfailed',ended);
  page.once('close',()=>{page.off('request',began);page.off('requestfinished',ended);page.off('requestfailed',ended);});
  const settle=async()=>{
    const start=now();let quietSince=start;
    while(true){
      quietSince=Math.max(quietSince,changed);
      if(!pending.size&&now()-quietSince>=quietMs)return;
      if(now()-start>=timeoutMs)throw Error('timeout');
      await pause(Math.min(100,Math.max(1,timeoutMs-(now()-start))));
    }
  };
  settle.pending=()=>Array.from(pending).map(request=>({path:new URL(request.url()).pathname.replace(/[0-9]{4,}/g,'#'),type:request.resourceType?.()||'unknown'}));
  waiters.set(page,settle);return settle;
}

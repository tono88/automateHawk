/** Predicate-first waits: no delay on a ready screen, bounded on a slow one. */
export async function waitForRendered(adapter,predicate,{timeoutMs=20000,now=()=>performance.now(),pause=ms=>new Promise(r=>setTimeout(r,ms))}={}) {
  const deadline=now()+timeoutMs;let attempt=0;
  while(true){
    await adapter.observe();
    try{if(await predicate())return;}catch{/* ADF replaces detached controls. */}
    if(now()>=deadline)throw Error('timeout');
    await pause(Math.min(75*Math.pow(1.35,attempt++),350,Math.max(0,deadline-now())));
  }
}

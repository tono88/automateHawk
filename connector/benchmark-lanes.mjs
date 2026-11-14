/** Operator CLI: repeat the same authorized UI reads with 2 and 4 lanes.
 * Credentials arrive on stdin, values stay in memory, only aggregate timing leaves.
 */
import {readFileSync} from 'node:fs';
let raw='';for await(const chunk of process.stdin){raw+=chunk;if(raw.length>16384)throw Error('input-limit');}
let input;try{input=JSON.parse(raw);}catch{raw='';throw Error('input');}raw='';
if(!Array.isArray(input.numbers)||input.numbers.length<8||input.numbers.length>40||new Set(input.numbers).size!==input.numbers.length||input.numbers.some(n=>typeof n!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(n)))throw Error('input');
const secret=readFileSync(process.env.HUB_WORKER_SECRET_FILE,'utf8').trim();
async function rpc(path,body){const response=await fetch('http://127.0.0.1:8767'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Worker-Secret':secret},body:JSON.stringify(body),signal:AbortSignal.timeout(160000)});const result=await response.json();if(!response.ok)throw Error(result.code||'unavailable');return result;}
const modes=input.modes||[{contexts:1,lanes:2},{contexts:1,lanes:4},{contexts:2,lanes:2}];
if(!Array.isArray(modes)||!modes.length||modes.length>3||modes.some(m=>![1,2].includes(m.contexts)||![2,4].includes(m.lanes)||m.contexts*m.lanes>4))throw Error('input');
try{
 for(const {contexts,lanes} of modes){
  let sessions=[];const started=performance.now(),durations=[];let cursor=0,completed=0,partial=0,retries=0;const failures=[];
  try{
   const logins=await Promise.allSettled(Array.from({length:contexts},()=>rpc('/login',{username:input.username,password:input.password})));
   sessions=logins.filter(r=>r.status==='fulfilled').map(r=>r.value);
   if(sessions.length!==contexts)throw Error('login-failed');
   console.log(JSON.stringify({phase:'started',contexts,lanes,records:input.numbers.length}));
   await Promise.all(Array.from({length:contexts*lanes},async(_,worker)=>{const lane=worker%lanes,session=sessions[Math.floor(worker/lanes)];
    while(cursor<input.numbers.length){const index=cursor++,number=input.numbers[index],before=performance.now();
     try{let result;
      for(let attempt=1;attempt<=3;attempt++){
       try{result=await rpc('/run',{id:session.id,kind:'detail',number,reuse:true,lane});break;}
       catch(error){if(attempt===3||!['unavailable','busy','layout'].includes(error.message))throw error;retries++;await new Promise(r=>setTimeout(r,attempt*500));}
      }
      if(result.opportunity_number!==number||result.schema_version!==2)throw Error('identity');
      if(result.pending_modules?.length)partial++;else completed++;
      durations.push((performance.now()-before)/1000);result=null;
     }catch(error){failures.push({index,code:['identity','session','layout','unavailable'].includes(error.message)?error.message:'error'});}
     if((completed+partial+failures.length)%4===0)console.log(JSON.stringify({phase:'progress',contexts,lanes,completed,partial,retries,failures:failures.length}));
    }
   }));
   const seconds=(performance.now()-started)/1000;
   console.log(JSON.stringify({phase:'result',contexts,lanes,records:input.numbers.length,completed,partial,retries,failures:failures.length,seconds:Math.round(seconds*100)/100,records_per_minute:Math.round((completed+partial)/seconds*6000)/100,mean_read_seconds:Math.round(durations.reduce((a,b)=>a+b,0)/durations.length*100)/100}));
   if(failures.length||partial)throw Error('benchmark-incomplete');
  }finally{await Promise.allSettled(sessions.map(session=>rpc('/logout',{id:session.id})));}
 }
}finally{input.password='';input.username='';input.numbers=[];}

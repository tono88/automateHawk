"use strict";
globalThis.UnisTableTools=(()=>{
  const collator=new Intl.Collator('es',{numeric:true,sensitivity:'base'});
  const numbers=new Set(['probability','amount','financial_requested_1','financial_granted_1','activities','local_activities','global_score','paa_score','grade_average','required_score','payment_amount','financial_requested_2','financial_granted_2']);
  const dates=new Set(['created_at','updated_at','pda_date','birth_date','payment_date','enrollment_due','letter_date','interview_date','close_date','test_date','documents_due','reservation_close','_last_seen']);
  function number(value){
    if(typeof value==='number')return Number.isFinite(value)?value:null;
    let text=String(value??'').replace(/[^0-9.,-]/g,'');if(!text)return null;
    if(text.includes(',')&&text.includes('.'))text=text.lastIndexOf(',')>text.lastIndexOf('.')?text.replace(/\./g,'').replace(',','.'):text.replace(/,/g,'');
    else if(text.includes(','))text=/^-?\d{1,3}(,\d{3})+$/.test(text)?text.replace(/,/g,''):text.replace(',','.');
    const result=Number(text);return Number.isFinite(result)?result:null;
  }
  function date(value){
    const text=String(value??'').trim();
    const local=text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})(?:\s|$)/);
    if(local){const y=Number(local[3].length===2?'20'+local[3]:local[3]),m=Number(local[2]),d=Number(local[1]);const n=Date.UTC(y,m-1,d),v=new Date(n);return v.getUTCFullYear()===y&&v.getUTCMonth()===m-1&&v.getUTCDate()===d?n:null;}
    if(!/^\d{4}-\d{2}-\d{2}(?:T|$)/.test(text))return null;
    const n=Date.parse(text);return Number.isFinite(n)?n:null;
  }
  function sort(rows,key,direction,get){
    if(!key)return rows.slice();
    const factor=direction==='desc'?-1:1;
    const normalized=row=>{const v=get(row,key);if(v===null||v===undefined||String(v).trim()==='')return null;return numbers.has(key)?number(v):dates.has(key)?date(v):String(v);};
    return rows.map((row,index)=>({row,index,value:normalized(row)})).sort((a,b)=>{
      if(a.value===null&&b.value!==null)return 1;if(b.value===null&&a.value!==null)return -1;
      let order=0;if(a.value!==null&&b.value!==null)order=typeof a.value==='number'&&typeof b.value==='number'?a.value-b.value:collator.compare(a.value,b.value);
      return order*factor||collator.compare(a.row.opportunity_number||'',b.row.opportunity_number||'')||a.index-b.index;
    }).map(x=>x.row);
  }
  function paginate(rows,size,page){
    const count=size==='all'?Math.max(1,rows.length):[12,25,50,100,250].includes(Number(size))?Number(size):12;
    const pages=Math.max(1,Math.ceil(rows.length/count));page=Math.min(pages,Math.max(1,page));
    const start=(page-1)*count;return {rows:rows.slice(start,start+count),pages,page,start:rows.length?start+1:0,end:Math.min(start+count,rows.length)};
  }
  return {sort,paginate};
})();

/** A global page budget across users; active pages are never eviction candidates. */
export class PageBudget {
 constructor(limit,takeIdle){
  if(!Number.isInteger(limit)||limit<1||limit>4)throw Error('configuration');
  this.limit=limit;this.takeIdle=takeIdle;this.pages=new Set();this.reserved=0;
 }
 async create(context){
  let victim;
  if(this.pages.size+this.reserved>=this.limit){
   victim=this.takeIdle();
   if(!victim||!this.pages.has(victim))throw Error('busy');
   this.pages.delete(victim);
  }
  this.reserved++;
  try{
   if(victim){try{await victim.close();}catch{if(!victim.isClosed()){this.pages.add(victim);throw Error('busy');}}}
   const page=await context.newPage();this.pages.add(page);
   page.once('close',()=>this.pages.delete(page));
   if(page.isClosed()){this.pages.delete(page);throw Error('session');}
   return page;
  }finally{this.reserved--;}
 }
}

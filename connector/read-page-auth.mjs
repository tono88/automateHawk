/** A slow page is not proof that the Oracle login was revoked. */
export async function ensureReadPage(page,origin,{timeout=45000}={}){
 const home=page.getByRole('link',{name:'Página Inicial',exact:true});
 try{await home.waitFor({state:'visible',timeout});}
 catch{
  if(page.isClosed())throw Error('unavailable');
  const destination=new URL(page.url()).origin;
  const login=await page.locator('input[type="password"]:visible').count();
  if(destination!==origin||login)throw Error('session');
  throw Error('unavailable');
 }
 if(new URL(page.url()).origin!==origin)throw Error('session');
}

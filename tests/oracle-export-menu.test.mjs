import test from 'node:test';
import assert from 'node:assert/strict';
import {openExportMenu} from '../connector/oracle-export-menu.mjs';
function mock({empty=false,ready=false,opens=1}={}){
 let presses=0;
 const menu={isVisible:async()=>ready,waitFor:async()=>{if(presses<opens)throw Error('redraw');ready=true;}};
 return {get presses(){return presses;},observe:async()=>{},ui:{locator:()=>({count:async()=>1,click:async()=>{presses++;}}),getByText:()=>({isVisible:async()=>empty}),getByRole:role=>role==='menuitem'?menu:{click:async()=>{presses++;}}}};
}
test('does not try to export an empty query or toggle an open menu',async()=>{
 for(const [config,result] of [[{empty:true},'empty'],[{ready:true},'ready']]){const a=mock(config);assert.equal(await openExportMenu(a),result);assert.equal(a.presses,0);}
});
test('recovers a replaced toolbar and bounds repeated menu failures',async()=>{
 const a=mock({opens:2});assert.equal(await openExportMenu(a),'ready');assert.equal(a.presses,2);
 const b=mock({opens:99});await assert.rejects(()=>openExportMenu(b),/timeout/);assert.equal(b.presses,4);
});

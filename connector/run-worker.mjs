/** Standalone option. User signs in interactively; no session files are saved. */
import {chromium} from 'playwright';
import {startWorker} from './oracle-sync.mjs';
const target=process.env.ORACLE_URL;
if(!target) throw Error('Define ORACLE_URL con la dirección institucional de Oracle. No incluyas credenciales.');
const url=new URL(target);
if(url.protocol!=='https:'||!url.hostname.endsWith('.oraclecloud.com')||url.username||url.password) throw Error('Se requiere una dirección HTTPS de Oracle Cloud sin credenciales.');
const browser=await chromium.launch({headless:false});
const context=await browser.newContext({acceptDownloads:false});
const page=await context.newPage();
await page.goto(url.href);
console.log('Inicia sesión en la ventana de Oracle. Después utiliza Cargar desde Oracle en el portal local.');
const adapter={
  ui:page,
  observe:async()=>{await page.locator('body').waitFor({state:'visible'});await page.waitForTimeout(600);},
  clickAdvanced:async()=>{
    const show=page.getByText('Mostrar búsqueda avanzada',{exact:true});
    if(await show.count())await show.click();
    else if(!await page.getByText('Ocultar búsqueda avanzada',{exact:true}).count())throw Error('layout');
  },
  scrollGrid:async()=>{
    const box=await page.getByRole('table',{name:'Oportunidad',exact:true}).last().boundingBox();
    if(!box)throw Error('layout');
    await page.mouse.move(box.x+Math.min(box.width,300)/2,box.y+Math.min(box.height,200)/2);
    await page.mouse.wheel(0,900);
    await page.waitForTimeout(600);
  }
};
const worker=startWorker(adapter,process.env.HUB_URL||'http://127.0.0.1:8765');
process.on('SIGINT',async()=>{worker.stop();await browser.close();process.exit(0);});
await worker.finished;

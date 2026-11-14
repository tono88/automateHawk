/** ADF can replace a search toolbar while its menu is opening. */
export async function openExportMenu(adapter){
  const {ui}=adapter;
  const empty=ui.getByText('No se ha encontrado ningún resultado.',{exact:true});
  const menu=ui.getByRole('menuitem',{name:'Exportar',exact:true});
  for(let attempt=0;attempt<4;attempt++){
    await adapter.observe();
    if(await empty.isVisible())return 'empty';
    if(await menu.isVisible())return 'ready';
    adapter.phase='export-actions';
    const arrow=ui.locator('a[title="Acciones"][id$="::popEl"]');
    if(await arrow.count()===1)await arrow.click();else await ui.getByRole('button',{name:'Acciones',exact:true}).click();
    adapter.phase='export-menu';
    try{await menu.waitFor({state:'visible',timeout:4000});return 'ready';}catch{}
  }
  throw Error('timeout');
}

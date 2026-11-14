/** Open the rendered advanced-search controls, including ADF checkbox variants. */
export async function ensureAdvancedSearch(ui,observe){
  const scope=ui.getByRole('combobox',{name:'Juego de registros',exact:true});
  for(let attempt=0;attempt<3;attempt++){
    if(await scope.count())return;
    const showCheck=ui.getByRole('checkbox',{name:'Mostrar búsqueda avanzada',exact:true}).first();
    const hideCheck=ui.getByRole('checkbox',{name:'Ocultar búsqueda avanzada',exact:true}).first();
    const show=ui.getByRole('button',{name:'Mostrar búsqueda avanzada',exact:true}).first();
    const hide=ui.getByRole('button',{name:'Ocultar búsqueda avanzada',exact:true}).first();
    if(await showCheck.count()){if(attempt){await showCheck.uncheck();await observe();}await showCheck.check();}
    else if(await hideCheck.count()){await hideCheck.uncheck();await observe();await showCheck.check();}
    else if(await show.count())await show.click();
    else if(await hide.count()){await hide.click();await observe();await show.click();}
    else throw Error('layout');
    for(let i=0;i<6;i++){await observe();if(await scope.count())return;await new Promise(r=>setTimeout(r,150));}
  }
  throw Error('layout');
}

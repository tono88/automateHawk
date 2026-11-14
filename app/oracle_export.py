"""Parse Oracle's user-triggered HTML Excel export in memory; never execute it."""
import re
from html.parser import HTMLParser
from .domain import ValidationError
COLUMNS={'Número de oportunidad':'opportunity_number','Nombre de contacto principal':'first_name','Apellido de contacto principal':'last_name','Nombre':'name','Cuenta':'account','Fecha de cierre':'close_date','Éxito (%)':'probability','Etapa de ventas':'stage','Estado':'status','Segmento':'segment','Contacto principal':'contact_name','Responsable':'owner','Teléfono':'phone','Importe':'amount','Correo electrónico de responsable':'owner_email','Fecha de creación de oportunidad':'created_at','Última actualización de oportunidad':'updated_at'}
class ExportTable(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]
        elif tag=='br' and self.cell is not None:self.cell.append(' ')
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.row is not None and self.cell is not None:self.row.append(''.join(self.cell).strip());self.cell=None
        elif tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None

def parse_export(html,scope):
    if not isinstance(html,str) or len(html.encode('utf-8'))>10_000_000:raise ValidationError('Exportación demasiado grande.')
    table=ExportTable();table.feed(html)
    header=next((r for r in table.rows if 'Número de oportunidad' in r),None)
    if not header:raise ValidationError('No se reconocieron las columnas exportadas por Oracle.')
    records={}
    for cells in table.rows:
        if len(cells)!=len(header) or cells==header:continue
        row={COLUMNS[h]:cells[i] for i,h in enumerate(header) if h in COLUMNS}
        number=row.get('opportunity_number','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',number):continue
        records[number]=row
        if len(records)>=1000:break
    if not records:raise ValidationError('Oracle no exportó filas verificables.')
    return {'records':list(records.values()),'scope':scope,'partial':True,'visible_fields':{n:list(r) for n,r in records.items()}}

"""Schemas contain observed UI labels, never real records or credentials."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

STAGES = ['01 - Interesado', '02 - Inscrito a prueba', '03 - Presente a prueba: resolución', '04 - Perdida', '05 - Matriculado', '06 - Inscrito']
RESPONSES = ['Llamada Contestada', 'No responde', 'Número Equivocado', 'Respuesta Positiva', 'Respuesta Negativa']
OWNERS = ['Asesor Demo A', 'Asesor Demo B', 'Asesor Demo C']
FACULTIES = ['Ingeniería', 'Arquitectura y Diseño', 'Ciencias Económicas', 'Derecho', 'Comunicación']

def field(key, label, kind='text', required=False, options=None, source='observado'):
    return dict(key=key, label=label, kind=kind, required=required, options=options or [], source=source)

SCHEMAS = {
 'contacts': dict(title='Contactos', singular='contacto', fields=[
    field('first_name','Nombre',required=True), field('middle_name','Segundo nombre'),
    field('last_name','Apellidos',required=True),field('second_last_name','Segundo apellido'),
    field('email','Correo electrónico','email'),field('phone','Teléfono móvil'),field('account','Cuenta'),
    field('graduation','Año de graduación Colegio'),field('segment','Segmento'),
    field('owner','Responsable','select',True,OWNERS,'propuesto'),
    field('faculty','Facultad','select',True,FACULTIES,'excel'),
    field('career','Carrera',source='excel'),field('school','Colegio',source='excel'),
    field('cycle','Ciclo de Ingreso','select',True,['2263','2271'],'lista observada'),
    field('test_type','Tipo de PDA','select',False,['PDA','PAA','Convenio'],'excel'),
    field('test_date','Fecha PDA','date',source='excel'),
    field('dossier','Expediente','select',False,['Pendiente','Incompleto','Completo'],'excel'),
    field('payment','Estado de pago','select',False,['Pendiente','Confirmado','Convenio'],'propuesto'),
    field('resolution','Admisión','select',False,['Pendiente','Admitido','No admitido'],'excel'),
    field('letter','Carta Entregada','select',False,['Pendiente','Entregada'],'excel'),
    field('enrollment_due','Fecha máxima de matrícula','date',source='excel'),
    field('notes','Comentarios seguimiento','textarea',source='excel')]),
 'opportunities': dict(title='Oportunidades',singular='oportunidad',fields=[
    field('name','Nombre',required=True),field('account','Cuenta'),field('contact_id','Contacto principal','contact'),
    field('probability','Probabilidad de ganar (%)','number'),field('close_date','Fecha de cierre','date',True),
    field('stage','Etapa de ventas','select',True,STAGES)]),
 'leads': dict(title='Oportunidades potenciales',singular='oportunidad potencial',fields=[
    field('contact_id','Contacto existente','contact'),field('name','Nombre de oportunidad potencial',required=True),
    field('job_title','Cargo'),field('account','Cuenta existente'),field('group','Grupo'),
    field('product_group','Grupo de productos'),field('phone','Teléfono de contacto'),field('email','Correo electrónico de contacto','email'),
    field('origin','Origen'),field('campaign','Campaña'),field('owner','Responsable','select',True,OWNERS)]),
 'tasks': dict(title='Tareas',singular='tarea',fields=[
    field('subject','Asunto',required=True),field('activity_with','Actividad se realizará con'),field('activity','Actividad'),
    field('owner','Responsable','select',True,OWNERS),field('state','Estado','text'),field('priority','Prioridad'),
    field('contact_id','Contacto principal','contact'),field('account','Cuenta'),
    *[f for n in range(1,5) for f in [field(f'interaction_{n}',f'Interacción {n}','date'),field(f'response_{n}',f'Respuesta Interacción {n}','select',False,RESPONSES)]],
    field('followup_date','Fecha de Seguimiento','date'),field('status','Estatus'),
    field('phone_belongs','Telefono Corresponde a'),field('description','Descripción','textarea')]),
 'appointments': dict(title='Citas',singular='cita',fields=[
    field('subject','Asunto',required=True),field('location','Ubicación'),field('type','Type'),field('subtype','Subtipo Actividad'),
    field('start_date','Fecha de inicio','date',True),field('start_time','Hora de inicio','time',True),
    field('end_date','Fecha de finalización','date',True),field('end_time','Hora de finalización','time',True),
    field('contact_id','Contacto principal','contact'),field('account','Cuenta'),field('opportunity_id','Oportunidad','opportunity'),
    field('reminder','Definir recordatorio'),field('description','Descripción','textarea')]),
 'interactions': dict(title='Informes de interacción',singular='informe de interacción',fields=[
    field('subject','Asunto',required=True),field('outcome','Outcome'),field('start_date','Fecha de inicio','date',True),
    field('start_time','Hora de inicio','time',True),field('end_date','Fecha de finalización','date',True),field('end_time','Hora de finalización','time',True),
    field('location','Ubicación'),field('type','Type'),field('account','Cuenta'),field('opportunity_id','Oportunidad','opportunity'),
    field('lead_id','Oportunidad potencial','lead'),field('minutes','Acta de reunión','textarea')])
}

class ValidationError(ValueError): pass
class ConflictError(ValueError): pass

class DemoStore:
    """Volatile synthetic data only. Restart resets all changes and audit events."""
    def __init__(self):
        self.lock=RLock()
        self.reset()

    def reset(self):
        with self.lock:
            self.tables={k:{} for k in SCHEMAS}
            self.events=[]
            self.today=date(2026,11,12)
            for i in range(1,61):
                cid=f'DEMO-C-{i:03d}'
                stage=STAGES[(i-1)%6]
                complete=(i%4!=0)
                self.tables['contacts'][cid]=dict(id=cid,version=1,first_name=f'Aspirante {i:03d}',last_name='Sintético',
                    email=f'aspirante{i:03d}@example.invalid',phone='SIN TELÉFONO REAL',owner=OWNERS[(i-1)%3],
                    faculty=FACULTIES[(i-1)%5],career=['Ingeniería en Sistemas','Diseño','Administración','Derecho','Comunicación'][(i-1)%5],
                    school=f'Colegio ficticio {(i-1)%8+1:02d}',cycle=['2263','2271'][i%2],test_type=['PDA','PAA','Convenio'][i%3],
                    test_date=str(self.today+timedelta(days=i%18-9)),dossier='Completo' if complete else 'Incompleto',
                    payment='Confirmado' if i%3 else 'Pendiente',resolution='Admitido' if stage in STAGES[4:] else 'Pendiente',
                    letter='Entregada' if stage in STAGES[4:] else 'Pendiente',enrollment_due=str(self.today+timedelta(days=i%14-4)),
                    notes='Registro generado por código. No representa a una persona real.')
                oid=f'DEMO-O-{i:03d}'
                self.tables['opportunities'][oid]=dict(id=oid,version=1,name=f'Admisión demostración {i:03d}',contact_id=cid,stage=stage,
                    close_date=str(self.today+timedelta(days=20)),probability=25)
                if i%3:
                    tid=f'DEMO-T-{i:03d}'
                    self.tables['tasks'][tid]=dict(id=tid,version=1,subject='Confirmar próximos pasos',owner=OWNERS[(i-1)%3],
                        contact_id=cid,state='No iniciada',priority='Intermedia',followup_date=str(self.today+timedelta(days=i%9-4)),
                        description='Seguimiento simulado',interaction_1=str(self.today-timedelta(days=2)),response_1=RESPONSES[i%5])
            self.tables['appointments']['DEMO-A-001']=dict(id='DEMO-A-001',version=1,subject='Entrevista de demostración',
                contact_id='DEMO-C-001',start_date=str(self.today),end_date=str(self.today),start_time='10:00',end_time='10:30',location='Sala ficticia')

    def snapshot(self):
        with self.lock:
            return deepcopy(dict(mode='demo',as_of=str(self.today),schemas=SCHEMAS,tables={k:list(v.values()) for k,v in self.tables.items()},events=self.events))

    def validate(self, entity, data):
        fields=SCHEMAS[entity]['fields']
        if set(data)-{f['key'] for f in fields}:
            raise ValidationError('Hay campos no permitidos.')
        clean={}
        for f in fields:
            value=data.get(f['key'],'')
            if not isinstance(value,(str,int,float)) or isinstance(value,bool): raise ValidationError('Tipo de dato no permitido.')
            value=str(value).strip()
            if f['required'] and not value: raise ValidationError(f"Falta {f['label']}.")
            if len(value)>2000: raise ValidationError('Texto demasiado largo.')
            if value and f['kind']=='select' and value not in f['options']: raise ValidationError(f"Valor inválido: {f['label']}.")
            if value and f['kind']=='date':
                try: date.fromisoformat(value)
                except ValueError: raise ValidationError('Fecha inválida.')
            if value and f['kind']=='time':
                try: datetime.strptime(value,'%H:%M')
                except ValueError: raise ValidationError('Hora inválida.')
            refs={'contact':'contacts','opportunity':'opportunities','lead':'leads'}
            if value and f['kind'] in refs and value not in self.tables[refs[f['kind']]]: raise ValidationError('Referencia inexistente.')
            if value and f['kind']=='email' and (not value.endswith('@example.invalid') or value.count('@')!=1):
                raise ValidationError('En el laboratorio usa correos @example.invalid.')
            if value and f['kind']=='number':
                try:
                    number=float(value)
                    if not 0<=number<=100: raise ValueError()
                except ValueError: raise ValidationError('La probabilidad debe estar entre 0 y 100.')
            clean[f['key']]=value
        if entity in ['appointments','interactions'] and clean['end_date']+'T'+clean['end_time']<=clean['start_date']+'T'+clean['start_time']:
            raise ValidationError('La finalización debe ser posterior al inicio.')
        return clean

    def save(self, entity, data, record_id=None, version=None):
        with self.lock:
            if entity not in self.tables: raise KeyError(entity)
            old=self.tables[entity].get(record_id) if record_id else None
            if record_id and not old: raise KeyError(record_id)
            if old and version!=old['version']: raise ConflictError('El registro cambió. Actualiza antes de guardar.')
            clean=self.validate(entity,data)
            if entity=='contacts' and clean.get('email') and any(r.get('email')==clean['email'] and r['id']!=record_id for r in self.tables[entity].values()):
                raise ConflictError('Ya existe un contacto con este correo de prueba.')
            rid=record_id or 'DEMO-'+str(uuid4())
            row=dict(clean,id=rid,version=old['version']+1 if old else 1)
            self.tables[entity][rid]=row
            self.audit('actualizar' if old else 'crear',entity,rid)
            return deepcopy(row)

    def delete(self,entity,rid,version):
        with self.lock:
            old=self.tables[entity][rid]
            if version!=old['version']: raise ConflictError('El registro cambió. Actualiza antes de eliminar.')
            ref={'contacts':'contact_id','opportunities':'opportunity_id','leads':'lead_id'}.get(entity)
            if ref and any(r.get(ref)==rid for t in self.tables.values() for r in t.values()):
                raise ConflictError('Elimina primero las relaciones de prueba de este registro.')
            del self.tables[entity][rid]
            self.audit('eliminar',entity,rid)

    def audit(self,action,entity,rid):
        self.events.insert(0,dict(action=action,entity=entity,id=rid,at=datetime.now(timezone.utc).isoformat(),actor='Operador demo'))
        self.events=self.events[:200]

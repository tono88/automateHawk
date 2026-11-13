"""Local activity drafts; never sent to Oracle."""
from copy import deepcopy
from datetime import date, time, datetime
from uuid import UUID
from .domain import SCHEMAS, field, ValidationError

KINDS={'tasks':'Seguimiento','appointments':'Cita','interactions':'Informe de interacción'}

def schemas():
    result={}
    for kind,title in KINDS.items():
        fields=[deepcopy(f) for f in SCHEMAS[kind]['fields'] if f['key'] not in ('contact_id','opportunity_id','lead_id')]
        for f in fields:
            if f['key']=='owner':f.update(kind='text',options=[])
        fields += [field('contact_reference','Contacto principal (referencia local)')]
        if kind!='tasks':
            fields += [field('owner','Responsable local',required=True),field('timezone','Zona horaria','select',True,['America/Guatemala'])]
        fields += [field('local_status','Estado local','select',True,['Pendiente','Completado','Cancelado'])]
        result[kind]={'title':title,'fields':fields,'oracle_form':{'tasks':'Crear tarea','appointments':'Crear cita','interactions':'Crear informe de interacción'}[kind]}
    return result

SCHEMA=schemas()

def validate(body):
    if not isinstance(body,dict) or set(body)-{'id','opportunity_number','kind','data','version'}:raise ValidationError('Actividad inválida.')
    try:identifier=str(UUID(body.get('id','')))
    except (ValueError,TypeError,AttributeError):raise ValidationError('Identificador de actividad inválido.')
    kind=body.get('kind');data=body.get('data')
    if kind not in SCHEMA or not isinstance(data,dict):raise ValidationError('Tipo de actividad inválido.')
    fields=SCHEMA[kind]['fields']
    if set(data)-{f['key'] for f in fields}:raise ValidationError('Campo de actividad no permitido.')
    clean={}
    for f in fields:
        value=data.get(f['key'],'')
        if not isinstance(value,str) or len(value)>(6000 if f['kind']=='textarea' else 500):raise ValidationError('Valor de actividad inválido.')
        value=value.strip()
        if f['required'] and not value:raise ValidationError(f"Completa {f['label']}.")
        if value:
            try:
                if f['kind']=='date':date.fromisoformat(value)
                if f['kind']=='time':time.fromisoformat(value)
            except ValueError:raise ValidationError(f"Revisa {f['label']}.")
            if f['options'] and value not in f['options']:raise ValidationError(f"Revisa {f['label']}.")
        clean[f['key']]=value
    if kind in ('appointments','interactions'):
        if datetime.combine(date.fromisoformat(clean['end_date']),time.fromisoformat(clean['end_time']))<=datetime.combine(date.fromisoformat(clean['start_date']),time.fromisoformat(clean['start_time'])):raise ValidationError('La finalización debe ser posterior al inicio.')
    for n in range(1,5):
        if clean.get(f'response_{n}') and not clean.get(f'interaction_{n}'):raise ValidationError(f'Indica la fecha de la interacción {n}.')
    version=body.get('version')
    if version is not None and (type(version)!=int or version<1):raise ValidationError('Versión de actividad inválida.')
    number=body.get('opportunity_number')
    if not isinstance(number,str) or not 0<len(number)<=80:raise ValidationError('Vincula una oportunidad válida.')
    return dict(id=identifier,kind=kind,opportunity_number=number,data=clean,version=version)

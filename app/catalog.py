"""Verified UI field labels, view definitions and conservative editing policy."""
import math
import os
import re
from datetime import date
from .domain import ValidationError, STAGES

DETAIL_FIELDS={
 'cycle':('Ciclo de Ingreso','general'), 'year':('Año','general'),
 'admission_status':('Estado Proceso Admision','general'),
 'test_call':('Convocatoria PA','tests'), 'test_type':('Prueba de Admisión','tests'),
 'test_date':('Fecha PA','tests'), 'test_route':('Tipo de Prueba','tests'),
 'paa_process':('Proceso PAA','tests'), 'agreement':('Convenio PA','tests'),
 'resolution':('Resolución','tests'), 'interview':('Entrevista','interviews'),
 'financial_aid':('Asistencia Economica','financial'),
 'financial_type_1':('Tipo Asistencia Economica 1','financial'),
 'financial_requested_1':('Porcentaje Solicitado AE1','financial'),
 'financial_granted_1':('Porcentaje Otorgado AE1','financial'),
 'financial_status':('Estatus','financial'),
 'documents_due':('Fecha limite entrega papeleria','financial'),
 'tuition_delay_reason':('Razon Retraso Pago de Matricula','payments'),
 'reservation_close':('Cierre Reserva de cupo','payments'),
 'amount':('Importe','payments'), 'origin':('Origen','general'),
 'name':('Nombre','general'), 'owner':('Responsable','advisor'),
 'owner_email':('Correo electrónico del asesor','advisor'),
 'stage':('Etapa de ventas','general'), 'status':('Estado de Oracle','general'), 'probability':('Probabilidad de ganar (%)','general'),
 'segment':('Segmento','general'), 'close_date':('Fecha de cierre','general')
}

DETAIL_FIELDS.update({'campus_id': ('ID Campus', 'contact'),
 'campus_status': ('Estado en Campus', 'contact'),
 'scala_id': ('ID SCALA', 'contact'),
 'contact_first_name': ('Nombre', 'contact'),
 'contact_middle_name': ('Segundo nombre', 'contact'),
 'contact_last_name': ('Apellidos', 'contact'),
 'contact_second_last_name': ('Segundo apellido', 'contact'),
 'birth_date': ('Fecha de nacimiento', 'contact'),
 'document_id': ('Número del documento de identidad', 'contact'),
 'contact_email': ('Correo electrónico', 'contact'),
 'contact_phone': ('Teléfono móvil', 'contact'),
 'contact_account': ('Cuenta', 'contact'),
 'career': ('Carrera de Interes', 'contact'),
 'faculty': ('Facultad', 'contact'),
 'lead_status': ('Estatus Lead', 'contact'),
 'test_month': ('Mes de Prueba', 'contact'),
 'contact_test_type': ('Tipo de Prueba', 'contact'),
 'hoodie_size': ('Talla Sudadero', 'contact'),
 'document_status': ('Estatus Papeleria', 'contact'),
 'financial_interest': ('Interes Asistencia Economica', 'contact'),
 'graduation_school_year': ('Año de graduacion colegio', 'contact'),
 'homeschool': ('Homeschool', 'contact'),
 'contact_link_status': ('Vínculo con contacto principal', 'contact'),
 'global_score': ('Puntaje Global', 'tests'),
 'paa_score': ('Puntaje PAA', 'tests'),
 'grade_average': ('Promedio', 'tests'),
 'required_score': ('Puntaje Requerido', 'tests'),
 'financial_type_2': ('Tipo Asistencia Economica 2', 'financial'),
 'financial_requested_2': ('Porcentaje Solicitado AE 2', 'financial'),
 'financial_granted_2': ('Porcentaje Otorgado AE 2', 'financial'),
 'financial_acceptance': ('Aceptacion', 'financial'),
 'financial_comments': ('Comentarios Asistencia Economica', 'financial')})

VIEWS=[
 {'id':'summary','title':'Resumen','description':'Indicadores sobre los registros de la copia local.'},
 {'id':'base','title':'Oportunidades','description':'Una fila por oportunidad, con ciclo y campos verificados.'},
 {'id':'contacts','title':'Aspirantes','description':'Personas y datos académicos vinculados a la cartera.'},
 {'id':'registration','title':'Inscripciones a prueba','description':'Seguimiento comercial de las inscripciones a prueba.'},
 {'id':'tests','title':'Pruebas y convocatorias','description':'PDA/PAA, convocatoria, fecha y resolución leídas del detalle.'},
 {'id':'interviews','title':'Entrevistas y citas','description':'Indicador de entrevista y actividades vinculadas consultadas.'},
 {'id':'payments','title':'Pagos y reservas','description':'Importe y campos de seguimiento; no acredita un pago.'},
 {'id':'financial','title':'Asistencia económica','description':'Solicitud y estado visibles en Oracle.'},
 {'id':'enrollment','title':'Matrícula','description':'Etapas 05 y 06; pendiente conciliación con Campus.'},
 {'id':'changes','title':'Cambios en Oracle','description':'Envío, conflictos y confirmación de los cambios solicitados.'},
 {'id':'sync','title':'Sincronización','description':'Frecuencia, frescura y estado del trabajador.'},
 {'id':'roadmap','title':'Roadmap','description':'Evolución operativa e inteligencia de negocio futura.'}
]
# Fields the screen writer can locate by their visible label: the opportunity
# "Resumen" panel and the profile of the linked primary contact. The kind drives
# validation, comparison and the editor. Oracle still decides per record and per
# user: a pencil only appears where the last detail read observed an enabled
# control, and the worker re-checks the live form (permission and current value)
# before saving.
EDIT_KINDS={
 'name':'text','stage':'choice','probability':'number','close_date':'date','amount':'number',
 'owner':'choice','cycle':'choice','year':'choice','admission_status':'choice','origin':'choice',
 'test_call':'choice','test_type':'choice','test_date':'date','test_route':'choice',
 'paa_process':'choice','agreement':'choice','interview':'choice',
 'financial_aid':'choice','financial_type_1':'choice','financial_requested_1':'number',
 'financial_type_2':'choice','financial_requested_2':'number','financial_status':'choice',
 'financial_comments':'text','documents_due':'date','tuition_delay_reason':'choice',
 'reservation_close':'date',
 'resolution':'choice','financial_granted_1':'number','financial_granted_2':'number',
 'financial_acceptance':'choice','global_score':'number','paa_score':'number',
 'grade_average':'number','required_score':'number',
 # Primary contact profile.
 'contact_first_name':'text','contact_middle_name':'text','contact_last_name':'text',
 'contact_second_last_name':'text','birth_date':'date','document_id':'text',
 'contact_email':'email','contact_phone':'text','career':'choice','faculty':'choice',
 'lead_status':'choice','test_month':'choice','contact_test_type':'choice','hoodie_size':'choice',
 'document_status':'choice','financial_interest':'choice','graduation_school_year':'choice',
 'homeschool':'boolean','campus_id':'text','scala_id':'text','campus_status':'choice',
}
CONTACT_EDIT_FIELDS={k for k in EDIT_KINDS if DETAIL_FIELDS.get(k,('',''))[1]=='contact'}
# Identifiers maintained by the Campus/SCALA integrations: only with explicit opt-in.
PROTECTED_EDIT_FIELDS={'campus_id','scala_id','campus_status'}
# Academic and award decisions: excluded by the conservative "safe" policy.
DECISION_FIELDS={'resolution','financial_granted_1','financial_granted_2','financial_acceptance',
 'global_score','paa_score','grade_average','required_score'}
# Writers exercised end to end with synthetic data or an authorised correction.
VERIFIED_EDIT_FIELDS={'name','stage','probability','close_date','test_call'}
REQUIRED_EDIT_FIELDS={'name','stage','probability','close_date','contact_first_name','contact_last_name'}

def configured_edit_fields(raw=None):
    raw=os.environ.get('HUB_EDIT_FIELDS','') if raw is None else raw
    raw=raw.strip()
    if not raw or raw=='default':return set(EDIT_KINDS)-PROTECTED_EDIT_FIELDS
    if raw=='safe':return set(EDIT_KINDS)-PROTECTED_EDIT_FIELDS-DECISION_FIELDS
    if raw=='verified':return set(VERIFIED_EDIT_FIELDS)
    if raw=='all':return set(EDIT_KINDS)
    chosen={f.strip() for f in raw.split(',') if f.strip()}
    unknown=chosen-set(EDIT_KINDS)
    if unknown:raise ValueError('HUB_EDIT_FIELDS contiene campos sin escritor: '+', '.join(sorted(unknown)))
    return chosen

EDIT_FIELDS=configured_edit_fields()

def validate_change(field,value):
    if field not in EDIT_FIELDS:raise ValidationError('Este campo no está habilitado para edición desde el portal.')
    if not isinstance(value,str) or len(value)>2000:raise ValidationError('Valor inválido.')
    value=value.strip()
    kind=EDIT_KINDS[field]
    if not value:
        if field in REQUIRED_EDIT_FIELDS:raise ValidationError('Este campo no puede quedar vacío.')
        return value
    if kind!='text' and len(value)>300:raise ValidationError('Valor inválido.')
    if field=='stage' and value not in STAGES:raise ValidationError('Etapa no permitida.')
    if kind=='number':
        try:
            number=float(value.replace(',',''))
            if not math.isfinite(number):raise ValueError()
        except ValueError:raise ValidationError('Ingresa un número válido.')
        if (field=='probability' or field.startswith('financial_')) and not 0<=number<=100:
            raise ValidationError('El porcentaje debe estar entre 0 y 100.')
    if kind=='date':
        try:date.fromisoformat(value)
        except ValueError:raise ValidationError('Utiliza una fecha AAAA-MM-DD.')
    if kind=='email' and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value):raise ValidationError('Correo electrónico inválido.')
    if kind=='boolean' and value not in ('Sí','No'):raise ValidationError('Elige Sí o No.')
    return value

CREATE_YEAR=2026  # The portal inventory covers opportunities that close in this year.
CREATE_BASE_FIELDS={'name','close_date','stage','probability'}

def _text(value,label,limit=150,required=True):
    if value is None:value=''
    if not isinstance(value,str) or len(value)>limit:raise ValidationError(f'{label} inválido.')
    value=value.strip()
    if required and not value:raise ValidationError(f'{label} es obligatorio.')
    return value

def validate_creation(body):
    """New opportunity requested from the portal; created in Oracle by the screen worker."""
    if not isinstance(body,dict) or set(body)-{'name','close_date','stage','probability','contact','extra'}:raise ValidationError('Solicitud inválida.')
    out={'name':_text(body.get('name'),'Nombre de la oportunidad',240)}
    close=_text(body.get('close_date'),'Fecha de cierre',10)
    try:closed=date.fromisoformat(close)
    except ValueError:raise ValidationError('Utiliza una fecha de cierre AAAA-MM-DD.')
    if closed.year!=CREATE_YEAR:raise ValidationError(f'La cartera del portal cubre cierres en {CREATE_YEAR}; usa una fecha de cierre de ese año.')
    out['close_date']=close
    out['stage']=_text(body.get('stage') or STAGES[0],'Etapa',80)
    if out['stage'] not in STAGES:raise ValidationError('Etapa no permitida.')
    probability=_text(body.get('probability'),'Probabilidad',6,required=False)
    if probability:
        try:
            number=float(probability)
            if not math.isfinite(number) or not 0<=number<=100:raise ValueError()
        except ValueError:raise ValidationError('La probabilidad debe estar entre 0 y 100.')
    out['probability']=probability
    contact=body.get('contact')
    if not isinstance(contact,dict) or contact.get('mode') not in ('existing','new','none'):raise ValidationError('Indica el contacto principal.')
    if contact['mode']=='existing':
        if set(contact)-{'mode','name'}:raise ValidationError('Contacto inválido.')
        out['contact']={'mode':'existing','name':_text(contact.get('name'),'Nombre del contacto',240)}
    elif contact['mode']=='new':
        if set(contact)-{'mode','first_name','last_name','email','phone'}:raise ValidationError('Contacto inválido.')
        email=_text(contact.get('email'),'Correo electrónico',300,required=False)
        if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):raise ValidationError('Correo electrónico inválido.')
        out['contact']={'mode':'new','first_name':_text(contact.get('first_name'),'Nombre del aspirante'),
            'last_name':_text(contact.get('last_name'),'Apellidos del aspirante'),'email':email,
            'phone':_text(contact.get('phone'),'Teléfono',40,required=False)}
    else:out['contact']={'mode':'none'}
    extra=body.get('extra') or {}
    if not isinstance(extra,dict) or len(extra)>20:raise ValidationError('Campos adicionales inválidos.')
    clean={}
    for field,value in extra.items():
        if field in CREATE_BASE_FIELDS or field in CONTACT_EDIT_FIELDS:raise ValidationError('Campo adicional no permitido.')
        value=validate_change(field,value)
        if value:clean[field]=value
    out['extra']=clean
    return out

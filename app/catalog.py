"""Verified UI field labels, view definitions and conservative editing policy."""
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
 'stage':('Etapa de ventas','general'), 'probability':('Probabilidad de ganar (%)','general'),
 'close_date':('Fecha de cierre','general')
}

VIEWS=[
 {'id':'summary','title':'Resumen','description':'Indicadores sobre los registros de la copia local.'},
 {'id':'base','title':'Base de aspirantes','description':'Una fila por oportunidad, con ciclo y campos verificados.'},
 {'id':'tests','title':'Pruebas y convocatorias','description':'PDA/PAA, convocatoria, fecha y resolución leídas del detalle.'},
 {'id':'interviews','title':'Entrevistas y citas','description':'Indicador de entrevista y actividades vinculadas consultadas.'},
 {'id':'payments','title':'Pagos y matrícula','description':'Importe y campos de seguimiento; no acredita un pago.'},
 {'id':'financial','title':'Asistencia económica','description':'Solicitud y estado visibles en Oracle.'},
 {'id':'enrollment','title':'Matrícula comercial','description':'Etapas 05 y 06; pendiente conciliación con Campus.'},
 {'id':'changes','title':'Cambios en Oracle','description':'Envío, conflictos y confirmación de los cambios solicitados.'},
 {'id':'sync','title':'Sincronización','description':'Frecuencia, frescura y estado del trabajador.'},
 {'id':'roadmap','title':'Roadmap','description':'Evolución operativa e inteligencia de negocio futura.'}
]
EDIT_FIELDS={'name','stage','probability','close_date'}

def validate_change(field,value):
    if field not in EDIT_FIELDS:raise ValidationError('Este campo todavía no tiene un escritor Oracle validado.')
    if not isinstance(value,str) or not value.strip() or len(value)>300:raise ValidationError('Valor inválido.')
    value=value.strip()
    if field=='stage' and value not in STAGES:raise ValidationError('Etapa no permitida.')
    if field=='probability':
        try:
            if not 0<=float(value)<=100:raise ValueError()
        except ValueError:raise ValidationError('La probabilidad debe estar entre 0 y 100.')
    if field=='close_date':
        try:date.fromisoformat(value)
        except ValueError:raise ValidationError('Utiliza una fecha AAAA-MM-DD.')
    return value

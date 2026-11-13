"""Read-only, volatile Oracle read model. Never merges real rows with demo data."""
from copy import deepcopy
from datetime import datetime, timezone
from secrets import token_urlsafe
from threading import RLock
from time import monotonic
from .domain import ValidationError, ConflictError
from .catalog import DETAIL_FIELDS, EDIT_FIELDS, validate_change

FIELDS = ('opportunity_number','first_name','last_name','name','account','close_date',
          'probability','stage','status','segment','contact_name','owner','phone',
          'created_at','updated_at')

class OracleReadStore:
    def __init__(self,repository=None,role='reader'):
        self.lock=RLock()
        self.records=[]
        self.loaded_at=None
        self.scope='Sin consulta'
        self.job=None
        self.tickets={}
        self.worker_seen=0
        self.claimed_at=0
        self.failure_count=0
        self.retry_after=0
        self.batch_numbers=[]
        self.batch_done=set()
        self.repository=repository
        self.role=role
        self.details={}
        self.settings={'enabled':False,'interval_minutes':15,'detail_ttl_minutes':30,'reconcile_hours':24}
        if repository:
            self._reload()
            self.settings.update(repository.settings().get('sync',{}))

    def _reload(self):
        state=self.repository.load()
        self.records=state['records'];self.loaded_at=state['loaded_at'];self.scope=state['scope'];self.details=state['details']

    def heartbeat(self):
        with self.lock:
            self.worker_seen=monotonic()
            return {'online':True}

    def ticket(self):
        with self.lock:
            now=monotonic()
            self.tickets={k:v for k,v in self.tickets.items() if v>now}
            token=token_urlsafe(32)
            self.tickets[token]=now+180
            return token

    def authorize(self,token):
        with self.lock:
            expires=self.tickets.pop(token,None)
            if not expires or expires<monotonic(): raise PermissionError()

    def request(self,kind='opportunities',number=None):
        with self.lock:
            if self.job and self.job['state']=='running' and self.claimed_at and monotonic()-self.claimed_at>900:self.fail('timeout')
            if self.job and self.job['state'] in ('pending','running'): return deepcopy(self.job)
            if kind not in ('opportunities','detail','details_batch'):raise ValidationError('Operación de consulta desconocida.')
            if kind=='detail' and not any(r['opportunity_number']==number for r in self.records):raise KeyError(number)
            self.job=dict(id=token_urlsafe(12),kind=kind,opportunity_number=number,state='pending',message='Esperando al trabajador de navegador local.',started_at=None,finished_at=None)
            if kind=='details_batch':
                self.batch_numbers=[r['opportunity_number'] for r in self.records if r['opportunity_number'] not in self.details]
                self.batch_done=set()
                self.job.update(total=len(self.batch_numbers),processed=0)
                if not self.batch_numbers:self.job.update(state='completed',message='La cartera cargada ya tiene sus detalles disponibles.')
            return deepcopy(self.job)

    def claim(self):
        with self.lock:
            if self.job and self.job['state']=='running' and self.claimed_at and monotonic()-self.claimed_at>900:self.fail('timeout')
            if not self.job or self.job['state']!='pending': return None
            self.job.update(state='running',message='Consultando Oracle mediante su interfaz.',started_at=datetime.now(timezone.utc).isoformat())
            self.claimed_at=monotonic()
            return deepcopy(self.job)

    def fail(self,message):
        # Worker sends only catalogued failure codes, never raw browser errors.
        with self.lock:
            safe={'session':'Oracle requiere iniciar sesión de nuevo.','empty':'La consulta no devolvió filas verificables. Se conserva la carga anterior.',
                  'layout':'No se reconoció la tabla de Oracle. Se conserva la carga anterior.',
                  'timeout':'Oracle no terminó la consulta. Se conserva la carga anterior.'}
            if not self.job: self.request()
            self.job.update(state='failed',message=safe.get(message,'No se pudo completar la consulta. Se conserva la carga anterior.'),finished_at=datetime.now(timezone.utc).isoformat())
            self.failure_count+=1
            self.retry_after=monotonic()+(900 if message=='session' else min(60*2**min(self.failure_count-1,5),1800))

    def ingest(self,body):
        if not isinstance(body,dict) or set(body)-{'records','scope','partial'}: raise ValidationError('Carga inválida.')
        rows=body.get('records')
        if not isinstance(rows,list) or not rows or len(rows)>1000: raise ValidationError('La carga debe contener entre 1 y 1000 filas verificadas.')
        if body.get('partial') is not True: raise ValidationError('Esta versión solo certifica cargas parciales.')
        scope=body.get('scope')
        if not isinstance(scope,str) or not 0<len(scope)<=240: raise ValidationError('Alcance inválido.')
        clean=[]; seen=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)-set(FIELDS): raise ValidationError('Campo no permitido.')
            out={}
            for key in FIELDS:
                value=row.get(key,'')
                if not isinstance(value,str) or len(value)>1000: raise ValidationError('Valor inválido.')
                out[key]=value.strip()
            number=out['opportunity_number']
            if not number or len(number)>80 or number in seen: raise ValidationError('Número oficial vacío o repetido.')
            seen.add(number);clean.append(out)
        with self.lock:
            if self.repository:
                self.repository.save_snapshot(clean,scope);self._reload()
            else:
                self.records=clean
                self.loaded_at=datetime.now(timezone.utc).isoformat()
            self.scope=scope
            if not self.job: self.request()
            self.job.update(state='completed',message=f'Carga parcial verificada: {len(clean)} oportunidades.',finished_at=self.loaded_at)
            self.failure_count=0;self.retry_after=0
            return self.status()

    def status(self):
        with self.lock:
            return deepcopy(dict(source='oracle-ui',read_only=True,partial=True,count=len(self.records),loaded_at=self.loaded_at,
                                 scope=self.scope,job=self.job,storage='postgresql' if self.repository else 'memory',worker_required=True,
                                 worker_online=bool(self.worker_seen and monotonic()-self.worker_seen<90),
                                 role=self.role,can_propose=self.role=='editor' and bool(self.repository),settings=self.settings,
                                 retry_in_seconds=max(0,int(self.retry_after-monotonic())),
                                 detail_count=len(self.details),database=self.repository.summary() if self.repository else None))

    def snapshot(self):
        with self.lock: return dict(**self.status(),records=deepcopy(self.records),details=deepcopy(self.details))

    def ingest_detail(self,body):
        if not isinstance(body,dict) or set(body)-{'opportunity_number','fields','capabilities','activities'}:raise ValidationError('Detalle inválido.')
        number=body.get('opportunity_number')
        if not any(r['opportunity_number']==number for r in self.records):raise KeyError(number)
        fields=body.get('fields',{});caps=body.get('capabilities',{})
        if not isinstance(fields,dict) or set(fields)-set(DETAIL_FIELDS):raise ValidationError('Campo de detalle no permitido.')
        if not isinstance(caps,dict) or set(caps)-set(DETAIL_FIELDS) or any(type(v)!=bool for v in caps.values()):raise ValidationError('Permisos inválidos.')
        if any(not isinstance(v,str) or len(v)>2000 for v in fields.values()):raise ValidationError('Valor de detalle inválido.')
        activity=body.get('activities',{'queried':False,'rows':[]})
        if not isinstance(activity,dict) or set(activity)-{'queried','rows'} or type(activity.get('queried'))!=bool or not isinstance(activity.get('rows'),list) or len(activity['rows'])>100:raise ValidationError('Actividades inválidas.')
        allowed={'activity','subject','date','owner','type','priority'}
        for row in activity['rows']:
            if not isinstance(row,dict) or set(row)-allowed or any(not isinstance(v,str) or len(v)>1000 for v in row.values()):raise ValidationError('Actividad inválida.')
        payload={'fields':fields,'capabilities':caps,'activities':activity,'source':'oracle-ui','partial':True}
        with self.lock:
            if self.repository:self.repository.save_detail(number,payload);self._reload()
            else:self.details[number]=dict(payload,loaded_at=datetime.now(timezone.utc).isoformat())
            if not self.job:self.request()
            if self.job.get('kind')=='details_batch' and number in self.batch_numbers:
                self.batch_done.add(number);self.claimed_at=monotonic();self.worker_seen=monotonic()
                self.job.update(processed=len(self.batch_done),message=f'Datos ampliados: {len(self.batch_done)} de {len(self.batch_numbers)} expedientes.')
                if len(self.batch_done)==len(self.batch_numbers):self.job.update(state='completed',finished_at=datetime.now(timezone.utc).isoformat())
            else:self.job.update(state='completed',message='Detalle consultado y guardado en la copia local.',finished_at=datetime.now(timezone.utc).isoformat())
            self.failure_count=0;self.retry_after=0
        return self.status()

    def batch(self):
        with self.lock:return {'job':deepcopy(self.job),'pending':[n for n in self.batch_numbers if n not in self.batch_done]}

    def propose(self,body):
        if self.role!='editor' or not self.repository:raise PermissionError()
        if not isinstance(body,dict) or set(body)-{'opportunity_number','field','value','version'}:raise ValidationError('Solicitud inválida.')
        number=body.get('opportunity_number');field=body.get('field')
        value=validate_change(field,body.get('value'))
        detail=self.details.get(number)
        if not detail or not detail.get('capabilities',{}).get(field):raise PermissionError()
        loaded=datetime.fromisoformat(detail['loaded_at'])
        if (datetime.now(timezone.utc)-loaded).total_seconds()>1800:raise ConflictError('Vuelve a consultar los permisos del detalle antes de editar.')
        return self.repository.propose(number,field,value,body.get('version'),'local-editor')

    def save_settings(self,body):
        if self.role!='editor' or not self.repository:raise PermissionError()
        if set(body)-{'enabled','interval_minutes'} or type(body.get('enabled'))!=bool or type(body.get('interval_minutes'))!=int or not 5<=body['interval_minutes']<=240:raise ValidationError('Intervalo permitido: de 5 a 240 minutos.')
        with self.lock:
            self.settings.update(body);self.repository.save_setting('sync',self.settings)
        return self.settings

    def scheduler_tick(self):
        with self.lock:
            if self.retry_after>monotonic():return None
            if not self.settings['enabled'] or not self.worker_seen or monotonic()-self.worker_seen>=90:return None
            if self.job and self.job['state'] in ('pending','running'):return None
            if self.loaded_at:
                elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(self.loaded_at)).total_seconds()
                if elapsed<self.settings['interval_minutes']*60:return None
            return self.request()

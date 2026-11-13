"""Read-only, volatile Oracle read model. Never merges real rows with demo data."""
from copy import deepcopy
from datetime import datetime, timezone
from secrets import token_urlsafe
from threading import RLock
from time import monotonic
from .domain import ValidationError, ConflictError

FIELDS = ('opportunity_number','first_name','last_name','name','account','close_date',
          'probability','stage','status','segment','contact_name','owner','phone',
          'created_at','updated_at')

class OracleReadStore:
    def __init__(self):
        self.lock=RLock()
        self.records=[]
        self.loaded_at=None
        self.scope='Sin consulta'
        self.job=None
        self.tickets={}
        self.worker_seen=0

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

    def request(self):
        with self.lock:
            if self.job and self.job['state'] in ('pending','running'): return deepcopy(self.job)
            self.job=dict(id=token_urlsafe(12),state='pending',message='Esperando al trabajador de navegador local.',started_at=None,finished_at=None)
            return deepcopy(self.job)

    def claim(self):
        with self.lock:
            if not self.job or self.job['state']!='pending': return None
            self.job.update(state='running',message='Consultando Oracle mediante su interfaz.',started_at=datetime.now(timezone.utc).isoformat())
            return deepcopy(self.job)

    def fail(self,message):
        # Worker sends only catalogued failure codes, never raw browser errors.
        with self.lock:
            safe={'session':'Oracle requiere iniciar sesión de nuevo.','empty':'La consulta no devolvió filas verificables. Se conserva la carga anterior.',
                  'layout':'No se reconoció la tabla de Oracle. Se conserva la carga anterior.',
                  'timeout':'Oracle no terminó la consulta. Se conserva la carga anterior.'}
            if not self.job: self.request()
            self.job.update(state='failed',message=safe.get(message,'No se pudo completar la consulta. Se conserva la carga anterior.'),finished_at=datetime.now(timezone.utc).isoformat())

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
            self.records=clean
            self.loaded_at=datetime.now(timezone.utc).isoformat()
            self.scope=scope
            if not self.job: self.request()
            self.job.update(state='completed',message=f'Carga parcial verificada: {len(clean)} oportunidades.',finished_at=self.loaded_at)
            return self.status()

    def status(self):
        with self.lock:
            return deepcopy(dict(source='oracle-ui',read_only=True,partial=True,count=len(self.records),loaded_at=self.loaded_at,
                                 scope=self.scope,job=self.job,storage='memory',worker_required=True,
                                 worker_online=bool(self.worker_seen and monotonic()-self.worker_seen<90)))

    def snapshot(self):
        with self.lock: return dict(**self.status(),records=deepcopy(self.records))

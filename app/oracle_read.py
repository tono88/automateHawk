"""Read-only, volatile Oracle read model. Never merges real rows with demo data."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from secrets import token_urlsafe
from threading import RLock
from time import monotonic
from .domain import ValidationError, ConflictError
import os
from .catalog import DETAIL_FIELDS, EDIT_FIELDS, validate_change, validate_creation

EDIT_DETAIL_MAX_AGE=int(os.environ.get('HUB_EDIT_DETAIL_MAX_AGE_MINUTES','480'))*60

FIELDS = ('opportunity_number','first_name','last_name','name','account','close_date',
          'probability','stage','status','segment','contact_name','owner','phone',
          'created_at','updated_at','amount','owner_email')

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
        self.batch_failed=set();self.batch_partial=set()
        self.batch_inflight=set()
        self.read_outcomes={}
        self.read_versions={}
        self.read_seconds=[]
        self.job_clock=0
        self.repository=repository
        self.role=role
        self.actor='local-editor'
        self.details={}
        self.detail_states={}
        self.settings={'enabled':False,'interval_minutes':15,'detail_ttl_minutes':30,'reconcile_hours':24}
        self.listing_coverage=None
        # Incremental refresh for the browser: a revision per record and per detail.
        self.epoch=token_urlsafe(8);self.revision=0;self._dirty=True;self._marker=None
        self._row_fp={};self._detail_fp={};self._state_fp={}
        self.row_rev={};self.detail_rev={};self.state_rev={};self.members_rev=0
        if repository:
            self._reload()
            self.settings.update(repository.settings().get('sync',{}))
            self.listing_coverage=repository.settings().get('listing_coverage:'+getattr(repository,'principal','local'))

    def _reload(self):
        with self.lock:
            marker=self.repository.fingerprint() if hasattr(self.repository,'fingerprint') else None
            state=self.repository.load()
            self.records=state['records'];self.loaded_at=state['loaded_at'];self.scope=state['scope'];self.details=state['details'];self.detail_states=state.get('detail_states',{})
            if hasattr(self.repository,'read_progress'):self.read_outcomes=self.repository.read_progress()
            self._marker=marker;self._dirty=True

    def refresh_if_changed(self):
        """Reloads the scoped copy only when the database changed (one light query per request)."""
        if not self.repository or not hasattr(self.repository,'fingerprint'):return self._reload() if self.repository else None
        if self.repository.fingerprint()!=getattr(self,'_marker',None):self._reload()

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
                self.read_seconds=[]
                # Unconfirmed rows (last copy) wait for the inventory: Oracle must confirm them first.
                self.batch_numbers=[r['opportunity_number'] for r in self.records if not r.get('_unconfirmed') and (self.needs_detail(r['opportunity_number']) or self.read_outcomes.get(r['opportunity_number'],{}).get('permission_refresh_required'))]
                self.batch_numbers.sort(key=lambda n:{'failed':1,'partial':2}.get(self.read_outcomes.get(n,{}).get('state'),0))
                self.batch_done=set();self.batch_failed=set();self.batch_partial=set()
                self.batch_inflight=set()
                self.job.update(successful=0,failed=0,total=len(self.batch_numbers),processed=0)
                if not self.batch_numbers:self.job.update(state='completed',message='La cartera cargada ya tiene sus detalles disponibles.')
            return deepcopy(self.job)

    def claim(self):
        with self.lock:
            if self.job and self.job['state']=='running' and self.claimed_at and monotonic()-self.claimed_at>900:self.fail('timeout')
            if not self.job or self.job['state']!='pending': return None
            self.job.update(state='running',message='Consultando Oracle mediante su interfaz.',started_at=datetime.now(timezone.utc).isoformat())
            self.claimed_at=monotonic()
            self.job_clock=self.claimed_at
            return deepcopy(self.job)

    def fail(self,message):
        # Worker sends only catalogued failure codes, never raw browser errors.
        with self.lock:
            safe={'session':'Oracle requiere iniciar sesión de nuevo.','empty':'La consulta no devolvió filas verificables. Se conserva la carga anterior.',
                  'layout':'No se reconoció la tabla de Oracle. Se conserva la carga anterior.',
                  'timeout':'Oracle no terminó la consulta. Se conserva la carga anterior.'}
            if not self.job: self.request()
            self.job.update(state='failed',failure_code=message,message=safe.get(message,'No se pudo completar la consulta. Se conserva la carga anterior.'),finished_at=datetime.now(timezone.utc).isoformat())
            self.failure_count+=1
            self.retry_after=monotonic()+(900 if message=='session' else min(60*2**min(self.failure_count-1,5),1800))

    def ingest(self,body,*,preserve_job=False):
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
            if not preserve_job:
                if not self.job:self.request()
                self.job.update(state='completed',message=f'Carga parcial verificada: {len(clean)} oportunidades.',finished_at=self.loaded_at)
            self.failure_count=0;self.retry_after=0
            return self.status()

    def status(self):
        with self.lock:
            return deepcopy(dict(source='oracle-ui',read_only=not getattr(self,'write_enabled',False),partial=True,count=len(self.records),loaded_at=self.loaded_at,
                                 scope=self.scope,job=self.job,storage='postgresql' if self.repository else 'memory',worker_required=True,
                                 worker_online=bool(self.worker_seen and monotonic()-self.worker_seen<90),
                                 role=self.role,can_propose=self.role=='editor' and bool(self.repository),settings=self.settings,
                                 retry_in_seconds=max(0,int(self.retry_after-monotonic())),
                                 detail_count=len(self.details),extraction=self.extraction_progress(),performance=self.performance(),
                                 source_limits={'contacts_unavailable':sum(self.read_outcomes.get(r['opportunity_number'],{}).get('error_code')=='contact-unavailable' for r in self.records)},
                                 listing_coverage=self.listing_coverage,unconfirmed=self.unconfirmed(),
                                 database=self.repository.summary() if self.repository else None))

    def record_listing_coverage(self,coverage):
        with self.lock:
            self.listing_coverage=deepcopy(coverage)
            if self.repository:self.repository.save_setting('listing_coverage:'+getattr(self.repository,'principal','local'),coverage)
            if self.job and self.job.get('state')=='running':
                self.claimed_at=monotonic()
                self.job['message']=f"Inventario 2026: {coverage['partitions_finished']} intervalos consultados · {coverage['row_count']} oportunidades identificadas."

    def record_timing(self,seconds):
        with self.lock:
            if 0<seconds<600:self.read_seconds=(self.read_seconds+[seconds])[-100:]

    def performance(self):
        if not self.job or self.job.get('kind')!='details_batch':
            return {'samples':0,'mean_read_seconds':None,'records_per_minute':None,'concurrent_reads':0,'estimated_remaining_seconds':None}
        samples=self.read_seconds
        remaining=len(self.batch(internal=True)['pending']) if self.job and self.job.get('kind')=='details_batch' else 0
        average=sum(samples)/len(samples) if samples else None
        elapsed=monotonic()-self.job_clock if self.job_clock else 0
        if self.job.get('finished_at') and self.job.get('started_at'):
            elapsed=max(0,(datetime.fromisoformat(self.job['finished_at'])-datetime.fromisoformat(self.job['started_at'])).total_seconds())
        recovered=len(self.batch_done|self.batch_partial)
        rate=recovered/elapsed if recovered and elapsed>0 else None
        return {'samples':len(samples),'mean_read_seconds':round(average,2) if average else None,
                'records_per_minute':round(60*rate,2) if rate else None,
                'concurrent_reads':len(self.batch_inflight),
                'estimated_remaining_seconds':round(remaining/rate) if rate and self.job and self.job.get('state')=='running' else None}

    def request_pause(self):
        with self.lock:
            if self.job and self.job.get('kind')=='details_batch' and self.job.get('state')=='running':
                self.job.update(stop_requested=True,message='Pausa solicitada. Se terminarán las fichas en curso y se conservará el avance.')
            return deepcopy(self.job)

    def pause(self):
        with self.lock:
            self.job.update(state='paused',message='Carga pausada; el avance quedó guardado.',finished_at=datetime.now(timezone.utc).isoformat())

    def _stamp(self):
        """Assigns a new revision to every record, detail or read state that changed."""
        if not self._dirty:return
        rev=self.revision+1;changed=False;numbers=set()
        for r in self.records:
            n=r['opportunity_number'];numbers.add(n)
            fp=json.dumps(r,sort_keys=True,default=str)
            if self._row_fp.get(n)!=fp:self._row_fp[n]=fp;self.row_rev[n]=rev;changed=True
            d=self.details.get(n)
            dfp=None if d is None else json.dumps([d.get('loaded_at'),d.get('unconfirmed'),sorted(k for k,v in (d.get('capabilities') or {}).items() if v),len(d.get('fields') or {})],default=str)
            if self._detail_fp.get(n,'∅')!=dfp:self._detail_fp[n]=dfp;self.detail_rev[n]=rev;changed=True
            sfp=json.dumps([self.detail_states.get(n),self.read_outcomes.get(n)],sort_keys=True,default=str)
            if self._state_fp.get(n)!=sfp:self._state_fp[n]=sfp;self.state_rev[n]=rev;changed=True
        gone=set(self._row_fp)-numbers
        for n in gone:
            for m in (self._row_fp,self._detail_fp,self._state_fp,self.row_rev,self.detail_rev,self.state_rev):m.pop(n,None)
        if gone:self.members_rev=rev;changed=True
        if changed:self.revision=rev
        self._dirty=False

    def delta(self,since=None,epoch=None):
        """Full snapshot, or only what changed after the client's revision of this same store."""
        with self.lock:
            self._stamp()
            if since is None or epoch!=self.epoch or since>self.revision:
                return dict(self.snapshot(),revision=self.revision,epoch=self.epoch,delta=False)
            out=dict(self.status(),revision=self.revision,epoch=self.epoch,delta=True,
                records=[deepcopy(r) for r in self.records if self.row_rev.get(r['opportunity_number'],0)>since],
                details={n:deepcopy(d) for n,d in self.details.items() if self.detail_rev.get(n,0)>since},
                detail_states={n:v for n,v in self.detail_states.items() if self.state_rev.get(n,0)>since},
                read_states={r['opportunity_number']:deepcopy(self.read_outcomes.get(r['opportunity_number'],{})) for r in self.records if self.state_rev.get(r['opportunity_number'],0)>since},
                removed_details=[n for n,rev in self.detail_rev.items() if rev>since and n not in self.details])
            if self.members_rev>since:out['numbers']=[r['opportunity_number'] for r in self.records]
            return out

    def snapshot(self):
        with self.lock: return dict(**self.status(),records=deepcopy(self.records),details=deepcopy(self.details),detail_states=deepcopy(self.detail_states),read_states={r['opportunity_number']:deepcopy(self.read_outcomes.get(r['opportunity_number'],{})) for r in self.records})

    def _detail_payload(self,body):
        if not isinstance(body,dict) or set(body)-{'opportunity_number','fields','capabilities','activities','schema_version','pending_modules','module_reason','validation_field'}:raise ValidationError('Detalle inválido.')
        if type(body.get('schema_version',1))!=int or body.get('schema_version',1) not in (1,2):raise ValidationError('Versión de detalle inválida.')
        if body.get('validation_field','') not in ('',*DETAIL_FIELDS):raise ValidationError('Campo de validación inválido.')
        modules=body.get('pending_modules',[])
        if not isinstance(modules,list) or len(modules)>2 or any(m not in ('contact','activities') for m in modules) or body.get('module_reason','') not in ('','validation'):raise ValidationError('Estado de módulos inválido.')
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
        payload={'schema_version':body.get('schema_version',1),'fields':fields,'capabilities':caps,'activities':activity,'source':'oracle-ui','partial':True,'pending_modules':modules,'module_reason':body.get('module_reason',''),'validation_field':body.get('validation_field','')}
        return number,payload,modules,fields

    def ingest_detail(self,body):
        number,payload,modules,fields=self._detail_payload(body)
        with self.lock:
            if self.repository:self.repository.save_detail(number,payload);self._reload()
            else:self.details[number]=dict(payload,loaded_at=datetime.now(timezone.utc).isoformat())
            if body.get('schema_version',1)>=2:self._read_outcome(number,'partial' if modules else 'completed',error_code='contact-unavailable' if fields.get('contact_link_status')=='Contacto eliminado o no accesible según Oracle' else '')
            if not self.job:self.request()
            if self.job.get('kind')=='details_batch' and number in self.batch_numbers:
                self.batch_partial.discard(number);self.batch_done.discard(number)
                (self.batch_partial if modules else self.batch_done).add(number);self.batch_failed.discard(number);self._batch_progress()
            else:self.job.update(state='completed',message='Detalle consultado y guardado en la copia local.',finished_at=datetime.now(timezone.utc).isoformat())
            self.failure_count=0;self.retry_after=0
        return self.status()

    def pending_details(self):
        """True when some visible opportunity has no completed detail or Oracle reported a change."""
        with self.lock:
            return any(not r.get('_unconfirmed') and (self.needs_detail(r['opportunity_number']) or self.read_outcomes.get(r['opportunity_number'],{}).get('permission_refresh_required')) for r in self.records)

    def resume_pending(self):
        """A download interrupted by a transient Oracle failure that still has work left."""
        with self.lock:
            job=self.job or {}
            if job.get('state')!='failed' or job.get('failure_code') not in ('timeout','layout','empty'):return False
            if job.get('kind') not in ('opportunities','details_batch'):return False
            if not (self.listing_coverage or {}).get('complete') or self.unconfirmed():return True
            # Records that already failed three reads are left for review, not retried forever.
            return any(not r.get('_unconfirmed') and self.read_outcomes.get(r['opportunity_number'],{}).get('state')!='failed'
                       and self.needs_detail(r['opportunity_number']) for r in self.records)

    def resume(self):
        """Restarts the interrupted download once its back-off has elapsed."""
        with self.lock:
            if not self.resume_pending() or self.retry_after>monotonic():return None
            if not (self.listing_coverage or {}).get('complete') or self.unconfirmed():return self.request('opportunities')
            return self.request('details_batch')

    def unconfirmed(self):
        """Rows shown from the last copy that Oracle has not re-confirmed in this session yet."""
        with self.lock:return sum(bool(r.get('_unconfirmed')) for r in self.records)

    def needs_detail(self,number):
        outcome=self.read_outcomes.get(number,{})
        if outcome.get('needs_refresh') or outcome.get('state') in ('failed','partial','reading'):return True
        if outcome.get('state')=='completed':return False
        detail=self.details.get(number,{})
        return detail.get('schema_version',1)<2 or bool(detail.get('pending_modules'))

    def extraction_progress(self):
        completed=sum(not self.needs_detail(r['opportunity_number']) for r in self.records)
        failed=sum(self.read_outcomes.get(r['opportunity_number'],{}).get('state')=='failed' for r in self.records)
        return {'completed':completed,'pending':len(self.records)-completed,'failed':failed,'partial':sum(self.read_outcomes.get(r['opportunity_number'],{}).get('state')=='partial' for r in self.records)}

    def _read_outcome(self,number,state,attempts=0,error_code=''):
        if state=='reading':self.read_versions[number]=next((r.get('_version') for r in self.records if r['opportunity_number']==number),None)
        version=self.read_versions.get(number)
        if self.repository and hasattr(self.repository,'save_read_progress'):
            self.repository.save_read_progress(number,state,attempts,error_code,source_version=version)
        if state!='reading':self.read_versions.pop(number,None)
        old=self.read_outcomes.get(number,{})
        current=next((r.get('_version') for r in self.records if r['opportunity_number']==number),None)
        changed=state=='completed' and version is not None and current is not None and version!=current
        self._dirty=True
        self.read_outcomes[number]={'state':state,'schema_version':2,'attempts':old.get('attempts',0)+attempts,'error_code':error_code,'source_version':version,'needs_refresh':changed}

    def read_attempt(self,number,attempt):
        with self.lock:
            self._read_outcome(number,'reading',1)
            self.claimed_at=monotonic()
            self.job['message']=f"Consultando detalles: {len(self.batch_done)} recuperados, {len(self.batch_failed)} pendientes de revisión. Intento {attempt} de 3."

    def reserve_detail(self):
        with self.lock:
            if not self.job or self.job.get('state')!='running' or self.job.get('stop_requested'):return None
            number=next((n for n in self.batch(internal=True)['pending'] if n not in self.batch_inflight),None)
            if number:self.batch_inflight.add(number)
            return number

    def release_detail(self,number):
        with self.lock:
            self.batch_inflight.discard(number)
            if self.job.get('stop_requested') and not self.batch_inflight:self.pause()

    def skip_detail(self,number,code='timeout',persist=True):
        with self.lock:
            if persist:self._read_outcome(number,'failed',error_code=code)
            self.batch_failed.add(number);self._batch_progress()

    def _batch_progress(self):
        self.claimed_at=monotonic();self.worker_seen=monotonic()
        processed=len(self.batch_done|self.batch_failed|self.batch_partial)
        self.job.update(processed=processed,successful=len(self.batch_done),failed=len(self.batch_failed),partial=len(self.batch_partial),message=f'Detalles completos: {len(self.batch_done)}. Lecturas parciales: {len(self.batch_partial)}. Pendientes de revisión: {len(self.batch_failed)}. Avance: {processed} de {len(self.batch_numbers)}.')
        if processed==len(self.batch_numbers):self.job.update(state='completed',finished_at=datetime.now(timezone.utc).isoformat())

    def batch(self,*,internal=False):
        with self.lock:
            allowed={r['opportunity_number'] for r in self.records}
            return {'job':deepcopy(self.job),'pending':[n for n in self.batch_numbers if n not in self.batch_done and n not in self.batch_failed and n not in self.batch_partial and (internal or n in allowed)],'failed':sorted(n for n in self.batch_failed if internal or n in allowed)}

    def propose(self,body):
        if self.role!='editor' or not self.repository:raise PermissionError()
        if not isinstance(body,dict) or set(body)-{'opportunity_number','field','value','version'}:raise ValidationError('Solicitud inválida.')
        number=body.get('opportunity_number');field=body.get('field')
        value=validate_change(field,body.get('value'))
        detail=self.details.get(number)
        if not detail or not detail.get('capabilities',{}).get(field):raise PermissionError()
        loaded=datetime.fromisoformat(detail['loaded_at'])
        # Oracle re-checks permission and the current value on the live form before saving;
        # this only bounds how old the observed permission may be.
        if (datetime.now(timezone.utc)-loaded).total_seconds()>EDIT_DETAIL_MAX_AGE:raise ConflictError('Vuelve a consultar el detalle en Oracle antes de editar este campo.')
        return self.repository.propose(number,field,value,body.get('version'),self.actor)

    def ingest_created(self,row,detail=None):
        """Adds an opportunity just created and verified in Oracle, without touching the sync job."""
        if not isinstance(row,dict) or set(row)-set(FIELDS):raise ValidationError('Campo no permitido.')
        clean={k:str(row.get(k) or '').strip()[:1000] for k in FIELDS if k in row}
        number=clean.get('opportunity_number','')
        if not number or len(number)>80:raise ValidationError('Número oficial vacío.')
        with self.lock:
            if not self.repository:raise PermissionError()
            self.repository.observed_fields={number:list(clean)}
            self.repository.save_snapshot([clean],'Oportunidad creada desde el portal')
            self._reload()
            if detail:
                _,payload,modules,_=self._detail_payload(dict(detail,opportunity_number=number))
                self.repository.save_detail(number,payload)
                self._reload()
                self._read_outcome(number,'reading',0)
                self._read_outcome(number,'partial' if modules else 'completed')
            return next((r for r in self.records if r['opportunity_number']==number),None)

    def propose_creation(self,body):
        if self.role!='editor' or not self.repository:raise PermissionError()
        payload=validate_creation(body)
        if any((r.get('name') or '').strip().casefold()==payload['name'].casefold() for r in self.records):
            raise ConflictError('Ya existe una oportunidad con ese nombre en tu cartera. Usa un nombre distinto para poder identificarla en Oracle.')
        return self.repository.propose_creation(payload,self.actor)

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
            if self.job and self.job['state'] in ('pending','running','paused'):return None
            if self.listing_coverage and not self.listing_coverage.get('complete'):return self.request()
            if any(r.get('_unconfirmed') for r in self.records):return self.request()
            new_details=any(not r.get('_unconfirmed') and not self.read_outcomes.get(r['opportunity_number'],{}).get('state')
                and self.needs_detail(r['opportunity_number']) for r in self.records)
            if new_details or any(r.get('needs_refresh') for r in self.read_outcomes.values()):return self.request('details_batch')
            observed=(self.listing_coverage or {}).get('finished_at') or self.loaded_at
            if observed:
                elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(observed)).total_seconds()
                if elapsed<self.settings['interval_minutes']*60:return None
            return self.request()

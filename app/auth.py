"""Screen-authenticated, ephemeral sessions. No Oracle passwords or cookies on disk."""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock,Lock
from time import monotonic,sleep
from http.cookies import SimpleCookie
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from .scoped_repository import ScopedRepository
from .oracle_read import OracleReadStore

IDLE_SECONDS=int(os.environ.get('HUB_IDLE_MINUTES','15'))*60
MAX_AGE_SECONDS=int(os.environ.get('HUB_SESSION_MAX_HOURS','8'))*3600
# While the portfolio is still being downloaded (first load, or resuming after a transient
# Oracle failure) the session stays alive in the background up to this limit.
SYNC_MAX_SECONDS=max(MAX_AGE_SECONDS,int(os.environ.get('HUB_SYNC_MAX_HOURS','24'))*3600)
ALIVE_GRACE_SECONDS=300

class AuthError(Exception):
    def __init__(self,code='session'):self.code=code

class ScreenAuth:
    def __init__(self,dsn,worker_url,secret_file,role='reader',clock=monotonic):
        if worker_url not in ('http://oracle-worker:8767','http://127.0.0.1:8767'):raise ValueError('Invalid worker')
        self.dsn=dsn;self.url=worker_url;self.secret=Path(secret_file).read_text().strip();self.role=role
        self.sessions={};self.attempts={};self.lock=RLock();self.clock=clock
        self.read_lanes=int(os.environ.get('HUB_READ_LANES','2'))
        screen_capacity=int(os.environ.get('HUB_SCREEN_OPERATIONS','2'))
        if self.read_lanes not in range(1,5) or screen_capacity not in range(1,5) or self.read_lanes>screen_capacity:raise ValueError('Read lanes must fit the screen capacity, between 1 and 4')
        self.pool=ThreadPoolExecutor(max_workers=max(2,self.read_lanes));self.record_locks={}
    def rpc(self,path,body):
        request=Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Worker-Secret':self.secret},method='POST')
        try:
            timeout=90 if path=='/login' else 360 if path=='/run' and body.get('kind')=='create' else 150 if path=='/run' else 5
            with urlopen(request,timeout=timeout) as r:return json.load(r)
        except HTTPError as error:
            try:code=json.load(error).get('code','unavailable')
            except Exception:code='unavailable'
            raise AuthError(code)
        except Exception:raise AuthError('unavailable')
    def login(self,body):
        try:return self._login(body)
        finally:body.clear()
    def _login(self,body):
        if set(body)!={'username','password'}:raise AuthError('credentials-or-challenge')
        user=body.get('username');password=body.get('password')
        if not isinstance(user,str) or not 0<len(user.strip())<=150 or not isinstance(password,str) or not 0<len(password)<=512:raise AuthError('credentials-or-challenge')
        key=hashlib.sha256(user.strip().casefold().encode()).hexdigest();now=self.clock()
        with self.lock:
            self.attempts={k:[t for t in v if now-t<900] for k,v in self.attempts.items() if any(now-t<900 for t in v)}
            times=self.attempts.setdefault(key,[])
            if len(times)>=5 or sum(map(len,self.attempts.values()))>=30:raise AuthError('rate')
            times.append(now)
        verified=None
        try:
            verified=self.rpc('/login',{'username':user.strip(),'password':password})
            principal=verified['principal']
            repository=ScopedRepository(self.dsn,principal)
            store=OracleReadStore(repository,role=self.role);store.actor=principal;store.write_enabled=True;store.heartbeat()
            token=token_urlsafe(48);now=self.clock()
            session={'worker_id':verified['id'],'principal':principal,'display':verified['display'],'store':store,'created':now,'seen':now,'checked':now,'demo':None,'task_lock':Lock(),'lane_locks':[Lock() for _ in range(self.read_lanes)],'grant_lock':Lock()}
            with self.lock:self.sessions[token]=session
            # Rows shown from the last copy are re-confirmed right away with a new inventory.
            if not store.records or not (store.listing_coverage or {}).get('complete') or store.unconfirmed():store.request('opportunities');self.execute(session)
            elif store.pending_details():store.request('details_batch');self.execute(session)
            return token,session
        except Exception:
            if verified:
                try:self.rpc('/logout',{'id':verified['id']})
                except Exception:pass
            raise
        finally:body.clear();password=None
    def resolve(self,cookie):
        jar=SimpleCookie()
        try:jar.load(cookie or '');token=jar['hub_session'].value
        except Exception:raise AuthError()
        with self.lock:
            session=self.sessions.get(token);now=self.clock()
            if session and self.sync_active(session):session['seen']=now
            if not session or now-session['seen']>IDLE_SECONDS or now>self.deadline(session):
                expired=self.sessions.pop(token,None)
                if expired:self.pool.submit(self.rpc,'/logout',{'id':expired['worker_id']})
                raise AuthError()
            if now-session['checked']>10:
                try:
                    self.rpc('/alive',{'id':session['worker_id']})
                    session['checked']=now
                except AuthError as error:
                    # Only a confirmed loss of the Oracle context ends the session. A worker
                    # that is slow to answer while it extracts (high CPU) is retried on the
                    # next request instead of logging the user out mid-sync.
                    if error.code=='session' or now-session['checked']>ALIVE_GRACE_SECONDS:
                        self.sessions.pop(token,None);raise
            session['store'].heartbeat()
            return session
    def logout(self,cookie):
        jar=SimpleCookie()
        try:jar.load(cookie or '');token=jar['hub_session'].value
        except Exception:return
        with self.lock:session=self.sessions.pop(token,None)
        if session:
            try:self.rpc('/logout',{'id':session['worker_id']})
            except AuthError:pass
    def sweep(self):
        with self.lock:
            now=self.clock();expired=[]
            for token,s in list(self.sessions.items()):
                # A synchronisation that is running or will resume keeps its session alive
                # until everything is downloaded, even if the browser tab is idle or closed.
                if self.sync_active(s):s['seen']=now
                if now-s['seen']>IDLE_SECONDS or now>self.deadline(s):expired.append(self.sessions.pop(token))
        for session in expired:
            try:self.rpc('/logout',{'id':session['worker_id']})
            except AuthError:pass
    def sync_active(self,session):
        """A download in progress, or one that resumes by itself after a transient failure."""
        store=session['store'];job=store.job or {}
        if self.clock()>=session.get('created',0)+SYNC_MAX_SECONDS:return False
        return job.get('state') in ('pending','running') or bool(getattr(store,'resume_pending',lambda:False)())
    def deadline(self,session):
        return session.get('created',0)+(SYNC_MAX_SECONDS if self.sync_active(session) else MAX_AGE_SECONDS)
    def batch_active(self,session):
        job=session['store'].job or {}
        return (job.get('kind') in ('details_batch','opportunities') and job.get('state')=='running'
                and session.get('batch_job')==job.get('id')
                and self.clock()<session.get('batch_deadline',0)
                and self.clock()<session.get('created',0)+SYNC_MAX_SECONDS)
    def session_rpc(self,session,body):
        if body.get('kind') in ('write','create'):
            # A write may run while a sync is in progress: it waits for the reads in
            # flight to finish and holds every lane, so Oracle never sees a save and a
            # read from the same user at the same time.
            with ExitStack() as stack:
                stack.enter_context(session['task_lock'])
                for lane_lock in session.get('lane_locks',[]):stack.enter_context(lane_lock)
                return self._session_rpc(session,body)
        lock=session['lane_locks'][body['lane']] if body.get('kind')=='detail' and 'lane' in body else session['task_lock']
        with lock:return self._session_rpc(session,body)
    def _session_rpc(self,session,body):
        with self.lock:
            batch_read=self.batch_active(session) and (body.get('kind')=='opportunities' or body.get('kind')=='detail' and body.get('number') in session['store'].batch_numbers)
            if (not any(s is session for s in self.sessions.values())
                or self.clock()>=self.deadline(session)
                or self.clock()-session['seen']>IDLE_SECONDS and not batch_read):raise AuthError('session')
        return self.rpc('/run',dict(body,id=session['worker_id']))
    def submit_write(self,session,identifier,reconcile=False):
        if session['store'].role!='editor':raise PermissionError()
        repo=session['store'].repository;actor=session['principal']
        request=next((r for r in repo.changes() if r['id']==identifier),None)
        if not request:raise PermissionError()
        repo.require(request['opportunity_number'],request['field'])
        if not reconcile and request['state']!='pending_validation':raise PermissionError()
        if reconcile and request['state']!='uncertain':raise PermissionError()
        if not reconcile:repo.write_state(identifier,actor,'queued')
        with self.lock:record_lock=self.record_locks.setdefault(request['opportunity_number'],Lock())
        def write():
            with record_lock:
                try:
                    with self.lock:
                        if not any(s is session for s in self.sessions.values()) or self.clock()-session['seen']>IDLE_SECONDS:raise AuthError('session')
                    if reconcile:
                        detail=self.session_rpc(session,{'kind':'detail','number':request['opportunity_number']})
                        actual=detail['fields'].get(request['field'],'')
                        from .persistence import same_value
                        if same_value(request['field'],actual,request['new_value']):repo.confirm_write(identifier,actor,detail)
                        else:repo.write_state(identifier,actor,'conflict','reconciled-different')
                    else:
                        current=repo.start_write(identifier,actor)
                        result=self.session_rpc(session,{'kind':'write','change':{k:current[k] for k in ('opportunity_number','field','old_value','new_value')}})
                        session['seen']=max(session['seen'],self.clock())
                        if not result.get('verified'):raise AuthError('uncertain')
                        repo.confirm_write(identifier,actor,result['detail'])
                    session['store']._reload()
                except AuthError as error:
                    state='conflict' if error.code=='conflict' else 'failed' if error.code in ('permission','validation','side-effects','write-not-started','session') else 'uncertain'
                    repo.write_state(identifier,actor,state,error.code)
                except Exception:repo.write_state(identifier,actor,'uncertain','unavailable')
        self.pool.submit(write)
        return {'id':identifier,'state':'uncertain' if reconcile else 'queued','message':'Verificando en Oracle.' if reconcile else 'Cambio en cola para guardar y verificar en Oracle.'}
    def submit_create(self,session,identifier,retry=False):
        """Creates an opportunity in Oracle with the user's session, then mirrors it locally."""
        store=session['store']
        if store.role!='editor':raise PermissionError()
        repo=store.repository;actor=session['principal']
        request=next((r for r in repo.creations() if r['id']==identifier),None)
        if not request or request['state']!=('failed' if retry else 'pending_validation'):raise PermissionError()
        repo.creation_state(identifier,actor,'queued')
        def create():
            contact_created=request['contact_created']
            try:
                with self.lock:
                    if not any(s is session for s in self.sessions.values()) or self.clock()-session['seen']>IDLE_SECONDS:raise AuthError('session')
                repo.creation_state(identifier,actor,'applying')
                result=self.session_rpc(session,{'kind':'create','request':dict(request['payload'],contact_created=contact_created)})
                session['seen']=max(session['seen'],self.clock())
                contact_created=contact_created or bool(result.get('contact_created'))
                if not result.get('created') or not result.get('opportunity_number'):raise AuthError('uncertain')
                number=result['opportunity_number']
                store.ingest_created(result.get('row') or {'opportunity_number':number},result.get('detail'))
                repo.creation_state(identifier,actor,'confirmed',number=number,contact_created=contact_created)
                # Admission fields chosen in the form are saved as ordinary verified changes.
                for field,value in (request['payload'].get('extra') or {}).items():
                    try:
                        record=next(r for r in store.records if r['opportunity_number']==number)
                        change=store.propose({'opportunity_number':number,'field':field,'value':value,'version':record['_version']})
                        self.submit_write(session,change['id'])
                    except Exception as error:
                        print('Follow-up field not queued:',field,type(error).__name__,flush=True)
            except AuthError as error:
                code=error.code
                if code=='contact-created':contact_created=True;code='write-not-started'
                state='uncertain' if code=='uncertain' else 'failed'
                repo.creation_state(identifier,actor,state,code,contact_created=contact_created)
            except Exception as error:
                print('Oracle create failure:',type(error).__name__,flush=True)
                repo.creation_state(identifier,actor,'uncertain','unavailable',contact_created=contact_created)
        self.pool.submit(create)
        return {'id':identifier,'state':'queued','message':'Creación en cola: se registrará en Oracle con tu sesión y se verificará.'}
    def execute(self,session):
        store=session['store'];job=store.claim()
        if not job:return
        if job['kind'] in ('details_batch','opportunities'):
            now=self.clock()
            session['batch_job']=job['id']
            session['batch_deadline']=session['created']+SYNC_MAX_SECONDS
            store.job['background_until']=datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()+session['batch_deadline']-now,timezone.utc).isoformat()
        consecutive_failures=0
        def run(lane=0):
            nonlocal consecutive_failures
            number=None
            try:
                if store.job.get('id')!=job['id'] or store.job.get('state')!='running':return
                if store.job.get('stop_requested'):
                    if not store.batch_inflight:store.pause()
                    return
                if job['kind']=='details_batch':
                    if not self.batch_active(session):raise AuthError('session')
                    number=store.reserve_detail()
                    if number:
                        # Renew the list grant when a long batch crosses its expiry.
                        if store.repository and hasattr(store.repository,'grants'):
                            with session['grant_lock']:
                                grant=store.repository.grant(number) if hasattr(store.repository,'grant') else store.repository.grants().get(number)
                                if not grant or (grant['read_until']-datetime.now(timezone.utc)).total_seconds()<180:
                                    self.refresh_listing(session)
                                    if number not in store.repository.grants():
                                        store.skip_detail(number,'permission',persist=False)
                                        return
                        for attempt in range(1,4):
                            store.read_attempt(number,attempt)
                            read_started=monotonic()
                            try:
                                result=self.session_rpc(session,{'kind':'detail','number':number,'reuse':True,'lane':lane})
                            except AuthError as error:
                                if error.code in ('session','credentials-or-challenge'):raise
                                if attempt<3 and error.code in ('unavailable','busy','layout'):
                                    sleep(attempt)
                                    continue
                                store.skip_detail(number,'permission' if error.code=='permission' else 'timeout')
                                consecutive_failures+=1
                                break
                            else:
                                if store.job.get('id')!=job['id']:return
                                store.record_timing(monotonic()-read_started)
                                store.ingest_detail(result);consecutive_failures=0
                                break
                        if consecutive_failures>=3 and store.batch(internal=True)['pending']:
                            store.fail('timeout')
                            store.job['message']='Oracle no está respondiendo. Se conserva el avance; la carga se retomará sola en unos minutos.'
                elif job['kind']=='opportunities':
                    coverage=self.refresh_listing(session)
                    store.job.update(state='completed' if coverage['complete'] else 'failed',
                      message=f"Inventario 2026: {coverage['row_count']} oportunidades identificadas en todos los estados."+('' if coverage['complete'] else ' Hay intervalos que exceden el límite de exportación.'),
                      finished_at=datetime.now(timezone.utc).isoformat())
                    # A verified inventory continues straight into the details that are
                    # missing or changed, without waiting for a click or the scheduler.
                    if coverage['complete'] and store.pending_details():
                        store.request('details_batch');self.pool.submit(self.execute,session)
                else:
                    store.repository.snapshot_started=datetime.now(timezone.utc)
                    if job['kind']=='detail':store.read_attempt(job['opportunity_number'],1)
                    result=self.session_rpc(session,{'kind':job['kind'],'number':job.get('opportunity_number')})
                    if job['kind']=='detail':store.ingest_detail(result)
                    else:
                        if 'export_html' in result:
                            from .oracle_export import parse_export
                            result=parse_export(result['export_html'],result['scope'])
                        store.repository.observed_fields=result.pop('visible_fields',{})
                        store.ingest(result)
            except AuthError as error:
                print('Oracle read failure:',error.code,flush=True)
                store.fail('session' if error.code in ('session','credentials-or-challenge') else 'timeout')
                if error.code=='session':
                    with self.lock:
                        for token,s in list(self.sessions.items()):
                            if s is session:self.sessions.pop(token,None)
            except Exception as error:
                print('Oracle mirror failure:',type(error).__name__,flush=True)
                store.fail('timeout')
            finally:
                if number and store.job.get('id')==job['id']:store.release_detail(number)
                if number and job['kind']=='details_batch' and store.job.get('id')==job['id'] and store.job.get('state')=='running' and not store.job.get('stop_requested') and store.batch(internal=True)['pending']:
                    self.pool.submit(run,lane)
        self.pool.submit(run)
        if job['kind']=='details_batch':
            for lane in range(1,getattr(self,'read_lanes',2)):self.pool.submit(run,lane)

    def refresh_listing(self,session):
        from .oracle_scope import inventory
        from .oracle_export import parse_export
        store=session['store']
        store.repository.snapshot_started=datetime.now(timezone.utc)
        def fetch(query):
            for attempt in range(1,4):
                try:
                    result=self.session_rpc(session,{'kind':'opportunities','query':query,'reuse':True});break
                except AuthError as error:
                    if attempt==3 or error.code not in ('unavailable','layout','busy'):raise
                    sleep(attempt)
            if 'export_html' in result:return parse_export(result['export_html'],result['scope'])
            if result.get('empty_verified') is True:return {'records':[],'empty_verified':True}
            raise AuthError('unavailable')
        def ingest(result):
            store.repository.observed_fields=result.pop('visible_fields',{})
            store.ingest(result,preserve_job=True)
        def finalize(numbers):
            with store.lock:
                store.repository.reconcile_visible_inventory(numbers)
                store._reload()
        return inventory(fetch,ingest,store.record_listing_coverage,finalize=finalize)

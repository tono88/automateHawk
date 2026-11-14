"""Screen-authenticated, ephemeral sessions. No Oracle passwords or cookies on disk."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock,Lock
from time import monotonic,sleep
from http.cookies import SimpleCookie
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
from .scoped_repository import ScopedRepository
from .oracle_read import OracleReadStore

class AuthError(Exception):
    def __init__(self,code='session'):self.code=code

class ScreenAuth:
    def __init__(self,dsn,worker_url,secret_file,role='reader',clock=monotonic):
        if worker_url not in ('http://oracle-worker:8767','http://127.0.0.1:8767'):raise ValueError('Invalid worker')
        self.dsn=dsn;self.url=worker_url;self.secret=Path(secret_file).read_text().strip();self.role=role
        self.sessions={};self.attempts={};self.lock=RLock();self.clock=clock
        self.pool=ThreadPoolExecutor(max_workers=2);self.record_locks={}
    def rpc(self,path,body):
        request=Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Worker-Secret':self.secret},method='POST')
        try:
            with urlopen(request,timeout=90 if path=='/login' else 150 if path=='/run' else 5) as r:return json.load(r)
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
            session={'worker_id':verified['id'],'principal':principal,'display':verified['display'],'store':store,'created':now,'seen':now,'checked':now,'demo':None,'task_lock':Lock(),'lane_locks':[Lock(),Lock()],'grant_lock':Lock()}
            with self.lock:self.sessions[token]=session
            if not store.records:store.request('opportunities');self.execute(session)
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
            if not session or now-session['seen']>900 or now-session['created']>28800:
                # An explicitly started read batch may finish without keeping the
                # interactive cookie usable. No writes receive this exemption.
                if session and self.batch_active(session):raise AuthError()
                expired=self.sessions.pop(token,None)
                if expired:self.pool.submit(self.rpc,'/logout',{'id':expired['worker_id']})
                raise AuthError()
            if now-session['checked']>10:
                try:self.rpc('/alive',{'id':session['worker_id']})
                except AuthError:self.sessions.pop(token,None);raise
                session['checked']=now
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
                if (now-s['seen']>900 or now-s['created']>28800) and not self.batch_active(s):expired.append(self.sessions.pop(token))
        for session in expired:
            try:self.rpc('/logout',{'id':session['worker_id']})
            except AuthError:pass
    def batch_active(self,session):
        job=session['store'].job or {}
        return (job.get('kind') in ('details_batch','opportunities') and job.get('state')=='running'
                and session.get('batch_job')==job.get('id')
                and self.clock()<session.get('batch_deadline',0)
                and self.clock()<session.get('created',0)+28800)
    def session_rpc(self,session,body):
        lock=session['lane_locks'][body['lane']] if body.get('kind')=='detail' and 'lane' in body else session['task_lock']
        with lock:
            with self.lock:
                batch_read=self.batch_active(session) and (body.get('kind')=='opportunities' or body.get('kind')=='detail' and body.get('number') in session['store'].batch_numbers)
                if (not any(s is session for s in self.sessions.values())
                    or self.clock()-session['created']>=28800
                    or self.clock()-session['seen']>900 and not batch_read):raise AuthError('session')
            return self.rpc('/run',dict(body,id=session['worker_id']))
    def submit_write(self,session,identifier,reconcile=False):
        if session['store'].role!='editor':raise PermissionError()
        if self.batch_active(session):raise PermissionError()
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
                        if not any(s is session for s in self.sessions.values()) or self.clock()-session['seen']>900:raise AuthError('session')
                    if reconcile:
                        detail=self.session_rpc(session,{'kind':'detail','number':request['opportunity_number']})
                        actual=detail['fields'].get(request['field'],'')
                        from .persistence import same_value
                        if same_value(request['field'],actual,request['new_value']):repo.confirm_write(identifier,actor,detail)
                        else:repo.write_state(identifier,actor,'conflict','reconciled-different')
                    else:
                        current=repo.start_write(identifier,actor)
                        result=self.session_rpc(session,{'kind':'write','change':{k:current[k] for k in ('opportunity_number','field','old_value','new_value')}})
                        if not result.get('verified'):raise AuthError('uncertain')
                        repo.confirm_write(identifier,actor,result['detail'])
                    session['store']._reload()
                except AuthError as error:
                    state='conflict' if error.code=='conflict' else 'failed' if error.code in ('permission','validation','side-effects','write-not-started','session') else 'uncertain'
                    repo.write_state(identifier,actor,state,error.code)
                except Exception:repo.write_state(identifier,actor,'uncertain','unavailable')
        self.pool.submit(write)
        return {'id':identifier,'state':'uncertain' if reconcile else 'queued','message':'Verificando en Oracle.' if reconcile else 'Cambio en cola para guardar y verificar en Oracle.'}
    def execute(self,session):
        store=session['store'];job=store.claim()
        if not job:return
        if job['kind'] in ('details_batch','opportunities'):
            now=self.clock()
            session['batch_job']=job['id']
            session['batch_deadline']=min(session['created']+28800,now+14400)
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
                                grant=store.repository.grants().get(number)
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
                            store.job['message']='Oracle no está respondiendo. Se conservan el avance y los pendientes; puedes retomar la carga con tu sesión.'
                elif job['kind']=='opportunities':
                    coverage=self.refresh_listing(session)
                    store.job.update(state='completed' if coverage['complete'] else 'failed',
                      message=f"Inventario 2026: {coverage['row_count']} oportunidades identificadas en todos los estados."+('' if coverage['complete'] else ' Hay intervalos que exceden el límite de exportación.'),
                      finished_at=datetime.now(timezone.utc).isoformat())
                else:
                    store.repository.snapshot_started=datetime.now(timezone.utc)
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
        if job['kind']=='details_batch':self.pool.submit(run,1)

    def refresh_listing(self,session):
        from .oracle_scope import inventory
        from .oracle_export import parse_export
        store=session['store']
        store.repository.snapshot_started=datetime.now(timezone.utc)
        def fetch(query):
            result=self.session_rpc(session,{'kind':'opportunities','query':query,'reuse':True})
            if 'export_html' in result:return parse_export(result['export_html'],result['scope'])
            if result.get('empty_verified') is True:return {'records':[],'empty_verified':True}
            raise AuthError('unavailable')
        def ingest(result):
            store.repository.observed_fields=result.pop('visible_fields',{})
            store.ingest(result,preserve_job=True)
        return inventory(fetch,ingest,store.record_listing_coverage)

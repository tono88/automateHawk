"""Screen-authenticated, ephemeral sessions. No Oracle passwords or cookies on disk."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock,Lock
from time import monotonic
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
            session={'worker_id':verified['id'],'principal':principal,'display':verified['display'],'store':store,'created':now,'seen':now,'checked':now,'demo':None,'task_lock':Lock()}
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
                if now-s['seen']>900 or now-s['created']>28800:expired.append(self.sessions.pop(token))
        for session in expired:
            try:self.rpc('/logout',{'id':session['worker_id']})
            except AuthError:pass
    def session_rpc(self,session,body):
        with session['task_lock']:
            with self.lock:
                if not any(s is session for s in self.sessions.values()) or self.clock()-session['seen']>900:raise AuthError('session')
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
        def run():
            try:
                if job['kind']=='details_batch':
                    pending=store.batch()['pending']
                    if pending:
                        result=self.session_rpc(session,{'kind':'detail','number':pending[0]});store.ingest_detail(result)
                        if store.batch()['pending']:self.pool.submit(run)
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
        self.pool.submit(run)

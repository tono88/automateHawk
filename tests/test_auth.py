import json,unittest
from unittest.mock import Mock
from threading import RLock
from app import server
from app.auth import ScreenAuth,AuthError
from app.oracle_read import OracleReadStore
import test_lab

class SessionTests(unittest.TestCase):
    def auth(self):
        a=object.__new__(ScreenAuth);a.sessions={};a.lock=RLock();a.clock=lambda:1000;a.rpc=Mock(return_value={'ok':True});a.pool=Mock()
        a.sessions['synthetic-token']={'created':900,'seen':990,'checked':990,'worker_id':'fake','store':OracleReadStore()}
        return a
    def test_cookie_required_and_forged_cookie_rejected(self):
        a=self.auth()
        for cookie in ('','hub_session=forged','role=editor'):
            with self.assertRaises(AuthError):a.resolve(cookie)
    def test_polling_does_not_extend_idle_lifetime(self):
        a=self.auth();s=a.resolve('hub_session=synthetic-token');self.assertEqual(s['seen'],990)
        a.clock=lambda:1891
        with self.assertRaises(AuthError):a.resolve('hub_session=synthetic-token')
        self.assertNotIn('synthetic-token',a.sessions)
    def test_worker_loss_revokes_session(self):
        a=self.auth();a.clock=lambda:1010;a.rpc.side_effect=AuthError('session')
        with self.assertRaises(AuthError):a.resolve('hub_session=synthetic-token')
        self.assertFalse(a.sessions)
    def test_running_sync_keeps_the_session_open_until_it_finishes(self):
        from threading import Lock
        a=self.auth();s=a.sessions['synthetic-token'];s['task_lock']=Lock();s['lane_locks']=[Lock(),Lock()]
        s['store'].ingest({'records':[{'opportunity_number':'SYNTHETIC-001'}],'scope':'Synthetic','partial':True})
        s['store'].request('details_batch');job=s['store'].claim()
        s.update(batch_job=job['id'],batch_deadline=900+28800)
        a.clock=lambda:2000
        self.assertIs(a.resolve('hub_session=synthetic-token'),s)
        self.assertEqual(s['seen'],2000)
        a.session_rpc(s,{'kind':'detail','number':'SYNTHETIC-001'})
        # Writes are accepted during the sync; they hold every read lane while they run.
        a.session_rpc(s,{'kind':'write'})
        self.assertFalse(any(l.locked() for l in s['lane_locks']+[s['task_lock']]))
        s['store'].job.update(state='completed')
        a.clock=lambda:2000+901
        with self.assertRaises(AuthError):a.resolve('hub_session=synthetic-token')
        self.assertNotIn('synthetic-token',a.sessions)
    def test_first_load_outlives_the_normal_session_limit(self):
        from app.auth import MAX_AGE_SECONDS,SYNC_MAX_SECONDS
        a=self.auth();s=a.sessions['synthetic-token'];s['created']=0;s['checked']=10**9
        s['store'].job={'kind':'details_batch','state':'running','id':'synthetic-job'}
        a.clock=lambda:MAX_AGE_SECONDS+3600
        self.assertIs(a.resolve('hub_session=synthetic-token'),s)
        s['store'].job['state']='completed'
        with self.assertRaises(AuthError):a.resolve('hub_session=synthetic-token')
        a.sessions['synthetic-token']=s;s['store'].job['state']='running';a.clock=lambda:SYNC_MAX_SECONDS+1
        with self.assertRaises(AuthError):a.resolve('hub_session=synthetic-token')
    def test_sweep_keeps_syncing_sessions_even_without_an_open_tab(self):
        a=self.auth();s=a.sessions['synthetic-token']
        s['store'].job={'kind':'details_batch','state':'running','id':'synthetic-job'}
        a.clock=lambda:5000;a.sweep()
        self.assertIn('synthetic-token',a.sessions);self.assertEqual(s['seen'],5000)
        s['store'].job['state']='paused';a.clock=lambda:5000+901;a.sweep()
        self.assertNotIn('synthetic-token',a.sessions)
    def test_slow_worker_does_not_log_out_but_lost_context_does(self):
        a=self.auth();a.clock=lambda:1010;a.rpc.side_effect=AuthError('unavailable')
        self.assertIs(a.resolve('hub_session=synthetic-token'),a.sessions['synthetic-token'])
        a.clock=lambda:990+301
        a.sessions['synthetic-token']['seen']=1290
        with self.assertRaises(AuthError):a.resolve('hub_session=synthetic-token')
        self.assertFalse(a.sessions)
    def test_logout_revokes_authorized_batch_too(self):
        a=self.auth();s=a.sessions['synthetic-token']
        s['store'].job={'kind':'details_batch','state':'running','id':'synthetic-job'}
        s.update(batch_job='synthetic-job',batch_deadline=5000)
        a.logout('hub_session=synthetic-token')
        self.assertFalse(a.sessions);a.rpc.assert_called_once_with('/logout',{'id':'fake'})
    def test_login_resumes_incomplete_inventory_even_when_some_grants_are_cached(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        # Incomplete inventory → inventory; complete with missing details → details; complete → nothing;
        # rows shown from the last copy → inventory to re-confirm them.
        for complete,pending,expected,stale in ((False,False,'opportunities',0),(True,True,'details_batch',0),(True,False,None,0),(True,True,'opportunities',5)):
            a=self.auth();a.attempts={};a.dsn='synthetic-dsn';a.role='reader';a.read_lanes=2;a.execute=Mock()
            a.rpc.return_value={'principal':'synthetic-user','id':'synthetic-worker','display':'Persona ficticia'}
            store=SimpleNamespace(records=[{'opportunity_number':'SYNTHETIC-001'}],listing_coverage={'complete':complete},heartbeat=Mock(),request=Mock(),pending_details=Mock(return_value=pending),unconfirmed=Mock(return_value=stale))
            with patch('app.auth.ScopedRepository'),patch('app.auth.OracleReadStore',return_value=store):
                body={'username':'synthetic-user','password':'synthetic-only'};a.login(body)
                self.assertEqual(body,{})
            self.assertEqual(a.execute.call_count,0 if expected is None else 1)
            if expected:store.request.assert_called_once_with(expected)

    def test_inventory_retries_only_transient_read_failures(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        a=self.auth();session=a.sessions['synthetic-token'];session['store'].repository=SimpleNamespace()
        invoke=lambda fetch,ingest,progress,**kwargs:fetch({})
        a.session_rpc=Mock(side_effect=[AuthError('unavailable'),{'empty_verified':True}])
        with patch('app.oracle_scope.inventory',side_effect=invoke),patch('app.auth.sleep'):
            self.assertEqual(a.refresh_listing(session),{'records':[],'empty_verified':True})
        self.assertEqual(a.session_rpc.call_count,2)
        for code,calls in [('unavailable',3),('session',1)]:
            a.session_rpc=Mock(side_effect=AuthError(code))
            with patch('app.oracle_scope.inventory',side_effect=invoke),patch('app.auth.sleep'),self.assertRaises(AuthError):a.refresh_listing(session)
            self.assertEqual(a.session_rpc.call_count,calls)

    def test_verified_inventory_continues_into_missing_details(self):
        from types import SimpleNamespace
        from app.oracle_read import OracleReadStore
        a=self.auth();session=a.sessions['synthetic-token'];store=OracleReadStore();session['store']=store
        store.ingest({'records':[{'opportunity_number':'SYNTHETIC-001'}],'scope':'Synthetic','partial':True})
        submitted=[];a.pool=SimpleNamespace(submit=lambda fn,*args:submitted.append((fn,args)))
        a.refresh_listing=Mock(return_value={'complete':True,'row_count':1})
        store.request('opportunities');a.execute(session)
        run,args=submitted.pop(0);run(*args)
        self.assertEqual(store.job['kind'],'details_batch');self.assertEqual(store.job['state'],'pending')
        self.assertEqual(submitted[0],(a.execute,(session,)))

    def test_logout_is_server_side_revocation(self):
        a=self.auth();a.logout('hub_session=synthetic-token');self.assertFalse(a.sessions);a.rpc.assert_called_once_with('/logout',{'id':'fake'})
    def test_login_failure_clears_credentials_and_enforces_attempt_limit(self):
        a=self.auth();a.attempts={};a.rpc.side_effect=AuthError('credentials-or-challenge')
        for i in range(5):
            body={'username':'synthetic-user','password':'synthetic-only'}
            with self.assertRaises(AuthError):a.login(body)
            self.assertEqual(body,{})
        body={'username':'synthetic-user','password':'synthetic-only'}
        with self.assertRaises(AuthError) as error:a.login(body)
        self.assertEqual(error.exception.code,'rate');self.assertEqual(body,{})

class WriteQueueTests(unittest.TestCase):
    def setup_auth(self,code=None,reconcile=False):
        from types import SimpleNamespace
        from threading import Lock
        a=object.__new__(ScreenAuth);a.clock=lambda:1000;a.lock=RLock();a.record_locks={}
        repo=Mock();repo.changes.return_value=[{'id':'synthetic-change','opportunity_number':'SYNTHETIC-001','field':'name','old_value':'Nombre anterior ficticio','new_value':'Nuevo ficticio','state':'uncertain' if reconcile else 'pending_validation'}]
        repo.start_write.return_value=repo.changes.return_value[0]
        store=SimpleNamespace(repository=repo,role='editor',job=None,_reload=Mock())
        session={'store':store,'principal':'synthetic-user','seen':999,'task_lock':Lock()};a.sessions={'test':session}
        a.pool=SimpleNamespace(submit=lambda fn:fn())
        a.session_rpc=Mock(return_value={'verified':True,'detail':{'fields':{'name':'Nuevo ficticio'}}})
        if code:a.session_rpc.side_effect=AuthError(code)
        return a,session,repo
    def test_verified_result_confirms_once(self):
        a,s,r=self.setup_auth();a.submit_write(s,'synthetic-change')
        r.confirm_write.assert_called_once();self.assertEqual(a.session_rpc.call_count,1)
    def test_uncertain_write_is_not_retried(self):
        a,s,r=self.setup_auth('unavailable');a.submit_write(s,'synthetic-change')
        r.confirm_write.assert_not_called();self.assertEqual(a.session_rpc.call_count,1)
        self.assertEqual(r.write_state.call_args.args[2],'uncertain')
    def test_conflict_never_claims_success(self):
        a,s,r=self.setup_auth('conflict');a.submit_write(s,'synthetic-change')
        r.confirm_write.assert_not_called();self.assertEqual(r.write_state.call_args.args[2],'conflict')
    def test_reader_cannot_request_a_write(self):
        a,s,r=self.setup_auth();s['store'].role='reader'
        with self.assertRaises(PermissionError):a.submit_write(s,'synthetic-change')
        a.session_rpc.assert_not_called()
    def test_reconciliation_reads_without_repeating_save(self):
        a,s,r=self.setup_auth(reconcile=True);a.session_rpc.return_value={'fields':{'name':'Nuevo ficticio'}}
        a.submit_write(s,'synthetic-change',reconcile=True)
        self.assertEqual(a.session_rpc.call_args.args[1]['kind'],'detail');r.confirm_write.assert_called_once()

    def test_write_is_accepted_while_a_sync_is_running(self):
        a,s,r=self.setup_auth();s['store'].job={'kind':'details_batch','state':'running','id':'synthetic-job'}
        s.update(batch_job='synthetic-job',batch_deadline=5000,created=900)
        a.submit_write(s,'synthetic-change')
        r.confirm_write.assert_called_once();self.assertEqual(a.session_rpc.call_args.args[1]['kind'],'write')

    def creation_setup(self,rpc=None,state='pending_validation',contact_created=False):
        a,s,r=self.setup_auth()
        payload={'name':'Oportunidad ficticia nueva','close_date':'2026-12-01','stage':'01 - Interesado','probability':'','contact':{'mode':'new','first_name':'Ana','last_name':'Ficticia','email':'','phone':''},'extra':{'test_call':'Enero 2027'}}
        r.creations.return_value=[{'id':'synthetic-create','payload':payload,'state':state,'contact_created':contact_created}]
        s['store'].ingest_created=Mock(return_value={'opportunity_number':'SYN-NEW','_version':1})
        s['store'].records=[{'opportunity_number':'SYN-NEW','_version':1}]
        s['store'].propose=Mock(return_value={'id':'follow-up'})
        a.submit_write=Mock()
        if isinstance(rpc,Exception):a.session_rpc=Mock(side_effect=rpc)
        else:a.session_rpc=Mock(return_value=rpc or {'created':True,'opportunity_number':'SYN-NEW','row':{'opportunity_number':'SYN-NEW','name':'Oportunidad ficticia nueva'},'detail':None,'contact_created':True})
        return a,s,r
    def test_created_opportunity_is_mirrored_and_follow_up_fields_are_queued(self):
        a,s,r=self.creation_setup();a.submit_create(s,'synthetic-create')
        self.assertEqual(a.session_rpc.call_args.args[1]['kind'],'create')
        s['store'].ingest_created.assert_called_once()
        r.creation_state.assert_called_with('synthetic-create','synthetic-user','confirmed',number='SYN-NEW',contact_created=True)
        s['store'].propose.assert_called_once();a.submit_write.assert_called_once_with(s,'follow-up')
    def test_failed_creation_remembers_a_created_contact_and_can_be_retried(self):
        a,s,r=self.creation_setup(AuthError('contact-created'));a.submit_create(s,'synthetic-create')
        r.creation_state.assert_called_with('synthetic-create','synthetic-user','failed','write-not-started',contact_created=True)
        a,s,r=self.creation_setup(state='failed',contact_created=True);a.submit_create(s,'synthetic-create',retry=True)
        self.assertTrue(a.session_rpc.call_args.args[1]['request']['contact_created'])
    def test_unknown_outcome_after_save_is_uncertain_not_retried(self):
        a,s,r=self.creation_setup(AuthError('uncertain'));a.submit_create(s,'synthetic-create')
        r.creation_state.assert_called_with('synthetic-create','synthetic-user','uncertain','uncertain',contact_created=False)
        with self.assertRaises(PermissionError):a.submit_create(s,'synthetic-create',retry=True)

class AuthHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):test_lab.HttpTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):test_lab.HttpTests.tearDownClass.__func__(cls)
    request=test_lab.HttpTests.request
    def setUp(self):
        self.old=server.AUTH;server.AUTH=Mock();server.AUTH.resolve.side_effect=AuthError()
    def tearDown(self):server.AUTH=self.old
    def test_all_data_routes_require_session(self):
        for path in ('/api/snapshot','/api/oracle/snapshot','/api/oracle/workspace','/api/oracle/status','/api/oracle/activities','/api/oracle/changes','/api/oracle/batch','/api/oracle/catalog'):
            with self.subTest(path=path):self.assertEqual(self.request(path)[0],401)
    def test_workspace_authenticates_and_reloads_the_scoped_model_once(self):
        store=OracleReadStore();store.ingest({'records':[{'opportunity_number':'SYNTHETIC-001'}],'scope':'Synthetic','partial':True})
        store.refresh_if_changed=Mock();server.AUTH.resolve.side_effect=None
        server.AUTH.resolve.return_value={'store':store,'principal':'synthetic-user'}
        code,body,_=self.request('/api/oracle/workspace')
        data=json.loads(body);self.assertEqual(code,200)
        self.assertEqual(data['snapshot']['records'][0]['opportunity_number'],'SYNTHETIC-001')
        self.assertEqual(data['changes'],[]);self.assertEqual(data['activities'],[])
        self.assertIn('appointments',data['schemas']);store.refresh_if_changed.assert_called_once()

    def test_no_origin_or_cross_origin_cannot_login(self):
        self.assertEqual(self.request('/api/auth/login','POST',{})[0],403)
        self.assertEqual(self.request('/api/auth/login','POST',{}, {'Origin':'http://example.invalid'})[0],403)
    def test_cookie_and_client_role_cannot_import_rows(self):
        server.AUTH.resolve.side_effect=None;store=OracleReadStore();store._reload=Mock();server.AUTH.resolve.return_value={'store':store,'principal':'ficticio','seen':0}
        for path in ('/api/oracle/import','/api/oracle/details/import','/api/oracle/ticket','/api/oracle/claim'):
            self.assertEqual(self.request(path,'POST',{'role':'editor'},{'Origin':self.base,'Cookie':'hub_session=fake'})[0],403)
    def test_login_cookie_and_logout_expiry(self):
        server.AUTH.login.return_value=('synthetic-token',{'display':'Persona ficticia'})
        code,body,headers=self.request('/api/auth/login','POST',{'username':'ficticio','password':'test-only'},{'Origin':self.base})
        self.assertEqual(code,200);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.assertNotIn('test-only',body.decode());self.assertNotIn('synthetic-token',body.decode())
        code,body,headers=self.request('/api/auth/logout','POST',{}, {'Origin':self.base})
        self.assertIn('Max-Age=0',headers['Set-Cookie'])


class BatchReadTests(unittest.TestCase):
    def setup_batch(self,count=3):
        from types import SimpleNamespace
        a=object.__new__(ScreenAuth);a.lock=RLock();a.sessions={};a.clock=lambda:1000;tasks=[]
        a.pool=SimpleNamespace(submit=lambda fn,*args:tasks.append(lambda:fn(*args)))
        store=OracleReadStore()
        store.ingest({'records':[{'opportunity_number':f'SYNTHETIC-{i}'} for i in range(count)],'scope':'Prueba sintética','partial':True})
        store.request('details_batch');session={'store':store,'created':900,'seen':990};a.sessions['synthetic']=session
        return a,session,store,tasks
    def drain(self,tasks):
        while tasks:tasks.pop(0)()
    def test_retries_skips_failed_record_and_continues(self):
        from unittest.mock import patch
        a,s,store,tasks=self.setup_batch();calls={}
        def rpc(session,body):
            n=body['number'];calls[n]=calls.get(n,0)+1
            if n=='SYNTHETIC-1' or n=='SYNTHETIC-0' and calls[n]==1:raise AuthError('unavailable')
            return {'opportunity_number':n,'schema_version':2,'fields':{'cycle':'2271'}}
        a.session_rpc=Mock(side_effect=rpc)
        with patch('app.auth.sleep'):
            a.execute(s);self.drain(tasks)
        self.assertEqual(calls,{'SYNTHETIC-0':2,'SYNTHETIC-1':3,'SYNTHETIC-2':1})
        self.assertEqual(store.job['state'],'completed');self.assertEqual(store.job['failed'],1)
        self.assertEqual(store.extraction_progress(),{'completed':2,'pending':1,'failed':1,'partial':0})
        self.assertEqual(store.request('details_batch')['total'],1)
        self.assertEqual(store.batch()['pending'],['SYNTHETIC-1'])
    def test_outage_stops_after_three_failed_records(self):
        from unittest.mock import patch
        a,s,store,tasks=self.setup_batch(5);a.session_rpc=Mock(side_effect=AuthError('unavailable'))
        with patch('app.auth.sleep'):
            a.execute(s);self.drain(tasks)
        self.assertEqual(a.session_rpc.call_count,9)
        self.assertEqual(store.job['state'],'failed')
        self.assertEqual(len(store.batch()['pending']),2)
        self.assertEqual(store.request('details_batch')['total'],5)
    def test_expired_session_is_not_retried(self):
        a,s,store,tasks=self.setup_batch();a.session_rpc=Mock(side_effect=AuthError('session'))
        a.execute(s);self.drain(tasks)
        self.assertEqual(a.session_rpc.call_count,1);self.assertEqual(store.job['state'],'failed')
        self.assertEqual(store.job['processed'],0);self.assertFalse(a.sessions)
    def test_cooperative_pause_saves_in_flight_read_and_stops_next(self):
        a,s,store,tasks=self.setup_batch()
        def rpc(session,body):
            store.request_pause()
            return {'opportunity_number':body['number'],'schema_version':2,'fields':{'cycle':'2271'}}
        a.session_rpc=Mock(side_effect=rpc)
        a.execute(s);self.drain(tasks)
        self.assertEqual(a.session_rpc.call_count,1)
        self.assertEqual(store.job['state'],'paused');self.assertEqual(store.job['successful'],1)
        self.assertEqual(store.request('details_batch')['total'],2)
    def test_two_read_lanes_reserve_distinct_records(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier,Lock
        from time import monotonic,sleep
        a,s,store,tasks=self.setup_batch(2);barrier=Barrier(2);lock=Lock();observed=[]
        def rpc(session,body):
            with lock:observed.append((body['number'],body['lane']))
            barrier.wait(timeout=2)
            return {'opportunity_number':body['number'],'schema_version':2,'fields':{'cycle':'2271'}}
        a.session_rpc=Mock(side_effect=rpc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a.pool=pool;a.execute(s);deadline=monotonic()+3
            while store.job['state']=='running' and monotonic()<deadline:sleep(.01)
        self.assertEqual(store.job['state'],'completed')
        self.assertEqual(len({n for n,_ in observed}),2);self.assertEqual({lane for _,lane in observed},{0,1})
        self.assertEqual(store.job['successful'],2);self.assertFalse(store.batch_inflight)
    def test_four_read_lanes_use_distinct_reservations_and_finish_all_records(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier,Lock
        from time import monotonic,sleep
        a,s,store,tasks=self.setup_batch(4);a.read_lanes=4;barrier=Barrier(4);lock=Lock();observed=[]
        def rpc(session,body):
            with lock:observed.append((body['number'],body['lane']))
            barrier.wait(timeout=3)
            return {'opportunity_number':body['number'],'schema_version':2,'fields':{'cycle':'2271'}}
        a.session_rpc=Mock(side_effect=rpc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            a.pool=pool;a.execute(s);deadline=monotonic()+5
            while store.job['state']=='running' and monotonic()<deadline:sleep(.01)
        self.assertEqual(store.job['state'],'completed');self.assertEqual(store.job['successful'],4)
        self.assertEqual(len({n for n,_ in observed}),4);self.assertEqual({lane for _,lane in observed},{0,1,2,3})
        self.assertFalse(store.batch_inflight)

    def test_lane_with_no_unreserved_work_does_not_spin(self):
        a,s,store,tasks=self.setup_batch(1);a.session_rpc=Mock()
        a.execute(s);store.batch_inflight.add('SYNTHETIC-0')
        for _ in range(2):tasks.pop(0)()
        self.assertEqual(tasks,[]);a.session_rpc.assert_not_called()

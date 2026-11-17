import unittest
from datetime import date,datetime,timezone
from app import trace
from app.catalog import configured_edit_fields,validate_change,PROTECTED_EDIT_FIELDS,EDIT_KINDS
from app.persistence import same_value
from app.domain import ValidationError

SNAPSHOT={'loaded_at':'2026-11-16T10:00:00+00:00','job':None,
 'records':[{'opportunity_number':'SYN-1','first_name':'Ana','last_name':'Ficticia','stage':'02 - Inscrito a prueba','owner':'Asesor A','status':'Abierta','close_date':'01/10/26','_last_seen':'2026-11-16T09:00:00+00:00'},
            {'opportunity_number':'SYN-2','name':'Oportunidad ficticia','stage':'05 - Matriculado','owner':'','status':'Ganada','close_date':'2026-12-01','_last_seen':'2026-11-01T09:00:00+00:00'},
            {'opportunity_number':'SYN-3','stage':'04 - Perdida','owner':'Asesor A','status':'Perdida'}],
 'details':{'SYN-1':{'fields':{'test_call':'','cycle':'2271'}},'SYN-2':{'fields':{'resolution':'','test_date':'15/01/27','cycle':'2271'}}},
 'detail_states':{},'read_states':{'SYN-3':{'state':'failed'}}}

class TraceDashboard(unittest.TestCase):
    def test_rows_merge_list_and_detail_fields(self):
        rows={r['number']:r for r in trace.compact_rows(SNAPSHOT)}
        self.assertEqual(rows['SYN-1']['cycle'],'2271');self.assertEqual(rows['SYN-1']['close_month'],'2026-10')
        self.assertEqual(rows['SYN-2']['test_month'],'2027-01');self.assertEqual(rows['SYN-3']['detail_state'],'Lectura con incidencia')
    def test_consistency_checks_find_each_case(self):
        changes=[{'opportunity_number':'SYN-1','state':'uncertain'},{'opportunity_number':'SYN-3','state':'queued'}]
        checks={c['id']:c['numbers'] for c in trace.consistency_checks(trace.compact_rows(SNAPSHOT),changes,today=date(2026,11,16))}
        self.assertEqual(checks['no-owner'],['SYN-2']);self.assertEqual(checks['overdue-open'],['SYN-1'])
        self.assertEqual(checks['test-without-call'],['SYN-1']);self.assertEqual(checks['enrolled-without-resolution'],['SYN-2'])
        self.assertEqual(checks['change-doubtful'],['SYN-1']);self.assertEqual(checks['change-pending'],['SYN-3'])
        self.assertEqual(checks['detail-missing'],['SYN-3'])
    def test_dashboard_funnel_follows_stage_order(self):
        d=trace.dashboard(SNAPSHOT,[{'opportunity_number':'SYN-2','state':'confirmed'}])
        self.assertEqual([f['label'][:2] for f in d['funnel']],['02','04','05'])
        self.assertEqual(d['kpis']['changes_confirmed'],1);self.assertEqual(d['kpis']['owners'],1)
        self.assertEqual(sum(b['count'] for b in d['freshness']),3)
    def test_version_diff_reports_only_changed_fields(self):
        t=trace.diff_versions([{'source_version':1,'observed_at':'a','payload':{'stage':'01','owner':'A'}},
                               {'source_version':2,'observed_at':'b','payload':{'stage':'01','owner':'A'}},
                               {'source_version':3,'observed_at':'c','payload':{'stage':'02','owner':'A'}}])
        self.assertEqual([e['kind'] for e in t],['first_seen','oracle_change'])
        self.assertEqual(t[1]['changes'],[{'field':'stage','before':'01','after':'02'}])

class EditPolicy(unittest.TestCase):
    def test_default_policy_covers_the_whole_process_except_integration_ids(self):
        fields=configured_edit_fields('')
        self.assertFalse(fields&PROTECTED_EDIT_FIELDS)
        for field in ('test_call','amount','resolution','owner','career','contact_email','homeschool'):self.assertIn(field,fields)
        self.assertFalse(configured_edit_fields('safe')&{'resolution','paa_score'})
        self.assertEqual(configured_edit_fields('all'),set(EDIT_KINDS))
        self.assertEqual(configured_edit_fields('name,stage'),{'name','stage'})
        with self.assertRaises(ValueError):configured_edit_fields('payment')
    def test_values_are_validated_by_kind(self):
        self.assertEqual(validate_change('test_call','  Enero 2027 '),'Enero 2027')
        self.assertEqual(validate_change('test_date',''),'')
        self.assertEqual(validate_change('homeschool','Sí'),'Sí')
        for field,value in [('contact_email','no-es-correo'),('homeschool','quizá'),('contact_last_name',' '),('test_date','15/01/27'),('amount','abc'),('financial_requested_1','150'),('name','  '),('amount','inf')]:
            with self.subTest(field=field),self.assertRaises(ValidationError):validate_change(field,value)
    def test_amounts_and_empty_values_compare_by_kind(self):
        self.assertTrue(same_value('amount','Q1,250.00','1250'));self.assertTrue(same_value('test_date','15/01/27','2027-01-15'))
        self.assertFalse(same_value('test_call','','Enero'));self.assertTrue(same_value('test_call',None,''))

if __name__=='__main__':unittest.main()

class LastCopyView(unittest.TestCase):
    def test_unconfirmed_rows_wait_for_the_inventory(self):
        from app.oracle_read import OracleReadStore
        store=OracleReadStore()
        store.records=[{'opportunity_number':'SYN-OLD','_unconfirmed':True},{'opportunity_number':'SYN-NEW'}]
        self.assertTrue(store.pending_details());self.assertEqual(store.unconfirmed(),1)
        job=store.request('details_batch');self.assertEqual(job['total'],1);self.assertEqual(store.batch_numbers,['SYN-NEW'])
        store.job=None;store.records=[{'opportunity_number':'SYN-OLD','_unconfirmed':True}]
        self.assertFalse(store.pending_details())
        store.settings['enabled']=True;store.worker_seen=__import__('time').monotonic()
        self.assertEqual(store.scheduler_tick()['kind'],'opportunities')

class ResumeAfterTransientFailure(unittest.TestCase):
    def test_interrupted_first_load_resumes_and_keeps_its_session(self):
        from app.oracle_read import OracleReadStore
        from app.auth import ScreenAuth
        store=OracleReadStore();store.listing_coverage={'complete':True}
        store.records=[{'opportunity_number':'SYN-1'},{'opportunity_number':'SYN-2'}]
        store.request('details_batch');store.claim();store.fail('timeout')
        self.assertTrue(store.resume_pending());self.assertIsNone(store.resume())  # waits its back-off
        store.retry_after=0;self.assertEqual(store.resume()['kind'],'details_batch')
        store.job=None;store.request('details_batch');store.claim();store.fail('session')
        self.assertFalse(store.resume_pending())  # a lost Oracle session needs the user
        store.job['failure_code']='timeout';store.read_outcomes={n:{'state':'failed'} for n in ('SYN-1','SYN-2')}
        self.assertFalse(store.resume_pending())  # only failed reads left: review, not loop
        auth=ScreenAuth.__new__(ScreenAuth);auth.clock=lambda:1000
        store.read_outcomes={};session={'store':store,'created':0}
        self.assertTrue(auth.sync_active(session))
        from app.auth import SYNC_MAX_SECONDS,MAX_AGE_SECONDS
        self.assertEqual(auth.deadline(session),SYNC_MAX_SECONDS);self.assertGreater(SYNC_MAX_SECONDS,MAX_AGE_SECONDS)
        auth.clock=lambda:SYNC_MAX_SECONDS+1;self.assertFalse(auth.sync_active(session))

class IncrementalRefresh(unittest.TestCase):
    def repo(self):
        from unittest.mock import Mock
        state={'records':[{'opportunity_number':'SYN-1','name':'A','_version':1},{'opportunity_number':'SYN-2','name':'B','_version':1}],
               'loaded_at':'x','scope':'s','details':{'SYN-1':{'loaded_at':'t1','fields':{'cycle':'2271'},'capabilities':{}}},'detail_states':{}}
        repo=Mock();repo.load.side_effect=lambda:__import__('copy').deepcopy(state);repo.fingerprint.return_value=('a',)
        repo.read_progress.return_value={};repo.settings.return_value={};repo.principal='synthetic-user'
        return repo,state
    def test_requests_reload_only_when_the_database_changed(self):
        from app.oracle_read import OracleReadStore
        repo,state=self.repo();store=OracleReadStore(repo);loads=repo.load.call_count
        store.refresh_if_changed();self.assertEqual(repo.load.call_count,loads)
        repo.fingerprint.return_value=('b',);store.refresh_if_changed();self.assertEqual(repo.load.call_count,loads+1)
    def test_delta_sends_only_changed_records_and_detects_removals(self):
        from app.oracle_read import OracleReadStore
        repo,state=self.repo();store=OracleReadStore(repo)
        full=store.delta(None);self.assertFalse(full['delta']);self.assertEqual(len(full['records']),2)
        rev,epoch=full['revision'],full['epoch']
        same=store.delta(rev,epoch);self.assertTrue(same['delta']);self.assertEqual(same['records'],[]);self.assertNotIn('numbers',same)
        state['records'][1]['name']='B2';state['details']['SYN-1']['loaded_at']='t2';store._reload()
        changed=store.delta(rev,epoch)
        self.assertEqual([r['opportunity_number'] for r in changed['records']],['SYN-2']);self.assertEqual(list(changed['details']),['SYN-1'])
        state['records'].pop(0);store._reload()
        removed=store.delta(changed['revision'],epoch);self.assertEqual(removed['numbers'],['SYN-2'])
        self.assertFalse(store.delta(rev,'other-epoch')['delta'])

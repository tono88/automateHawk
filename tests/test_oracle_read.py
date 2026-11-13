import unittest
from app.oracle_read import OracleReadStore
from app.domain import ValidationError
from app import server
import test_lab

def payload(number='SYNTHETIC-001'):
    return {'records':[{'opportunity_number':number,'first_name':'Persona sintética','stage':'01 - Interesado'}],
            'scope':'Consulta de prueba sintética','partial':True}

class ReadModelTests(unittest.TestCase):
    def setUp(self): self.s=OracleReadStore()
    def test_isolation_and_metadata(self):
        s=self.s.ingest(payload())
        self.assertEqual(s['count'],1);self.assertTrue(s['read_only']);self.assertTrue(s['partial'])
        self.assertEqual(s['storage'],'memory')
        self.assertIsNotNone(s['loaded_at'])
        self.assertNotIn('records',s)
    def test_atomic_validation_preserves_previous(self):
        self.s.ingest(payload())
        bad=payload('SYNTHETIC-002');bad['records'].append({'opportunity_number':''})
        with self.assertRaises(ValidationError): self.s.ingest(bad)
        self.assertEqual(self.s.snapshot()['records'][0]['opportunity_number'],'SYNTHETIC-001')
    def test_empty_duplicate_unknown_and_false_complete_rejected(self):
        for bad in [dict(payload(),records=[]),dict(payload(),records=payload()['records']*2),
                    dict(payload(),partial=False),dict(payload(),records=[{'opportunity_number':'SYNTHETIC','password':'forbidden'}])]:
            with self.subTest(bad=bad),self.assertRaises(ValidationError):self.s.ingest(bad)
    def test_ticket_is_single_use(self):
        token=self.s.ticket();self.s.authorize(token)
        with self.assertRaises(PermissionError):self.s.authorize(token)
    def test_failure_preserves_last_data(self):
        self.s.ingest(payload());self.s.request();self.s.fail('layout')
        self.assertEqual(self.s.status()['count'],1)
        self.assertEqual(self.s.status()['job']['state'],'failed')
    def test_deduplicated_queue_and_worker(self):
        a=self.s.request();b=self.s.request();self.assertEqual(a['id'],b['id'])
        self.assertEqual(self.s.claim()['state'],'running');self.assertIsNone(self.s.claim())
        self.assertFalse(self.s.status()['worker_online']);self.s.heartbeat();self.assertTrue(self.s.status()['worker_online'])
    def test_verified_details_and_activity_contract(self):
        self.s.ingest(payload())
        data={'opportunity_number':'SYNTHETIC-001','fields':{'cycle':'2271','resolution':'Pendiente'},'capabilities':{'resolution':False},'activities':{'queried':True,'rows':[]}}
        self.s.ingest_detail(data)
        self.assertEqual(self.s.snapshot()['details']['SYNTHETIC-001']['fields']['cycle'],'2271')
        self.assertFalse(self.s.snapshot()['details']['SYNTHETIC-001']['capabilities']['resolution'])
        data['fields']={'unmapped_secret':'not allowed'}
        with self.assertRaises(ValidationError):self.s.ingest_detail(data)
    def test_batch_progress_is_idempotent_and_retries_only_missing(self):
        body=payload();body['records'] += [{'opportunity_number':'SYNTHETIC-002'}]
        self.s.ingest(body)
        self.assertEqual(self.s.request('details_batch')['total'],2)
        self.s.claim()
        detail={'opportunity_number':'SYNTHETIC-001','schema_version':2,'fields':{'cycle':''}}
        self.s.ingest_detail(detail);self.s.ingest_detail(detail)
        self.assertEqual(self.s.status()['job']['processed'],1)
        self.assertEqual(self.s.batch()['pending'],['SYNTHETIC-002'])
        self.s.fail('timeout')
        self.assertEqual(self.s.request('details_batch')['total'],1)
        self.s.claim();self.s.ingest_detail(dict(detail,opportunity_number='SYNTHETIC-002'))
        self.assertEqual(self.s.status()['job']['state'],'completed')
        self.assertEqual(self.s.request('details_batch')['total'],0)
        self.assertEqual(self.s.batch()['pending'],[])

    def test_expanded_profile_schema_and_upgrade(self):
        self.s.ingest(payload())
        data={'opportunity_number':'SYNTHETIC-001','fields':{'cycle':'2271'}}
        self.s.ingest_detail(data)
        self.assertEqual(self.s.request('details_batch')['total'],1)
        self.s.claim()
        data.update(schema_version=2,fields={'campus_id':'SYNTHETIC-CAMPUS','faculty':'Facultad ficticia'})
        self.s.ingest_detail(data)
        self.assertEqual(self.s.snapshot()['details']['SYNTHETIC-001']['schema_version'],2)
        self.assertEqual(self.s.request('details_batch')['total'],0)
        for version in (True,3,'2'):
            with self.assertRaises(ValidationError):self.s.ingest_detail(dict(data,schema_version=version))

    def test_reader_cannot_propose_or_change_schedule(self):
        with self.assertRaises(PermissionError):self.s.propose({})
        with self.assertRaises(PermissionError):self.s.save_settings({'enabled':True,'interval_minutes':15})
    def test_detail_job_is_scoped_to_known_record(self):
        self.s.ingest(payload());job=self.s.request('detail','SYNTHETIC-001')
        self.assertEqual(job['kind'],'detail')
        self.assertEqual(job['opportunity_number'],'SYNTHETIC-001')
        self.s.fail('timeout')
        with self.assertRaises(KeyError):self.s.request('detail','UNKNOWN-SYNTHETIC')
    def test_scheduler_respects_connection_frequency_and_single_job(self):
        from datetime import datetime,timedelta,timezone
        self.s.settings['enabled']=True
        self.s.loaded_at=(datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
        self.assertIsNone(self.s.scheduler_tick())
        self.s.heartbeat();job=self.s.scheduler_tick();self.assertEqual(job['state'],'pending')
        self.assertIsNone(self.s.scheduler_tick())

class ReadHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): test_lab.HttpTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): test_lab.HttpTests.tearDownClass.__func__(cls)
    request=test_lab.HttpTests.request
    def setUp(self): server.ORACLE=OracleReadStore()
    def test_protected_import_read_only_and_separate(self):
        data=payload()
        self.assertEqual(self.request('/api/oracle/import','POST',data)[0],403)
        status,b,_=self.request('/api/oracle/ticket','POST',{})
        import json
        token=json.loads(b)['ticket']
        self.assertEqual(self.request('/api/oracle/import','POST',data,{'X-Sync-Ticket':token})[0],200)
        self.assertEqual(self.request('/api/oracle/import','POST',data,{'X-Sync-Ticket':token})[0],403)
        status,b,_=self.request('/api/oracle/snapshot');self.assertEqual(json.loads(b)['count'],1)
        status,b,_=self.request('/api/snapshot');self.assertEqual(len(json.loads(b)['tables']['contacts']),60)
        self.assertEqual(self.request('/api/oracle/import','PATCH',data)[0],405)

if __name__=='__main__':unittest.main()

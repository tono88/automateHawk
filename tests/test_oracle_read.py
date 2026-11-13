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

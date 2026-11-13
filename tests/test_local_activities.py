import unittest
from uuid import uuid4
from app.local_activities import validate
from app.domain import ValidationError
from app import server
from app.oracle_read import OracleReadStore
import test_lab

class ActivityValidationTests(unittest.TestCase):
    def item(self,kind='tasks'):
        data={'subject':'Seguimiento ficticio','owner':'Asesor ficticio','local_status':'Pendiente'}
        if kind!='tasks':data.update(start_date='2026-11-15',start_time='09:00',end_date='2026-11-15',end_time='10:00',timezone='America/Guatemala')
        return dict(id=str(uuid4()),opportunity_number='SYNTHETIC-001',kind=kind,data=data)
    def test_three_forms_and_no_oracle_write_state(self):
        for kind in ('tasks','appointments','interactions'):
            clean=validate(self.item(kind));self.assertEqual(clean['kind'],kind)
            self.assertNotIn('sync_state',clean['data'])
    def test_invalid_dates_ranges_and_fields(self):
        for patch in ({'end_time':'08:00'},{'start_date':'2026-02-30'},{'timezone':'invalid'},{'unexpected':'x'}):
            item=self.item('appointments');item['data'].update(patch)
            with self.subTest(patch=patch),self.assertRaises(ValidationError):validate(item)
    def test_required_subject_and_interaction_date(self):
        for patch in ({'subject':''},{'owner':''},{'response_1':'No responde'}):
            item=self.item();item['data'].update(patch)
            with self.subTest(patch=patch),self.assertRaises(ValidationError):validate(item)
    def test_identifiers_and_version(self):
        for patch in ({'id':'invalid'},{'opportunity_number':''},{'version':True},{'kind':'contacts'}):
            with self.subTest(patch=patch),self.assertRaises(ValidationError):validate(dict(self.item(),**patch))

class ActivityHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):test_lab.HttpTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):test_lab.HttpTests.tearDownClass.__func__(cls)
    request=test_lab.HttpTests.request
    def setUp(self):server.ORACLE=OracleReadStore()
    def test_reader_cannot_create_even_with_supplied_role(self):
        self.assertEqual(self.request('/api/oracle/activities','POST',{'role':'editor'})[0],403)
    def test_forms_available_without_demo_records(self):
        import json
        code,body,_=self.request('/api/oracle/activities');data=json.loads(body)
        self.assertEqual(code,200);self.assertEqual(data['activities'],[])
        self.assertEqual(set(data['schemas']),{'tasks','appointments','interactions'})

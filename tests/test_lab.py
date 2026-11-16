import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from app.domain import DemoStore,SCHEMAS,STAGES,ValidationError,ConflictError
from app import server

def fields(row): return {k:v for k,v in row.items() if k not in ('id','version')}

class DomainTests(unittest.TestCase):
    def setUp(self): self.s=DemoStore()
    def test_synthetic_only_and_stages(self):
        snap=self.s.snapshot()
        self.assertEqual(len(snap['tables']['contacts']),60)
        self.assertEqual({r['stage'] for r in snap['tables']['opportunities']},set(STAGES))
        self.assertTrue(all(r['email'].endswith('@example.invalid') for r in snap['tables']['contacts']))
        self.assertNotIn('password',str(SCHEMAS).lower())
    def test_every_entity_create_edit_delete(self):
        for entity,schema in SCHEMAS.items():
            with self.subTest(entity=entity):
                data={}
                for f in schema['fields']:
                    if f['required']:
                        data[f['key']]=f['options'][0] if f['options'] else ('2026-11-13' if f['kind']=='date' else '10:00' if f['kind']=='time' else 'Prueba sintética')
                if entity in ['appointments','interactions']: data['end_time']='11:00'
                row=self.s.save(entity,data)
                row=self.s.save(entity,fields(row),row['id'],row['version'])
                self.assertEqual(row['version'],2)
                self.s.delete(entity,row['id'],row['version'])
                self.assertNotIn(row['id'],self.s.tables[entity])
    def test_conflict_does_not_overwrite(self):
        row=self.s.tables['opportunities']['DEMO-O-001']
        data=fields(row);data['stage']=STAGES[1]
        updated=self.s.save('opportunities',data,row['id'],1)
        with self.assertRaises(ConflictError): self.s.save('opportunities',data,row['id'],1)
        self.assertEqual(updated,self.s.tables['opportunities'][row['id']])
    def test_invalid_relationship_stage_dates_and_fields(self):
        row=fields(self.s.tables['opportunities']['DEMO-O-001'])
        for change in [{'contact_id':'nonexistent'},{'stage':'inventada'},{'probability':'nan'},{'close_date':'31/99/00'},{'secret':'x'}]:
            with self.subTest(change=change),self.assertRaises(ValidationError): self.s.save('opportunities',dict(row,**change))
    def test_real_email_and_duplicates_blocked(self):
        row=fields(self.s.tables['contacts']['DEMO-C-001'])
        with self.assertRaises(ConflictError): self.s.save('contacts',row)
        row['email']='persona@example.com'
        with self.assertRaises(ValidationError): self.s.save('contacts',row)
    def test_referenced_contact_cannot_be_deleted(self):
        with self.assertRaises(ConflictError): self.s.delete('contacts','DEMO-C-001',1)
    def test_snapshot_is_independent(self):
        x=self.s.snapshot();x['tables']['contacts'][0]['first_name']='Changed'
        self.assertNotEqual(x['tables']['contacts'][0],self.s.tables['contacts']['DEMO-C-001'])
    def test_time_sequence(self):
        with self.assertRaises(ValidationError): self.s.save('appointments',dict(subject='Prueba',start_date='2026-11-13',end_date='2026-11-13',start_time='11:00',end_time='10:00'))

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls): cls.http.shutdown();cls.http.server_close();cls.thread.join()
    def request(self,path,method='GET',body=None,headers=None):
        h={'Content-Type':'application/json'};h.update(headers or {})
        req=Request(self.base+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers=h)
        try:
            with urlopen(req) as r: return r.status,r.read(),r.headers
        except HTTPError as r: return r.code,r.read(),r.headers
    def test_health_and_assets(self):
        for path in ['/','/app.js','/style.css','/trace.js','/api/snapshot','/health','/api/oracle/trace','/api/oracle/catalog']:
            status,body,headers=self.request(path)
            self.assertEqual(status,200);self.assertTrue(body)
            self.assertEqual(headers['Cache-Control'],'no-store')
    def test_http_crud_and_stale_version(self):
        status,b,_=self.request('/api/tasks','POST',{'data':{'subject':'Prueba HTTP','owner':'Asesor Demo A'}})
        self.assertEqual(status,201);r=json.loads(b)
        data=fields(r);data['subject']='Actualizada'
        status,b,_=self.request('/api/tasks/'+r['id'],'PATCH',{'data':data,'version':1});self.assertEqual(status,200)
        status,_,_=self.request('/api/tasks/'+r['id'],'PATCH',{'data':data,'version':1});self.assertEqual(status,409)
        status,_,_=self.request('/api/tasks/'+r['id'],'DELETE',{'version':2});self.assertEqual(status,200)
    def test_origin_host_and_path_rejected(self):
        self.assertEqual(self.request('/api/tasks','POST',{'data':{}},{'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request('/health',headers={'Host':'evil.invalid'})[0],403)
        self.assertEqual(self.request('/../domain.py')[0],404)
        self.assertEqual(self.request('/api/oracle','POST',{'data':{}})[0],404)
    def test_trace_dashboard_and_catalog_shape(self):
        d=json.loads(self.request('/api/oracle/trace')[1])
        self.assertTrue({'kpis','funnel','checks','rows','dimensions'}<=set(d))
        catalog=json.loads(self.request('/api/oracle/catalog')[1])
        self.assertEqual(set(catalog['edit_kinds']),set(catalog['edit_fields']))
        self.assertEqual(self.request('/api/oracle/trace/opportunity?number=NONE')[0],404)
    def test_invalid_payload(self):
        self.assertEqual(self.request('/api/tasks','POST',[])[0],400)
        self.assertEqual(self.request('/api/tasks','POST',{'data':{}})[0],400)

if __name__=='__main__': unittest.main()

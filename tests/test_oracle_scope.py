import unittest
from datetime import date,timedelta
from app.oracle_scope import month_queries,inventory,PARTITION_LIMIT
from app.domain import ValidationError

def row(query,index=0):
    return {'opportunity_number':f"SYNTHETIC-{query['from']}-{query['states'][0]}-{index}",
            'close_date':query['from'],'status':query['states'][0]}
def result(query,count=1):
    return {'records':[row(query,i) for i in range(count)],'partial':True,'scope':'Sintético'}

class ScopeTests(unittest.TestCase):
    def test_calendar_has_no_gaps_or_overlap_and_is_fixed_to_authorized_year(self):
        queries=month_queries();self.assertEqual(len(queries),12)
        self.assertEqual(queries[0]['from'],'2026-01-01');self.assertEqual(queries[-1]['to'],'2026-12-31')
        for left,right in zip(queries,queries[1:]):
            self.assertEqual(date.fromisoformat(left['to'])+timedelta(days=1),date.fromisoformat(right['from']))
        with self.assertRaises(ValidationError):month_queries(2025)
    def test_complete_inventory_contains_all_months_and_only_aggregate_coverage(self):
        ingested=[];observed=[]
        coverage=inventory(lambda q:result(q),ingested.append,observed.append)
        self.assertTrue(coverage['complete']);self.assertEqual(coverage['row_count'],12)
        self.assertEqual(coverage['partitions_pending'],0);self.assertEqual(len(ingested),12)
        self.assertNotIn('opportunity_number',str(coverage))
        self.assertEqual(coverage['states'],['Abierta','Inscrito','Perdida'])
    def test_saturated_month_is_split_and_parent_rows_are_not_imported(self):
        ingested=[]
        def fetch(q):
            days=(date.fromisoformat(q['to'])-date.fromisoformat(q['from'])).days
            return result(q,PARTITION_LIMIT if q['from'].startswith('2026-01') and days else 1)
        coverage=inventory(fetch,ingested.append,lambda c:None)
        self.assertTrue(coverage['complete']);self.assertEqual(coverage['row_count'],42)
        self.assertTrue(all(len(p['records'])==1 for p in ingested))
    def test_unverifiable_empty_outside_year_and_wrong_status_are_rejected_before_import(self):
        for mode in ('empty','date','status'):
            ingested=[]
            def fetch(q):
                payload=result(q)
                if mode=='empty':payload['records']=[]
                elif mode=='date':payload['records'][0]['close_date']='2025-12-31'
                else:payload['records'][0]['status']='Unknown'
                return payload
            with self.subTest(mode=mode),self.assertRaises(ValidationError):inventory(fetch,ingested.append,lambda c:None)
            self.assertEqual(ingested,[])
    def test_verified_empty_partitions_are_recorded(self):
        coverage=inventory(lambda q:{'records':[],'empty_verified':True},lambda p:self.fail('Empty import'),lambda c:None)
        self.assertTrue(coverage['complete']);self.assertEqual(coverage['row_count'],0)
        self.assertEqual(coverage['partitions_finished'],12)
    def test_single_day_state_limit_is_reported_and_does_not_loop_forever(self):
        def fetch(q):
            if q['from']=='2026-01-01':return result(q,PARTITION_LIMIT)
            return {'records':[],'empty_verified':True}
        coverage=inventory(fetch,lambda p:None,lambda c:None)
        self.assertFalse(coverage['complete']);self.assertEqual(len(coverage['unresolved']),3)

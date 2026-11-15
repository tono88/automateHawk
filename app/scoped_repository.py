"""One global mirror with persistent, expiring per-user permissions."""
from datetime import datetime,timezone
from psycopg.types.json import Jsonb
from .persistence import PostgresRepository
from .domain import ConflictError

class ScopedRepository(PostgresRepository):
    def __init__(self,dsn,principal):
        self.principal=principal;self.observed_fields={}
        super().__init__(dsn)
    def grants(self):
        with self.connect() as c:
            rows=c.execute('SELECT * FROM user_permissions WHERE principal=%s AND read_until>now()',(self.principal,)).fetchall()
        return {r['opportunity_number']:r for r in rows}
    def require(self,number,field=None):
        grant=self.grant(number)
        if not grant:raise PermissionError()
        if field and (not grant['detail_until'] or grant['detail_until']<datetime.now(timezone.utc) or not grant['capabilities'].get(field)):raise PermissionError()
        return grant
    def grant(self,number):
        with self.connect() as c:
            return c.execute('SELECT * FROM user_permissions WHERE principal=%s AND opportunity_number=%s AND read_until>now()',
                             (self.principal,number)).fetchone()
    def save_snapshot(self,rows,scope):
        # Preserve globally known fields not exposed by this user's list.
        original={r['opportunity_number']:r for r in super().load()['records']};merged=[]
        for row in rows:
            number=row['opportunity_number'];allowed=self.observed_fields.get(number,list(row))
            previous={k:v for k,v in original.get(number,{}).items() if not k.startswith('_')}
            previous.update({k:v for k,v in row.items() if k in allowed});merged.append(previous)
        result=super().save_snapshot(merged,scope)
        with self.connect() as c:
            for row in rows:
                number=row['opportunity_number'];fields=self.observed_fields.get(number,list(row))
                c.execute("""INSERT INTO user_permissions(principal,opportunity_number,basic_fields,read_until)
                  VALUES(%s,%s,%s,now()+interval '1 hour') ON CONFLICT(principal,opportunity_number)
                  DO UPDATE SET basic_fields=excluded.basic_fields,read_until=excluded.read_until,checked_at=now()""",(self.principal,number,Jsonb(fields)))
        self.observed_fields={};return result
    def reconcile_visible_inventory(self,numbers):
        """Expire this principal's missing grants; retain shared data and history."""
        with self.connect() as c:
            c.execute("""UPDATE user_permissions SET read_until=now(),detail_until=now(),
              detail_fields='[]'::jsonb,capabilities='{}'::jsonb,activities_visible=false
              WHERE principal=%s AND NOT(opportunity_number=ANY(%s::text[]))""",
              (self.principal,list(numbers)))
    def load(self):
        result=super().load();grants=self.grants();now=datetime.now(timezone.utc)
        result['records']=[{k:v for k,v in r.items() if k in grants[r['opportunity_number']]['basic_fields'] or k.startswith('_') or k=='opportunity_number'} for r in result['records'] if r['opportunity_number'] in grants]
        result['detail_states']={r['opportunity_number']:('not_loaded' if r['opportunity_number'] not in result['details'] else 'permission_required' if not grants[r['opportunity_number']]['detail_until'] else 'permission_expired' if grants[r['opportunity_number']]['detail_until']<now else 'available') for r in result['records']}
        details={}
        for number,d in result['details'].items():
            g=grants.get(number)
            if not g or not g['detail_until'] or g['detail_until']<now:continue
            details[number]=dict(d,fields={k:v for k,v in d['fields'].items() if k in g['detail_fields']},capabilities=g['capabilities'],activities=d.get('activities') if g['activities_visible'] else {'queried':False,'rows':[]},loaded_at=min(d['loaded_at'],g['checked_at'].isoformat()))
        result['details']=details
        if not grants:result.update(loaded_at=None,scope='Verificación de permisos pendiente con tu sesión de Oracle')
        return result
    def save_detail(self,number,detail):
        self.require(number)
        with self.connect() as c:
            row=c.execute('SELECT payload FROM record_details WHERE opportunity_number=%s',(number,)).fetchone()
        old=row['payload'] if row else {}
        merged=dict(detail,fields=dict(old.get('fields',{}),**detail['fields']))
        super().save_detail(number,merged)
        with self.connect() as c:
            c.execute("""UPDATE user_permissions SET detail_fields=%s,capabilities=%s,activities_visible=%s,
              detail_until=now()+interval '30 minutes',checked_at=now() WHERE principal=%s AND opportunity_number=%s""",(Jsonb(list(detail['fields'])),Jsonb(detail['capabilities']),detail['activities']['queried'],self.principal,number))
    def changes(self,number=None):
        if number:self.require(number)
        rows=super().changes(number)
        if not rows:return []
        grants=self.grants()
        return [r for r in rows if r['opportunity_number'] in grants and r['field'] in (grants[r['opportunity_number']]['basic_fields']+grants[r['opportunity_number']]['detail_fields']) and r['actor']==self.principal]
    def propose(self,number,field,*args):
        self.require(number,field);return super().propose(number,field,*args)
    def cancel(self,identifier,actor):
        if not any(r['id']==identifier for r in self.changes()):raise PermissionError()
        return super().cancel(identifier,actor)
    def local_activities(self):
        items=super().local_activities()
        if not items:return []
        grants=self.grants()
        rows=[r for r in items if r['opportunity_number'] in grants and (r['actor']==self.principal or (grants[r['opportunity_number']]['activities_visible'] and grants[r['opportunity_number']]['detail_until'] and grants[r['opportunity_number']]['detail_until']>datetime.now(timezone.utc)))]
        for r in rows:r['can_edit']=r.pop('actor')==self.principal
        return rows
    def save_local_activity(self,item,actor):
        self.require(item['opportunity_number'])
        with self.connect() as c:
            existing=c.execute('SELECT actor FROM local_activities WHERE id=%s',(item['id'],)).fetchone()
        if existing and existing['actor']!=self.principal:raise PermissionError()
        return super().save_local_activity(item,actor)
    def summary(self):
        with self.connect() as c:
            count=c.execute('SELECT count(*) AS n FROM user_permissions WHERE principal=%s AND read_until>now()', (self.principal,)).fetchone()['n']
        return dict(engine='postgresql',persistent=True,records=count,historical_versions=None,sync_runs=None,global_mirror=True)

    def read_progress(self):
        with self.connect() as c:
            rows=c.execute('''SELECT r.opportunity_number,r.state,r.attempts,r.error_code,r.schema_version
              FROM detail_read_progress r JOIN user_permissions p
              ON p.principal=r.principal AND p.opportunity_number=r.opportunity_number
              WHERE r.principal=%s AND p.read_until>now()''',(self.principal,)).fetchall()
        return {r['opportunity_number']:{k:v for k,v in r.items() if k!='opportunity_number'} for r in rows}
    def save_read_progress(self,number,state,attempts=0,error_code=''):
        self.require(number)
        if state not in ('reading','completed','partial','failed') or error_code not in ('','timeout','layout','permission','unavailable','contact-unavailable'):raise ValueError('Invalid read outcome')
        with self.connect() as c:
            c.execute("""INSERT INTO detail_read_progress(principal,opportunity_number,state,attempts,error_code)
              VALUES(%s,%s,%s,%s,%s) ON CONFLICT(principal,opportunity_number) DO UPDATE
              SET state=excluded.state,attempts=detail_read_progress.attempts+excluded.attempts,
                  error_code=excluded.error_code,schema_version=2,updated_at=now()""",(self.principal,number,state,attempts,error_code))

"""One global mirror with persistent, expiring per-user permissions."""
import os
from datetime import datetime,timezone
from psycopg.types.json import Jsonb
from .persistence import PostgresRepository
from .domain import ConflictError

def read_grant_minutes(key,default):
    value=int(os.environ.get(key,str(default)))
    if not 15<=value<=480:raise ValueError('Read permission lifetime must be between 15 and 480 minutes')
    return value

class ScopedRepository(PostgresRepository):
    def __init__(self,dsn,principal):
        self.principal=principal;self.observed_fields={}
        self.basic_minutes=read_grant_minutes('HUB_LIST_GRANT_MINUTES',60)
        self.detail_minutes=read_grant_minutes('HUB_DETAIL_GRANT_MINUTES',30)
        super().__init__(dsn)
    def grants(self):
        with self.connect() as c:
            rows=c.execute('SELECT * FROM user_permissions WHERE principal=%s AND read_until>now()',(self.principal,)).fetchall()
        return {r['opportunity_number']:r for r in rows}
    def require(self,number,field=None):
        grant=self.grant(number)
        if not grant:raise PermissionError()
        now=datetime.now(timezone.utc)
        if field and (not grant['detail_until'] or grant['detail_until']<now or not grant['edit_until'] or grant['edit_until']<now or not grant['capabilities'].get(field)):raise PermissionError()
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
                  VALUES(%s,%s,%s,now()+make_interval(mins => %s)) ON CONFLICT(principal,opportunity_number)
                  DO UPDATE SET basic_fields=excluded.basic_fields,read_until=excluded.read_until,checked_at=now()""",(self.principal,number,Jsonb(fields),self.basic_minutes))
        self.observed_fields={};return result
    def reconcile_visible_inventory(self,numbers):
        """Expire this principal's missing grants; retain shared data and history."""
        with self.connect() as c:
            c.execute("""UPDATE user_permissions SET read_until=now(),detail_until=now(),edit_until=now(),
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
            edit_valid=bool(g['edit_until'] and g['edit_until']>now)
            details[number]=dict(d,fields={k:v for k,v in d['fields'].items() if k in g['detail_fields']},capabilities={k:bool(v and edit_valid) for k,v in g['capabilities'].items()},activities=d.get('activities') if g['activities_visible'] else {'queried':False,'rows':[]},loaded_at=min(d['loaded_at'],g['detail_checked_at'].isoformat()))
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
              detail_until=now()+make_interval(mins => %s),edit_until=now()+interval '30 minutes',
              detail_checked_at=now(),checked_at=now() WHERE principal=%s AND opportunity_number=%s""",(Jsonb(list(detail['fields'])),Jsonb(detail['capabilities']),detail['activities']['queried'],self.detail_minutes,self.principal,number))
    def changes(self,number=None):
        if number:self.require(number)
        rows=super().changes(number)
        if not rows:return []
        grants=self.grants();now=datetime.now(timezone.utc)
        def visible(row):
            g=grants.get(row['opportunity_number'])
            return bool(g and row['field'] in (g['basic_fields']+(g['detail_fields'] if g['detail_until'] and g['detail_until']>now else [])))
        return [r for r in rows if visible(r) and r['actor']==self.principal]
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
            rows=c.execute('''SELECT r.opportunity_number,r.state,r.attempts,r.error_code,r.schema_version,r.source_version,
              (r.state='completed' AND (
                r.updated_at<now()-interval '24 hours'
                OR (r.source_version IS NOT NULL AND r.source_version<>o.version)
                OR (r.source_version IS NULL AND EXISTS(
                  SELECT 1 FROM opportunity_history h WHERE h.opportunity_number=o.opportunity_number
                  AND h.source_version=o.version AND h.observed_at>r.updated_at)))) AS needs_refresh
              FROM detail_read_progress r JOIN user_permissions p
              ON p.principal=r.principal AND p.opportunity_number=r.opportunity_number
              JOIN opportunities o ON o.opportunity_number=r.opportunity_number
              WHERE r.principal=%s AND p.read_until>now()''',(self.principal,)).fetchall()
        return {r['opportunity_number']:{k:v for k,v in r.items() if k!='opportunity_number'} for r in rows}
    def save_read_progress(self,number,state,attempts=0,error_code='',source_version=None):
        self.require(number)
        if state not in ('reading','completed','partial','failed') or error_code not in ('','timeout','layout','permission','unavailable','contact-unavailable'):raise ValueError('Invalid read outcome')
        if source_version is not None and (type(source_version)!=int or source_version<1):raise ValueError('Invalid source version')
        with self.connect() as c:
            if state=='reading' and source_version is None:
                source_version=c.execute('SELECT version FROM opportunities WHERE opportunity_number=%s',(number,)).fetchone()['version']
            c.execute("""INSERT INTO detail_read_progress(principal,opportunity_number,state,attempts,error_code,source_version)
              VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(principal,opportunity_number) DO UPDATE
              SET state=excluded.state,attempts=detail_read_progress.attempts+excluded.attempts,
                  error_code=excluded.error_code,schema_version=2,updated_at=now(),
                  source_version=coalesce(excluded.source_version,detail_read_progress.source_version)""",(self.principal,number,state,attempts,error_code,source_version))

"""PostgreSQL source mirror and operational queue. No credentials in source."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from decimal import Decimal,InvalidOperation
from .domain import ValidationError, ConflictError

def database_dsn():
    path=os.environ.get('HUB_DATABASE_DSN_FILE')
    return Path(path).read_text(encoding='utf-8').strip() if path else os.environ.get('HUB_DATABASE_URL')

def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def same_value(field,old,new):
    if field=='probability':
        try:return Decimal(old)==Decimal(new)
        except InvalidOperation:pass
    if field=='close_date':
        for pattern in ('%Y-%m-%d','%d/%m/%y','%d/%m/%Y'):
            try:return datetime.strptime(old,pattern).date().isoformat()==new
            except ValueError:pass
    return old==new

class PostgresRepository:
    def __init__(self,dsn):
        import psycopg
        from psycopg.rows import dict_row
        self.psycopg=psycopg;self.dict_row=dict_row;self.dsn=dsn
        with self.connect() as conn:
            for f in sorted((Path(__file__).parent/'migrations').glob('*.sql')):
                conn.execute(f.read_text(encoding='utf-8'))

    def connect(self):
        return self.psycopg.connect(self.dsn,row_factory=self.dict_row,connect_timeout=5)

    def save_snapshot(self,rows,scope):
        from psycopg.types.json import Jsonb
        changed=0
        with self.connect() as c:
            for row in rows:
                number=row['opportunity_number'];digest=fingerprint(row)
                old=c.execute('SELECT source_hash FROM hub.opportunities WHERE opportunity_number=%s FOR UPDATE',(number,)).fetchone()
                different=not old or old['source_hash']!=digest
                changed+=int(different)
                written=c.execute('''INSERT INTO hub.opportunities(opportunity_number,payload,source_hash)
                    VALUES(%s,%s,%s) ON CONFLICT(opportunity_number) DO UPDATE
                    SET payload=excluded.payload,source_hash=excluded.source_hash,last_seen=now(),
                    version=hub.opportunities.version+CASE WHEN hub.opportunities.source_hash<>excluded.source_hash THEN 1 ELSE 0 END RETURNING version''',
                    (number,Jsonb(row),digest)).fetchone()
                if different:
                    c.execute('INSERT INTO hub.opportunity_history(opportunity_number,source_hash,payload,source_version) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(number,digest,Jsonb(row),written['version']))
                    pending=c.execute("SELECT id,field,old_value FROM hub.change_requests WHERE opportunity_number=%s AND state='pending_validation'",(number,)).fetchall()
                    for request in pending:
                        if str(row.get(request['field'],''))!=request['old_value']:
                            c.execute("UPDATE hub.change_requests SET state='conflict',updated_at=now() WHERE id=%s",(request['id'],))
            result=c.execute('INSERT INTO hub.sync_runs(scope,partial,row_count,changed_count) VALUES(%s,true,%s,%s) RETURNING loaded_at',(scope,len(rows),changed)).fetchone()
        return result['loaded_at'].isoformat()

    def load(self):
        with self.connect() as c:
            rows=c.execute('SELECT opportunity_number,payload,version,last_seen FROM hub.opportunities ORDER BY opportunity_number').fetchall()
            last=c.execute('SELECT * FROM hub.sync_runs ORDER BY id DESC LIMIT 1').fetchone()
            details=c.execute('SELECT opportunity_number,payload,loaded_at FROM hub.record_details').fetchall()
        return {'records':[dict(r['payload'],_version=r['version'],_last_seen=r['last_seen'].isoformat()) for r in rows],
                'loaded_at':last['loaded_at'].isoformat() if last else None,'scope':last['scope'] if last else 'Sin consulta',
                'details':{d['opportunity_number']:dict(d['payload'],loaded_at=d['loaded_at'].isoformat()) for d in details}}

    def save_detail(self,number,detail):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM hub.opportunities WHERE opportunity_number=%s',(number,)).fetchone():raise KeyError(number)
            c.execute('''INSERT INTO hub.record_details(opportunity_number,payload) VALUES(%s,%s)
                ON CONFLICT(opportunity_number) DO UPDATE SET payload=excluded.payload,loaded_at=now()''',(number,Jsonb(detail)))

    def changes(self,number=None):
        with self.connect() as c:
            if number: rows=c.execute('SELECT * FROM hub.change_requests WHERE opportunity_number=%s ORDER BY created_at DESC',(number,)).fetchall()
            else: rows=c.execute('SELECT * FROM hub.change_requests ORDER BY created_at DESC LIMIT 250').fetchall()
        for row in rows:
            for key in ('created_at','updated_at'):row[key]=row[key].isoformat()
        return rows

    def propose(self,number,field,new_value,version,actor):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            row=c.execute('SELECT payload,version FROM hub.opportunities WHERE opportunity_number=%s FOR UPDATE',(number,)).fetchone()
            if not row:raise KeyError(number)
            if row['version']!=version:raise ConflictError('Oracle cambió desde la lectura. Actualiza antes de editar.')
            if c.execute("SELECT 1 FROM hub.change_requests WHERE opportunity_number=%s AND field=%s AND state IN ('pending_validation','approved','applying')",(number,field)).fetchone():
                raise ConflictError('Ya existe una propuesta pendiente para este campo.')
            identifier=str(uuid4());old=str(row['payload'].get(field,''))
            if same_value(field,old,new_value):raise ValidationError('El valor no cambió.')
            c.execute('''INSERT INTO hub.change_requests(id,opportunity_number,field,old_value,new_value,expected_version,actor)
                VALUES(%s,%s,%s,%s,%s,%s,%s)''',(identifier,number,field,old,new_value,version,actor))
            c.execute('INSERT INTO hub.audit_events(actor,action,opportunity_number,metadata) VALUES(%s,%s,%s,%s)',
                      (actor,'propose_change',number,Jsonb({'request_id':identifier,'field':field})))
        return {'id':identifier,'state':'pending_validation','message':'Propuesta guardada. Oracle todavía no se ha modificado.'}

    def cancel(self,identifier,actor):
        with self.connect() as c:
            r=c.execute("UPDATE hub.change_requests SET state='cancelled',updated_at=now() WHERE id=%s AND state IN ('pending_validation','conflict') RETURNING opportunity_number",(identifier,)).fetchone()
            if not r:raise ConflictError('La propuesta no puede cancelarse en su estado actual.')
            c.execute('INSERT INTO hub.audit_events(actor,action,opportunity_number) VALUES(%s,%s,%s)',(actor,'cancel_change',r['opportunity_number']))
        return {'state':'cancelled'}

    def local_activities(self):
        with self.connect() as c:
            rows=c.execute('SELECT * FROM hub.local_activities ORDER BY updated_at DESC').fetchall()
        for r in rows:
            r['data']=r.pop('payload');r['sync_state']='local_only'
            for key in ('created_at','updated_at'):r[key]=r[key].isoformat()
        return rows

    def save_local_activity(self,item,actor):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM hub.opportunities WHERE opportunity_number=%s FOR UPDATE',(item['opportunity_number'],)).fetchone():raise KeyError()
            old=c.execute('SELECT * FROM hub.local_activities WHERE id=%s FOR UPDATE',(item['id'],)).fetchone()
            if old:
                if old['opportunity_number']!=item['opportunity_number'] or old['kind']!=item['kind']:raise ConflictError('No se puede cambiar el vínculo de una actividad.')
                if item['version'] is None and old['payload']==item['data']:return {'id':item['id'],'version':old['version'],'sync_state':'local_only'}
                if old['version']!=item['version']:raise ConflictError('La actividad cambió. Abre la versión actual antes de guardar.')
                c.execute('UPDATE hub.local_activities SET payload=%s,version=version+1,updated_at=now() WHERE id=%s',(Jsonb(item['data']),item['id']))
                version=old['version']+1
            else:
                if item['version'] is not None:raise ConflictError('La actividad ya no está disponible.')
                c.execute('INSERT INTO hub.local_activities(id,opportunity_number,kind,payload,actor) VALUES(%s,%s,%s,%s,%s)',(item['id'],item['opportunity_number'],item['kind'],Jsonb(item['data']),actor))
                version=1
            c.execute('INSERT INTO hub.audit_events(actor,action,opportunity_number,metadata) VALUES(%s,%s,%s,%s)',(actor,'save_local_activity',item['opportunity_number'],Jsonb({'id':item['id'],'kind':item['kind'],'version':version})))
        return {'id':item['id'],'version':version,'sync_state':'local_only'}

    def settings(self):
        with self.connect() as c:return {r['key']:r['value'] for r in c.execute('SELECT key,value FROM hub.settings').fetchall()}

    def save_setting(self,key,value):
        from psycopg.types.json import Jsonb
        with self.connect() as c:c.execute('INSERT INTO hub.settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,Jsonb(value)))

    def summary(self):
        with self.connect() as c:
            count=c.execute('SELECT count(*) n FROM hub.opportunities').fetchone()['n']
            history=c.execute('SELECT count(*) n FROM hub.opportunity_history').fetchone()['n']
            runs=c.execute('SELECT count(*) n FROM hub.sync_runs').fetchone()['n']
        return {'engine':'postgresql','persistent':True,'records':count,'historical_versions':history,'sync_runs':runs}

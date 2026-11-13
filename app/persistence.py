"""PostgreSQL source mirror and operational queue. No credentials in source."""
import hashlib
import json
import os
import re
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
    def __init__(self,dsn,schema='hub'):
        if not re.fullmatch(r'hub(?:_u_[a-f0-9]{32})?',schema):raise ValueError('Invalid namespace')
        self.schema=schema
        import psycopg
        from psycopg.rows import dict_row
        self.psycopg=psycopg;self.dict_row=dict_row;self.dsn=dsn
        with self.connect() as conn:
            if not conn.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s',(self.schema,)).fetchone():
                from psycopg import sql
                conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(self.schema,))
            conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY)')
            for f in sorted((Path(__file__).parent/'migrations').glob('*.sql')):
                if not conn.execute('SELECT 1 FROM schema_migrations WHERE name=%s',(f.name,)).fetchone():
                    conn.execute(f.read_text(encoding='utf-8').replace('hub.',self.schema+'.'))
                    conn.execute('INSERT INTO schema_migrations(name) VALUES(%s)',(f.name,))

    def connect(self):
        c=self.psycopg.connect(self.dsn,row_factory=self.dict_row,connect_timeout=5)
        from psycopg import sql
        try:c.execute(sql.SQL('SET search_path TO {}, pg_catalog').format(sql.Identifier(self.schema)))
        except Exception:c.close();raise
        return c

    def save_snapshot(self,rows,scope):
        from psycopg.types.json import Jsonb
        changed=0
        with self.connect() as c:
            for row in rows:
                number=row['opportunity_number'];digest=fingerprint(row)
                old=c.execute('SELECT source_hash,last_write_verified_at FROM opportunities WHERE opportunity_number=%s FOR UPDATE',(number,)).fetchone()
                started=getattr(self,'snapshot_started',None)
                if old and started and old['last_write_verified_at'] and old['last_write_verified_at']>started:continue
                different=not old or old['source_hash']!=digest
                changed+=int(different)
                written=c.execute('''INSERT INTO opportunities(opportunity_number,payload,source_hash)
                    VALUES(%s,%s,%s) ON CONFLICT(opportunity_number) DO UPDATE
                    SET payload=excluded.payload,source_hash=excluded.source_hash,last_seen=now(),
                    version=opportunities.version+CASE WHEN opportunities.source_hash<>excluded.source_hash THEN 1 ELSE 0 END RETURNING version''',
                    (number,Jsonb(row),digest)).fetchone()
                if different:
                    c.execute('INSERT INTO opportunity_history(opportunity_number,source_hash,payload,source_version) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(number,digest,Jsonb(row),written['version']))
                    pending=c.execute("SELECT id,field,old_value FROM change_requests WHERE opportunity_number=%s AND state='pending_validation'",(number,)).fetchall()
                    for request in pending:
                        if str(row.get(request['field'],''))!=request['old_value']:
                            c.execute("UPDATE change_requests SET state='conflict',updated_at=now() WHERE id=%s",(request['id'],))
            result=c.execute('INSERT INTO sync_runs(scope,partial,row_count,changed_count) VALUES(%s,true,%s,%s) RETURNING loaded_at',(scope,len(rows),changed)).fetchone()
        return result['loaded_at'].isoformat()

    def load(self):
        with self.connect() as c:
            rows=c.execute('SELECT opportunity_number,payload,version,last_seen FROM opportunities ORDER BY opportunity_number').fetchall()
            last=c.execute('SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1').fetchone()
            details=c.execute('SELECT opportunity_number,payload,loaded_at FROM record_details').fetchall()
        return {'records':[dict(r['payload'],_version=r['version'],_last_seen=r['last_seen'].isoformat()) for r in rows],
                'loaded_at':last['loaded_at'].isoformat() if last else None,'scope':last['scope'] if last else 'Sin consulta',
                'details':{d['opportunity_number']:dict(d['payload'],loaded_at=d['loaded_at'].isoformat()) for d in details}}

    def save_detail(self,number,detail):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM opportunities WHERE opportunity_number=%s',(number,)).fetchone():raise KeyError(number)
            c.execute('''INSERT INTO record_details(opportunity_number,payload) VALUES(%s,%s)
                ON CONFLICT(opportunity_number) DO UPDATE SET payload=excluded.payload,loaded_at=now()''',(number,Jsonb(detail)))

    def changes(self,number=None):
        with self.connect() as c:
            if number: rows=c.execute('SELECT * FROM change_requests WHERE opportunity_number=%s ORDER BY created_at DESC',(number,)).fetchall()
            else: rows=c.execute('SELECT * FROM change_requests ORDER BY created_at DESC LIMIT 250').fetchall()
        for row in rows:
            for key in ('created_at','updated_at'):row[key]=row[key].isoformat()
            if row.get('oracle_verified_at'):row['oracle_verified_at']=row['oracle_verified_at'].isoformat()
        return rows

    def propose(self,number,field,new_value,version,actor):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            row=c.execute('SELECT payload,version FROM opportunities WHERE opportunity_number=%s FOR UPDATE',(number,)).fetchone()
            if not row:raise KeyError(number)
            if row['version']!=version:raise ConflictError('Oracle cambió desde la lectura. Actualiza antes de editar.')
            if c.execute("SELECT 1 FROM change_requests WHERE opportunity_number=%s AND field=%s AND state IN ('pending_validation','queued','approved','applying','uncertain')",(number,field)).fetchone():
                raise ConflictError('Ya existe una propuesta pendiente para este campo.')
            identifier=str(uuid4());old=str(row['payload'].get(field,''))
            if same_value(field,old,new_value):raise ValidationError('El valor no cambió.')
            c.execute('''INSERT INTO change_requests(id,opportunity_number,field,old_value,new_value,expected_version,actor)
                VALUES(%s,%s,%s,%s,%s,%s,%s)''',(identifier,number,field,old,new_value,version,actor))
            c.execute('INSERT INTO audit_events(actor,action,opportunity_number,metadata) VALUES(%s,%s,%s,%s)',
                      (actor,'propose_change',number,Jsonb({'request_id':identifier,'field':field})))
        return {'id':identifier,'state':'pending_validation','message':'Propuesta guardada. Oracle todavía no se ha modificado.'}

    def cancel(self,identifier,actor):
        with self.connect() as c:
            r=c.execute("UPDATE change_requests SET state='cancelled',updated_at=now() WHERE id=%s AND state IN ('pending_validation','conflict') RETURNING opportunity_number",(identifier,)).fetchone()
            if not r:raise ConflictError('La propuesta no puede cancelarse en su estado actual.')
            c.execute('INSERT INTO audit_events(actor,action,opportunity_number) VALUES(%s,%s,%s)',(actor,'cancel_change',r['opportunity_number']))
        return {'state':'cancelled'}

    def write_state(self,identifier,actor,state,code=None):
        with self.connect() as c:
            c.execute('UPDATE change_requests SET state=%s,result_code=%s,updated_at=now() WHERE id=%s AND actor=%s',(state,code,identifier,actor))
    def start_write(self,identifier,actor):
        with self.connect() as c:
            row=c.execute("UPDATE change_requests SET state='applying',updated_at=now() WHERE id=%s AND actor=%s AND state='queued' RETURNING *",(identifier,actor)).fetchone()
            if not row:raise ConflictError('Este cambio ya se procesó o requiere verificar el resultado.')
        return row
    def confirm_write(self,identifier,actor,detail):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            request=c.execute('SELECT * FROM change_requests WHERE id=%s AND actor=%s FOR UPDATE',(identifier,actor)).fetchone()
            if not request or request['state'] not in ('applying','uncertain'):raise ConflictError('Estado de escritura inválido.')
            actual=detail['fields'].get(request['field'])
            if not same_value(request['field'],str(actual),request['new_value']):raise ConflictError('Oracle no confirmó el nuevo valor.')
            row=c.execute('SELECT payload,version FROM opportunities WHERE opportunity_number=%s FOR UPDATE',(request['opportunity_number'],)).fetchone()
            payload=dict(row['payload']);payload[request['field']]=actual;digest=fingerprint(payload)
            result=c.execute('UPDATE opportunities SET payload=%s,source_hash=%s,version=version+1,last_seen=now(),last_write_verified_at=now() WHERE opportunity_number=%s RETURNING version',(Jsonb(payload),digest,request['opportunity_number'])).fetchone()
            c.execute('INSERT INTO opportunity_history(opportunity_number,source_hash,payload,source_version) VALUES(%s,%s,%s,%s)',(request['opportunity_number'],digest,Jsonb(payload),result['version']))
            c.execute("UPDATE change_requests SET state='confirmed',result_code=NULL,oracle_verified_at=now(),updated_at=now() WHERE id=%s",(identifier,))
            c.execute('INSERT INTO audit_events(actor,action,opportunity_number,metadata) VALUES(%s,%s,%s,%s)',(actor,'oracle_write_verified',request['opportunity_number'],Jsonb({'request_id':identifier,'field':request['field']})))
        self.save_detail(request['opportunity_number'],detail)

    def local_activities(self):
        with self.connect() as c:
            rows=c.execute('SELECT * FROM local_activities ORDER BY updated_at DESC').fetchall()
        for r in rows:
            r['data']=r.pop('payload');r['sync_state']='local_only'
            for key in ('created_at','updated_at'):r[key]=r[key].isoformat()
        return rows

    def save_local_activity(self,item,actor):
        from psycopg.types.json import Jsonb
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM opportunities WHERE opportunity_number=%s FOR UPDATE',(item['opportunity_number'],)).fetchone():raise KeyError()
            old=c.execute('SELECT * FROM local_activities WHERE id=%s FOR UPDATE',(item['id'],)).fetchone()
            if old:
                if old['opportunity_number']!=item['opportunity_number'] or old['kind']!=item['kind']:raise ConflictError('No se puede cambiar el vínculo de una actividad.')
                if item['version'] is None and old['payload']==item['data']:return {'id':item['id'],'version':old['version'],'sync_state':'local_only'}
                if old['version']!=item['version']:raise ConflictError('La actividad cambió. Abre la versión actual antes de guardar.')
                c.execute('UPDATE local_activities SET payload=%s,version=version+1,updated_at=now() WHERE id=%s',(Jsonb(item['data']),item['id']))
                version=old['version']+1
            else:
                if item['version'] is not None:raise ConflictError('La actividad ya no está disponible.')
                c.execute('INSERT INTO local_activities(id,opportunity_number,kind,payload,actor) VALUES(%s,%s,%s,%s,%s)',(item['id'],item['opportunity_number'],item['kind'],Jsonb(item['data']),actor))
                version=1
            c.execute('INSERT INTO audit_events(actor,action,opportunity_number,metadata) VALUES(%s,%s,%s,%s)',(actor,'save_local_activity',item['opportunity_number'],Jsonb({'id':item['id'],'kind':item['kind'],'version':version})))
        return {'id':item['id'],'version':version,'sync_state':'local_only'}

    def settings(self):
        with self.connect() as c:return {r['key']:r['value'] for r in c.execute('SELECT key,value FROM settings').fetchall()}

    def save_setting(self,key,value):
        from psycopg.types.json import Jsonb
        with self.connect() as c:c.execute('INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,Jsonb(value)))

    def summary(self):
        with self.connect() as c:
            count=c.execute('SELECT count(*) n FROM opportunities').fetchone()['n']
            history=c.execute('SELECT count(*) n FROM opportunity_history').fetchone()['n']
            runs=c.execute('SELECT count(*) n FROM sync_runs').fetchone()['n']
        return {'engine':'postgresql','persistent':True,'records':count,'historical_versions':history,'sync_runs':runs}

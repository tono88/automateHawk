"""Exercise real PostgreSQL against an isolated database containing synthetic rows."""
import json
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
import psycopg
from psycopg import sql
from app.persistence import PostgresRepository
from app.oracle_read import OracleReadStore
from app.domain import ConflictError,ValidationError

private=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'automateHawk'
admin=(private/'postgres-admin.secret').read_text().strip()
app=(private/'postgres-app.secret').read_text().strip()
name='automatehawk_test_'+uuid4().hex[:12]
admin_base=f'postgresql://hub_admin:{quote(admin)}@127.0.0.1:55432/'
with psycopg.connect(admin_base+'automatehawk',autocommit=True) as owner:
    owner.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        with psycopg.connect(admin_base+name,autocommit=True) as setup:
            setup.execute('CREATE SCHEMA hub AUTHORIZATION hub_app')
            setup.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO hub_app').format(sql.Identifier(name)))
        dsn=f'postgresql://hub_app:{quote(app)}@127.0.0.1:55432/{name}'
        repo=PostgresRepository(dsn)
        row={'opportunity_number':'SYNTHETIC-ONLY-001','name':'Prueba ficticia','stage':'01 - Interesado'}
        repo.save_snapshot([row],'Prueba sintética aislada')
        assert PostgresRepository(dsn).load()['records'][0]['name']=='Prueba ficticia'
        repo.save_snapshot([row],'Carga repetida');assert repo.summary()['historical_versions']==1
        store=OracleReadStore(repo,role='editor')
        store.ingest_detail({'opportunity_number':row['opportunity_number'],'fields':{'stage':row['stage']},'capabilities':{'stage':True},'activities':{'queried':True,'rows':[]}})
        request=store.propose({'opportunity_number':row['opportunity_number'],'field':'stage','value':'02 - Inscrito a prueba','version':1})
        assert request['state']=='pending_validation'
        assert repo.load()['records'][0]['stage']=='01 - Interesado'
        try:OracleReadStore(repo,role='reader').propose({'opportunity_number':row['opportunity_number'],'field':'stage','value':'02 - Inscrito a prueba','version':1});raise AssertionError('Un lector pudo editar')
        except PermissionError:pass
        changed=dict(row,stage='03 - Presente a prueba: resolución');repo.save_snapshot([changed],'Cambio externo simulado')
        assert repo.changes()[0]['state']=='conflict'
        repo.save_snapshot([row],'Regreso de estado simulado')
        assert repo.summary()['historical_versions']==3
        assert repo.load()['records'][0]['_version']==3
        second=dict(row,opportunity_number='SYNTHETIC-ONLY-002');repo.save_snapshot([second],'Carga parcial')
        assert repo.summary()['records']==2
        assert len(repo.load()['details'])==1
        repo.save_setting('sync',{'enabled':True,'interval_minutes':15})
        assert OracleReadStore(repo).settings['interval_minutes']==15
        from app.local_activities import validate
        item=validate({'id':str(uuid4()),'opportunity_number':row['opportunity_number'],'kind':'tasks','data':{'subject':'Seguimiento ficticio','owner':'Asesor ficticio','local_status':'Pendiente'}})
        repo.save_local_activity(item,'synthetic-test')
        repo.save_local_activity(item,'synthetic-test')
        assert len(repo.local_activities())==1
        assert PostgresRepository(dsn).local_activities()[0]['data']['subject']=='Seguimiento ficticio'
        edited=dict(item,version=1,data=dict(item['data'],local_status='Completado'))
        assert repo.save_local_activity(edited,'synthetic-test')['version']==2
        try:repo.save_local_activity(edited,'synthetic-test');raise AssertionError('Conflicto no detectado')
        except ConflictError:pass
        assert repo.local_activities()[0]['sync_state']=='local_only'
        assert repo.load()['records'][0]['stage']=='01 - Interesado'
        from app.scoped_repository import ScopedRepository
        a=ScopedRepository(dsn,'synthetic-user-a');b=ScopedRepository(dsn,'synthetic-user-b')
        a.save_snapshot([row],'Solo usuario ficticio A')
        assert a.load()['records'] and not b.load()['records']
        try:b.save_local_activity(item,'synthetic-user-b');raise AssertionError('Cross-user write')
        except PermissionError:pass
        assert ScopedRepository(dsn,'synthetic-user-a').load()['records']
        a.save_detail(row['opportunity_number'],{'fields':{'cycle':'2271','name':row['name']},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]}})
        assert a.load()['details'] and ScopedRepository(dsn,'synthetic-user-a').load()['details']
        assert not b.local_activities() and a.schema==b.schema=='hub'
        b.save_snapshot([row],'Usuario B autorizado al mismo registro')
        assert b.load()['detail_states'][row['opportunity_number']]=='permission_required'
        assert not b.load()['details']
        assert len(b.load()['records'])==1
        assert len(repo.load()['records'])==2
        owned=dict(item,id=str(uuid4()))
        a.save_local_activity(owned,'synthetic-user-a')
        b.save_detail(row['opportunity_number'],{'fields':{'name':row['name']},'capabilities':{'name':False},'activities':{'queried':True,'rows':[]}})
        assert any(not r['can_edit'] for r in b.local_activities())
        try:b.save_local_activity(dict(owned,version=1),'synthetic-user-b');raise AssertionError('Cross-user activity edit')
        except PermissionError:pass
        current=a.load()['records'][0]
        change=a.propose(row['opportunity_number'],'name','Nombre ficticio actualizado',current['_version'],'synthetic-user-a')
        a.write_state(change['id'],'synthetic-user-a','queued')
        assert a.start_write(change['id'],'synthetic-user-a')['state']=='applying'
        a.confirm_write(change['id'],'synthetic-user-a',{'fields':{'name':'Nombre ficticio actualizado'},'capabilities':{'name':True},'activities':{'queried':False,'rows':[]}})
        assert a.changes()[0]['state']=='confirmed'
        assert b.load()['records'][0]['name']=='Nombre ficticio actualizado'
        from datetime import datetime,timezone,timedelta
        a.snapshot_started=datetime.now(timezone.utc)-timedelta(minutes=1)
        a.save_snapshot([row],'Lectura antigua que terminó después de guardar')
        assert b.load()['records'][0]['name']=='Nombre ficticio actualizado'
        a.save_read_progress(row['opportunity_number'],'reading',1)
        a.save_read_progress(row['opportunity_number'],'completed')
        assert ScopedRepository(dsn,'synthetic-user-a').read_progress()[row['opportunity_number']]['state']=='completed'
        assert not b.read_progress()
        assert a.load()['detail_states'][row['opportunity_number']]=='available'
        with a.connect() as c:c.execute("UPDATE user_permissions SET detail_until=now()-interval '1 hour' WHERE principal=%s",('synthetic-user-a',))
        assert a.load()['detail_states'][row['opportunity_number']]=='permission_expired' and not a.load()['details']
        resumed=OracleReadStore(ScopedRepository(dsn,'synthetic-user-a'))
        assert resumed.request('details_batch')['total']==0
        assert not resumed.details
        a.save_read_progress(row['opportunity_number'],'partial')
        assert OracleReadStore(ScopedRepository(dsn,'synthetic-user-a')).request('details_batch')['total']==1
        assert a.read_progress()[row['opportunity_number']]['state']=='partial'
        with a.connect() as c:c.execute("UPDATE user_permissions SET read_until=now()-interval '1 hour' WHERE principal=%s",('synthetic-user-a',))
        assert not a.load()['records']
        assert b.load()['records']
        print(json.dumps({'postgresql_integration':'passed','checks':41,'data':'synthetic isolated database'}))
    finally:
        if not name.startswith('automatehawk_test_'):raise RuntimeError('Base de prueba inválida')
        owner.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))

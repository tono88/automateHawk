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
        expired=a.load()
        assert expired['detail_states'][row['opportunity_number']]=='unconfirmed'
        assert expired['details'][row['opportunity_number']]['unconfirmed'] and not any(expired['details'][row['opportunity_number']]['capabilities'].values())
        resumed=OracleReadStore(ScopedRepository(dsn,'synthetic-user-a'))
        assert resumed.request('details_batch')['total']==1
        assert resumed.details[row['opportunity_number']]['unconfirmed']
        a.save_read_progress(row['opportunity_number'],'partial')
        assert OracleReadStore(ScopedRepository(dsn,'synthetic-user-a')).request('details_batch')['total']==1
        assert a.read_progress()[row['opportunity_number']]['state']=='partial'
        # Longer reading never extends editing or invents a fresh detail check.
        a.basic_minutes=480;a.detail_minutes=480
        a.save_detail(row['opportunity_number'],{'fields':{'cycle':'2271','name':row['name']},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]}})
        grant=a.grant(row['opportunity_number'])
        assert 28790<(grant['detail_until']-grant['detail_checked_at']).total_seconds()<=28800
        assert 1790<(grant['edit_until']-grant['detail_checked_at']).total_seconds()<=1800
        checked=grant['detail_checked_at']
        a.save_snapshot([row],'Renovación ficticia de la lista')
        assert a.grant(row['opportunity_number'])['detail_checked_at']==checked
        with a.connect() as c:c.execute("UPDATE user_permissions SET edit_until=now()-interval '1 second' WHERE principal=%s",('synthetic-user-a',))
        assert a.load()['details'][row['opportunity_number']]['fields']['cycle']=='2271'
        assert not a.load()['details'][row['opportunity_number']]['capabilities']['name']
        try:a.require(row['opportunity_number'],'name');raise AssertionError('Expired edit allowed by long read grant')
        except PermissionError:pass
        with a.connect() as c:c.execute("UPDATE user_permissions SET read_until=now()-interval '1 hour' WHERE principal=%s",('synthetic-user-a',))
        last=a.load()['records']
        assert len(last)==1 and last[0]['_unconfirmed'] and a.grant(row['opportunity_number']) is None
        assert b.load()['records']
        missing=dict(row,opportunity_number='SYNTHETIC-MISSING')
        a.save_snapshot([row,missing],'Inventario ficticio inicial')
        a.save_detail(missing['opportunity_number'],{'fields':{'name':'Ficticio'},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]}})
        a.reconcile_visible_inventory({row['opportunity_number']})
        assert len(a.load()['records'])==1
        assert missing['opportunity_number'] not in a.load()['details']
        assert a.grant(missing['opportunity_number']) is None
        assert b.grant(row['opportunity_number']) is not None
        assert len(repo.load()['records'])==3
        a.reconcile_visible_inventory(set())
        assert not a.load()['records']
        assert b.load()['records']
        with b.connect() as c:
            c.execute("UPDATE user_permissions SET detail_checked_at=NULL,edit_until=NULL,detail_until=now()+interval '10 minutes',checked_at=now() WHERE principal=%s",('synthetic-user-b',))
            c.execute((Path(__file__).resolve().parents[1]/'app/migrations/009_separate_read_edit_grants.sql').read_text(encoding='utf-8'))
        legacy=b.grant(row['opportunity_number'])
        assert legacy['edit_until']==legacy['detail_until']
        assert legacy['detail_checked_at']==legacy['detail_until']-timedelta(minutes=30)
        b.save_read_progress(row['opportunity_number'],'reading',1)
        b.save_snapshot([dict(row,name='Versión posterior ficticia')],'Cambio ficticio durante una lectura')
        b.save_read_progress(row['opportunity_number'],'completed')
        assert b.read_progress()[row['opportunity_number']]['needs_refresh']
        b.save_read_progress(row['opportunity_number'],'reading',1)
        b.save_read_progress(row['opportunity_number'],'completed')
        assert not b.read_progress()[row['opportunity_number']]['needs_refresh']
        with b.connect() as c:c.execute("UPDATE detail_read_progress SET updated_at=now()-interval '169 hours' WHERE principal=%s",('synthetic-user-b',))
        assert b.read_progress()[row['opportunity_number']]['needs_refresh']
        with b.connect() as c:c.execute("UPDATE detail_read_progress SET source_version=NULL,updated_at=now() WHERE principal=%s",('synthetic-user-b',))
        assert not b.read_progress()[row['opportunity_number']]['needs_refresh']
        with b.connect() as c:c.execute("UPDATE detail_read_progress SET updated_at=now()-interval '1 minute' WHERE principal=%s",('synthetic-user-b',))
        assert b.read_progress()[row['opportunity_number']]['needs_refresh']
        reader=ScopedRepository(dsn,'synthetic-policy-user');reader.basic_minutes=reader.detail_minutes=480
        reader.save_snapshot([row],'Cartera recién comprobada ficticia')
        reader.save_detail(row['opportunity_number'],{'fields':{'name':'Persona ficticia'},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]}})
        reader.save_read_progress(row['opportunity_number'],'reading',1)
        reader.save_read_progress(row['opportunity_number'],'completed')
        with reader.connect() as c:
            c.execute("UPDATE user_permissions SET detail_checked_at=now()-interval '2 hours',detail_until=now()-interval '90 minutes',edit_until=now()-interval '90 minutes' WHERE principal=%s",(reader.principal,))
            c.execute("UPDATE detail_read_progress SET updated_at=now()-interval '119 minutes' WHERE principal=%s",(reader.principal,))
        before=reader.grant(row['opportunity_number']);other=b.grant(row['opportunity_number'])
        assert reader.extend_observed_detail_reads()==1
        after=reader.grant(row['opportunity_number'])
        assert after['edit_until']==before['edit_until']
        assert after['detail_checked_at']==before['detail_checked_at']
        assert after['detail_fields']==before['detail_fields'] and after['capabilities']==before['capabilities']
        assert after['detail_until']==before['detail_checked_at']+timedelta(hours=8)
        try:reader.require(row['opportunity_number'],'name');raise AssertionError('Policy transition extended editing')
        except PermissionError:pass
        assert b.grant(row['opportunity_number'])['detail_until']==other['detail_until']
        assert reader.extend_observed_detail_reads()==0
        reader.reconcile_visible_inventory(set())
        with reader.connect() as c:revoked=c.execute('SELECT revoked_at FROM user_permissions WHERE principal=%s',(reader.principal,)).fetchone()['revoked_at']
        assert revoked is not None
        assert reader.extend_observed_detail_reads()==0
        reader.save_snapshot([row],'Acceso ficticio a la lista restaurado')
        assert reader.grant(row['opportunity_number'])['revoked_at'] is None
        assert reader.extend_observed_detail_reads()==0
        reader.save_detail(row['opportunity_number'],{'fields':{'name':'Persona ficticia'},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]}})
        with reader.connect() as c:
            c.execute("UPDATE user_permissions SET detail_checked_at=now()-interval '9 hours',detail_until=now()-interval '8 hours' WHERE principal=%s",(reader.principal,))
            c.execute("UPDATE detail_read_progress SET updated_at=now()-interval '9 hours' WHERE principal=%s",(reader.principal,))
        assert reader.extend_observed_detail_reads()==0
        # Detail-only fields (tests, financial aid) are edited and traced like list fields.
        editor=ScopedRepository(dsn,'synthetic-detail-editor');editor.basic_minutes=editor.detail_minutes=editor.edit_minutes=240
        editor.save_snapshot([row],'Acceso ficticio para edición de detalle')
        editor.save_detail(row['opportunity_number'],{'fields':{'name':'Persona ficticia','test_call':'No Aplica'},'capabilities':{'test_call':True},'activities':{'queried':True,'rows':[]}})
        current=editor.load()['records'][0]
        proposal=editor.propose(row['opportunity_number'],'test_call','Convocatoria ficticia',current['_version'],editor.principal)
        pending=next(c for c in editor.changes() if c['id']==proposal['id'])
        assert pending['old_value']=='No Aplica',pending
        editor.write_state(proposal['id'],editor.principal,'queued');editor.start_write(proposal['id'],editor.principal)
        editor.confirm_write(proposal['id'],editor.principal,{'fields':{'name':'Persona ficticia','test_call':'Convocatoria ficticia'},'capabilities':{'test_call':True},'activities':{'queried':False,'rows':[]}})
        assert editor.load()['details'][row['opportunity_number']]['fields']['test_call']=='Convocatoria ficticia'
        assert 'test_call' not in editor.load()['records'][0]
        trace=editor.opportunity_trace(row['opportunity_number'])
        assert trace['versions'] and any(e['action']=='oracle_write_verified' and e['field']=='test_call' for e in trace['events'])
        activity=editor.trace_activity([row['opportunity_number'],'NOT-VISIBLE'])
        assert activity['recent'] and all(e['opportunity_number']==row['opportunity_number'] for e in activity['recent'])
        try:ScopedRepository(dsn,'synthetic-stranger').opportunity_trace(row['opportunity_number']);raise AssertionError('Trace without permission')
        except PermissionError:pass
        # Incremental sync: an unchanged record renews its detail window from the list;
        # a changed record (new "Última actualización") is marked for a new detail read.
        inc=ScopedRepository(dsn,'synthetic-incremental');inc.basic_minutes=inc.detail_minutes=inc.edit_minutes=60
        base={'opportunity_number':'SYN-INC-1','name':'Incremental ficticia','updated_at':'01/11/26'}
        inc.save_snapshot([base],'Inventario incremental ficticio')
        inc.save_detail('SYN-INC-1',{'fields':{'name':'Incremental ficticia'},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]},'schema_version':2})
        version=inc.load()['records'][0]['_version']
        inc.save_read_progress('SYN-INC-1','completed',source_version=version)
        with inc.connect() as c:c.execute("UPDATE user_permissions SET detail_until=now()-interval '1 minute' WHERE principal=%s",(inc.principal,))
        assert inc.read_progress()['SYN-INC-1']['permission_refresh_required']
        inc.save_snapshot([base],'Inventario incremental ficticio')
        progress=inc.read_progress()['SYN-INC-1']
        assert not progress['permission_refresh_required'] and not progress['needs_refresh'],progress
        inc.save_snapshot([dict(base,updated_at='16/11/26')],'Inventario incremental ficticio')
        assert inc.read_progress()['SYN-INC-1']['needs_refresh']
        # Opportunities created from the portal: request, mirror and confirmation.
        from app.oracle_read import OracleReadStore
        creator=OracleReadStore(ScopedRepository(dsn,'synthetic-creator'),role='editor');creator.actor='synthetic-creator'
        request=creator.propose_creation({'name':'Creación ficticia','close_date':'2026-12-01','contact':{'mode':'none'},'extra':{}})
        try:creator.propose_creation({'name':'creación ficticia','close_date':'2026-12-01','contact':{'mode':'none'}});raise AssertionError('Duplicate creation accepted')
        except ConflictError:pass
        assert [c['state'] for c in creator.repository.creations()]==['pending_validation']
        assert not ScopedRepository(dsn,'synthetic-other').creations()
        created=creator.ingest_created({'opportunity_number':'SYN-CREATED-1','name':'Creación ficticia','stage':'01 - Interesado'},
            {'fields':{'name':'Creación ficticia','test_call':''},'capabilities':{'test_call':True},'activities':{'queried':False,'rows':[]},'schema_version':2})
        assert created and created['opportunity_number']=='SYN-CREATED-1'
        assert creator.details['SYN-CREATED-1']['capabilities']['test_call'] and not creator.needs_detail('SYN-CREATED-1')
        creator.repository.creation_state(request['id'],'synthetic-creator','confirmed',number='SYN-CREATED-1')
        assert creator.repository.creations()[0]['opportunity_number']=='SYN-CREATED-1'
        follow=creator.propose({'opportunity_number':'SYN-CREATED-1','field':'test_call','value':'Enero 2027','version':created['_version']})
        assert follow['state']=='pending_validation'
        try:creator.propose_creation({'name':'Creación ficticia','close_date':'2026-12-01','contact':{'mode':'none'}});raise AssertionError('Existing name accepted')
        except ConflictError:pass
        # Last-copy view: expired grants are shown as unconfirmed (read-only) within the
        # window; revoked or too old ones are not; a new inventory confirms them again.
        stale=ScopedRepository(dsn,'synthetic-stale');stale.basic_minutes=stale.detail_minutes=stale.edit_minutes=60
        rows=[{'opportunity_number':f'SYN-STALE-{i}','name':f'Copia ficticia {i}'} for i in range(3)]
        stale.save_snapshot(rows,'Inventario ficticio')
        for r in rows:stale.save_detail(r['opportunity_number'],{'fields':{'name':r['name']},'capabilities':{'name':True},'activities':{'queried':True,'rows':[]},'schema_version':2})
        with stale.connect() as c:
            c.execute("UPDATE user_permissions SET read_until=now()-interval '1 day',detail_until=now()-interval '1 day',edit_until=now()-interval '1 day' WHERE principal=%s",(stale.principal,))
            c.execute("UPDATE user_permissions SET revoked_at=now() WHERE principal=%s AND opportunity_number='SYN-STALE-1'",(stale.principal,))
            c.execute("UPDATE user_permissions SET read_until=now()-interval '30 days' WHERE principal=%s AND opportunity_number='SYN-STALE-2'",(stale.principal,))
        view=stale.load()
        assert [(r['opportunity_number'],r.get('_unconfirmed')) for r in view['records']]==[('SYN-STALE-0',True)],view['records']
        assert view['details']['SYN-STALE-0']['unconfirmed'] and not any(view['details']['SYN-STALE-0']['capabilities'].values())
        assert view['detail_states']['SYN-STALE-0']=='unconfirmed' and view['unconfirmed']==1
        try:stale.propose('SYN-STALE-0','name','Otro nombre',view['records'][0]['_version'],stale.principal);raise AssertionError('Edit on unconfirmed row')
        except PermissionError:pass
        stale.save_snapshot([rows[0]],'Inventario ficticio')
        view=stale.load()
        assert not view['records'][0].get('_unconfirmed') and view['unconfirmed']==0
        stale.reconcile_visible_inventory({'SYN-STALE-2'})
        assert not stale.load()['records']
        # Incremental refresh: the fingerprint moves with writes and with permission expiry.
        marker=stale.fingerprint()
        assert stale.fingerprint()==marker
        stale.save_snapshot([dict(rows[2],name='Copia ficticia 2b')],'Inventario ficticio')
        moved=stale.fingerprint();assert moved!=marker
        with stale.connect() as c:c.execute("UPDATE user_permissions SET read_until=now()-interval '1 second' WHERE principal=%s",(stale.principal,))
        assert stale.fingerprint()!=moved
        print(json.dumps({'postgresql_integration':'passed','checks':107,'data':'synthetic isolated database'}))
    finally:
        if not name.startswith('automatehawk_test_'):raise RuntimeError('Base de prueba inválida')
        owner.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))

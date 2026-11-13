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
        with psycopg.connect(admin_base+name,autocommit=True) as setup:setup.execute('CREATE SCHEMA hub AUTHORIZATION hub_app')
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
        print(json.dumps({'postgresql_integration':'passed','checks':10,'data':'synthetic isolated database'}))
    finally:
        if not name.startswith('automatehawk_test_'):raise RuntimeError('Base de prueba inválida')
        owner.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))

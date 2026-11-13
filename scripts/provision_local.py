"""Provision only this project's private PostgreSQL container and app role."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'automateHawk'

def run(args,**kwargs):
    return subprocess.run(args,cwd=ROOT,check=True,**kwargs)

def main():
    PRIVATE.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        who=subprocess.check_output(['whoami'],text=True).strip()
        run(['icacls',str(PRIVATE),'/inheritance:r','/grant:r',f'{who}:(OI)(CI)F'],stdout=subprocess.DEVNULL)
    else:PRIVATE.chmod(0o700)
    admin_file=PRIVATE/'postgres-admin.secret';app_file=PRIVATE/'postgres-app.secret'
    for path in [admin_file,app_file]:
        if not path.exists():path.write_text(secrets.token_urlsafe(36),encoding='utf-8')
    admin=admin_file.read_text().strip();app=app_file.read_text().strip()
    host_dsn=f'postgresql://hub_app:{quote(app)}@127.0.0.1:55432/automatehawk'
    docker_dsn=f'postgresql://hub_app:{quote(app)}@postgres:5432/automatehawk'
    (PRIVATE/'database-host.dsn').write_text(host_dsn,encoding='utf-8')
    (PRIVATE/'database-docker.dsn').write_text(docker_dsn,encoding='utf-8')
    env=ROOT/'.env'
    if env.exists() and 'HUB_PG_ADMIN_SECRET_FILE' not in env.read_text():raise SystemExit('Existe un .env ajeno a esta configuración; no se modificó.')
    existing=env.read_text(encoding='utf-8').splitlines() if env.exists() else []
    preserve=[line for line in existing if not line.startswith(('HUB_PG_ADMIN_SECRET_FILE=','HUB_PG_DOCKER_DSN_FILE='))]
    env.write_text('\n'.join(preserve+[f'HUB_PG_ADMIN_SECRET_FILE={admin_file.as_posix()}',f'HUB_PG_DOCKER_DSN_FILE={(PRIVATE/"database-docker.dsn").as_posix()}'])+'\n',encoding='utf-8')
    run(['docker','compose','up','-d','postgres'])
    import psycopg
    from psycopg import sql
    for attempt in range(60):
        try:
            c=psycopg.connect(f'postgresql://hub_admin:{quote(admin)}@127.0.0.1:55432/automatehawk',autocommit=True,connect_timeout=2)
            break
        except psycopg.OperationalError:time.sleep(1)
    else:raise SystemExit('PostgreSQL no respondió; los secretos no se imprimieron.')
    with c:
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='hub_app'").fetchone():
            c.execute(sql.SQL('CREATE ROLE hub_app LOGIN PASSWORD {}').format(sql.Literal(app)))
        c.execute('GRANT CONNECT ON DATABASE automatehawk TO hub_app')
        c.execute('CREATE SCHEMA IF NOT EXISTS hub AUTHORIZATION hub_app')
    print('PostgreSQL local preparado en 127.0.0.1:55432. Configuración privada fuera de Git.')

if __name__=='__main__':main()

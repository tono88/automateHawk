"""Private pg_dump with optional isolated restore verification; no row output."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote
from uuid import uuid4
import psycopg
from psycopg import sql

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'automateHawk'

def contents_signature(connection):
    signature={}
    names=connection.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='hub' AND table_type='BASE TABLE' ORDER BY table_name").fetchall()
    for (name,) in names:
        query=sql.SQL("SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,E'\\n' ORDER BY row_to_json(t)::text),'')) FROM hub.{} t").format(sql.Identifier(name))
        signature[name]=connection.execute(query).fetchone()
    return signature

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    target=PRIVATE/'backups';target.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive=target/f'automatehawk-{stamp}.dump'
    command=['docker','compose','exec','-T','postgres','sh','-c',
             'export PGPASSWORD="$(cat /run/secrets/postgres_admin_password)"; exec pg_dump -U hub_admin -d automatehawk -Fc --no-owner']
    with archive.open('wb') as output:subprocess.run(command,cwd=ROOT,stdout=output,check=True)
    result={'backup':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'restored_and_verified':False}
    if args.verify:
        admin=(PRIVATE/'postgres-admin.secret').read_text().strip()
        base=f'postgresql://hub_admin:{quote(admin)}@127.0.0.1:55432/'
        name='automatehawk_verify_'+uuid4().hex[:12]
        with psycopg.connect(base+'automatehawk',autocommit=True) as connection:
            source_count=connection.execute('SELECT count(*) FROM hub.opportunities').fetchone()[0]
            source_signature=contents_signature(connection)
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            try:
                command=['docker','compose','exec','-T','postgres','sh','-c',
                  'export PGPASSWORD="$(cat /run/secrets/postgres_admin_password)"; exec pg_restore -U hub_admin --no-owner -d "$1"','restore',name]
                with archive.open('rb') as content:subprocess.run(command,cwd=ROOT,stdin=content,check=True)
                with psycopg.connect(base+name) as restored:
                    restored_count=restored.execute('SELECT count(*) FROM hub.opportunities').fetchone()[0]
                    restored_signature=contents_signature(restored)
                if restored_count!=source_count or source_signature!=restored_signature:raise RuntimeError('La restauración no coincide con la copia de origen.')
                result.update(restored_and_verified=True,records=restored_count,verified_tables=len(source_signature))
            finally:
                if not name.startswith('automatehawk_verify_'):raise RuntimeError('Nombre de verificación inválido.')
                connection.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
    (archive.with_suffix('.manifest.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()

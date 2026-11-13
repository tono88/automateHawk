"""Move the existing volatile copy straight into PostgreSQL, without files."""
import json
import os
from pathlib import Path
from urllib.request import urlopen
from app.persistence import PostgresRepository

private=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'automateHawk'
repo=PostgresRepository((private/'database-host.dsn').read_text().strip())
with urlopen('http://127.0.0.1:8765/api/oracle/snapshot') as response:state=json.load(response)
rows=[{k:v for k,v in r.items() if not k.startswith('_')} for r in state['records']]
if rows:repo.save_snapshot(rows,state['scope'])
print(json.dumps({'persisted_records':repo.summary()['records'],'source':'local-memory-to-postgresql'}))

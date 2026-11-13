import os
from pathlib import Path
import runpy

private=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'automateHawk'
os.environ['HUB_DATABASE_DSN_FILE']=str(private/'database-host.dsn')
os.environ.setdefault('HUB_LOCAL_ROLE','editor')
runpy.run_module('app.server',run_name='__main__')

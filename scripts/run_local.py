"""Start the authenticated local stack; do not expose the browser gateway on the host."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
if not (root/'.env').exists():raise SystemExit('Prepara PostgreSQL y secretos con python -m scripts.provision_local.')
subprocess.run(['docker','compose','up','--build','-d'],cwd=root,check=True)
print('Portal local: http://127.0.0.1:8765. Inicia sesión con Oracle.')

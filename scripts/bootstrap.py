"""Install the pinned host dependencies without changing the system Python."""
from pathlib import Path
import hashlib
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
env = root / '.venv'
requirements = root / 'requirements.txt'
stamp = env / '.requirements-sha256'
digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
if not (env / 'bin/python').exists():
    subprocess.run([sys.executable, '-m', 'venv', str(env)], check=True)
if not stamp.exists() or stamp.read_text() != digest:
    subprocess.run([str(env / 'bin/python'), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)], check=True)
    stamp.write_text(digest)
print('Python environment ready.')

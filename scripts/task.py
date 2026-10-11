"""Run any preserved first-party tool by name, with argv, never shell eval."""
from pathlib import Path
import os
import shlex
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
paths = sorted([*root.glob('firmware/mf79u/*.py'), *root.glob('firmware/mf79u/*.sh'), *root.glob('outputs/*.py'), *root.glob('outputs/*.sh'), *root.glob('outputs/mikopbx/*.py'), *root.glob('work/zte/voice/*.py')])
tasks = {str(p.relative_to(root)): p for p in paths}
if sys.argv[1:] == ['--list']:
    for name in tasks:
        print(name)
else:
    name = os.environ.get('TASK', '')
    found = [p for key, p in tasks.items() if key == name or p.name == name or p.stem == name]
    if len(found) != 1:
        raise SystemExit('Specify one unambiguous TASK from make tasks.')
    p = found[0]
    interpreter = sys.executable if p.suffix == '.py' else '/bin/sh'
    subprocess.run([interpreter, str(p), *shlex.split(os.environ.get('ARGS', ''))], cwd=root, check=True)

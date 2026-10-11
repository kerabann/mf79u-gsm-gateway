"""Exercise Go/Unix-packet APIs on the same isolated Linux as GitHub builds."""
from pathlib import Path
import os
import subprocess
root = Path(__file__).resolve().parents[1]
arch = subprocess.check_output(['docker', 'image', 'inspect', 'mf79u-build-tools:local', '--format', '{{.Architecture}}']).decode().strip()
env = dict(os.environ, GOOS='linux', GOARCH=arch, CGO_ENABLED='0', GOTOOLCHAIN='go1.25.12')
subprocess.run(['go', 'test', '-c', '-o', '../build/control-linux-tests', '.'], cwd=root / 'firmware/mf79u/control', env=env, check=True)
subprocess.run(['docker', 'run', '--rm', '-v', str(root) + ':/work', '-w', '/work', 'mf79u-build-tools:local', '/work/firmware/mf79u/build/control-linux-tests', '-test.v'], check=True)
print('PASS all Go tests in Linux, including Unix-packet IMS SMS IPC.')

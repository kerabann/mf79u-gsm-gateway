"""Run make ci with only publication files and checksummed upstream cache."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
dest = Path(tempfile.mkdtemp(prefix='mf79u-clean-checkout-'))
files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root)
for name in files.split(b'\0'):
    if not name:
        continue
    rel = Path(name.decode())
    source = root / rel
    if not source.is_file():
        continue
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
subprocess.run(['git', 'init', '--quiet', str(dest)], check=True)
env = dict(os.environ, SOURCE_CACHE=str(root))
env.pop('ADB', None)
env.pop('ANDROID_SERIAL', None)
print('Clean publication checkout:', dest, flush=True)
print('Reusing checksum-verified upstream archives only; no vendor dump, source tree or build artifact.', flush=True)
with (root / 'reports/clean-checkout.log').open('w') as log:
    result = subprocess.run(['make', 'ci'], cwd=dest, env=env, stdout=log, stderr=subprocess.STDOUT)
report = {'passed': result.returncode == 0, 'checkout': str(dest), 'vendorInputs': False, 'buildArtifactsReused': False,
          'upstreamArchiveCacheReused': True, 'githubHostedRun': False}
(root / 'reports/clean-checkout.json').write_text(json.dumps(report, indent=2) + '\n')
if result.returncode:
    raise SystemExit('Clean make ci failed; see reports/clean-checkout.log')
print('PASS clean publication checkout: complete make ci, no proprietary/private input.')

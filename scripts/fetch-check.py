"""Independently verify every public download URL against the source lock."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
results = []
for item in json.loads((root / 'sources.lock.json').read_text()):
    with tempfile.TemporaryDirectory(prefix='mf79u-source-url-') as tmp:
        path = Path(tmp) / 'archive'
        # curl follows SourceForge's redirect chain consistently on Linux/macOS.
        result = subprocess.run(['curl', '--fail', '--location', '--retry', '2', '--connect-timeout', '20', '--max-time', '180', '--silent', '--show-error', '--output', str(path), item['url']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        passed = result.returncode == 0 and hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        results.append({'source': item['path'], 'passed': passed})
        print(('PASS ' if passed else 'FAIL ') + Path(item['path']).name, flush=True)
report = {'passed': all(r['passed'] for r in results), 'sources': results}
(root / 'reports').mkdir(exist_ok=True)
(root / 'reports/source-downloads.json').write_text(json.dumps(report, indent=2) + '\n')
if not report['passed']:
    raise SystemExit('A public download is unavailable or differs from the source lock.')

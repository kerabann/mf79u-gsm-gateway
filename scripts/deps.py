"""Fetch and unpack checksum-pinned upstream sources; no firmware downloads."""
from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import time
import urllib.request
import subprocess
import os

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / 'sources.lock.json').read_text())
for item in lock:
    archive = root / item['path']
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        cache = os.environ.get('SOURCE_CACHE', '')
        cached = Path(cache) / item['path'] if cache else None
        if cached and cached.is_file() and hashlib.sha256(cached.read_bytes()).hexdigest() == item['sha256']:
            shutil.copy2(cached, archive)
    if not archive.exists():
        tmp = archive.with_suffix(archive.suffix + '.next')
        for attempt in range(3):
            try:
                subprocess.run(['curl', '--fail', '--location', '--retry', '2', '--connect-timeout', '20', '--max-time', '180', '--silent', '--show-error', '--output', str(tmp), item['url']], check=True)
                if hashlib.sha256(tmp.read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError('Archive checksum mismatch: ' + archive.name)
                tmp.replace(archive)
                break
            except Exception:
                tmp.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(2)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
        raise SystemExit('Archive checksum mismatch: ' + archive.name)
    directory = root / item['directory']
    if not directory.is_dir():
        with tarfile.open(archive) as bundle:
            bundle.extractall(directory.parent, filter='data')
        if not directory.is_dir():
            raise SystemExit('Unexpected upstream directory: ' + archive.name)
# Preserve the old scripts' checked source manifest, generated from this lock.
sip = root / 'work/zte/voice/sip-deps'
(sip / 'sources.json').write_text(json.dumps([{'file': Path(i['path']).name, 'url': i['url'], 'sha256': i['sha256']} for i in lock if '/sip-deps/' in i['path']], indent=2) + '\n')
pj = root / 'work/zte/voice/sip-deps/pjproject-2.17'
if not pj.exists():
    with tarfile.open(root / 'work/zte/voice/pjproject/pjproject-2.17.tar.gz') as bundle:
        bundle.extractall(pj.parent, filter='data')
print('PASS all nine upstream archive hashes and source trees.')

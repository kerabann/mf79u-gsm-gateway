"""Verified RAM uploads in small sync requests for the modem's old adbd."""
import gzip
import hashlib
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import uuid


def ram_push(adb, local, remote):
    if not remote.startswith('/dev/.mf79u-') or '/' in remote[5:]:
        raise ValueError('Upload destination must be an MF79U RAM file')
    data = Path(local).read_bytes()
    expected = hashlib.md5(data).hexdigest()
    current = subprocess.check_output(adb + ['shell', 'md5sum ' + shlex.quote(remote)],
                                      timeout=12).decode()
    if current.split()[:1] == [expected]:
        return
    prefix = '/dev/.mf79u-transfer-' + uuid.uuid4().hex[:12]
    stage = prefix + '-out'
    parts = []
    try:
        packed = gzip.compress(data)
        with tempfile.TemporaryDirectory(prefix='mf79u-transfer-') as temporary:
            part = Path(temporary) / 'part'
            for index, start in enumerate(range(0, len(packed), 4096)):
                destination = prefix + '-' + str(index).zfill(6)
                parts.append(destination)
                part.write_bytes(packed[start:start + 4096])
                for attempt in range(3):
                    result = subprocess.run(adb + ['push', '-Z', str(part), destination],
                                            capture_output=True, timeout=12)
                    if result.returncode == 0:
                        break
                    if attempt == 2:
                        raise RuntimeError('RAM upload failed after three sync attempts')
                    subprocess.run(adb + ['shell', 'rm -f ' + shlex.quote(destination)],
                                   check=True, capture_output=True, timeout=12)
                    time.sleep(.15)
        command = ('cat ' + shlex.quote(prefix) + '-[0-9]* | gzip -dc > ' +
                   shlex.quote(stage) + '; md5sum ' + shlex.quote(stage))
        result = subprocess.check_output(adb + ['shell', command], timeout=12).decode()
        if result.split()[:1] != [expected]:
            raise RuntimeError('RAM upload checksum mismatch')
        command = ('chmod 755 ' + shlex.quote(stage) + ' && mv ' + shlex.quote(stage) +
                   ' ' + shlex.quote(remote) + ' && echo MF79U_TRANSFER_OK')
        result = subprocess.check_output(adb + ['shell', command], timeout=12).decode()
        if 'MF79U_TRANSFER_OK' not in result:
            raise RuntimeError('Verified RAM upload was not installed')
    finally:
        subprocess.run(adb + ['shell', 'rm -f ' + shlex.quote(prefix) + '-*'],
                       capture_output=True, timeout=12)

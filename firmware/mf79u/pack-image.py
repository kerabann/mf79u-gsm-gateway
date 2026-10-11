#!/usr/bin/env python3
"""Package the verified, device-specific rootfs candidate; never flash a device."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
manifest = json.loads((BUILD / 'manifest.json').read_text())
version = manifest['version']
if version != 'mf79u-custom-0.9-experimental' or manifest['boot_tested']:
    raise SystemExit('Unexpected candidate stage; review packaging before release')
image = BUILD / 'rootfs.experimental.jffs2'
if hashlib.sha256(image.read_bytes()).hexdigest() != manifest['image']['sha256']:
    raise SystemExit('Rootfs changed after verification')
files = {
    'rootfs.experimental.jffs2': image,
    'manifest.json': BUILD / 'manifest.json',
    'native-cp-verification.json': BUILD / 'native-cp-verification.json',
    'standalone-verification.json': BUILD / 'standalone-verification.json',
    'AUTONOMOUS.md': HERE / 'AUTONOMOUS.md',
    'README.md': HERE / 'README.md',
}
content = {name: source.read_bytes() for name, source in files.items()}
content['SHA256SUMS'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                              for name, data in content.items()).encode()
target = BUILD / (version + '.tar.gz')
staged = target.with_suffix('.gz.next')
with staged.open('wb') as out, gzip.GzipFile(filename='', fileobj=out, mode='wb', mtime=0) as zipped:
    with tarfile.open(fileobj=zipped, mode='w') as archive:
        for name, data in content.items():
            member = tarfile.TarInfo(version + '/' + name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
with tarfile.open(staged, 'r:gz') as archive:
    for name, expected in content.items():
        actual = archive.extractfile(version + '/' + name).read()
        if actual != expected:
            raise SystemExit('Candidate package integrity check failed')
staged.replace(target)
print(f'Packaged {target.name}: {target.stat().st_size} bytes; no flash operations')

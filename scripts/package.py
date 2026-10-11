"""Deterministic overlay package: allowlisted runtime, recipes, hashes, no secrets."""
from pathlib import Path, PurePosixPath
import argparse
import gzip
import hashlib
import io
import json
import os
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / 'firmware/mf79u'
BUILD = FW / 'build'
DATA = '/mnt/userdata/mf79u'
ARTIFACTS = {
    '.mf79u-control': 'mf79u-control', '.mf79u-native-gateway': 'mf79u-native-gateway',
    '.mf79u-sip-gateway': 'modem-sip-gateway', '.mf79u-ims-userspace-ipsec.so': 'ims-userspace-ipsec.so',
    '.mf79u-net-led': 'mf79u-net-led', '.mf79u-cs-voice': 'mf79u-cs-voice',
    '.mf79u-cs-pcm-bridge': 'mf79u-cs-pcm-bridge', '.mf79u-cs-voice.ko': 'mf79u_cs_voice.ko',
    '.mf79u-vowifi-charon': 'mf79u-vowifi-charon', '.mf79u-vowifi-swanctl': 'mf79u-vowifi-swanctl',
    '.mf79u-vowifi-prepare': 'mf79u-vowifi-prepare', 'tools/busybox': 'busybox-extended',
    'tools/dropbearmulti': 'dropbearmulti', 'tools/system-imei': 'system-imei',
    'tools/sd-reread': 'sd-reread', 'tools/sd-backup-server': 'sd-backup-server',
}
SCRIPTS = {'start-control.sh': 'start-control-userdata.sh', 'start-native.sh': 'start-native.sh',
           'start-vowifi.sh': 'start-vowifi.sh', 'vowifi-updown.sh': 'vowifi-updown.sh', 'tools/ssh-shell': 'ssh-shell.sh'}
EXTRAS = {'helpers/detach-control': BUILD / 'detach-control', 'helpers/detach-native': BUILD / 'detach-native',
          'helpers/adb-boot': BUILD / 'mf79u-adb-boot', 'recipes/private-ims.json': FW / 'profiles/b03/private-ims-patch.json',
          'recipes/kernel-abi.json': FW / 'profiles/b03/kernel-abi.json',
          'recipes/boot-wait.html': FW / 'boot-wait.html'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files():
    output = {DATA.lstrip('/') + '/' + dest: (BUILD / source).read_bytes() for dest, source in ARTIFACTS.items()}
    output.update({DATA.lstrip('/') + '/' + dest: (FW / source).read_bytes() for dest, source in SCRIPTS.items()})
    output.update({dest: source.read_bytes() for dest, source in EXTRAS.items()})
    names = ['.mf79u-cs-voice', '.mf79u-cs-pcm-bridge', '.mf79u-cs-voice.ko']
    checksums = ''.join(hashlib.md5(output[DATA.lstrip('/') + '/' + n]).hexdigest() + '  ' + n + '\n' for n in names)
    output[DATA.lstrip('/') + '/cs-runtime.md5'] = checksums.encode()
    return output


def check(path):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate package member')
        for member in members:
            p = PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or not member.isfile():
                raise ValueError('Unsafe package member')
        manifest = json.load(archive.extractfile('manifest.json'))
        expected = set(manifest['files']) | {'manifest.json'}
        if set(names) != expected:
            raise ValueError('Unexpected package file')
        allow = {DATA.lstrip('/') + '/' + name for name in set(ARTIFACTS) | set(SCRIPTS) | {'cs-runtime.md5'}} | set(EXTRAS)
        if set(manifest['files']) != allow:
            raise ValueError('Incomplete runtime or unexpected payload')
        for name, metadata in manifest['files'].items():
            data = archive.extractfile(name).read()
            if sha(data) != metadata['sha256'] or len(data) != metadata['bytes']:
                raise ValueError('Package checksum mismatch: ' + name)
        if manifest['pcm'] != {'format': 's16le', 'channels': 1, 'rate': 16000, 'samples': 320}:
            raise ValueError('PCM contract changed')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    dist = ROOT / 'dist'
    path = ROOT / os.environ.get('PACKAGE', 'dist/mf79u-gateway.tar.gz') if args.check else dist / 'mf79u-gateway.tar.gz'
    if args.check:
        manifest = check(path)
        print('PASS package hashes, complete', len(manifest['files']), 'file allowlist, path safety and PCM contract.')
        return
    output = files()
    # Link-only SDK/vendor dumps/configuration never appear in this allowlist.
    manifest = {'schema': 1, 'device': 'MF79U B03', 'delivery': 'userdata-overlay',
                'pcm': {'format': 's16le', 'channels': 1, 'rate': 16000, 'samples': 320},
                'vendor_binary_included': False, 'private_ims': 'derive on installer host from the checksum-verified device binary',
                'files': {name: {'sha256': sha(data), 'md5': hashlib.md5(data).hexdigest(), 'bytes': len(data),
                                 'mode': 0o600 if name.endswith(('.json', '.md5', '.html')) else 0o700} for name, data in sorted(output.items())}}
    output['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    dist.mkdir(exist_ok=True)
    with path.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as archive:
        for name, data in sorted(output.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = manifest['files'].get(name, {}).get('mode', 0o600)
            member.mtime = 0
            archive.addfile(member, io.BytesIO(data))
    (dist / 'manifest.json').write_bytes(output['manifest.json'])
    (dist / 'SHA256SUMS').write_text(sha(path.read_bytes()) + '  ' + path.name + '\n')
    check(path)
    print('PASS deterministic complete overlay:', len(manifest['files']), 'files,', path.stat().st_size, 'compressed bytes.')


if __name__ == '__main__':
    main()

"""Offline package rejection and installation preflight/order regressions."""
from pathlib import Path
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import tarfile
from unittest import mock
import device
import package

# Exercise a real Git index: untracked helpers and unstaged edits must never
# make a publication checkout pass when they are absent from the next commit.
spec = importlib.util.spec_from_file_location('clean_checkout_fixture', Path(__file__).with_name('clean-checkout.py'))
clean_checkout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clean_checkout)
with tempfile.TemporaryDirectory(prefix='mf79u-checkout-test-') as directory:
    base = Path(directory)
    repo = base / 'repo'
    subprocess.run(['git', 'init', '--quiet', str(repo)], check=True)
    (repo / 'tracked.txt').write_text('staged source\n')
    subprocess.run(['git', 'add', 'tracked.txt'], cwd=repo, check=True)
    (repo / 'tracked.txt').write_text('unstaged source\n')
    (repo / 'untracked.py').write_text('untracked helper\n')
    first = base / 'first'
    clean_checkout.export_index(repo, first)
    assert (first / 'tracked.txt').read_text() == 'staged source\n'
    assert not (first / 'untracked.py').exists()
    subprocess.run(['git', 'add', 'untracked.py'], cwd=repo, check=True)
    second = base / 'second'
    clean_checkout.export_index(repo, second)
    assert (second / 'untracked.py').read_text() == 'untracked helper\n'
    assert (second / 'tracked.txt').read_text() == 'staged source\n'
print('PASS clean checkout uses staged Git contents; untracked files and unstaged edits excluded.')

# A real complete allowlist with tiny synthetic contents, no build dependency.
names = {package.DATA.lstrip('/') + '/' + p for p in set(package.ARTIFACTS) | set(package.SCRIPTS) | {'cs-runtime.md5'}} | set(package.EXTRAS)
contents = {name: b'isolated fixture\n' for name in names}
manifest = {'pcm': {'format': 's16le', 'channels': 1, 'rate': 16000, 'samples': 320},
            'files': {n: {'sha256': hashlib.sha256(v).hexdigest(), 'bytes': len(v)} for n, v in contents.items()}}

def archive(path, data, info, extra=None):
    entries = dict(data, **{'manifest.json': json.dumps(info).encode()})
    with tarfile.open(path, 'w:gz') as output:
        for name, value in list(entries.items()) + (extra or []):
            member = tarfile.TarInfo(name)
            member.size = len(value)
            output.addfile(member, io.BytesIO(value))

with tempfile.TemporaryDirectory(prefix='mf79u-workflow-test-') as directory:
    path = Path(directory) / 'fixture.tar.gz'
    archive(path, contents, manifest)
    assert package.check(path)['pcm']['samples'] == 320
    cases = ['corrupt', 'missing', 'extra', 'traversal', 'duplicate', 'pcm']
    for case in cases:
        data = dict(contents)
        info = json.loads(json.dumps(manifest))
        extra = None
        name = next(iter(data))
        if case == 'corrupt':
            data[name] = b'changed'
        elif case == 'missing':
            del data[name]; del info['files'][name]
        elif case == 'extra':
            data['unreviewed.so'] = b'extra'
        elif case == 'traversal':
            extra = [('../outside', b'unsafe')]
        elif case == 'duplicate':
            extra = [(name, data[name])]
        elif case == 'pcm':
            info['pcm']['rate'] = 8000
        archive(path, data, info, extra)
        try:
            package.check(path)
        except (ValueError, KeyError):
            pass
        else:
            raise AssertionError('Unsafe package accepted: ' + case)

# Largest compressed replacement happens while the disk is emptiest; shrinking
# files earn no credit, BusyBox's old inode remains until the atomic rename.
large = bytes(range(256)) * 4096
small = b'x' * 2048
changed = {device.DATA + '/later': small, device.DATA + '/first': large}
sizes = {n: {'oldBytes': len(v), 'newBytes': len(v)} for n, v in changed.items()}
ordered, needed = device.storage_plan(changed, sizes)
assert next(iter(ordered)).endswith('/first')
assert needed == len(gzip.compress(large, 9, mtime=0)) + 512 * 1024
bb = device.DATA + '/tools/busybox'
_, need_bb = device.storage_plan({bb: small}, {bb: {'oldBytes': len(small)}})
assert need_bb == len(small) + len(gzip.compress(small, 9, mtime=0)) + 512 * 1024

# Low space or a transfer bind failure must not stop any running modem service.
files = {'helpers/detach-control': b'fixture'}
with mock.patch.object(device, 'plan', return_value=({'/unused': b'data'}, files, {'spaceAvailable': False})), mock.patch.object(device, 'stop_owned') as stop:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            device.install()
    except RuntimeError as error:
        assert 'Insufficient userdata' in str(error)
    else:
        raise AssertionError('Low-space installation proceeded')
    stop.assert_not_called()

with tempfile.TemporaryDirectory(prefix='mf79u-install-test-') as directory, mock.patch.object(device, 'ROOT', Path(directory)), mock.patch.object(device, 'plan', return_value=({device.DATA + '/.mf79u-control': b'new'}, files, {'spaceAvailable': True})), mock.patch.object(device, 'hash_remote', return_value=None), mock.patch.object(device, 'idle'), mock.patch.object(device, 'shell', return_value=''), mock.patch.object(device, 'server', side_effect=OSError('isolated bind failure')), mock.patch.object(device, 'stop_owned') as stop:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            device.install()
    except OSError:
        pass
    else:
        raise AssertionError('Failed transfer setup proceeded')
    stop.assert_not_called()

# A failed remote probe cannot be mistaken for success by legacy ADB shells.
with tempfile.TemporaryDirectory(prefix='mf79u-transfer-test-') as directory, mock.patch.object(device, 'ROOT', Path(directory)), mock.patch.object(device, 'plan', return_value=({device.DATA + '/.mf79u-control': b'new'}, files, {'spaceAvailable': True})), mock.patch.object(device, 'hash_remote', return_value=None), mock.patch.object(device, 'idle'), mock.patch.object(device, 'shell', return_value=''), mock.patch.object(device, 'server', return_value=contextlib.nullcontext('http://127.0.0.1:1')), mock.patch.object(device, 'stop_owned') as stop:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            device.install()
    except RuntimeError as error:
        assert 'cannot fetch' in str(error)
    else:
        raise AssertionError('Failed remote transfer probe proceeded')
    stop.assert_not_called()

for output in ['"State": "queued"\nMF79U_SMS_CHECKED', 'unreadable state']:
    with mock.patch.object(device, 'status', return_value=({}, {})), mock.patch.object(device, 'shell', return_value=output):
        try:
            device.idle()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Pending/unverifiable SMS state accepted')
with mock.patch.object(device, 'shell', side_effect=['LOADED', '']):
    try:
        device.loaded_driver()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Unknown loaded CS driver accepted')

print('PASS package allowlist/corruption/traversal/duplicates/PCM, staging bounds, low-space and transfer preflight rejection; no device access.')

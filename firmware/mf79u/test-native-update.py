#!/usr/bin/env python3
"""Updater refusal paths must stop before transferring or stopping services."""
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import tempfile

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_update_fixture', BASE / 'install-native-update.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)
previous = b'previous native fixture'
digest = hashlib.md5(previous).hexdigest()

for failure in ['active_call', 'wrong_executable', 'wrong_parent', 'no_staging_space', 'call_during_staging']:
    calls, transfers = [], []

    def shell(command):
        calls.append(command)
        if command == 'cat /dev/.mf79u-native-status.json':
            return json.dumps({'pid': 42, 'callBackend': 'none'})
        if command == 'cat /dev/.mf79u-gateway-status.json':
            return json.dumps({'activeCall': failure == 'active_call' or (failure == 'call_during_staging' and len(transfers) == 2)})
        if command == 'cat /dev/.mf79u-native-supervisor.pid':
            return '33'
        if command.startswith('md5sum '):
            if '.mf79u-native.update-next' in command:
                return hashlib.md5(b'candidate fixture').hexdigest() + ' fixture'
            if failure == 'wrong_executable' and '/proc/' in command:
                return '0' * 32 + ' fixture'
            return digest + ' fixture'
        if command == 'cat /proc/42/stat':
            return '42 (native fixture) S ' + ('32' if failure == 'wrong_parent' else '33')
        if command.startswith('grep -F -q start-native.sh '):
            return 'OWNED'
        if command == 'cat /proc/sys/kernel/random/boot_id':
            return 'fixture-boot'
        if 'gzip -c ' in command:
            return base64.b64encode(gzip.compress(previous)).decode()
        if command.startswith('df -k '):
            return 'Filesystem 1K-blocks Used Available Use% Mounted\nfixture 100 100 ' + ('0' if failure == 'no_staging_space' else '10000') + ' 100% /fixture'
        if command.startswith('set -e; ') or command == 'chmod 700 /dev/.mf79u-native-update-start':
            return ''
        raise AssertionError('Unexpected device operation before a failed guard')

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        base = root / 'firmware/mf79u'
        (base / 'build').mkdir(parents=True)
        (base / 'build/mf79u-native-gateway').write_bytes(b'candidate fixture')
        with patch.object(update, 'ROOT', root), patch.object(update, 'BASE', base), \
             patch.object(update, 'shell', shell), patch.object(update, 'push', lambda *args: transfers.append(args)), \
             patch('sys.argv', ['fixture', '--install']):
            try:
                update.main()
            except RuntimeError:
                pass
            else:
                raise AssertionError('Updater accepted ' + failure)
        assert not any(command.startswith('kill ') for command in calls)
        assert len(transfers) == (2 if failure == 'call_during_staging' else 0)

print('PASS native-only updater: call, executable/owner, staging-space and late-call guards refuse before shutdown')

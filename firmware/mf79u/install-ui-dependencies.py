#!/usr/bin/env python3
"""Restore missing System executables; never enable SSH or replace other builds."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = '/mnt/userdata/mf79u'
spec = importlib.util.spec_from_file_location('ui_transfer', HERE / 'device-transfer.py')
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
shell = transfer.shell


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore-missing', action='store_true')
    args = parser.parse_args()
    before = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    gateway = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
    if gateway.get('activeCall') or before.get('callBackend', 'none') != 'none':
        raise RuntimeError('Wait until the call ends')
    settings = shell('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini')
    artifacts = {'dropbearmulti': HERE / 'build/dropbearmulti',
                 'ssh-shell': HERE / 'ssh-shell.sh'}
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'restored': [], 'present': [], 'missing': [], 'sshEnabledByInstaller': False}
    for name, source in artifacts.items():
        target = DATA + '/tools/' + name
        if shell('test -x ' + target + ' && echo READY') == 'READY':
            report['present'].append(name)
            continue
        report['missing'].append(name)
        if not args.restore_missing:
            continue
        expected = hashlib.md5(source.read_bytes()).hexdigest()
        if shell('test -e ' + target + ' && echo EXISTS') == 'EXISTS':
            if shell('md5sum ' + target).split()[0] != expected:
                raise RuntimeError('Unexpected non-executable System artifact; refusing replacement')
            shell('chmod 700 ' + target)
        else:
            transfer.push(source, target + '.ui-next')
            shell('set -e; chmod 700 ' + target + '.ui-next; mv ' + target + '.ui-next ' + target + '; sync')
        if shell('md5sum ' + target).split()[0] != expected:
            raise RuntimeError('System artifact verification failed')
        report['restored'].append(name)
    for name in ['dropbear', 'dropbearkey']:
        target = DATA + '/tools/' + name
        existing = shell('readlink ' + target + ' 2>/dev/null || true')
        if existing == 'dropbearmulti':
            continue
        if shell('test -e ' + target + ' -o -L ' + target + ' && echo EXISTS') == 'EXISTS':
            raise RuntimeError('Unexpected System executable link; refusing replacement')
        report['missing'].append(name)
        if args.restore_missing:
            shell('ln -s dropbearmulti ' + target)
            report['restored'].append(name)
    if args.restore_missing:
        shell('set -e; mkdir -p ' + DATA + '/ssh-home ' + DATA + '/tools/bin; chmod 700 ' + DATA + '/ssh-home; ' + DATA + '/tools/busybox --install -s ' + DATA + '/tools/bin')
    after = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    report['nativeSipPreserved'] = all(before[k] == after[k] for k in ['pid', 'sipPid'])
    report['settingsPreserved'] = settings == shell('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini')
    if not report['nativeSipPreserved'] or not report['settingsPreserved']:
        raise RuntimeError('Device state changed during dependency recovery')
    (ROOT / 'reports/ui-dependencies.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

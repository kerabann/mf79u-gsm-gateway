#!/usr/bin/env python3
"""Guarded native update, optionally shared-INI SIP parser; preserve settings/media."""
import argparse
import base64
import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
DATA = '/mnt/userdata/mf79u'
spec = importlib.util.spec_from_file_location('native_update_transfer', BASE / 'device-transfer.py')
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
shell, push = transfer.shell, transfer.push


def checksum(path):
    return shell('md5sum ' + path).split()[0]

def ring_guard_present():
    return shell('test ! -e ' + DATA + '/native-ring-only || echo PRESENT') == 'PRESENT'


def wait_exit(pid):
    for _ in range(240):
        if shell('test -e /proc/' + str(pid) + '/exe && echo PRESENT') != 'PRESENT':
            return
        time.sleep(.5)
    raise RuntimeError('Owned native/supervisor cleanup did not finish')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--with-sip', action='store_true', help='Also install the SIP binary for a new shared-INI mode; preserve IMS media and CS driver')
    parser.add_argument('--ring-only', action='store_true', help='Enable persistent dial/answer protection for a roaming registration-only check')
    args = parser.parse_args()
    candidate = BASE / 'build/mf79u-native-gateway'
    if not args.install:
        print('Prepared native controller update; use --install within authorized idle device scope.')
        return
    native = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    gateway = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
    if native.get('callBackend', 'none') != 'none' or gateway.get('activeCall'):
        raise RuntimeError('Native controller update requires an idle modem')
    pid = int(native['pid'])
    parent = int(shell('cat /dev/.mf79u-native-supervisor.pid'))
    oldhash = checksum(DATA + '/.mf79u-native-gateway')
    if pid < 2 or parent < 2 or checksum('/proc/' + str(pid) + '/exe') != oldhash:
        raise RuntimeError('Unexpected native executable')
    stat = shell('cat /proc/' + str(pid) + '/stat').rsplit(')', 1)[-1].split()
    if int(stat[1]) != parent or shell('grep -F -q start-native.sh /proc/' + str(parent) + '/cmdline && echo OWNED') != 'OWNED':
        raise RuntimeError('Unexpected native supervisor owner')
    boot = shell('cat /proc/sys/kernel/random/boot_id')
    sip_candidate = BASE / 'build/modem-sip-gateway'
    sip_hash = checksum(DATA + '/.mf79u-sip-gateway') if args.with_sip else None
    if args.with_sip and (not sip_candidate.is_file() or checksum('/proc/' + str(native['sipPid']) + '/exe') != sip_hash):
        raise RuntimeError('SIP candidate missing or unexpected installed SIP executable')
    if args.ring_only and not ring_guard_present():
        shell('set -e; umask 077; touch ' + DATA + '/native-ring-only')
    guard = ring_guard_present()
    protected = [DATA + '/' + name for name in ['settings.json', 'gateway.ini', '.mf79u-cs-voice',
                 '.mf79u-cs-pcm-bridge', '.mf79u-cs-voice.ko', '.mf79u-sip-gateway', '.mf79u-volte-private',
                 '.mf79u-ims-userspace-ipsec.so']]
    if guard:
        protected.append(DATA + '/native-ring-only')
    before = shell('md5sum ' + ' '.join(protected))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'private/backups' / ('native-update-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    encoded = shell(DATA + '/tools/busybox gzip -c ' + DATA + '/.mf79u-native-gateway | ' + DATA + '/tools/busybox base64')
    old = backup / 'mf79u-native-gateway'
    old.write_bytes(gzip.decompress(base64.b64decode(encoded)))
    old.chmod(0o600)
    if hashlib.md5(old.read_bytes()).hexdigest() != oldhash:
        raise RuntimeError('Native backup checksum mismatch')
    sip_packed = None
    if args.with_sip:
        encoded = shell(DATA + '/tools/busybox gzip -c ' + DATA + '/.mf79u-sip-gateway | ' + DATA + '/tools/busybox base64')
        sip_old = backup / 'modem-sip-gateway'
        sip_old.write_bytes(gzip.decompress(base64.b64decode(encoded)))
        sip_old.chmod(0o600)
        if hashlib.md5(sip_old.read_bytes()).hexdigest() != sip_hash:
            raise RuntimeError('SIP backup checksum mismatch')
        sip_packed = backup / 'sip-candidate.gz'
        sip_packed.write_bytes(gzip.compress(sip_candidate.read_bytes(), 9, mtime=0))
        sip_packed.chmod(0o600)
    packed = backup / 'candidate.gz'
    packed.write_bytes(gzip.compress(candidate.read_bytes(), 9, mtime=0))
    packed.chmod(0o600)
    required = candidate.stat().st_size + packed.stat().st_size + (sip_packed.stat().st_size if sip_packed else 0) + 65536
    free = int(shell('df -k ' + DATA).splitlines()[-1].split()[3]) * 1024
    if free < required:
        raise RuntimeError('Insufficient staging space; services remain running')
    push(packed, DATA + '/.mf79u-native.update.gz')
    if sip_packed:
        push(sip_packed, DATA + '/.mf79u-sip.update.gz')
    digest = hashlib.md5(candidate.read_bytes()).hexdigest()
    shell('set -e; ' + DATA + '/tools/busybox gzip -dc ' + DATA + '/.mf79u-native.update.gz > ' + DATA + '/.mf79u-native.update-next; chmod 700 ' + DATA + '/.mf79u-native.update-next')
    if checksum(DATA + '/.mf79u-native.update-next') != digest:
        raise RuntimeError('Staged native checksum mismatch; services remain running')
    push(BASE / 'build/detach-native', '/dev/.mf79u-native-update-start')
    shell('chmod 700 /dev/.mf79u-native-update-start')
    # A call or another update may begin while the candidate is transferred.
    current = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    gateway = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
    if current.get('callBackend', 'none') != 'none' or gateway.get('activeCall'):
        raise RuntimeError('A call began during staging; services remain running')
    if current.get('pid') != pid or current.get('sipPid') != native.get('sipPid') or \
       shell('cat /dev/.mf79u-native-supervisor.pid') != str(parent) or \
       ring_guard_present() != guard or \
       checksum('/proc/' + str(pid) + '/exe') != oldhash or \
       before != shell('md5sum ' + ' '.join(protected)):
        raise RuntimeError('Runtime or protected settings changed during staging; refusing shutdown')
    # The supervisor trap terminates its exact child and waits for owned cleanup.
    shell('kill -TERM ' + str(parent))
    wait_exit(pid)
    wait_exit(parent)
    if args.with_sip:
        wait_exit(native['sipPid'])
        sip_digest = hashlib.md5(sip_candidate.read_bytes()).hexdigest()
        try:
            # The old child has exited, freeing its inode. Expand one checked
            # backed-up executable at a time on the small userdata volume.
            shell('set -e; rm -f ' + DATA + '/.mf79u-sip-gateway; ' + DATA + '/tools/busybox gzip -dc ' + DATA + '/.mf79u-sip.update.gz > ' + DATA + '/.mf79u-sip.update-next; chmod 700 ' + DATA + '/.mf79u-sip.update-next')
            if checksum(DATA + '/.mf79u-sip.update-next') != sip_digest:
                raise RuntimeError('Staged SIP checksum mismatch')
            shell('set -e; mv ' + DATA + '/.mf79u-sip.update-next ' + DATA + '/.mf79u-sip-gateway; rm -f ' + DATA + '/.mf79u-sip.update.gz; sync')
        except Exception:
            restore = backup / 'sip-restore.gz'
            restore.write_bytes(gzip.compress(sip_old.read_bytes(), 9, mtime=0))
            restore.chmod(0o600)
            push(restore, DATA + '/.mf79u-sip.restore.gz')
            shell('set -e; rm -f ' + DATA + '/.mf79u-sip.update-next; ' + DATA + '/tools/busybox gzip -dc ' + DATA + '/.mf79u-sip.restore.gz > ' + DATA + '/.mf79u-sip-gateway; chmod 700 ' + DATA + '/.mf79u-sip-gateway; rm -f ' + DATA + '/.mf79u-sip.restore.gz; /dev/.mf79u-native-update-start')
            raise
    shell('set -e; mv ' + DATA + '/.mf79u-native.update-next ' + DATA + '/.mf79u-native-gateway; sync; /dev/.mf79u-native-update-start; rm -f /dev/.mf79u-native-update-start ' + DATA + '/.mf79u-native.update.gz')
    for _ in range(120):
        current = json.loads(shell('cat /dev/.mf79u-native-status.json'))
        if current.get('pid') != pid and current.get('voiceReady'):
            break
        time.sleep(1)
    else:
        raise RuntimeError('Updated native controller did not become voice ready; checked backup retained')
    after = shell('md5sum ' + ' '.join(protected))
    if args.with_sip:
        if checksum('/proc/' + str(current['sipPid']) + '/exe') != sip_digest:
            raise RuntimeError('Updated SIP process differs from the candidate')
        after = after.replace(sip_digest + '  ' + DATA + '/.mf79u-sip-gateway', sip_hash + '  ' + DATA + '/.mf79u-sip-gateway')
    if before != after or boot != shell('cat /proc/sys/kernel/random/boot_id') or ring_guard_present() != guard:
        raise RuntimeError('Protected artifact, settings or boot changed')
    if checksum('/proc/' + str(current['pid']) + '/exe') != digest:
        raise RuntimeError('Updated native process differs from the candidate')
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'nativeMD5': digest,
              'nativePid': current['pid'], 'sipPid': current.get('sipPid'), 'voiceMode': current.get('voiceMode'),
              'voiceBackend': current.get('voiceBackend'), 'voiceReady': current.get('voiceReady'),
              'ringOnlyGuard': guard,
              'sipUpdated': args.with_sip, 'sipMD5': sip_digest if args.with_sip else None,
              'bootSettingsMediaDriverPreserved': True, 'realCallsSmsMade': False,
              'backup': str(backup.relative_to(ROOT))}
    (ROOT / 'reports/native-update-install.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

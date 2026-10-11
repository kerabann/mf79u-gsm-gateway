#!/usr/bin/env python3
"""Guarded SMS-status Control/SIP update; public binary backups, no reboot/flash."""
import base64, datetime, gzip, hashlib, importlib.util, json, re, subprocess, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / 'build'
DATA = '/mnt/userdata/mf79u'
BB = DATA + '/tools/busybox'
ADB = [str(ROOT / 'outputs/adb')]
spec = importlib.util.spec_from_file_location('transfer', HERE / 'device-transfer.py')
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
sh, push = transfer.shell, transfer.push
backup = BUILD / ('pre-sms-status-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(mode=0o700)
artifacts = {'.mf79u-control': 'mf79u-control', '.mf79u-sip-gateway': 'modem-sip-gateway'}
def md5(data): return hashlib.md5(data).hexdigest()
def status(): return json.loads(sh('cat /dev/.mf79u-native-status.json'))
def idle():
    s = status()
    g = json.loads(sh('cat /dev/.mf79u-gateway-status.json'))
    assert s['callBackend'] == 'none' and not g['activeCall'], 'Active call'
    assert not sh(BB + " grep -o '\"State\":\"\\(queued\\|sending\\)\"' " + DATA + '/sms-sip-state.json'), 'SMS in progress'
    return s
before = idle()
boot = sh('cat /proc/sys/kernel/random/boot_id')
settings = sh('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini')
hashes = {}
for remote, local in artifacts.items():
    expected = sh('md5sum ' + DATA + '/' + remote).split()[0]
    raw = gzip.decompress(base64.b64decode(sh(BB + ' gzip -c ' + DATA + '/' + remote + ' | ' + BB + ' base64')))
    assert md5(raw) == expected
    (backup / local).write_bytes(raw)
    (backup / local).chmod(0o700)
    hashes[local] = expected
(backup / 'checksums.json').write_text(json.dumps(hashes, indent=2) + '\n')
# Stage only compressed public artifacts. Keep uncompressed RAM at zero.
for remote, local in artifacts.items():
    packed = backup / (local + '.next.gz')
    packed.write_bytes(gzip.compress((BUILD / local).read_bytes(), 9, mtime=0))
    push(packed, DATA + '/' + remote + '.sms-next.gz')
idle()
supervisor = int(sh('cat /dev/.mf79u-native-supervisor.pid'))
control = int(sh('cat /dev/.mf79u-control.pid'))
assert supervisor > 1 and control > 1
assert 'start-native.sh' in sh('cat /proc/' + str(supervisor) + '/cmdline')
assert sh('test /proc/' + str(control) + '/exe -ef ' + DATA + '/.mf79u-control && echo OWNED') == 'OWNED'
def wait_exit(pid):
    for _ in range(120):
        if not sh(BB + ' readlink /proc/' + str(pid) + '/exe'): return
        time.sleep(.25)
    raise RuntimeError('Owned process failed to stop')
sh('kill -TERM ' + str(supervisor))
wait_exit(supervisor)
wait_exit(before['pid'])
wait_exit(before['sipPid'])
sh('kill -TERM ' + str(control))
wait_exit(control)
# All old processes exited; remove one backed-up executable before expansion.
# Keeping the old inode plus both compressed candidates exceeds 24MiB userdata.
installed = {}
try:
    for remote, local in artifacts.items():
        expected = md5((BUILD / local).read_bytes())
        sh('set -e; rm -f ' + DATA + '/' + remote + '; gzip -dc ' + DATA + '/' + remote + '.sms-next.gz > ' + DATA + '/' + remote + '.sms-next; chmod 700 ' + DATA + '/' + remote + '.sms-next')
        assert sh('md5sum ' + DATA + '/' + remote + '.sms-next').split()[0] == expected
        sh('mv ' + DATA + '/' + remote + '.sms-next ' + DATA + '/' + remote + '; rm -f ' + DATA + '/' + remote + '.sms-next.gz; sync')
        installed[local] = expected
except Exception:
    for remote, local in artifacts.items():
        if sh('md5sum ' + DATA + '/' + remote).split()[:1] == [hashes[local]]:
            continue
        sh('rm -f ' + DATA + '/' + remote + ' ' + DATA + '/' + remote + '.sms-next ' + DATA + '/' + remote + '.sms-next.gz')
        packed = backup / (local + '.restore.gz')
        packed.write_bytes(gzip.compress((backup / local).read_bytes(), 9, mtime=0))
        push(packed, DATA + '/' + remote + '.sms-restore.gz')
        sh('gzip -dc ' + DATA + '/' + remote + '.sms-restore.gz > ' + DATA + '/' + remote + '.restore; chmod 700 ' + DATA + '/' + remote + '.restore; mv ' + DATA + '/' + remote + '.restore ' + DATA + '/' + remote + '; rm -f ' + DATA + '/' + remote + '.sms-restore.gz')
    raise
finally:
    # Existing reviewed double-fork helper; wrapper starts native as its child.
    push(BUILD / 'detach-control', '/dev/.mf79u-sms-detach-control')
    sh('chmod 700 /dev/.mf79u-sms-detach-control; /dev/.mf79u-sms-detach-control; rm -f /dev/.mf79u-sms-detach-control')
print('Control/SIP installed; waiting for autonomous IMS/SIP recovery.', flush=True)
start = last = time.monotonic()
while time.monotonic() - start < 180:
    try:
        s = status()
        g = json.loads(sh('cat /dev/.mf79u-gateway-status.json'))
        if s.get('imsReady') and g.get('running') and g.get('voiceReady') and s.get('pid') != before['pid'] and g.get('pid') != before['sipPid']:
            assert sh('test /proc/' + str(g['pid']) + '/exe -ef ' + DATA + '/.mf79u-sip-gateway && echo OWNED') == 'OWNED'
            break
    except (subprocess.SubprocessError, json.JSONDecodeError): pass
    if time.monotonic() - last > 30:
        print('Waiting for IMS/SIP recovery.', flush=True); last = time.monotonic()
    time.sleep(2)
else: raise RuntimeError('IMS/SIP recovery timeout; installed backups preserved')
assert sh('cat /proc/sys/kernel/random/boot_id') == boot
assert sh('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini') == settings
assert sh('md5sum ' + DATA + '/.mf79u-cs-voice.ko').split()[0] == 'b3440aadf8e7be2e2321d13e539ba078'
report = {'installedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'boot': boot,
          'artifacts': installed, 'backup': str(backup), 'settingsPreserved': True,
          'imsReady': s['imsReady'], 'imsAccess': s['imsAccess'], 'sipRunning': g['running'],
          'voiceReady': g['voiceReady'], 'role': g['role'], 'nativePid': s['pid'], 'sipPid': s['sipPid'],
          'softwareReboot': False, 'smsOrCallsInitiatedByInstaller': False, 'rawFlash': False}
(BUILD / 'sms-submission-status-install-20261011.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS same boot, original settings, IMS ready and SIP running.', flush=True)

#!/usr/bin/env python3
"""Read-only sanitized Webhooks install receipt; never sends SMS or Telegram."""
from pathlib import Path
import argparse
import hashlib
import gzip
import json
import os
import subprocess
import urllib.request

root = Path(__file__).resolve().parents[2]
data = '/mnt/userdata/mf79u'
adb = [os.environ.get('ADB', 'adb')]


def shell(command):
    result = subprocess.run(adb + ['shell', command], capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Device check failed; private output omitted')
    return result.stdout.replace(b'\r', b'').strip()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--after', action='store_true')
parser.add_argument('--report-prefix', default='telegram-device')
args = parser.parse_args()
if not args.report_prefix.replace('-', '').isalnum():
    raise SystemExit('Use an alphanumeric report prefix')
native = json.loads(shell('cat /dev/.mf79u-native-status.json'))
sip = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
settings = shell('cat ' + data + '/settings.json')
config = json.loads(settings).get('webhooks', {}).get('telegramSMS', {})
free_kib = int(shell(data + '/tools/busybox df -k ' + data).decode().splitlines()[-1].split()[3])
old_bytes = int(shell(data + '/tools/busybox stat -c %s ' + data + '/.mf79u-control'))
candidate_bytes = (root / 'firmware/mf79u/build/mf79u-control').read_bytes()
required_bytes = len(gzip.compress(candidate_bytes, 9, mtime=0)) + max(0, len(candidate_bytes)-old_bytes) + 512*1024
receipt = {
    'boot': shell('cat /proc/sys/kernel/random/boot_id').decode(),
    'nativePid': native.get('pid'), 'sipPid': sip.get('pid'),
    'controlPid': int(shell('cat /dev/.mf79u-control.pid')),
    'imsReady': native.get('imsReady'), 'imsAccess': native.get('imsAccess'),
    'voiceReady': sip.get('voiceReady'),
    'sipLocalRegistered': bool(sip.get('localRegistered')),
    'activeCall': bool(sip.get('activeCall')) or native.get('callBackend', 'none') != 'none',
    'settingsHash': hashlib.sha256(settings).hexdigest(),
    'gatewayHash': hashlib.sha256(shell('cat ' + data + '/gateway.ini')).hexdigest(),
    'ringOnly': shell('test ! -e ' + data + '/native-ring-only || echo YES') == b'YES',
    'telegramConfigured': bool(config.get('botToken') and config.get('chatId')),
    'telegramEnabled': bool(config.get('enabled')),
    'systemRootsPresent': shell('test -s /etc/ssl/certs/ca-certificates.crt && echo YES') == b'YES',
    'controlStageSpaceOK': free_kib*1024 >= required_bytes,
    'realTelegramOrSMS': False,
}
out = root / ('reports/' + args.report_prefix + ('-after.json' if args.after else '-before.json'))
if args.after:
    before = json.loads((root / ('reports/' + args.report_prefix + '-before.json')).read_text())
    for key in ['boot', 'nativePid', 'sipPid', 'settingsHash', 'gatewayHash', 'ringOnly']:
        receipt[key + 'Preserved'] = receipt[key] == before[key]
    receipt['controlUpdated'] = receipt['controlPid'] != before['controlPid']
    receipt['sipBindingPreserved'] = not before.get('sipLocalRegistered') or receipt['sipLocalRegistered']
    candidate = (root / 'firmware/mf79u/build/mf79u-control').read_bytes()
    actual = shell('md5sum ' + data + '/.mf79u-control').decode().split()[0]
    receipt['controlBinaryMatches'] = actual == hashlib.md5(candidate).hexdigest()
    receipt['assetsMatch'] = {}
    for name in ['index.html', 'app.js', 'system.js', 'sms-format.js', 'style.css']:
        served = urllib.request.urlopen('http://192.168.0.1/' + ('' if name == 'index.html' else name), timeout=10).read()
        receipt['assetsMatch'][name] = served == (root / 'firmware/mf79u/control/web' / name).read_bytes()
out.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: v for k, v in receipt.items() if k not in ['settingsHash', 'gatewayHash']}, indent=2))
if not args.after and (receipt['activeCall'] or not receipt['controlStageSpaceOK']):
    raise SystemExit('Control preflight failed; services remain running')
if args.after and (not all(v for k, v in receipt.items() if k.endswith('Preserved')) or
                   not receipt['controlBinaryMatches'] or not all(receipt['assetsMatch'].values()) or
                   not receipt['imsReady'] or not receipt['voiceReady']):
    raise SystemExit('Post-install verification failed; inspect the sanitized receipt')

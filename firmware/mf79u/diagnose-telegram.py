#!/usr/bin/env python3
"""Private Telegram/SMS inputs stay in process memory; output is metadata only."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

root = Path(__file__).resolve().parents[2]
data = '/mnt/userdata/mf79u'
adb = [os.environ.get('ADB', 'adb')]


def shell(command, timeout=30):
    result = subprocess.run(adb + ['shell', command], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Telegram diagnostic failed; raw device output omitted')
    return result.stdout.replace(b'\r', b'').strip()


def private_json(name):
    raw = shell('if [ -f ' + data + '/' + name + ' ]; then cat ' + data + '/' + name + '; fi')
    return json.loads(raw) if raw else {}


settings = private_json('settings.json')
c = settings.get('webhooks', {}).get('telegramSMS', {})
s = private_json('sms-telegram-state.json')
ims = private_json('sms-ims-state.json')
sip = private_json('sms-sip-state.json')
gateway = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
jobs = s.get('Jobs') or []
iface = c.get('interface', '')
interface_up = False
if re.fullmatch(r'bridge0|wlan0-vxd|wan[0-9]', iface):
    flags = shell('if [ -f /sys/class/net/' + iface + '/flags ]; then cat /sys/class/net/' + iface + '/flags; fi')
    interface_up = bool(flags and int(flags, 16) & 1)
routes = shell('ip route show').decode().splitlines()
resolver = shell('cat /etc/resolv.conf').decode()
report = {
    'enabled': bool(c.get('enabled')), 'tokenSet': bool(c.get('botToken')),
    'chatSet': bool(c.get('chatId')), 'interface': iface, 'interfaceUp': interface_up,
    'deleteAfterSend': bool(c.get('deleteAfterSend')),
    'ordinaryMobileDataEnabled': bool(settings.get('internetSharing')),
    'queueExists': bool(s), 'destinationMatches': s.get('Destination') == hashlib.sha256(c.get('chatId', '').encode()).hexdigest()[:32],
    'seenCount': len(s.get('Seen') or []), 'queued': len(jobs),
    'unsent': sum(not j.get('Sent') for j in jobs),
    'sentAwaitingDelete': sum(bool(j.get('Sent') and j.get('Delete')) for j in jobs),
    'delivered': s.get('Delivered', 0),
    'sipRole': gateway.get('role'),
    'sipLocalRegistered': bool(gateway.get('localRegistered')),
    'sipBufferedIncoming': len(sip.get('Inbox') or []),
    'sipAcknowledgedCount': len(sip.get('Delivered') or []),
    'imsIncoming': sum(m.get('Tag') in ['0', '1'] for m in (ims.get('Messages') or [])),
    'imsOutgoing': sum(m.get('Tag') in ['2', '3'] for m in (ims.get('Messages') or [])),
    'selectedInterfaceInternetRoute': any(line.split()[0] in ['default', '0.0.0.0/1', '128.0.0.0/1'] and 'dev ' + iface in line for line in routes) if iface else False,
    'dnsConfigured': any(line.strip().startswith('nameserver ') for line in resolver.splitlines()),
    'deviceTimeUTC': shell('date -u +%Y-%m-%dT%H:%M:%SZ').decode(),
    'readOnly': True,
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--installed-network', action='store_true', help='Use installed Control read-only DNS/TLS/getMe/getChat diagnostic; no sendMessage')
parser.add_argument('--report-prefix', default='telegram-diagnosis')
args = parser.parse_args()
if not args.report_prefix.replace('-', '').isalnum():
    raise SystemExit('Use an alphanumeric report prefix')
if args.installed_network:
    raw = shell('GOMAXPROCS=1 GOGC=20 GOMEMLIMIT=6MiB ' + data + '/.mf79u-control -native -telegram-diagnose', timeout=60)
    report['networkProbe'] = json.loads(raw)
out = root / ('reports/' + args.report_prefix + '.json')
out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

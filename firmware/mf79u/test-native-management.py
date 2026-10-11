#!/usr/bin/env python3
"""Owned firewall repair and LAN rollback integration; never mutates SMS or calls.

Reads the existing admin password from stdin. Requires idle voice and disabled
Wi-Fi uplink, and retains 192.168.0.1 throughout the temporary LAN-alias test.
"""
import copy
import http.cookiejar
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = 'http://192.168.0.1'
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
csrf = ''


def api(path, method='GET', value=None):
    headers = {'Origin': BASE, 'X-CSRF-Token': csrf}
    data = None
    if value is not None:
        data = json.dumps(value).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(BASE + '/api/' + path, data=data, headers=headers, method=method)
    with opener.open(req, timeout=10) as response:
        return json.load(response)


def shell(command):
    return subprocess.check_output([str(ROOT / 'outputs/adb'), 'shell', command], timeout=10).decode()


def has_alias(status, address):
    return any(address in interface['addresses'] for interface in status['interfaces'] if interface['name'] == 'bridge0')


def wait_for(predicate, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(1)
    raise RuntimeError('Native management assertion timed out')


password = sys.stdin.readline().rstrip('\n')
csrf = api('login', 'POST', {'password': password})['csrf']
password = ''
original = api('settings')
status = api('status')
if status['bootstrapRemaining']:
    wait_for(lambda: not api('status')['bootstrapRemaining'], 70)
    status = api('status')
if original['wifi']['enabled'] or status['gateway']['activeCall'] or status['pendingNetwork']:
    raise SystemExit('Requires an idle device, completed bootstrap and disabled Wi-Fi uplink')
if original['lan']['address'] != '192.168.0.1/24':
    raise SystemExit('Requires the default recovery LAN; existing settings left intact')

report = {'simCalls': False, 'smsMutated': False}
# Reproduce precisely the vendor boot defect, clearing only our owned rules.
shell('iptables -F MF79U_WEB; iptables -t nat -D PREROUTING -i bridge0 -p tcp --dport 80 -j REDIRECT --to-ports 18080')


def repaired():
    rules = shell('iptables -S MF79U_WEB; iptables -t nat -S PREROUTING')
    return '--dport 18080 -j REJECT' in rules and '-i bridge0 -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 18080' in rules


wait_for(repaired, 15)
assert api('status')['networkError'] == ''
report['vendorFirewallRepair'] = True
print('Owned firewall rules recovered after simulated vendor reset', flush=True)
temporary = copy.deepcopy(original)
temporary['lan']['address'] = '192.168.0.2/24'
pending = ''
try:
    api('settings', 'PUT', temporary)
    pending = api('apply', 'POST', {'network': True})['networkToken']
    wait_for(lambda: has_alias(api('status'), '192.168.0.2/24'), 15)
    assert has_alias(api('status'), '192.168.0.1/24')
    report['recoveryAddressRetained'] = True
    print('Temporary LAN alias applied; recovery address retained; awaiting 90-second rollback', flush=True)
    wait_for(lambda: not api('status')['pendingNetwork'], 100)
    pending = ''
    assert not has_alias(api('status'), '192.168.0.2/24')
    assert api('settings')['lan'] == original['lan']
    report['automatic90SecondRollback'] = True
    # Confirm a no-op network transaction, restoring the status after rollback.
    pending = api('apply', 'POST', {'network': True})['networkToken']
    time.sleep(3)
    api('network/confirm', 'POST', {'token': pending})
    pending = ''
    assert api('status')['networkError'] == ''
    report['networkConfirmation'] = True
    (ROOT / 'firmware/mf79u/build/native-management-integration.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
finally:
    if pending:
        api('network/rollback', 'POST', {'token': pending})
    # Recovery is scoped to the LAN/Wi-Fi transaction; unrelated SIP settings
    # are not overwritten if a user edited them during the waiting period.
    current = api('settings')
    if current['lan'] != original['lan']:
        current['lan'] = original['lan']
        api('settings', 'PUT', current)
        token = api('apply', 'POST', {'network': True})['networkToken']
        time.sleep(3)
        api('network/confirm', 'POST', {'token': token})

#!/usr/bin/env python3
"""Read-only physical check of selected VoWiFi access, LED and management."""
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', choices=['USB', 'WIFI'], required=True)
parser.add_argument('--duration', type=int, default=120)
parser.add_argument('--require-wifi', action='store_true', help='Also require a connected Wi-Fi client with a DHCP/static IPv4 address')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not 10 <= args.duration <= 600:
    parser.error('duration must be between 10 and 600 seconds')
adb = [str(ROOT / 'outputs/adb'), '-s', '1234567890ABCDEF']


def shell(command):
    return subprocess.check_output(adb + ['shell', command], timeout=10).decode().replace('\r', '').strip()


def wifi_status():
    fields = dict(line.split('=', 1) for line in shell('wpa_cli -p /dev/mf79u/wpa -i wlan0 status').splitlines() if '=' in line)
    return {k: fields.get(k) for k in ['wpa_state', 'ssid', 'ip_address']}


boot = shell('cat /proc/sys/kernel/random/boot_id')
peer = shell('sed -n "2p" /dev/mf79u/vowifi/epdg')
import ipaddress
peer = str(ipaddress.IPv4Address(peer))
interface = 'bridge0' if args.source == 'USB' else 'wlan0'
samples, failures = [], []
start = time.monotonic()
while True:
    elapsed = round(time.monotonic() - start, 1)
    try:
        runtime = json.loads(shell('cat /dev/.mf79u-native-status.json'))
        led = json.loads(shell('/mnt/userdata/mf79u/.mf79u-net-led --status'))
        wifi = wifi_status()
        route = shell('ip route get ' + peer)
        with urllib.request.urlopen('http://192.168.0.1/index.html', timeout=10) as response:
            management = 'SIM Gateway' in response.read(2048).decode(errors='replace')
        checks = {
            'sameBoot': shell('cat /proc/sys/kernel/random/boot_id') == boot,
            'selectedSource': runtime.get('vowifiUplink') == args.source,
            'imsReady': runtime.get('imsReady') is True and runtime.get('voiceReady') is True and runtime.get('vowifiTunnelReady') is True,
            'peerRoute': 'dev ' + interface + ' ' in route,
            'management': management,
            'idleLED': runtime.get('callBackend') != 'none' or led.get('hardware_mask') == 5,
        }
        if args.source == 'WIFI' or args.require_wifi:
            try:
                address = ipaddress.IPv4Address(wifi.get('ip_address'))
                valid_ip = not address.is_unspecified and not address.is_loopback and not address.is_link_local
            except (ValueError, TypeError):
                valid_ip = False
            checks['wifiLease'] = wifi.get('wpa_state') == 'COMPLETED' and valid_ip
        sample = {'elapsed': elapsed, 'checks': checks, 'runtime': runtime, 'led': led, 'wifi': wifi, 'peerRoute': route}
        if not all(checks.values()):
            failures.append({'elapsed': elapsed, 'failedChecks': [k for k, v in checks.items() if not v]})
        print(json.dumps({'elapsed': elapsed, 'checks': checks, 'wifi': wifi}), flush=True)
    except Exception as error:
        sample = {'elapsed': elapsed, 'errorType': type(error).__name__}
        failures.append(sample)
        print(json.dumps(sample), flush=True)
    samples.append(sample)
    if elapsed >= args.duration:
        break
    time.sleep(min(15, max(0, args.duration - (time.monotonic() - start))))
receipt = {'source': args.source, 'requireWiFi': args.require_wifi, 'boot': boot, 'duration': round(time.monotonic() - start, 1), 'samples': samples, 'failures': failures, 'passed': not failures, 'readOnly': True, 'callsInitiated': False}
args.output.write_text(json.dumps(receipt, indent=2) + '\n')
raise SystemExit(1 if failures else 0)

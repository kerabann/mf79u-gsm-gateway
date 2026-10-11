#!/usr/bin/env python3
"""Install verified local binaries; guarded native stop and software reboot.
No raw flash, vendor library, IMEI, SIP/Wi-Fi settings, or PCM change.
"""
import argparse
import hashlib
import http.server
import json
from pathlib import Path
import re
import subprocess
import threading
import time

from ram_transfer import ram_push

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / 'build'
ADB = [str(ROOT / 'outputs/adb'), '-s', '123456789ABCDEF']
DATA = '/mnt/userdata/mf79u'
BACKUP = BUILD / 'pre-sms-sip-20261008'
ARTIFACTS = {'modem-sip-gateway': '.mf79u-sip-gateway', 'mf79u-control': '.mf79u-control'}


def shell(command):
    return subprocess.check_output(ADB + ['shell', command], stderr=subprocess.PIPE,
                                   timeout=30).decode().replace('\r', '').strip()


def digest(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def status():
    return json.loads(shell('cat /dev/.mf79u-gateway-status.json'))


def main(restore):
    manifest = json.loads((BACKUP / 'checksums.json').read_text())
    for name in ARTIFACTS:
        if digest(BACKUP / name) != manifest[name]['md5']:
            raise RuntimeError('Original binary backup checksum mismatch')
    if status().get('activeCall') is not False:
        raise RuntimeError('End the active call before installation')
    sources = {name: (BACKUP if restore else BUILD) / name for name in ARTIFACTS}
    old_settings = shell('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini')
    old_boot = shell('cat /proc/sys/kernel/random/boot_id')
    report_path = BUILD / 'sms-sip-verification.json'
    prior = json.loads(report_path.read_text()).get('installedArtifacts', {}) if report_path.exists() else {}
    for name, target in ARTIFACTS.items():
        current = shell('md5sum ' + DATA + '/' + target).split()[0]
        allowed = {manifest[name]['md5'], digest(BUILD / name)}
        recorded = prior.get(name, {}).get('md5', '')
        if re.fullmatch(r'[0-9a-f]{32}', recorded): allowed.add(recorded)
        if current not in allowed:
            raise RuntimeError('Unexpected installed binary; no service stop')
    # All paths are fixed, only two non-secret artifacts can be downloaded.
    ip = subprocess.check_output(['ipconfig', 'getifaddr', 'en10']).decode().strip()
    if not re.fullmatch(r'192\.168\.0\.[0-9]{1,3}', ip):
        raise RuntimeError('Expected verified modem USB LAN on en10')
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            name = self.path.removeprefix('/')
            if name not in sources:
                self.send_error(404); return
            data = sources[name].read_bytes()
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer((ip, 18089), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ram_push(ADB, BUILD / 'ram-http-get', '/dev/.mf79u-sms-http-get')
        # Verify process identity and no active call immediately before stopping.
        if status().get('activeCall') is not False:
            raise RuntimeError('A call became active; installation postponed')
        supervisor = shell('cat /dev/.mf79u-native-supervisor.pid')
        native = json.loads(shell('cat /dev/.mf79u-native-status.json'))
        pid = int(native['pid'])
        if not supervisor.isdigit() or int(supervisor) < 2 or pid < 2:
            raise RuntimeError('Invalid owned process identifiers')
        check = shell('test /proc/' + str(pid) + '/exe -ef ' + DATA + '/.mf79u-native-gateway && '
                      "grep -F -q start-native.sh /proc/" + supervisor + "/cmdline && echo OWNED")
        if check != 'OWNED':
            raise RuntimeError('Native service ownership mismatch')
        shell('kill -TERM ' + supervisor)
        for _ in range(45):
            if shell('test -e /proc/' + str(pid) + '/exe && echo PRESENT') != 'PRESENT': break
            time.sleep(1)
        else:
            raise RuntimeError('Native controller did not complete guarded cleanup')
        print('Native controller stopped with owned-child/queue cleanup.', flush=True)
        # Sequential replacement fits userdata. Old control remains mapped until
        # reboot; original binaries are safely backed up on the Mac.
        for name, target in ARTIFACTS.items():
            stage = DATA + '/' + target + '.sms-next'
            result = shell('set -e; /dev/.mf79u-sms-http-get ' + ip + ' ' + name + ' ' + stage + '; md5sum ' + stage)
            if digest(sources[name]) not in result:
                raise RuntimeError('Staged binary checksum mismatch')
            result = shell('set -e; chmod 700 ' + stage + '; mv ' + stage + ' ' + DATA + '/' + target + '; sync; echo INSTALLED')
            if 'INSTALLED' not in result or shell('md5sum ' + DATA + '/' + target).split()[0] != digest(sources[name]):
                raise RuntimeError('Atomic binary installation mismatch')
            print(name + ' installed and verified.', flush=True)
        # Never silently boot the older archived SD binary.
        shell('set -e; touch ' + DATA + '/control-internal-preferred; chmod 600 ' + DATA + '/control-internal-preferred; rm -f /dev/.mf79u-sms-http-get; sync')
        if shell('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini') != old_settings:
            raise RuntimeError('Unexpected settings change during binary installation')
    finally:
        server.shutdown(); server.server_close()
    print('Rebooting to verify autonomous startup.', flush=True)
    start = last = time.monotonic()
    try:
        subprocess.run(ADB + ['shell', 'sync; reboot'], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired: pass
    ready = None
    while time.monotonic() - start < 240:
        try:
            if shell('cat /proc/sys/kernel/random/boot_id') != old_boot:
                ready = status()
                if ready.get('running') and ready.get('imsReady'): break
        except (subprocess.SubprocessError, json.JSONDecodeError): pass
        if time.monotonic() - last > 25:
            print('Waiting for autonomous IMS/SIP startup.', flush=True); last = time.monotonic()
        time.sleep(3)
    if not ready or not ready.get('imsReady'):
        raise RuntimeError('Autonomous startup verification timed out')
    print(json.dumps({'restored': restore, 'softwareRebootVerified': True, 'imsReady': ready['imsReady'],
                      'sipRunning': ready['running'], 'sipRole': ready['role'],
                      'settingsUnchanged': shell('md5sum ' + DATA + '/settings.json ' + DATA + '/gateway.ini') == old_settings,
                      'observedRebootSeconds': round(time.monotonic()-start,1)}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--install', action='store_true'); mode.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    main(args.restore)

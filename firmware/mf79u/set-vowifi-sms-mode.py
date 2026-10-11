#!/usr/bin/env python3
"""Apply the authorized VoWiFi-only/GSM-SMS option; never submit calls or SMS."""
import argparse
import base64
import copy
import datetime
import importlib.util
import json
from pathlib import Path
import re
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
DATA = '/mnt/userdata/mf79u'
spec = importlib.util.spec_from_file_location('mode_transfer', BASE / 'device-transfer.py')
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)
shell, push = transfer.shell, transfer.push


def private_read(name):
    return base64.b64decode(shell(DATA + '/tools/busybox base64 ' + DATA + '/' + name))


def states():
    native = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    sip = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
    if native.get('callBackend') != 'none' or sip.get('activeCall'):
        raise RuntimeError('An active call prevents changing registration')
    return native, sip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print('Use --apply only for an authorized idle registration change.')
        return
    before, gateway = states()
    if not before.get('vowifiCellularSmsSupported') or before.get('imsAccess') != 'WIFI':
        raise RuntimeError('Install the compatibility runtime and establish VoWiFi first')
    original = private_read('settings.json')
    ini = private_read('gateway.ini')
    saved = json.loads(original)
    if saved.get('voiceMode') != 'VOWIFI' or not re.search(rb'^voice_mode=VOWIFI\r?$', ini, re.M):
        raise RuntimeError('Expected the original VoWiFi-only baseline; refusing unrelated configuration')
    edited = copy.deepcopy(saved)
    edited['voiceMode'] = 'VOWIFI_SMS'
    content = json.dumps(edited, indent=2).encode() + b'\n'
    next_ini = re.sub(rb'^voice_mode=VOWIFI\r?$', b'voice_mode=VOWIFI_SMS', ini, count=1, flags=re.M)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'private/backups' / ('vowifi-sms-mode-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    for name, value in [('settings.json', original), ('gateway.ini', ini),
                        ('settings.next', content), ('gateway.next', next_ini)]:
        path = backup / name
        path.write_bytes(value)
        path.chmod(0o600)
    boot = shell('cat /proc/sys/kernel/random/boot_id')
    protected = ['.mf79u-cs-voice.ko', '.mf79u-cs-voice', '.mf79u-cs-pcm-bridge',
                 '.mf79u-volte-private', '.mf79u-ims-userspace-ipsec.so']
    hashes = shell('md5sum ' + ' '.join(DATA + '/' + name for name in protected))
    control = int(shell('cat /dev/.mf79u-control.pid'))
    parent = int(shell("sed -n 's/^PPid:[[:space:]]*//p' /proc/" + str(control) + '/status'))
    if control < 2 or parent < 2 or shell('test /proc/' + str(control) + '/exe -ef ' + DATA + '/.mf79u-control && grep -F -q start-control.sh /proc/' + str(parent) + '/cmdline && echo OWNED') != 'OWNED':
        raise RuntimeError('Unexpected Control process owner')
    push(backup / 'settings.next', DATA + '/.settings.vowifi-sms-next')
    push(backup / 'gateway.next', DATA + '/.gateway.vowifi-sms-next')
    now, _ = states()
    if now['pid'] != before['pid'] or now['sipPid'] != before['sipPid'] or private_read('settings.json') != original or private_read('gateway.ini') != ini:
        raise RuntimeError('Runtime or settings changed during staging')
    shell('kill -TERM ' + str(control))
    for pid in (control, parent):
        for _ in range(120):
            if shell('test -e /proc/' + str(pid) + '/exe && echo LIVE') != 'LIVE':
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Control cleanup did not finish; checked backup retained')
    try:
        states()
        shell('set -e; mv ' + DATA + '/.settings.vowifi-sms-next ' + DATA + '/settings.json; mv ' + DATA + '/.gateway.vowifi-sms-next ' + DATA + '/gateway.ini; sync')
    except Exception:
        push(backup / 'settings.json', DATA + '/.settings.vowifi-sms-restore')
        push(backup / 'gateway.ini', DATA + '/.gateway.vowifi-sms-restore')
        shell('set -e; mv ' + DATA + '/.settings.vowifi-sms-restore ' + DATA + '/settings.json; mv ' + DATA + '/.gateway.vowifi-sms-restore ' + DATA + '/gateway.ini; sync')
        raise
    finally:
        push(BASE / 'build/detach-control', '/dev/.mf79u-mode-control-start')
        shell('chmod 700 /dev/.mf79u-mode-control-start; /dev/.mf79u-mode-control-start; rm -f /dev/.mf79u-mode-control-start')
    print('Compatibility mode selected; waiting for GSM SMS and VoWiFi registration.', flush=True)
    start = last = time.monotonic()
    snapshots = []
    while time.monotonic() - start < 180:
        current, gateway = states()
        safe = {k: current.get(k) for k in ['voiceMode', 'effectiveVoiceMode', 'imsAccess', 'imsReady', 'voiceReady', 'voiceBackend', 'callBackend', 'csRegistration', 'epsRegistration', 'cellularRegistered', 'cellularSmsRadioReady', 'csSignalingReady', 'csAudioReady', 'pid', 'sipPid', 'ringOnly']}
        if time.monotonic() - last >= 15:
            print(json.dumps(safe), flush=True)
            snapshots.append(safe)
            last = time.monotonic()
        if current.get('cellularSmsRadioReady') and current.get('voiceReady') and current.get('imsAccess') == 'WIFI':
            snapshots.append(safe)
            break
        time.sleep(2)
    persisted = json.loads(private_read('settings.json'))
    persisted['voiceMode'] = saved['voiceMode']
    if persisted != saved or hashes != shell('md5sum ' + ' '.join(DATA + '/' + name for name in protected)) or boot != shell('cat /proc/sys/kernel/random/boot_id'):
        raise RuntimeError('An unrelated setting, media/CS artifact or boot changed')
    probe = BASE / 'build/network-registration-probe'
    push(probe, '/dev/.mf79u-mode-registration-probe')
    try:
        shell('chmod 700 /dev/.mf79u-mode-registration-probe')
        registration = shell('/dev/.mf79u-mode-registration-probe').splitlines()
    finally:
        shell('rm -f /dev/.mf79u-mode-registration-probe')
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'runtime': safe,
              'gsmAndVoWiFiReady': bool(current.get('cellularSmsRadioReady') and current.get('voiceReady') and current.get('imsAccess') == 'WIFI'),
              'registration': registration, 'snapshots': snapshots, 'bootPreserved': True,
              'onlyVoiceModeSettingChanged': True, 'imsMediaAndCsPreserved': True,
              'nativeSipPidsPreserved': current['pid'] == before['pid'] and current['sipPid'] == before['sipPid'],
              'deviceUtc': shell('date -u +%Y-%m-%dT%H:%M:%SZ'), 'callsOrSmsSubmitted': False,
              'backup': str(backup.relative_to(ROOT))}
    (ROOT / 'reports/vowifi-gsm-sms-live-20261012.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()

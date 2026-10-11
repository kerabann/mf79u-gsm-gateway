#!/usr/bin/env python3
"""Read-only ADB boot evidence; --reboot explicitly requests a normal reboot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request
from adb_boot import patch_rc, START

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reboot', action='store_true')
parser.add_argument('--timeout', type=int, default=180)
parser.add_argument('--serial', default='1234567890ABCDEF')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not 30 <= args.timeout <= 300:
    parser.error('timeout must be 30..300 seconds')
adb = [str(ROOT / 'outputs/adb'), '-s', args.serial]


def shell(command):
    return subprocess.check_output(adb + ['shell', command], timeout=8, stderr=subprocess.DEVNULL).decode().replace('\r', '').strip()


before = json.loads(shell('cat /dev/.mf79u-native-status.json'))
before_boot = shell('cat /proc/sys/kernel/random/boot_id')
if args.reboot and before.get('callBackend') != 'none':
    raise SystemExit('Active call; reboot refused')
rc = subprocess.check_output(adb + ['shell', 'cat /etc/rc'], timeout=8).replace(b'\r\n', b'\n')
if START not in rc or patch_rc(rc) != rc:
    raise SystemExit('Expected installed ADB boot policy')
expected_helper = hashlib.md5((HERE / 'build/mf79u-adb-boot').read_bytes()).hexdigest()
if shell('md5sum /usr/zte/mf79u/adb-boot').split()[:1] != [expected_helper]:
    raise SystemExit('Expected installed ADB helper')
started = time.monotonic()
if args.reboot:
    try:
        subprocess.run(adb + ['shell', 'sync; reboot'], timeout=8, capture_output=True)
    except subprocess.TimeoutExpired:
        pass  # The old USB shell may disappear while the requested reboot proceeds.
samples = []
first_adb = None
passed = False
while time.monotonic() - started < args.timeout:
    elapsed = round(time.monotonic() - started, 1)
    try:
        boot = shell('cat /proc/sys/kernel/random/boot_id')
        if args.reboot and boot == before_boot:
            samples.append({'elapsed': elapsed, 'state': 'waitingForNewBoot'})
            time.sleep(3)
            continue
        if first_adb is None:
            first_adb = elapsed
            print('ADB returned on ' + boot + ' at ' + str(elapsed) + 's', flush=True)
        functions = shell('cat /sys/class/android_usb/android0/functions').split(',')
        # Stock B03 has no pidof applet. Filter the command column, not the
        # entire line (which would also match our own inspection shell).
        pids = shell("ps | awk '$4 == \"adbd\" && NF == 4 {print $1}'").split()
        checks = {'newBoot': not args.reboot or boot != before_boot,
                  'usbADB': 'adb' in functions, 'usbECM': 'ecm' in functions,
                  'configured': shell('cat /sys/class/android_usb/android0/state') == 'CONFIGURED',
                  'debugProfile': shell('nv getro usb_modetype') == 'debug',
                  'helperRan': shell('cat /dev/.mf79u-adb-boot.log') in ['ADB_PROFILE_DEBUG_UNCHANGED','ADB_PROFILE_DEBUG_APPLIED'],
                  'singleDaemon': len(pids) == 1,
                  'rootReadOnly': ' / jffs2 ro,' in shell('cat /proc/mounts'),
                  'sameStartup': shell('md5sum /etc/rc').split()[:1] == [hashlib.md5(rc).hexdigest()],
                  'helperHash': shell('md5sum /usr/zte/mf79u/adb-boot').split()[:1] == [expected_helper]}
        parent = shell('sed -n "s/^PPid:[[:space:]]*//p" /proc/' + pids[0] + '/status') if len(pids) == 1 else None
        checks['daemonFromInit'] = parent == '1'
        runtime = json.loads(shell('cat /dev/.mf79u-native-status.json'))
        checks['runtimeRestored'] = runtime.get('state') == 'ready' and runtime.get('voiceMode') == before.get('voiceMode') and runtime.get('vowifiUplink') == before.get('vowifiUplink')
        checks['voiceRestored'] = before.get('voiceReady') is not True or runtime.get('voiceReady') is True
        checks['sipRunning'] = runtime.get('sipPid', 0) > 0 and 'mf79u-sip' in shell('cat /proc/' + str(runtime['sipPid']) + '/comm')
        with urllib.request.urlopen('http://192.168.0.1/index.html', timeout=5) as response:
            checks['management'] = 'SIM Gateway' in response.read(2048).decode(errors='replace')
        led = json.loads(shell('/mnt/userdata/mf79u/.mf79u-net-led --status'))
        if runtime.get('voiceMode') == 'VOWIFI' and runtime.get('voiceReady'):
            checks['purpleLED'] = led.get('hardware_mask') == 5
        sample = {'elapsed': elapsed, 'boot': boot, 'checks': checks, 'usbFunctions': functions,
                  'usbPID': shell('cat /sys/class/android_usb/android0/idProduct'),
                  'adbdPids': pids, 'adbdPPid': parent, 'runtime': runtime, 'led': led}
        samples.append(sample)
        print(json.dumps({'elapsed': elapsed, 'checks': checks}), flush=True)
        if all(checks.values()):
            passed = True
            break
    except (subprocess.SubprocessError, ValueError, OSError) as error:
        samples.append({'elapsed': elapsed, 'state': 'unavailable', 'errorType': type(error).__name__})
    time.sleep(3)
receipt = {'passed': passed, 'normalRebootRequested': args.reboot, 'beforeBoot': before_boot,
           'firstADBSeconds': first_adb, 'elapsed': round(time.monotonic()-started,1),
           'rcMD5': hashlib.md5(rc).hexdigest(), 'helperMD5': expected_helper,
           'samples': samples, 'coldPowerCycleTested': False, 'callsInitiated': False}
args.output.write_text(json.dumps(receipt, indent=2)+'\n')
raise SystemExit(0 if passed else 1)

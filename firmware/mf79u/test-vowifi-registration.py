"""Actual ARM controller: authenticated SWu admits IMS without cellular service."""
import json
import subprocess
import time
from pathlib import Path

if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():
    raise SystemExit('Requires disposable Linux fixture; never run on a modem')
build = Path('firmware/mf79u/build').resolve()
flags = ['-Os', '-Wall', '-Wextra', '-Werror', '-static', '-march=armv7-a', '-mfloat-abi=soft']
subprocess.run(['arm-linux-gnueabi-gcc', *flags, 'firmware/mf79u/src/native-fallback-fixture.c',
                '-o', str(build / 'native-fallback-fixture')], check=True)
for name in ('test-ims', 'test-sip', 'test-cs'):
    (build / name).unlink(missing_ok=True)
    (build / name).symlink_to('native-fallback-fixture')
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-DMF79U_IMS_TIMEOUT=5', '-DMF79U_RADIO_INTERVAL=1',
                '-DMF79U_USB_CARRIER_FILE="/tmp/usb-carrier"', 'firmware/mf79u/src/cp-ipc.c',
                'firmware/mf79u/src/cp-pdp.c', 'firmware/mf79u/src/native-gateway.c',
                'firmware/mf79u/src/net-led-policy.c', '-o', str(build / 'vowifi-registration-test')], check=True)
for name in ('radio-lte', 'radio-search', 'cp-status-error', 'ims-accept', 'ims-crash', 'test-call',
             'guard-test', 'cs-incoming', 'cs-force-incoming', 'cs-crash', 'charged-command', 'non3gpp-admitted', 'tunnel-permitted', 'gsm-sms-supported'):
    Path('/tmp/' + name).unlink(missing_ok=True)
Path('/tmp/radio-search').touch()
Path('/tmp/ims-non3gpp-gated').touch()
Path('/tmp/gsm-sms-supported').touch()
Path('/tmp/usb-carrier').write_text('1\n')
runtime = Path('/dev/mf79u/vowifi')
runtime.mkdir(parents=True, exist_ok=True)
Path('/dev/mf79u/vowifi-usb-ready').touch()
base = Path('/mnt/userdata/mf79u')
(base / 'tools').mkdir(parents=True, exist_ok=True)
(base / 'tools/busybox').write_text('#!/usr/bin/python3\nimport os,sys\nassert sys.argv[1]=="sh"\nos.execv("/bin/sh", ["sh", *sys.argv[2:]])\n')
(base / 'tools/busybox').chmod(0o700)
(base / 'native-ring-only').touch()
(base / 'start-vowifi.sh').write_text('''#!/bin/sh
runtime=/dev/mf79u/vowifi
if [ "${1:-}" = --cleanup-only ]; then rm -f "$runtime/address" "$runtime/mf79u-pcscf"; exit; fi
trap 'rm -f "$runtime/address" "$runtime/mf79u-pcscf"; exit' TERM INT
generation=0
while :; do
 if [ -e /tmp/tunnel-permitted ]; then
  if [ ! -s "$runtime/address" ]; then
   generation=$((generation + 1))
   echo "$generation" > "$runtime/generation"
   echo 127.0.0.1 > "$runtime/mf79u-pcscf"
   echo 10.77.0.2 > "$runtime/address"
  fi
 else rm -f "$runtime/address" "$runtime/mf79u-pcscf"; fi
 sleep 0.1
done
''')
config = Path('/tmp/vowifi-registration.ini')
config.write_text('role=SERVER\nvoice_mode=VOWIFI\nvowifi_uplink=USB\n')
cp = subprocess.Popen([str(build / 'native-fallback-fixture'), 'cp'], stdout=subprocess.PIPE, text=True)
assert cp.stdout.readline().strip() == 'FIXTURE_CP_READY'
logpath = Path('/tmp/vowifi-registration.log')
log = logpath.open('w')
proc = subprocess.Popen([str(build / 'vowifi-registration-test'), str(build / 'test-ims'),
                         '/dev/null', str(build / 'test-sip'), str(config), str(build / 'test-cs')],
                        stdout=log, stderr=subprocess.STDOUT)

def state():
    try:
        return json.loads(Path('/dev/.mf79u-native-status.json').read_text())
    except (OSError, ValueError):
        return {}

def wait(check, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError('Controller exited: ' + logpath.read_text())
        current = state()
        if check(current):
            return current
        time.sleep(.1)
    raise AssertionError('State timeout: ' + str(state()) + ' ' + logpath.read_text())

try:
    before = wait(lambda s: s.get('registrationState') == 'connecting_vowifi' and s.get('sipPid', 0) > 0)
    pid, sip = before['pid'], before['sipPid']
    time.sleep(1)
    assert not state()['imsReady'] and not Path('/tmp/non3gpp-admitted').exists()
    Path('/tmp/tunnel-permitted').touch()
    ready = wait(lambda s: s.get('voiceReady') and s.get('imsReady'))
    assert ready['pid'] == pid and ready['sipPid'] == sip and ready['vowifiTunnelReady']
    assert ready['epsRegistration'] == 4 and ready['csRegistration'] == 4 and not ready['cellularRegistered']
    assert ready['imsAccess'] == 'WIFI' and ready['registrationState'] == 'ready' and ready['ringOnly']
    assert Path('/tmp/non3gpp-admitted').exists()
    with open('/proc/' + str(sip) + '/fd/0', 'wb', buffering=0) as pipe:
        pipe.write(b'DIAL 1234567\nANSWER\n')
    time.sleep(.5)
    assert state()['callBackend'] == 'none' and not Path('/tmp/charged-command').exists()
    Path('/tmp/tunnel-permitted').unlink()
    lost = wait(lambda s: not s.get('imsReady') and not s.get('vowifiTunnelReady'))
    assert lost['pid'] == pid and lost['sipPid'] == sip and not lost['voiceReady']
    Path('/tmp/cp-status-error').touch()
    Path('/tmp/tunnel-permitted').touch()
    recovered = wait(lambda s: s.get('imsReady') and s.get('voiceReady'))
    assert recovered['pid'] == pid and recovered['sipPid'] == sip and not recovered['cellularRegistered']
    assert 'event=cereg_field_missing' in logpath.read_text()
    Path('/tmp/cp-status-error').unlink()
    config.write_text('role=SERVER\nvoice_mode=VOWIFI_SMS\nvowifi_uplink=USB\n')
    hybrid = wait(lambda s: s.get('effectiveVoiceMode') == 'VOWIFI_SMS' and s.get('cellularSmsRadioReady') and s.get('voiceReady'))
    assert hybrid['imsAccess'] == 'WIFI' and hybrid['voiceBackend'] == 'ims' and hybrid['sipPid'] == sip
    assert hybrid['csRegistration'] == 5 and hybrid['cellularRegistered'] and not hybrid['csAudioReady']
    assert json.loads(Path('/tmp/gsm-sms-radio.json').read_text()) == {'profile': 13, 'fun': 1, 'voice': 0, 'openVoice': 0}
    (base / 'native-ring-only').unlink()
    Path('/tmp/usb-carrier').write_text('0\n')
    lost = wait(lambda s: s.get('registrationState') == 'waiting_for_usb' and not s.get('imsReady'))
    assert lost['cellularSmsRadioReady'] and lost['voiceBackend'] == 'none' and not lost['voiceReady']
    with open('/proc/' + str(sip) + '/fd/0', 'wb', buffering=0) as pipe:
        pipe.write(b'DIAL 1234567\nANSWER\n')
    Path('/tmp/cs-force-incoming').touch()
    time.sleep(1)
    assert state()['callBackend'] == 'none' and not Path('/tmp/charged-command').exists()
    commands = Path('/tmp/cs-commands').read_text()
    assert 'DIAL ' not in commands and 'ANSWER ' not in commands and 'RESUME ' not in commands
    assert 'HANGUP ' in commands
    Path('/tmp/cs-force-incoming').unlink()
    # A legacy CS-only marker must never override either VoWiFi-only mode.
    (base / 'native-cs-only').touch()
    time.sleep(2)
    assert state()['voiceBackend'] == 'none' and 'RESUME ' not in Path('/tmp/cs-commands').read_text()
    (base / 'native-cs-only').unlink()
    Path('/tmp/usb-carrier').write_text('1\n')
    wait(lambda s: s.get('voiceReady') and s.get('cellularSmsRadioReady'))
    proc.terminate()
    assert proc.wait(timeout=15) == 0
    Path('reports').mkdir(exist_ok=True)
    Path('reports/vowifi-registration-fixture.json').write_text(json.dumps({
        'passed': True, 'physicalDeviceAccess': False, 'authenticatedTunnelRequired': True,
        'noCellularService': True, 'realCellularStatusPreserved': True,
        'privateImsPacketServiceQueriesAdapted': True, 'tunnelLossRevokesReadiness': True,
        'cellularQueryFailureDoesNotBlockRecovery': True, 'sipPidPreserved': True,
        'ringOnlyBlocksDialAndAnswer': True, 'gsmSmsRadioRegisteredWithVoiceFlagsOff': True,
        'hybridFreshCellularTelemetry': True, 'hybridTunnelLossNeverFallsBack': True,
        'hybridUnexpectedCsCallRejected': True, 'csOnlyMarkerCannotOverrideVoWiFiOnly': True}, indent=2) + '\n')
    print('PASS actual ARM controller: SWu-gated IMS with no cellular service; private queries, tunnel loss/recovery, CP failure, stable SIP and ring-only')
finally:
    if proc.poll() is None:
        proc.kill()
        proc.wait()
    cp.terminate()
    cp.wait()
    log.close()

#!/usr/bin/env python3
"""Read-only proof of device-local startup. Never dial, record or print secrets."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / 'build'
DATA = '/mnt/userdata/mf79u'
ADB = [str(ROOT / 'outputs/adb'), '-s', '123456789ABCDEF']

def shell(command):
    return subprocess.check_output(ADB + ['shell', command], timeout=20).decode().replace('\r', '').strip()

def main(audio_confirmed=False, previous_call_proof=None):
    runtime = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    gateway = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
    if runtime.get('version') != '0.9' or runtime.get('state') != 'ready' or runtime.get('imsReady') is not True:
        raise RuntimeError('Standalone IMS/controller is not ready')
    if gateway.get('running') is not True or gateway.get('imsReady') is not True:
        raise RuntimeError('SIP gateway is not ready')
    pid = int(runtime['pid'])
    if pid < 2 or shell(f'test /proc/{pid}/exe -ef {DATA}/.mf79u-native-gateway && echo OWNED') != 'OWNED':
        raise RuntimeError('Controller executable identity mismatch')
    supervisor = int(shell('cat /dev/.mf79u-native-supervisor.pid'))
    status = shell(f'cat /proc/{pid}/status')
    parent = int(re.search(r'^PPid:\s*(\d+)', status, re.M)[1])
    if parent != supervisor:
        raise RuntimeError('Controller did not start from the on-device supervisor')
    ancestors = []
    current = supervisor
    for _ in range(6):
        cmdline = shell(f'cat /proc/{current}/cmdline').replace('\x00', ' ')
        if any(s in cmdline for s in ('adbd', 'adb shell', '/bin/sh -c')):
            raise RuntimeError('Voice startup has a host-session ancestor')
        ancestors.append('init' if current == 1 else 'native_supervisor' if current == supervisor else 'boot_wrapper')
        if current == 1:
            break
        current = int(re.search(r'^PPid:\s*(\d+)', shell(f'cat /proc/{current}/status'), re.M)[1])
    if current != 1:
        raise RuntimeError('Voice startup is not rooted in init')
    processes = shell('ps')
    disabled = ['zte_topsw_led', 'zte_topsw_self_regist', 'zte_dm', 'zte_topsw_dua']
    for name in disabled:
        if re.search(r'\b' + name + r'\b', processes):
            raise RuntimeError('Disabled stock service is running: ' + name)
    host = subprocess.check_output(['ps', '-axo', 'command']).decode()
    if any(re.search(r'\bpython\S* .*run-(usb|pbx)-gateway\.py', line) for line in host.splitlines()):
        raise RuntimeError('A Mac relay or watcher is running')
    artifacts = {
        'mf79u-native-gateway': (BUILD / 'mf79u-native-gateway', DATA + '/.mf79u-native-gateway'),
        'mf79u-net-led': (BUILD / 'mf79u-net-led', DATA + '/.mf79u-net-led'),
        'volte-private-ipc': (BUILD / 'volte-private-ipc', DATA + '/.mf79u-volte-private'),
        'ims-userspace-ipsec.so': (BUILD / 'ims-userspace-ipsec.so', DATA + '/.mf79u-ims-userspace-ipsec.so'),
        'modem-sip-gateway': (BUILD / 'modem-sip-gateway', DATA + '/.mf79u-sip-gateway'),
        'start-native.sh': (HERE / 'start-native.sh', DATA + '/start-native.sh'),
        'start-control-userdata.sh': (HERE / 'start-control-userdata.sh', DATA + '/start-control.sh'),
    }
    hashes = {}
    for name, (local, remote) in artifacts.items():
        data = local.read_bytes()
        if shell('md5sum ' + remote).split()[0] != hashlib.md5(data).hexdigest():
            raise RuntimeError('Installed artifact differs from the current build: ' + name)
        hashes[name] = hashlib.sha256(data).hexdigest()
    log = shell('cat /dev/.mf79u-native.log')
    events = {event: int(elapsed) for elapsed, event in re.findall(r'NATIVE_GATEWAY elapsed=(\d+) event=([a-z_]+)', log)}
    for event in ('ims_bearer_verified', 'ims_registered', 'autonomous_control_ready'):
        if event not in events:
            raise RuntimeError('Missing startup proof event: ' + event)
    if not re.search(r'CP_COMPLETED tag=sim_aka bytes=\d+ ok=1', log):
        raise RuntimeError('Local SIM AKA completion was not observed')
    led = json.loads(shell(DATA + '/.mf79u-net-led --status'))
    samples = re.findall(r'PCM_COUNTERS received=(\d+) sent=(\d+) received_nonzero=(\d+) sent_nonzero=(\d+)', log)
    counters = dict(zip(('received', 'sent', 'received_nonzero', 'sent_nonzero'), map(int, samples[-1]))) if samples else {}
    duplex = bool(counters) and all(value > 0 for value in counters.values())
    connected = 'CELLULAR_STATE direction=0 state=0' in log and 'event=sip_connected' in log
    contacts = subprocess.check_output(['docker', 'exec', 'mf79u-mikopbx', 'asterisk', '-rx', 'pjsip show contacts'], timeout=10).decode()
    if not any('SIP-TRUNK-51091984/' in line and 'Avail' in line for line in contacts.splitlines()):
        raise RuntimeError('Lab PBX cannot reach the standalone SIP gateway')
    report = {
        'tested_at': datetime.now(timezone.utc).isoformat(),
        'target': 'physical MF79U B03 ARMv7 soft-float',
        'artifact_sha256': hashes,
        'controller_version': runtime['version'],
        'startup_ancestors': ancestors,
        'boot_autostart_confirmed': True,
        'mac_relay_or_watcher_running': False,
        'local_ims_pdp_device_tested': True,
        'local_sim_aka_device_tested': True,
        'local_ims_registration_device_tested': True,
        'controller_startup_seconds': events,
        'sip_peer_reachable_from_pbx': True,
        'disabled_stock_services_absent': disabled,
        'led': led,
        'pcm_rate_unchanged': 16000,
        'outgoing_cellular_and_sip_connected': connected,
        'voice_pcm_counters': counters,
        'voice_duplex_dataflow_verified': duplex,
        'voice_audio_on_phone_user_confirmed': audio_confirmed,
        'voice_audio_without_relay_verified': connected and duplex and audio_confirmed,
        'full_replacement_rootfs_boot_tested': False,
        'raw_flash_written': False,
    }
    if previous_call_proof and not report['voice_audio_without_relay_verified']:
        previous = json.loads(Path(previous_call_proof).read_text())
        voice = ('mf79u-native-gateway', 'volte-private-ipc', 'ims-userspace-ipsec.so', 'modem-sip-gateway')
        if not previous.get('voice_audio_without_relay_verified') or any(previous.get('artifact_sha256', {}).get(name) != hashes[name] for name in voice):
            raise RuntimeError('Prior call proof does not match the installed voice binaries')
        for field in ('outgoing_cellular_and_sip_connected', 'voice_pcm_counters', 'voice_duplex_dataflow_verified',
                      'voice_audio_on_phone_user_confirmed', 'voice_audio_without_relay_verified'):
            report[field] = previous[field]
        report['call_evidence_from_prior_boot_with_identical_voice_binaries'] = previous['tested_at']
    incoming = ROOT / 'outputs/mikopbx/standalone-incoming-result.json'
    if incoming.exists():
        proof = json.loads(incoming.read_text())
        report['incoming_call_verification'] = proof
        report['incoming_call_live_tested'] = proof.get('incoming_channel_seen') is True
    (BUILD / 'standalone-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS standalone boot: local PDP/SIM AKA/IMS/SIP, init ancestry, artifact hashes, stock service policy, no Mac relay')
    print('Outgoing audio verified=' + str(report['voice_audio_without_relay_verified']))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio-confirmed', action='store_true', help='Use only after the human confirms hearing the test tone')
    parser.add_argument('--previous-call-proof', help='Preserve an earlier successful call only if all four voice binary hashes match')
    args = parser.parse_args()
    main(args.audio_confirmed, args.previous_call_proof)

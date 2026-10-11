#!/usr/bin/env python3
"""Sanitized UI audit snapshot; private configuration never reaches stdout."""
import argparse
import datetime
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DATA = '/mnt/userdata/mf79u'
ADB = [os.environ.get('ADB', 'adb')]


def shell(command):
    result = subprocess.run(ADB + ['shell', command], capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Device diagnostic failed; raw output omitted')
    return result.stdout.replace(b'\r', b'').strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', action='store_true')
    parser.add_argument('--assets', action='store_true')
    parser.add_argument('--call-stats', action='store_true')
    parser.add_argument('--pbx-diagnostics', action='store_true')
    parser.add_argument('--cs-diagnostics', action='store_true')
    parser.add_argument('--network-policy', action='store_true')
    args = parser.parse_args()
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if args.backup:
        backup = ROOT / 'private/backups' / ('ui-e2e-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(parents=True, mode=0o700)
        for name in ['settings.json', 'gateway.ini', 'ssh.json', 'ssh.password']:
            value = shell('if [ -f ' + DATA + '/' + name + ' ]; then cat ' + DATA + '/' + name + '; fi')
            if value:
                path = backup / name
                path.write_bytes(value + b'\n')
                path.chmod(0o600)
        report['privateBackup'] = str(backup.relative_to(ROOT))
    report['boot'] = shell('cat /proc/sys/kernel/random/boot_id').decode()
    n = json.loads(shell('cat /dev/.mf79u-native-status.json'))
    s = json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
    report['native'] = {k: n.get(k) for k in ['pid', 'sipPid', 'csPid', 'imsReady', 'voiceReady', 'imsAccess', 'voiceMode', 'effectiveVoiceMode', 'vowifiUplink', 'vowifiTunnelReady', 'voiceBackend', 'callBackend', 'registrationState', 'fallbackReason', 'csRegistration', 'csSignalingReady', 'csAudioReady', 'ringOnly']}
    report['sip'] = {k: s.get(k) for k in ['pid', 'running', 'role', 'registerMode', 'registered', 'registrationCode', 'localRegistered', 'activeCall', 'codec']}
    report['controlPid'] = shell('cat /dev/.mf79u-control.pid').decode()
    report['publicHashes'] = shell('md5sum ' + ' '.join(DATA + '/' + p for p in ['.mf79u-control', '.mf79u-native-gateway', '.mf79u-sip-gateway'])).decode().splitlines()
    report['settingsHash'] = hashlib.sha256(shell('cat ' + DATA + '/settings.json')).hexdigest()
    if args.network_policy:
        report['mobileInternetEnabled'] = json.loads(shell('cat ' + DATA + '/settings.json'))['internetSharing']
        report['firewall'] = {}
        for tool in ['iptables', 'ip6tables']:
            target = 'REJECT' if tool == 'iptables' else 'DROP'
            data_rules = [line.strip() for line in shell(tool + ' -S MF79U_DATA').decode().splitlines()]
            share_rules = [line.strip() for line in shell(tool + ' -S MF79U_SHARE').decode().splitlines()]
            output = [line.strip() for line in shell(tool + ' -S OUTPUT').decode().splitlines()]
            forward = [line.strip() for line in shell(tool + ' -S FORWARD').decode().splitlines()]
            report['firewall'][tool] = {
                'imsBearerException': '-A MF79U_DATA -o wan5 -j RETURN' in data_rules,
                'ordinaryCellularOutputBlocked': any(line == '-A MF79U_DATA -o wan+ -j ' + target or line.startswith('-A MF79U_DATA -o wan+ -j ' + target + ' ') for line in data_rules),
                'cellularForwardBlocked': all(any(line == '-A MF79U_SHARE ' + direction + ' wan+ -j ' + target or line.startswith('-A MF79U_SHARE ' + direction + ' wan+ -j ' + target + ' ') for line in share_rules) for direction in ['-i', '-o']),
                'ownedOutputJumpCount': output.count('-A OUTPUT -j MF79U_DATA'),
                'ownedForwardJumpCount': forward.count('-A FORWARD -j MF79U_SHARE'),
                'outputGuardFirst': next((line for line in output if line.startswith('-A ')), '') == '-A OUTPUT -j MF79U_DATA',
                'forwardGuardFirst': next((line for line in forward if line.startswith('-A ')), '') == '-A FORWARD -j MF79U_SHARE',
            }
    if args.cs_diagnostics:
        session = shell('if [ -f /sys/mf79u_cs_voice/session ]; then cat /sys/mf79u_cs_voice/session; fi').decode()
        match = re.fullmatch(r'MF79U_CS_DRIVER 1 ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+)', session)
        report['csDriver'] = {'sessionAvailable': bool(match)}
        if match:
            report['csDriver'].update(zip(['enabled', 'desired', 'stage', 'hasCall', 'incoming', 'mm', 'audio', 'fault'],
                                         [int(x) for x in match.groups()[1:]]))
            report['csDriver']['hasCall'] = bool(report['csDriver']['hasCall'])
        report['csArtifacts'] = {}
        for name in ['.mf79u-cs-voice', '.mf79u-cs-pcm-bridge', '.mf79u-cs-voice.ko']:
            value = shell('if [ -f ' + DATA + '/' + name + ' ]; then md5sum ' + DATA + '/' + name + '; fi').decode()
            report['csArtifacts'][name] = value.split()[0] if value else None
        report['csDriver']['explicitRatDiagnosticPresent'] = b'wcdma_nb_codec_offer' in shell('cat ' + DATA + '/.mf79u-cs-voice.ko')
        if isinstance(n.get('csPid'), int) and n['csPid'] > 0:
            proc = '/proc/' + str(n['csPid'])
            executable = shell('readlink ' + proc + '/exe').decode()
            report['csDriver']['adapterExecutableDeleted'] = executable.endswith(' (deleted)')
            state = shell('cat ' + proc + '/stat').decode().rsplit(')', 1)[-1].split()
            report['csDriver']['adapterProcessState'] = state[0]
            report['csDriver']['adapterOwnedByNative'] = int(state[1]) == n.get('pid')
            digest = shell('md5sum ' + proc + '/exe').decode().split()[0]
            report['csDriver']['adapterRunningMD5'] = digest
            report['csDriver']['adapterMatchesInstalled'] = digest == report['csArtifacts']['.mf79u-cs-voice']
            report['csDriver']['adapterExecutableVerified'] = report['csDriver']['adapterMatchesInstalled'] and report['csDriver']['adapterOwnedByNative']
        log = shell('cat /dev/.mf79u-native.log').decode(errors='replace')
        pattern = re.compile(r'NATIVE_GATEWAY elapsed=[0-9]+ event=(?:cs_adapter_started|cs_media_ready|cs_protocol_rejected|cs_duplicate_hello_rejected|cs_unrequested_ready_rejected|cs_radio_selected|cs_adapter_exited|volte_radio_selected)')
        report['csDriver']['events'] = [line for line in log.splitlines() if pattern.fullmatch(line)][-20:]
    if args.call_stats:
        # Accept only fixed numeric/codec metadata, never call addresses or text.
        log = shell('cat /dev/.mf79u-native.log').decode(errors='replace')
        pattern = re.compile(r'(?:NATIVE_GATEWAY elapsed=[0-9]+ event=(?:outgoing_call|cs_outgoing_call|sip_connected|sip_media_connected|incoming_forwarded|cs_incoming_call|call_answered|call_ended|cellular_dial_failed|outgoing_call_blocked|sip_untrusted_peer)|SIP_RESULT code=[0-9]+|PCM_COUNTERS received=[0-9]+ sent=[0-9]+ received_nonzero=[0-9]+ sent_nonzero=[0-9]+)')
        report['callMetadata'] = [line for line in log.splitlines() if pattern.fullmatch(line)][-30:]
    if args.pbx_diagnostics:
        report['pbxDiagnostics'] = {}
        for kind in ['aor', 'endpoint']:
            result = subprocess.run(['docker', 'exec', 'mf79u-mikopbx', 'asterisk', '-rx', 'pjsip show ' + kind + ' mf79u'], capture_output=True, timeout=15)
            report['pbxDiagnostics'][kind + 'Found'] = 'Unable to find object' not in result.stdout.decode(errors='replace')
        config = subprocess.run(['docker', 'exec', 'mf79u-mikopbx', 'cat', '/etc/asterisk/pjsip.conf'], capture_output=True, timeout=15).stdout.decode(errors='replace')
        report['pbxDiagnostics']['generatedAorNamedUsername'] = bool(re.search(r'\[mf79u\][^\[]*type\s*=\s*aor', config))
        for name in ['messages', 'security_log', 'error', 'verbose']:
            result = subprocess.run(['docker', 'exec', 'mf79u-mikopbx', 'tail', '-n', '100', '/storage/usbdisk1/mikopbx/log/asterisk/' + name], capture_output=True, timeout=15)
            log = result.stdout.decode(errors='replace')
            report['pbxDiagnostics'][name] = {term: log.count(term) for term in ['REGISTER', 'No matching endpoint', 'Failed to authenticate', 'AOR', 'InvalidPassword', 'SuccessfulAuth', 'ChallengeSent']}
    if args.assets:
        report['embeddedAssets'] = {}
        for name in ['index.html', 'app.js', 'system.js', 'sms-format.js', 'style.css']:
            url = 'http://192.168.0.1/' + ('' if name == 'index.html' else name)
            served = urllib.request.urlopen(url, timeout=10).read()
            source = (ROOT / 'firmware/mf79u/control/web' / name).read_bytes()
            report['embeddedAssets'][name] = served == source
    path = ROOT / 'reports/ui-e2e-device.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    dated = path.with_name('ui-e2e-device-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    dated.write_text(path.read_text())
    print(json.dumps(report, indent=2))
    if args.assets and not all(report['embeddedAssets'].values()):
        raise SystemExit('Installed UI assets do not match the current source')


if __name__ == '__main__':
    main()

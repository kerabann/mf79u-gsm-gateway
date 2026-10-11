#!/usr/bin/env python3
"""Authorized physical API checks; credentials remain in RAM/protected backups."""
import argparse
import base64
import copy
import datetime
import getpass
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = 'http://192.168.0.1'
spec = importlib.util.spec_from_file_location('pbx_audit', ROOT / 'outputs/mikopbx/configure-sip-messages.py')
pbx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pbx)


def write_report(report):
    target = ROOT / 'reports/ui-e2e-api.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    stamp = datetime.datetime.fromisoformat(report['at']).strftime('%Y%m%dT%H%M%SZ')
    target.with_name('ui-e2e-api-' + stamp + '.json').write_text(target.read_text())


class API:
    def __init__(self, password):
        self.cookies = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf = self.request('login', 'POST', {'password': password})['csrf']

    def request(self, path, method='GET', body=None):
        headers = {'Origin': BASE}
        if hasattr(self, 'csrf'):
            headers['X-CSRF-Token'] = self.csrf
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(BASE + '/api/' + path,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers=headers, method=method)
        try:
            with self.client.open(req, timeout=35) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError('Modem API ' + path.split('?')[0] + ': HTTP ' + str(error.code)) from None

    def settings(self):
        value = self.request('settings')
        credentials = self.request('settings/credentials')
        value['sip']['password'] = credentials['sipPassword']
        value['sip']['extensionPassword'] = credentials['sipExtensionPassword']
        value['wifi']['password'] = credentials['wifiPassword']
        return value

    def apply(self, value):
        self.idle()
        self.request('settings', 'PUT', value)
        return self.request('apply', 'POST', {'network': False})

    def network(self, value):
        self.idle()
        self.request('settings', 'PUT', value)
        result = self.request('apply', 'POST', {'network': True})
        token = result.get('networkToken')
        if not token:
            raise RuntimeError('A physical network confirmation token was not returned')
        try:
            deadline = time.monotonic() + 75
            while time.monotonic() < deadline:
                status = self.request('status')
                if status.get('pendingNetwork') != token:
                    raise RuntimeError('The network transaction ended before confirmation')
                if status.get('networkReady') and not status.get('networkRollingBack'):
                    self.request('network/confirm', 'POST', {'token': token})
                    return status
                time.sleep(1)
            raise RuntimeError('The network did not become ready within the test deadline')
        except Exception:
            if self.request('status').get('pendingNetwork') == token:
                self.request('network/rollback', 'POST', {'token': token})
            raise

    def idle(self):
        status = self.request('status')
        if status['gateway'].get('activeCall') or status['runtime'].get('callBackend', 'none') != 'none' or status.get('pendingNetwork'):
            raise RuntimeError('A call or pending network transaction prevents this check')
        return status


def private_backup(name, data):
    directory = ROOT / 'private/backups'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / (name + '-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as file:
        json.dump(data, file)


def registration(api, report):
    api.idle()
    pbx.require_no_calls()
    original = api.settings()
    provider = pbx.api('sip-providers/' + pbx.PROVIDER)
    fields = ['registration_type', 'username', 'secret']
    if provider['registration_type'] != 'none' or provider.get('secret'):
        raise RuntimeError('This temporary test requires the existing password-free IP peer')
    prior = {k: provider[k] for k in fields}
    private_backup('ui-pbx-registration', {'settings': original, 'provider': prior})
    password = secrets.token_urlsafe(24)
    # This running PBX exposes the existing provider AOR under its stable ID.
    # Keep Digest identity and REGISTER To user aligned with that actual AOR.
    test_username = pbx.PROVIDER
    changed = copy.deepcopy(original)
    changed['sip'].update(role='TRUNK', server='192.168.0.169', port=5060, transport='UDP',
                          username=test_username, password=password, passwordSet=False,
                          register=True, realm='*', bind='192.168.0.1')
    try:
        temporary_provider = copy.deepcopy(provider)
        temporary_provider.update(registration_type='inbound', username=test_username, secret=password)
        pbx.api('sip-providers/' + pbx.PROVIDER, temporary_provider, 'PUT')
        report['pbxTemporaryRegistrationType'] = pbx.api('sip-providers/' + pbx.PROVIDER)['registration_type']
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            config = subprocess.check_output(['docker', 'exec', 'mf79u-mikopbx', 'cat', '/etc/asterisk/pjsip.conf'], timeout=10).decode()
            if password in config:
                pbx.cli('module reload res_pjsip.so')
                report['pbxAorLoaded'] = 'Unable to find object' not in pbx.cli('pjsip show aor ' + test_username)
                report['pbxEndpointLoaded'] = 'Unable to find object' not in pbx.cli('pjsip show endpoint ' + test_username)
                if not report['pbxAorLoaded'] or not report['pbxEndpointLoaded']:
                    raise RuntimeError('The PBX did not load the temporary registration account')
                break
            time.sleep(1)
        else:
            raise RuntimeError('Temporary PBX auth configuration did not reach Asterisk')
        api.apply(changed)
        report['pbxRegistrationCodes'] = []
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            gateway = api.request('status')['gateway']
            code = gateway.get('registrationCode')
            if code not in report['pbxRegistrationCodes']:
                report['pbxRegistrationCodes'].append(code)
            if gateway.get('registered'):
                report['pbxRegistration'] = {'registered': True, 'registrationCode': gateway.get('registrationCode'),
                                             'transport': 'UDP', 'realCallsMade': 0}
                break
            time.sleep(1)
        else:
            raise RuntimeError('Modem REGISTER did not succeed')
    finally:
        api.apply(original)
        pbx.require_no_calls()
        restored_provider = pbx.api('sip-providers/' + pbx.PROVIDER)
        restored_provider.update(prior)
        pbx.api('sip-providers/' + pbx.PROVIDER, restored_provider, 'PUT')
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            config = subprocess.check_output(['docker', 'exec', 'mf79u-mikopbx', 'cat', '/etc/asterisk/pjsip.conf'], timeout=10).decode()
            if password not in config:
                pbx.cli('module reload res_pjsip.so')
                break
            time.sleep(1)
        else:
            raise RuntimeError('PBX configuration restoration did not reach Asterisk')
        report['pbxAndModemRestored'] = api.settings() == original and all(pbx.api('sip-providers/' + pbx.PROVIDER)[k] == v for k, v in prior.items())
        if not report['pbxAndModemRestored']:
            raise RuntimeError('PBX or modem profile differs after restoration')
        write_report(report)


def password_cycle(api, original_password, report):
    api.idle()
    password = secrets.token_urlsafe(18)
    changed = False
    try:
        result = api.request('system/password', 'POST', {'currentPassword': original_password, 'newPassword': password, 'confirmPassword': password})
        changed = True
        temporary = API(password)
        try:
            api.request('status')
            invalidated = False
        except RuntimeError:
            invalidated = True
        try:
            API(original_password)
            old_rejected = False
        except RuntimeError:
            old_rejected = True
        report['administratorPassword'] = {'signInRequired': result.get('signInRequired'),
                                             'oldSessionInvalidated': invalidated, 'oldPasswordRejected': old_rejected,
                                             'newSignInSucceeded': True}
        temporary.request('system/password', 'POST', {'currentPassword': password, 'newPassword': original_password, 'confirmPassword': original_password})
        changed = False
        report['administratorPassword']['originalRestored'] = bool(API(original_password))
    finally:
        if changed:
            # One explicit restoration, never blindly repeat an uncertain mutation.
            API(password).request('system/password', 'POST', {'currentPassword': password, 'newPassword': original_password, 'confirmPassword': original_password})


def ssh_cycle(api, report):
    import paramiko
    spec = importlib.util.spec_from_file_location('ssh_audit_transfer', Path(__file__).with_name('device-transfer.py'))
    transfer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transfer)
    data = '/mnt/userdata/mf79u'
    api.idle()
    previous = api.request('system/ssh')
    if previous['enabled'] or not previous['installed']:
        raise RuntimeError('SSH cycle requires an installed, currently disabled server')
    prior_files = {}
    for name in ['ssh.json', 'ssh.password']:
        prior_files[name] = transfer.shell('if [ -f ' + data + '/' + name + ' ]; then ' + data + '/tools/busybox base64 ' + data + '/' + name + '; fi')
    private_backup('ui-ssh-cycle', prior_files)
    first, second = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    try:
        state = api.request('system/ssh', 'PUT', {'enabled': True, 'password': first, 'confirmPassword': first})
        if not state['running']:
            raise RuntimeError('SSH failed to start')
        public = transfer.shell(data + '/tools/dropbearkey -y -f ' + data + '/ssh-host-ed25519')
        key = next(line.split()[1] for line in public.splitlines() if line.startswith('ssh-ed25519 '))
        hostkey = paramiko.Ed25519Key(data=base64.b64decode(key))

        def connect(password):
            client = paramiko.SSHClient()
            client.get_host_keys().add('192.168.0.1', 'ssh-ed25519', hostkey)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            try:
                client.connect('192.168.0.1', username='admin', password=password,
                               allow_agent=False, look_for_keys=False, timeout=10, auth_timeout=10)
                _, out, _ = client.exec_command('id -u; command -v ash', timeout=10)
                rows = out.read().decode().splitlines()
                return rows[0] == '0' and rows[1].startswith(data + '/tools/bin/')
            finally:
                client.close()
        if not connect(first):
            raise RuntimeError('SSH shell or existing admin UID is incorrect')
        api.request('system/ssh', 'PUT', {'enabled': True, 'password': second, 'confirmPassword': second})
        try:
            old_rejected = not connect(first)
        except paramiko.AuthenticationException:
            old_rejected = True
        if not old_rejected or not connect(second):
            raise RuntimeError('SSH credential rotation failed')
        report['sshPassword'] = {'firstLoginSucceeded': True, 'oldPasswordRejected': True,
                                 'newLoginSucceeded': True, 'hostKeyVerifiedThroughUSB': True}
    finally:
        api.request('system/ssh', 'PUT', {'enabled': False, 'password': '', 'confirmPassword': ''})
        for name, encoded in prior_files.items():
            target = data + '/' + name
            if encoded:
                directory = ROOT / 'private/backups'
                local = directory / ('ui-ssh-restore-' + name)
                local.write_bytes(base64.b64decode(encoded))
                local.chmod(0o600)
                try:
                    transfer.push(local, target + '.audit-restore')
                    transfer.shell('set -e; chmod 600 ' + target + '.audit-restore; mv ' + target + '.audit-restore ' + target)
                finally:
                    local.unlink()
            else:
                transfer.shell('rm -f ' + target)
        report['sshStateRestored'] = api.request('system/ssh')['enabled'] == previous['enabled'] and api.request('system/ssh')['passwordSet'] == previous['passwordSet']


def hotspot_cycle(api, report):
    original = api.settings()
    api.idle()
    if original['wifi']['enabled']:
        raise RuntimeError('Hotspot cycle requires the currently disabled Wi-Fi profile')
    private_backup('ui-hotspot-cycle', original)
    changed = copy.deepcopy(original)
    changed['wifi'].update(mode='HOTSPOT', enabled=True, ssid='MF79U-UI-test',
                           security='WPA2', password=secrets.token_urlsafe(24), passwordSet=False, hidden=False)
    report['hotspotSettings'] = {'clientAssociationTested': False, 'stages': []}
    try:
        for hidden in [False, True]:
            if hidden:
                changed['wifi'].update(ssid='MF79U-UI-test-hidden', hidden=True,
                                       password=secrets.token_urlsafe(24))
            status = api.network(changed)
            wifi = api.settings()['wifi']
            if status['wifi'].get('state') != 'ENABLED' or any(wifi[k] != changed['wifi'][k] for k in ['mode', 'enabled', 'ssid', 'password', 'hidden']):
                raise RuntimeError('Hotspot did not apply the requested settings')
            report['hotspotSettings']['stages'].append({'enabled': True, 'hidden': hidden,
                                                       'ssidAndPasswordVerifiedWithoutDisclosure': True,
                                                       'networkConfirmed': True})
    finally:
        api.network(original)
        report['hotspotSettings']['originalProfileRestored'] = api.settings() == original
        if not report['hotspotSettings']['originalProfileRestored']:
            raise RuntimeError('The original Wi-Fi profile was not restored')
        write_report(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pbx-registration', action='store_true')
    parser.add_argument('--administrator-password', action='store_true')
    parser.add_argument('--ssh-password', action='store_true')
    parser.add_argument('--hotspot-settings', action='store_true')
    parser.add_argument('--restore-pbx', action='store_true')
    args = parser.parse_args()
    if args.restore_pbx:
        pbx.require_no_calls()
        backup = sorted((ROOT / 'private/backups').glob('ui-pbx-registration-*.json'))[-1]
        prior = json.loads(backup.read_text())['provider']
        current = pbx.api('sip-providers/' + pbx.PROVIDER)
        current.update(prior)
        pbx.api('sip-providers/' + pbx.PROVIDER, current, 'PUT')
        time.sleep(5)
        pbx.cli('module reload res_pjsip.so')
        print(json.dumps({'pbxRestored': all(pbx.api('sip-providers/' + pbx.PROVIDER)[k] == v for k, v in prior.items())}))
        return
    password = getpass.getpass('Existing modem administrator password (not logged): ')
    api = API(password)
    status = api.idle()
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'authenticated': True,
              'runtime': {k: status['runtime'].get(k) for k in ['pid', 'sipPid', 'voiceMode', 'imsReady', 'imsAccess']}}
    info = api.request('system/info')
    report['system'] = {'imeiReadSucceeded': bool(info.get('imei')) and not info.get('imeiError'),
                        'sshInstalled': info['ssh']['installed'], 'infoRowsAvailable': bool(info.get('memory'))}
    report['logSources'] = {}
    for source in ['native', 'kernel', 'ssh']:
        data = api.request('system/logs?source=' + source)
        report['logSources'][source] = {'requestSucceeded': True, 'bytes': len(data.get('text', ''))}
    report['smsStorage'] = {}
    for storage in ['modem', 'sim']:
        data = api.request('sms?storage=' + storage)
        report['smsStorage'][storage] = {'requestSucceeded': True, 'listed': len(data['messages']), 'transport': data.get('transport')}
    if args.pbx_registration:
        registration(api, report)
    if args.administrator_password:
        password_cycle(api, password, report)
    if args.ssh_password:
        ssh_cycle(api, report)
    if args.hotspot_settings:
        hotspot_cycle(api, report)
    write_report(report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Disposable frontend HTTP fixture, never accesses a modem, PBX or real data."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import time

BASE = Path(__file__).resolve().parent / 'control/web'
settings = {'version': 1, 'voiceMode': 'AUTO', 'bootstrapSeconds': 60, 'internetSharing': False,
            'webhooks': {'telegramSMS': {'enabled': False, 'botTokenSet': False, 'chatId': '', 'interface': '', 'deleteAfterSend': False}},
            'vowifi': {'uplink': 'USB', 'gateway': '192.168.0.169', 'dns': ['1.1.1.1']},
            'sip': {'role': 'SERVER', 'extension': '100', 'extensionPasswordSet': True,
                    'server': '192.168.0.169', 'port': 5060, 'transport': 'UDP', 'username': 'fixture',
                    'passwordSet': True, 'realm': '*', 'register': False, 'incomingUser': 'fixture',
                    'localPort': 5080, 'bind': '192.168.0.1', 'trustedPeers': ['192.168.0.169'],
                    'codecs': ['OPUS', 'G722', 'PCMA', 'PCMU', 'G729'], 'ca': ''},
            'wifi': {'mode': 'HOTSPOT', 'enabled': True, 'hidden': False, 'ssid': 'Fixture AP',
                     'security': 'WPA2', 'passwordSet': True, 'network': {'mode': 'DHCP', 'dns': []}},
            'lan': {'mode': 'STATIC', 'address': '192.168.0.1/24', 'subnet': '192.168.0.0/24',
                    'gateway': '192.168.0.1', 'poolStart': '192.168.0.2', 'poolEnd': '192.168.0.253',
                    'dns': ['1.1.1.1', '8.8.8.8'], 'routes': []}}
applied = deepcopy(settings)
pending = ''
started = 0
feedback = ''
password = 'fixture-password'
authenticated = True
messages = [{'id': '1', 'number': 'Fixture sender', 'text': 'Fixture only: Привет 🌍',
             'content': '', 'date': '26,10,11,12,00,00,+00', 'tag': '1', 'direction': 'received'}]
ssh = {'enabled': False, 'running': False, 'username': 'admin', 'port': 22, 'passwordSet': True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, value, code=200):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        global pending, settings, feedback
        if self.path == '/favicon.ico':
            self.send_response(204)
            return self.end_headers()
        if self.path.startswith('/api/') and not authenticated:
            return self.reply({'error': 'Sign in required'}, 401)
        if self.path == '/api/session':
            return self.reply({'csrf': 'fixture-csrf'})
        if self.path == '/api/settings':
            return self.reply(settings)
        if self.path == '/api/settings/credentials':
            return self.reply({'sipPassword': 'fixture-only-trunk', 'sipExtensionPassword': 'fixture-only-client', 'wifiPassword': 'fixture-only-wifi'})
        if self.path == '/api/status':
            if pending and time.monotonic() - started >= args.timeout:
                for key in ['wifi', 'lan', 'vowifi']:
                    settings[key] = deepcopy(applied[key])
                pending = ''
                feedback = 'Network changes were not confirmed in time and were rolled back.'
            cs = settings['voiceMode'] == 'CS'
            return self.reply({'radio': {'network_provider': 'UI fixture', 'network_type': 'GSM' if cs else 'LTE', 'simcard_roam': 'Home', 'modem_main_state': 'modem_init_complete'},
                               'gateway': {'running': True, 'role': settings['sip']['role'], 'registered': True, 'registerMode': settings['sip']['register'], 'localRegistered': True, 'activeCall': False},
                               'runtime': {'imsAccess': 'WIFI' if settings['voiceMode'] != 'VOLTE' else 'LTE', 'vowifiUplink': settings['vowifi']['uplink'], 'voiceBackend': 'cs' if cs else 'ims', 'voiceReady': True, 'imsReady': not cs, 'hostRelayRequired': False, 'registrationState': 'ready', 'callBackend': 'none'},
                               'wifi': {'mode': settings['wifi']['mode'], 'state': 'COMPLETED' if settings['wifi']['mode'] == 'CLIENT' else 'ENABLED', 'ssid': 'Fixture AP'},
                               'telegramSMS': {'running': True, 'initialized': True, 'queued': 0, 'delivered': 2, 'error': ''},
                               'interfaces': [{'name': 'bridge0', 'up': True, 'addresses': ['192.168.0.1/24']}, {'name': 'wan0', 'up': True, 'addresses': []}, {'name': 'wan5', 'up': True, 'addresses': []}], 'internetSharing': settings['internetSharing'], 'pendingNetwork': pending, 'networkReady': bool(pending) and time.monotonic() - started > 3,
                               'networkRemaining': max(0, int(args.timeout - (time.monotonic() - started))), 'networkNotice': feedback, 'networkError': ''})
        if self.path.startswith('/api/sms?'):
            return self.reply({'messages': messages, 'capacity': {'sms_nv_total': 100, 'sms_nvused_total': len(messages)}, 'transport': 'SMSoIP'})
        if self.path == '/api/system/info':
            return self.reply({'model': 'ZTE MF79U', 'controlVersion': '0.10', 'gateway': {'version': '0.8'}, 'runtime': {'version': '0.9'}, 'imei': '490154203237518', 'imeiWriteAvailable': True, 'operatorCodecs': ['AMR-WB', 'AMR-NB'], 'sipCodecs': ['Opus', 'G.722', 'PCMA', 'PCMU', 'G.729'], 'pcm': 'Mono PCM16LE 16000 Hz / 320 samples', 'native': True, 'ssh': ssh})
        if self.path.startswith('/api/system/logs?'):
            return self.reply({'text': 'Fixture log: service ready; no private data.'})
        path = BASE / ('index.html' if self.path == '/' else self.path.lstrip('/'))
        if path.parent != BASE or not path.is_file():
            return self.send_error(404)
        self.send_response(200)
        self.send_header('Content-Type', {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'}.get(path.suffix, 'text/plain'))
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def mutate(self):
        global settings, pending, started, feedback, applied, authenticated, password, messages
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or '{}')
        if self.path == '/api/login':
            if body.get('password') != password:
                return self.reply({'error': 'Incorrect password'}, 403)
            authenticated = True
            return self.reply({'csrf': 'fixture-csrf'})
        if not authenticated:
            return self.reply({'error': 'Sign in required'}, 401)
        if self.path == '/api/settings':
            settings = body
            return self.reply({'saved': True})
        if self.path == '/api/webhooks/telegram':
            settings['webhooks']['telegramSMS'] = dict(body, botTokenSet=bool(body.get('botToken') or body.get('botTokenSet')))
            settings['webhooks']['telegramSMS'].pop('botToken', None)
            return self.reply({'saved': True})
        if self.path == '/api/apply':
            feedback = ''
            if body.get('network'):
                pending, started = 'fixture-network', time.monotonic()
            else:
                applied = deepcopy(settings)
            return self.reply({'networkToken': pending})
        if self.path == '/api/network/confirm':
            if not pending or body.get('token') != pending or time.monotonic() - started < 3:
                return self.reply({'error': 'Network settings are still being applied'}, 409)
            applied, pending, feedback = deepcopy(settings), '', 'Network settings confirmed.'
            return self.reply({'ok': True})
        if self.path == '/api/network/rollback':
            for key in ['wifi', 'lan', 'vowifi']:
                settings[key] = deepcopy(applied[key])
            pending, feedback = '', 'Network changes rolled back.'
            return self.reply({'ok': True})
        if self.path == '/api/wifi/scan':
            return self.reply({'networks': [{'ssid': '<Fixture network>', 'security': 'WPA2', 'signal': -51, 'supported': True}, {'ssid': 'Fixture Open', 'security': 'OPEN', 'signal': -64, 'supported': True}, {'ssid': 'Fixture Enterprise', 'security': 'Unsupported', 'signal': -72, 'supported': False}]})
        if self.path == '/api/system/password':
            if body.get('currentPassword') != password:
                return self.reply({'error': 'Current password is incorrect'}, 400)
            if body.get('newPassword') != body.get('confirmPassword'):
                return self.reply({'error': 'Passwords do not match'}, 400)
            password, authenticated = body['newPassword'], False
            return self.reply({'signInRequired': True})
        if self.path == '/api/system/ssh':
            ssh.update(enabled=body['enabled'], running=body['enabled'])
            return self.reply(ssh)
        if self.path == '/api/sms/action':
            if body['action'] == 'delete':
                messages = []
            return self.reply({'ok': True})
        if self.path == '/api/logout':
            authenticated = False
        return self.reply({'ok': True})

    do_POST = mutate
    do_PUT = mutate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18092)
    parser.add_argument('--timeout', type=int, default=90)
    args = parser.parse_args()
    print('Disposable frontend fixture ready on loopback; no device access.', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

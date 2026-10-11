#!/usr/bin/env python3
"""Persist scoped SMS/CID customizations through the local MikoPBX API.
Secrets stay in protected backups/in-memory API responses, never printed.
Does not send messages/calls, modify credentials, or repair historical CDRs.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
PRIVATE = HERE.parent / 'private'
BACKUP = PRIVATE / 'pbx-sip-messages-pre.json'
PROVIDER = 'SIP-TRUNK-51091984'
FILES = {'42': 'sip-messages.conf', '45': 'sip-message-endpoints.conf'}


def cli(command):
    return subprocess.check_output(['docker', 'exec', 'mf79u-mikopbx',
                                    'asterisk', '-rx', command], timeout=12).decode()


def require_no_calls():
    # Asterisk retains Message/ast_msg_queue between SIP MESSAGE requests.
    if any('!' in row and not row.startswith('Message/')
           for row in cli('core show channels concise').splitlines()):
        raise RuntimeError('End PBX calls before updating routes')


def reload_saved_files(expected):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        actual = {i: subprocess.check_output(['docker', 'exec', 'mf79u-mikopbx',
                  'cat', '/etc/asterisk/' + ('extensions.conf' if i == '42' else 'pjsip.conf')],
                  timeout=8).decode() for i in FILES}
        if all(content in actual[i] and
               ('; MF79U SIP SMS BEGIN' in actual[i]) ==
               ('; MF79U SIP SMS BEGIN' in content)
               for i, content in expected.items()):
            require_no_calls()
            cli('module reload res_pjsip.so')
            cli('dialplan reload')
            return
        time.sleep(.5)
    raise RuntimeError('Saved PBX customizations have not reached generated config')


def api(path, data=None, method=None):
    cmd = ['docker', 'exec', '-i', 'mf79u-mikopbx', 'curl', '-sS', '--max-time', '40',
           'http://127.0.0.1/pbxcore/api/v3/' + path]
    if data is not None:
        cmd += ['-X', method or 'PATCH', '-H', 'Content-Type: application/json', '--data-binary', '@-']
    result = subprocess.run(cmd, input=json.dumps(data).encode() if data is not None else None,
                            capture_output=True, check=True, timeout=45)
    value = json.loads(result.stdout)
    if not value.get('result'):
        raise RuntimeError('PBX API operation failed: ' + path)  # No raw response.
    return value['data']


def main(restore):
    require_no_calls()
    current = {i: api('custom-files/' + i) for i in FILES}
    provider = api('sip-providers/' + PROVIDER)
    if restore:
        previous = json.loads(BACKUP.read_text())
        for i in FILES:
            api('custom-files/' + i, {k: previous['files'][i][k] for k in ('content', 'mode')})
        api('sip-providers/' + PROVIDER, {'cid_source': previous['provider']['cid_source']})
    else:
        PRIVATE.mkdir(mode=0o700, exist_ok=True)
        os.chmod(PRIVATE, 0o700)
        if not BACKUP.exists():
            fd = os.open(BACKUP, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w') as file:
                json.dump({'files': current, 'provider': provider}, file)
        for i, filename in FILES.items():
            item = current[i]
            if item['mode'] not in ('none', 'append'):
                raise RuntimeError('Existing custom file needs merging: ' + i)
            content = base64.b64decode(item.get('content') or '').decode()
            content = re.sub(r'(?ms)^; MF79U SIP SMS BEGIN\n.*?^; MF79U SIP SMS END\n?', '', content)
            content = content.rstrip() + '\n\n' + (HERE / filename).read_text()
            api('custom-files/' + i, {'mode': 'append', 'content': base64.b64encode(content.encode()).decode()})
        api('sip-providers/' + PROVIDER, {'cid_source': 'pai', 'cid_did_debug': '0'})
    if not restore:
        reload_saved_files({i: (HERE / filename).read_text().strip() for i, filename in FILES.items()})
        context = cli('dialplan show ' + PROVIDER + '-incoming-custom')
        if 'id([^a-z]|$)' not in context:
            raise RuntimeError('Caller privacy rule was not loaded intact')
    else:
        reload_saved_files({i: base64.b64decode(previous['files'][i].get('content') or '').decode().strip()
                            for i in FILES})
    print(json.dumps({'persistentCustomFilesSaved': True, 'restored': restore,
                      'incomingSMSExtension': '201', 'smsSent': False, 'callsMade': False}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply', action='store_true'); mode.add_argument('--restore', action='store_true')
    main(p.parse_args().restore)

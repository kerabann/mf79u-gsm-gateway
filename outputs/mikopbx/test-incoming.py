#!/usr/bin/env python3
"""One user-initiated SIM call: beep/echo, caller-ID metadata, restore PBX route.
No outbound dialling and no audio capture/export by this script.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
PROVIDER = json.loads((HERE / 'connection.json').read_text())['provider_id']
stopping = False

def stop(signum, frame):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def cli(command):
    return subprocess.check_output(['docker', 'exec', 'mf79u-mikopbx', 'asterisk', '-rx', command], timeout=10).decode()

def api(path, data=None, method=None):
    command = ['docker', 'exec', '-i', 'mf79u-mikopbx', 'curl', '-sS', '--max-time', '30', 'http://127.0.0.1/pbxcore/api/v3/' + path]
    if method:
        command += ['-X', method]
    elif data is not None:
        command += ['-X', 'POST']
    if data is not None:
        command += ['-H', 'Content-Type: application/json', '--data-binary', '@-']
    result = json.loads(subprocess.check_output(command, input=None if data is None else json.dumps(data).encode(), timeout=35))
    if not result.get('result'):
        raise RuntimeError('PBX API operation failed: ' + path)
    return result['data']

def channels():
    return [line.split('!') for line in cli('core show channels concise').splitlines() if '!' in line]

route = application = None
armed = seen = numeric_caller = False
owned = set()
started = None
try:
    if channels():
        raise RuntimeError('Existing PBX call; incoming test skipped')
    routes = api('incoming-routes')
    selected = next(item for item in routes if item['providerid'] == PROVIDER and item['rulename'] == 'MF79U SIM')
    route = api('incoming-routes/' + str(selected['id']))
    if any(item['extension'] == '880' for item in api('dialplan-applications')):
        raise RuntimeError('Test extension 880 is occupied')
    logic = '\n'.join(['1,Answer()', '2,Wait(2)', '3,PlayTones(700)', '4,Wait(3)',
                       '5,StopPlayTones()', '6,Echo()', '7,Hangup()'])
    application = api('dialplan-applications', {'extension': '880', 'name': 'MF79U standalone incoming check',
        'type': 'plaintext', 'applicationlogic': logic, 'description': 'Temporary user-initiated beep/echo and caller-ID check'})
    api('incoming-routes/' + str(route['id']), {'extension': '880'}, 'PATCH')
    armed = True
    for _ in range(40):
        if 'Local/880@internal' in cli('dialplan show ' + PROVIDER + '-incoming'):
            break
        time.sleep(.5)
    else:
        raise RuntimeError('Incoming test route has not been generated')
    print('INCOMING_TEST_READY: call modem SIM; 3-second beep then echo; hang up after speaking. 45-second watchdog.', flush=True)
    started = time.monotonic()
    seen_at = None
    while not stopping:
        rows = channels()
        current = {row[0] for row in rows}
        for row in rows:
            if row[0].startswith('PJSIP/' + PROVIDER + '-'):
                owned.add(row[0])
                if len(row) > 7:
                    numeric_caller |= re.fullmatch(r'\+?[0-9]{3,32}', row[7]) is not None
        if owned and not seen:
            seen = True
            seen_at = time.monotonic()
            print('INCOMING_PBX_CHANNEL: numeric_caller=' + str(numeric_caller), flush=True)
        if seen and not (owned & current):
            break
        if time.monotonic() - (seen_at or started) >= (45 if seen else 600):
            break
        time.sleep(.3)
finally:
    if armed and route:
        current_route = api('incoming-routes/' + str(route['id']))
        if current_route['extension'] == '880':
            api('incoming-routes/' + str(route['id']), {'extension': route['extension']}, 'PATCH')
    active = {row[0] for row in channels()}
    for channel in owned & active:
        cli('channel request hangup ' + channel)
    if application:
        api('dialplan-applications/' + application['id'], method='DELETE')
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'incoming_channel_seen': seen,
              'numeric_caller_id': numeric_caller, 'route_restored': armed,
              'outbound_calls': 0, 'audio_captured_by_script': False}
    (HERE / 'standalone-incoming-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)

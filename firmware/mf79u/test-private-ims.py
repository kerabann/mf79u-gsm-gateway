#!/usr/bin/env python3
"""Probe the isolated, non-persisting native IMS instance over ADB stdin.

Requires the RAM copy built by isolate-volte.py to be running. A test dial is
available only by explicit flag, to one authorized destination after live IMS
registration. Only allowed CP commands are forwarded; stock queues are untouched.
"""
import json
from pathlib import Path
import re
import selectors
import subprocess
import time
import sys

root = Path(__file__).resolve().parents[2]
dial_test='--dial-test' in sys.argv
if dial_test and not all(x in sys.argv for x in ['--relay','--ims-auth','--ims-state','--stop-native','--post-register-status']):
    raise RuntimeError('Test dial requires IMS authentication/state forwarding, status checks and controlled shutdown')
session_command='/dev/.mf79u-volte-probe --session'+(' --allow-test-call' if dial_test else '')
process = subprocess.Popen([str(root/'outputs/adb'), '-s', '123456789ABCDEF',
                            'shell', session_command],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, bufsize=0)
poller = selectors.DefaultSelector()
poller.register(process.stdout, selectors.EVENT_READ)
buffer = b''
events = []
test_started=time.monotonic()
stopped_pid=None
cleanup_done=False
calls_attempted=False
call_cleaned=False
relay_commands={'AT^CARDMODE', 'AT+CFUN?', 'AT+CEREG?', 'AT+CGREG?', 'AT+CREG?',
                'AT+CPIN?', 'AT+COPS?', 'AT+CEN?', 'AT+CNEM?', 'AT+CGSN', 'AT+CIMI',
                'AT+CRSM=176,28589,0,0,4', 'AT+ZMODE?', 'AT+CSMS?', 'AT+CSTA?', 'AT^ZCSVOICESPT'}

def receive(duration):
    global buffer
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        ready = poller.select(max(0, deadline-time.monotonic()))
        if not ready:
            break
        chunk = process.stdout.read(4096)
        if not chunk:
            break
        buffer += chunk
        while b'\n' in buffer:
            raw, buffer = buffer.split(b'\n', 1)
            line = raw.decode(errors='replace').rstrip('\r')
            if line.startswith('REPLY '):
                # Legacy ADB PTY echoes stdin. Never persist raw CP replies.
                continue
            m = re.fullmatch(r'MESSAGE cmd=0x([0-9a-f]+) port=(\d+) hex=([0-9a-f]*)', line)
            if m:
                item = {'message_id': '0x'+m[1], 'port': int(m[2]),
                        'text': bytes.fromhex(m[3]).decode(errors='replace')}
            else:
                item = {'status': line}
            logged_item=dict(item)
            logged_item['elapsed_s']=round(time.monotonic()-test_started,3)
            for field in ('text','status'):
                if field in logged_item:
                    logged_item[field]=logged_item[field].replace('TEST_DESTINATION_E164','[authorized test number]').replace('TEST_DESTINATION_LOCAL','[authorized local number]')
            if 'text' in logged_item:
                logged_item['text']=re.sub(r'\b\d{14,16}\b','[identifier redacted]',logged_item['text'])
                if logged_item['text'].startswith('AT^MBAU='):
                    logged_item['text']='AT^MBAU=[AKA challenge omitted]'
            events.append(logged_item)
            print(json.dumps(logged_item, ensure_ascii=False), flush=True)
            if '--relay' in sys.argv and not stopped_pid and m and m[1]=='150c':
                command=item['text'].strip('\r\n\x00')
                ims_command = ('--ims-bearer' in sys.argv and
                    (command == 'AT+ZPDPACT=0,"IPV4V6","ims",0,1,1' or
                     command in {'AT+CGCONTRDP=5', 'AT+ZPDPDEACT=5', 'AT+CEREG=2'}))
                ims_state_command=('--ims-state' in sys.argv and command in {'AT+ZIMSSTATE=0','AT+ZIMSSTATE=1'})
                call_setup_command=(dial_test and command in {'AT+ZNUMTYPE="TEST_DESTINATION_E164"','AT+ZNUMTYPE="TEST_DESTINATION_LOCAL"'})
                aka_command = ('--ims-auth' in sys.argv and bool(re.fullmatch(
                    r'AT\^MBAU="[0-9a-fA-F]{32}","[0-9a-fA-F]{32}"',command)))
                if command not in relay_commands and not ims_command and not aka_command and not ims_state_command and not call_setup_command:
                    print(json.dumps({'relay_blocked_command': logged_item['text']}),flush=True)
                    continue
                try:
                    reply=subprocess.run([str(root/'outputs/zte-native-usb'),command],
                                         capture_output=True,check=True,timeout=8).stdout
                except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
                    raise RuntimeError('CP request failed: '+('AT^MBAU [AKA]' if aka_command else command)) from None
                # The backend expects a complete AT transaction, while USB
                # transfers can prepend unsolicited PDP/RF notifications.
                # Keep the response plus terminal result together. USB does
                # not supply the native URC channel ID; injecting those PDP
                # notifications into a request channel causes duplicate setup.
                response_lines=[x.strip() for x in reply.splitlines() if x.strip()]
                if aka_command:
                    # Inspect only the status/field sizes, never the RES/CK/IK/AUTS values.
                    aka_lines=[x for x in response_lines if x.startswith(b'^MBAU:')]
                    shape={'aka_response_lines':len(aka_lines),'aka_reply_held':'--hold-aka-reply' in sys.argv}
                    if len(aka_lines)==1:
                        fields=aka_lines[0].split(b':',1)[1].strip().split(b',')
                        if fields and fields[0].strip() in (b'0',b'1',b'2'):
                            shape['aka_status']=int(fields[0])
                        shape['aka_field_lengths']=[len(x.strip().strip(b'"')) for x in fields[1:]]
                    events.append(shape);print(json.dumps(shape),flush=True)
                transaction=[]; notifications=[]
                for response_line in response_lines:
                    if response_line==command.encode() or response_line.startswith(b'+ZEPCG:'):
                        continue
                    (notifications if response_line.startswith((b'+CGEV:',b'+ZGIPDNS:'))
                     else transaction).append(response_line)
                if transaction and not (aka_command and '--hold-aka-reply' in sys.argv):
                    send('REPLY '+m[2]+' '+(b'\r\n'+b'\r\n'.join(transaction)+b'\r\n').hex())
                relay_event={'relayed_command':'AT^MBAU [AKA]' if aka_command else 'AT+ZNUMTYPE [authorized number]' if call_setup_command else command,
                                  'read_only':command in relay_commands or command=='AT+CGCONTRDP=5',
                                  'pdp_notifications_not_replayed':len(notifications),
                                  'terminal_result':'OK' if b'OK' in response_lines else
                                      'ERROR' if any(b'ERROR' in x for x in response_lines) else 'none',
                                  'response_bytes':len(reply)}
                events.append(relay_event);print(json.dumps(relay_event),flush=True)

def send(command):
    process.stdin.write((command+'\n').encode())
    process.stdin.flush()

def cp_query(command):
    return subprocess.run([str(root/'outputs/zte-native-usb'),command],
                          capture_output=True,check=True,timeout=8).stdout.decode(errors='replace')

try:
    receive(.5)
    if not any(e.get('status', '').startswith('READY') for e in events):
        raise RuntimeError('Private IPC session unavailable')
    commands=['AT+CVMOD=?', 'AT+CVMOD=3', 'AT+CVMOD?', 'AT+CLCC',
              'AT+ZIMSAPN?', 'AT+ZIMSAMRW?']
    if '--prefer-amr-nb' in sys.argv:commands=['AT+ZIMSAMRW=0','AT+ZIMSAMRW?']+commands
    if '--ims-profile' in sys.argv:
        commands += ['AT+ZIMSTEST="NET_IMS_CAP"', 'AT+ZIMSAPN="ims"',
                     'AT+ZIMSAPN?', 'AT+ZIMSTEST="NET_IMS_CAP",1',
                     'AT+ZIMSTEST="NET_IMS_CAP"']
    elif '--network-state' in sys.argv:
        commands += ['AT+ZIMSAPN="ims"', 'AT+ZIMSAPN?']
    if '--initialize' in sys.argv:
        commands += ['AT+AUTOSTART=1', 'AT+CFUN=1']
    if '--cp-status' in sys.argv:
        reply=subprocess.run([str(root/'outputs/zte-native-usb'),'AT+CEREG?'],
                             capture_output=True,check=True,timeout=8).stdout.decode(errors='replace')
        match=re.search(r'\+CEREG:\s*\d+,([^\r\n]+)',reply)
        if not match:
            raise RuntimeError('Real CP registration status unavailable')
        # Convert the query response's n,stat,... to the stat,... URC layout.
        status=('\r\n+CEREG: '+match[1]+'\r\n').encode()
        if '--reset-private-state' in sys.argv:
            # Explicit synthetic fixture, confined to the private IMS process.
            # Does not disconnect the real CP or count as live network evidence.
            commands += ['STATUS '+b'\r\n+CEREG: 0\r\n'.hex()]
        commands += ['STATUS '+status.hex()]
    if '--network-state' in sys.argv:
        # Explicit query-to-indication adapter. These are derived status messages,
        # not a claim that the modem emitted the corresponding unsolicited lines.
        sysinfo=re.search(r'\^SYSINFO:\s*([^\r\n]+)',cp_query('AT^SYSINFO'))
        capability=re.search(r'\+CIREP:\s*\d+,(\d+)',cp_query('AT+CIREP?'))
        if not sysinfo or not capability:
            raise RuntimeError('Real network metadata unavailable')
        fields=sysinfo[1].split(',')
        if len(fields)!=7 or not fields[3].isdigit() or not fields[6].isdigit():
            raise RuntimeError('Unexpected SYSINFO layout')
        commands += ['STATUS '+('\r\n^MODE: '+fields[3]+','+fields[6]+'\r\n').encode().hex(),
                     'STATUS '+('\r\n+CIREPI: '+capability[1]+'\r\n').encode().hex()]
    commands += ['AT+CVMOD=0', 'AT+CVMOD?']
    for command in commands:
        if command=='AT+CVMOD=0' and '--ims-auth' in sys.argv:
            seconds=8 if '--inspect-sa' in sys.argv else 40
            print(json.dumps({'status':f'Waiting {seconds} seconds for IMS authentication/registration'}),flush=True)
            receive(seconds)
            if '--post-register-status' in sys.argv:
                status_start=len(events)
                send('AT+CLCC');receive(2)
                send('AT+CVMOD?');receive(2)
                if dial_test:
                    if '--prefer-amr-nb' in sys.argv and not any('+ZIMSAMRW: 0' in e.get('text','') for e in events):
                        raise RuntimeError('Test dial skipped: AMR-WB was not disabled in the private process')
                    registered=any(e.get('relayed_command')=='AT+ZIMSSTATE=1' and e.get('terminal_result')=='OK' for e in events)
                    responsive=any('+CVMOD: 3' in e.get('text','') for e in events[status_start:])
                    occupied=any('+CLCC:' in e.get('text','') for e in events[status_start:])
                    print(json.dumps({'test_call_readiness':{'registered':registered,'frontend_responsive':responsive,'existing_call':occupied}}),flush=True)
                    if not registered or not responsive or occupied:
                        raise RuntimeError('Test dial skipped: live IMS/state/frontend readiness is not confirmed or a call already exists')
                    calls_attempted=True
                    send('ATDTEST_DESTINATION_LOCAL;' if '--local-number' in sys.argv else 'ATDTEST_DESTINATION_E164;');receive(32)
                    send('ATH');receive(2)
                    send('AT+CHUP');receive(2)
                    call_cleaned=True
                    send('AT+CLCC');receive(2)
        send(command)
        receive(18 if command.startswith('STATUS ') else 8 if command=='AT+CFUN=1' else 1)
    if '--stop-native' in sys.argv:
        stopped=subprocess.run([sys.executable,str(Path(__file__).with_name('stop-private-ims.py')),
                                '--terminate-only'],capture_output=True,check=True,timeout=15)
        match=re.search(rb'Stopped test PID (\d+)',stopped.stdout)
        if not match:raise RuntimeError('Native stop identity unavailable')
        stopped_pid=match[1].decode()
        print(json.dumps({'status':'Native daemon stopped before removing probe queue',
                          'pid':int(stopped_pid)}),flush=True)
    send('QUIT')
    receive(.5)
    process.wait(timeout=5)
    if stopped_pid:
        cleaned=subprocess.run([sys.executable,str(Path(__file__).with_name('stop-private-ims.py')),
                                '--cleanup-only',stopped_pid],capture_output=True,check=True,timeout=20)
        print(json.dumps({'status':cleaned.stdout.decode().strip()}),flush=True)
        cleanup_done=True
finally:
    if calls_attempted and not call_cleaned and not stopped_pid and process.poll() is None:
        try:
            send('ATH');receive(2);send('AT+CHUP');receive(2)
            call_cleaned=True
        except Exception:
            print(json.dumps({'cleanup_error':'Native test hangup could not be confirmed; closing IMS bearer'}),flush=True)
    if '--stop-native' in sys.argv and not stopped_pid:
        stopped=subprocess.run([sys.executable,str(Path(__file__).with_name('stop-private-ims.py')),
                                '--terminate-only'],capture_output=True,timeout=15)
        match=re.search(rb'Stopped test PID (\d+)',stopped.stdout)
        if stopped.returncode==0 and match:stopped_pid=match[1].decode()
        else:print(json.dumps({'cleanup_error':'Could not verify native shutdown; inspect device before restarting'}),flush=True)
    if process.poll() is None:
        # Close only this host ADB session. The remote helper has a 360s timeout.
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
    if stopped_pid and not cleanup_done:
        subprocess.run([sys.executable,str(Path(__file__).with_name('stop-private-ims.py')),
                       '--cleanup-only',stopped_pid],check=True,timeout=20)
    if '--ims-state' in sys.argv:
        # These runtime flags/bearer belong to this isolated IMS test. Keep CID1.
        for command in ['AT+ZIMSSTATE=0','AT+ZPDPDEACT=5']:
            if any(e.get('relayed_command')==command and e.get('terminal_result')=='OK' for e in events):continue
            result=subprocess.run([str(root/'outputs/zte-native-usb'),command],capture_output=True,timeout=8)
            ok=result.returncode==0 and b'OK' in result.stdout.splitlines()
            print(json.dumps({'fallback_runtime_cleanup':command,'terminal_ok':ok}),flush=True)
    poller.close()
    (root/'firmware/mf79u/build/private-ims-test.json').write_text(
        json.dumps({'calls_attempted': calls_attempted,'native_hangup_submitted':call_cleaned, 'cp_forwarding': '--relay' in sys.argv,
                    'ims_bearer_allowed':'--ims-bearer' in sys.argv,
                    'ims_auth_allowed':'--ims-auth' in sys.argv,
                    'ims_state_allowed':'--ims-state' in sys.argv,
                    'aka_reply_held':'--hold-aka-reply' in sys.argv,
                    'events': events}, ensure_ascii=False, indent=2)+'\n')

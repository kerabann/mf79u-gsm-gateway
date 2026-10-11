#!/usr/bin/env python3
"""RAM-only modem SIP gateway plus factory-USB CP relay. No raw CP logs.
Calls are driven by configured trusted PBX peers. The modem validates numeric
destinations separately from authentication. Ctrl-C shuts down our IMS
instance and its own bearer/queues.
"""
import json
import ipaddress
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
from ram_transfer import ram_push

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'firmware/mf79u/build'
ADB=[str(ROOT/'outputs/adb'),'-s','123456789ABCDEF']
CP=str(ROOT/'outputs/zte-native-usb')
POLL=selectors.DefaultSelector()
processes={}
buffers={}
registered=False
running=True
call_active=False
last_frontend=''
last_amrwide=''
adaptive_audio='--adaptive-audio' in sys.argv
native_started=False
gateway_started=False
started_at=time.monotonic()
last_network_status=None
owned_return_route=None
read_only={'AT^CARDMODE','AT+CFUN?','AT+CEREG?','AT+CGREG?','AT+CREG?',
    'AT+CPIN?','AT+COPS?','AT+CEN?','AT+CNEM?','AT+CGSN','AT+CIMI',
    'AT+CRSM=176,28589,0,0,4','AT+ZMODE?','AT+CSMS?','AT+CSTA?','AT^ZCSVOICESPT'}
runtime={'AT+ZPDPACT=0,"IPV4V6","ims",0,1,1','AT+CGCONTRDP=5',
         'AT+ZPDPDEACT=5','AT+CEREG=2','AT+ZIMSSTATE=0','AT+ZIMSSTATE=1',
         'AT+ZNUMTYPE="TEST_DESTINATION_LOCAL"','AT+ZNUMTYPE="TEST_DESTINATION_E164"'}

def report(event,**fields):
    print(json.dumps({'time':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                      'elapsed':round(time.monotonic()-started_at,1),
                      'event':event,**fields}),flush=True)

def cp(command):
    return subprocess.run([CP,command],capture_output=True,check=True,timeout=8).stdout

def shell(command,timeout=12):
    return subprocess.run(ADB+['shell',command],capture_output=True,check=True,timeout=timeout).stdout.decode(errors='replace')

def ensure_pbx_return_route():
    """Docker Desktop uses the Mac primary IPv4 as its outbound UDP source."""
    global owned_return_route
    default=subprocess.check_output(['route','-n','get','default'],timeout=5).decode()
    interface=re.search(r'interface:\s*(\w+)',default)
    if not interface:raise RuntimeError('Mac primary interface unavailable')
    addresses=subprocess.check_output(['ifconfig',interface[1]],timeout=5).decode()
    address=re.search(r'\binet\s+(\d+\.\d+\.\d+\.\d+)\b',addresses)
    if not address:raise RuntimeError('Mac primary IPv4 unavailable')
    host=ipaddress.IPv4Address(address[1])
    if host in ipaddress.IPv4Network('192.168.0.0/24'):return
    prefix=str(host)+'/32';spec=prefix+' via 192.168.0.169 dev bridge0'
    routes=[line.split() for line in shell('ip route show').splitlines() if line.split()]
    existing=next((r for r in routes if r[0] in (str(host),prefix)),None)
    if existing:
        if existing[1:5]!=['via','192.168.0.169','dev','bridge0']:
            raise RuntimeError('Existing PBX return route uses another path')
    else:
        if 'MF79U_RETURN_ROUTE_OK' not in shell('ip route add '+spec+' && echo MF79U_RETURN_ROUTE_OK'):
            raise RuntimeError('PBX return route was not installed')
        owned_return_route=spec
    report('pbx_return_route_ready',source=str(host),via='192.168.0.169',persistent=False)

def spawn(name,command):
    process=subprocess.Popen(ADB+['shell',command],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0,start_new_session=True)
    processes[name]=process;buffers[name]=b'';POLL.register(process.stdout,selectors.EVENT_READ,name)
    return process

def send(name,line):
    p=processes[name]
    if p.poll() is not None:raise RuntimeError(name+' has exited')
    p.stdin.write((line+'\n').encode());p.stdin.flush()

def refresh_network_status():
    """Recheck attach while IMS starts; CFUN can finish before LTE registers."""
    global last_network_status
    registration=re.search(r'\+CEREG:\s*\d+,([^\r\n]+)',cp('AT+CEREG?').decode())
    system=re.search(r'\^SYSINFO:\s*([^\r\n]+)',cp('AT^SYSINFO').decode())
    capability=re.search(r'\+CIREP:\s*\d+,(\d+)',cp('AT+CIREP?').decode())
    if not registration or not system or not capability:raise RuntimeError('Live CP network state unavailable')
    fields=system[1].split(',')
    if len(fields)!=7 or not fields[3].isdigit() or not fields[6].isdigit():raise RuntimeError('Unexpected CP system state')
    status=(registration[1],fields[3],fields[6],capability[1])
    if status!=last_network_status:
        for text in ['\r\n+CEREG: '+status[0]+'\r\n',
                     '\r\n^MODE: '+status[1]+','+status[2]+'\r\n',
                     '\r\n+CIREPI: '+status[3]+'\r\n']:
            send('ipc','STATUS '+text.encode().hex());pump(2)
        last_network_status=status

def native_event(text):
    global call_active,last_frontend,last_amrwide
    if '+CVMOD:' in text:last_frontend=text
    if '+ZIMSAMRW:' in text:last_amrwide=text
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('^DSCI:'):
            m=re.match(r'\^DSCI:\s*(\d+),(\d+),(\d+)',line)
            if not m:continue
            state=int(m[3]);report('cellular_call_state',index=int(m[1]),direction=int(m[2]),state=state)
            if state in (4,5) and not call_active:
                call_active=True
                if gateway_started:send('sip','INCOMING')
            elif state==3 and gateway_started:send('sip','ALERT')
            elif state==0 and gateway_started:send('sip','CONNECTED')
            elif state==6:
                call_active=False
                if gateway_started:send('sip','ENDED')
        elif line.startswith('^CONN:'):
            report('cellular_connected')
            if gateway_started:send('sip','CONNECTED')
        elif line.startswith('^CEND:'):
            call_active=False;report('cellular_ended')
            if gateway_started:send('sip','ENDED')

def handle(name,line):
    global registered,call_active
    if name=='sip':
        if re.fullmatch(r'DIAL \+?[0-9]{3,32}',line):
            if not registered:send('sip','ENDED');return
            call_active=True;send('ipc','ATD'+line[5:]+';');report('pbx_dial_trusted_peer')
        elif line=='HANGUP':
            if native_started:send('ipc','ATH');send('ipc','AT+CHUP')
            call_active=False;report('pbx_hangup')
        elif line=='ANSWER':send('ipc','ATA');report('pbx_answer')
        elif line.startswith(('GATEWAY_','SIP_','PCM_STATS','PCM_QUEUE','REJECT_')):report(line)
        return
    m=re.fullmatch(r'MESSAGE cmd=0x([0-9a-f]+) port=(\d+) hex=([0-9a-f]*)',line)
    if not m:
        if line.startswith(('ERROR','REJECT')):raise RuntimeError('IPC rejected a control message')
        return
    text=bytes.fromhex(m[3]).decode(errors='replace')
    if m[1]=='150a':native_event(text);return
    if m[1]!='150c':return
    command=text.strip('\r\n\x00')
    aka=bool(re.fullmatch(r'AT\^MBAU="[0-9a-fA-F]{32}","[0-9a-fA-F]{32}"',command))
    classification=bool(re.fullmatch(r'AT\+ZNUMTYPE="\+?[0-9]{3,32}"',command))
    if not aka and not classification and command not in read_only and command not in runtime:
        raise RuntimeError('Native IMS requested an unlisted CP operation')
    reply=cp(command)
    response=[x.strip() for x in reply.splitlines() if x.strip()]
    transaction=[x for x in response if x!=command.encode() and not x.startswith((b'+ZEPCG:',b'+CGEV:',b'+ZGIPDNS:'))]
    if transaction:send('ipc','REPLY '+m[2]+' '+(b'\r\n'+b'\r\n'.join(transaction)+b'\r\n').hex())
    if command in ('AT+ZIMSSTATE=0','AT+ZIMSSTATE=1') and b'OK' in response:
        registered=command.endswith('1');report('ims_registration',registered=registered)
        if gateway_started:send('sip','READY' if registered else 'NOT_READY')

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        for key,_ in POLL.select(min(.25,max(0,deadline-time.monotonic()))):
            name=key.data;chunk=os.read(key.fileobj.fileno(),8192)
            if not chunk:raise RuntimeError(name+' connection closed')
            buffers[name]+=chunk
            if len(buffers[name])>65536:raise RuntimeError('Unexpected unframed control output')
            while b'\n' in buffers[name]:
                raw,buffers[name]=buffers[name].split(b'\n',1)
                handle(name,raw.decode(errors='replace').rstrip('\r'))

def stop_signal(signum,frame):
    global running
    running=False

signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal)
try:
    if any(int(line.split()[0])==0x701e for line in shell('cat /proc/sysvipc/msg').splitlines()[1:] if line.split()):
        raise RuntimeError('A private IMS process is already active')
    subprocess.run(['python3',str(ROOT/'firmware/mf79u/start-private-ims.py'),
        '--userspace-ipsec','--software-media','--network-media']+
        (['--prefer-high-amr'] if '--prefer-high-amr' in sys.argv or adaptive_audio else [])+
        (['--adaptive-audio'] if adaptive_audio else [])+
        (['--legacy-operator-codecs'] if '--legacy-operator-codecs' in sys.argv else [])+
        (['--operator-codec',sys.argv[sys.argv.index('--operator-codec')+1]] if '--operator-codec' in sys.argv else []),check=True,stdout=subprocess.DEVNULL)
    native_started=True
    spawn('ipc','/dev/.mf79u-volte-probe --session --gateway');pump(.5)
    for command in ['AT+ZIMSAMRW='+('1' if adaptive_audio else '0'),'AT+CVMOD=3','AT+ZIMSAPN="ims"','AT+AUTOSTART=1','AT+CFUN=1']:
        send('ipc',command);pump(8 if command=='AT+CFUN=1' else 1)
    refresh_network_status()
    report('waiting_for_ims_registration')
    registration_deadline=time.monotonic()+300
    next_network_check=time.monotonic()+15
    while running and not registered and time.monotonic()<registration_deadline:
        pump(1)
        if running and not registered and time.monotonic()>=next_network_check:
            refresh_network_status();next_network_check=time.monotonic()+15
    if not running:raise SystemExit(0)
    send('ipc','AT+CVMOD?');pump(2)
    send('ipc','AT+ZIMSAMRW?');pump(1)
    if not registered or '+CVMOD: 3' not in last_frontend:
        raise RuntimeError('IMS registration/frontend readiness not confirmed')
    if not re.search(r'\+ZIMSAMRW:\s*'+('1' if adaptive_audio else '0')+r'\b',last_amrwide):
        raise RuntimeError('AMR-WB advertisement preference not confirmed')
    ram_push(ADB,BUILD/'modem-sip-gateway','/dev/.mf79u-sip-gateway')
    shell('chmod 755 /dev/.mf79u-sip-gateway')
    ensure_pbx_return_route()
    spawn('sip','/dev/.mf79u-sip-gateway --config /mnt/userdata/mf79u/gateway.ini'+(' --wideband' if adaptive_audio else ''));gateway_started=True;pump(1)
    send('sip','READY');pump(1)
    report('pbx_gateway_running',modem='192.168.0.1:5080',pbx='192.168.0.169:5060')
    (BUILD/'pbx-gateway-host-pid.txt').write_text(str(os.getpid())+'\n')
    last_stats=time.monotonic()
    while running:
        pump(.5)
        if time.monotonic()-last_stats>=30:
            send('sip','STATS');last_stats=time.monotonic()
finally:
    report('gateway_cleanup')
    if native_started and 'ipc' in processes and processes['ipc'].poll() is None:
        try:
            if gateway_started:send('sip','NOT_READY')
            send('ipc','ATH');send('ipc','AT+CHUP');pump(2)
            send('ipc','AT+CVMOD=0');pump(8)
        except Exception:report('control_cleanup_failed')
    if gateway_started and processes['sip'].poll() is None:
        try:send('sip','QUIT');pump(.5)
        except Exception:pass
    if native_started:
        result=subprocess.run(['python3',str(ROOT/'firmware/mf79u/stop-private-ims.py'),
                               '--terminate-only'],capture_output=True,timeout=20)
        match=re.search(rb'Stopped test PID (\d+)',result.stdout)
        if match:
            if 'ipc' in processes and processes['ipc'].poll() is None:
                try:send('ipc','QUIT');pump(.5)
                except Exception:pass
            subprocess.run(['python3',str(ROOT/'firmware/mf79u/stop-private-ims.py'),
                            '--cleanup-only',match[1].decode()],capture_output=True,timeout=20)
        else:report('native_shutdown_not_confirmed')
        for command in ['AT+ZIMSSTATE=0','AT+ZPDPDEACT=5']:
            try:cp(command)
            except Exception:report('bearer_cleanup_failed')
    for process in processes.values():
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.terminate()
    if owned_return_route:
        try:
            prefix=owned_return_route.split()[0]
            expected=owned_return_route.split()[1:5]
            routes=[line.split() for line in shell('ip route show').splitlines() if line.split()]
            route=next((r for r in routes if r[0] in (prefix,prefix[:-3])),None)
            if route and route[1:5]==expected:
                if 'MF79U_RETURN_ROUTE_REMOVED' not in shell('ip route del '+owned_return_route+' && echo MF79U_RETURN_ROUTE_REMOVED'):
                    raise RuntimeError('Owned PBX return route cleanup failed')
        except Exception:report('return_route_cleanup_failed')
    POLL.close()

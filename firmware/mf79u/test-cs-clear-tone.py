#!/usr/bin/env python3
"""One authorized DSP-tone call: observe the real ASC clearing wire metadata.

The remote phone must be observed separately. Local RELEASE/MM clearing never
sets remote_hangup_verified. Destination stays on stdin/in-memory pipes only.
"""
from pathlib import Path
import argparse, datetime, importlib.util, json, re, subprocess, sys, time

BASE=Path(__file__).resolve().parent; BUILD=BASE/'build'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--authorized-single-dial',action='store_true')
p.add_argument('--instance',type=int,required=True)
p.add_argument('--asc-instance',type=int,required=True)
p.add_argument('--signaling-only',action='store_true',help='No DSP commands; isolate clearing from audio shutdown')
args=p.parse_args()
if not args.authorized_single_dial:p.error('Explicit outgoing-call authorization required')
if not all(1<=n<=32 for n in (args.instance,args.asc_instance)):p.error('Fresh instances1..32 required')
number=sys.stdin.buffer.readline(34).strip()
if not re.fullmatch(rb'[0-9]{5,32}',number):raise SystemExit('Numeric authorized destination required on stdin')
def load(name,file):
    s=importlib.util.spec_from_file_location(name,BASE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
radio=load('clear_radio','test-cs-reattach.py');restore=load('clear_restore','restore-cs-test.py')
def run(file,*arguments,timeout=60,input_bytes=None):
    r=subprocess.run(['python3',str(BASE/file),*arguments],input=input_bytes,
                     stdin=subprocess.DEVNULL if input_bytes is None else None,capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError(file+' failed: '+(r.stderr or r.stdout).decode(errors='replace')[-1000:])
    return r.stdout.decode()
def wait(predicate,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        s=radio.status()
        if predicate(s):return s
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')
def audit():
    run('test-cs-kernel-probe.py','--routing');r=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not r.get('restoration_verified'):raise RuntimeError('Original callbacks/MM not confirmed')
    return r
before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
guard='/mnt/userdata/mf79u/native-ring-only'
module='mf79u_cs_mo'+(str(args.instance) if args.instance!=1 else '')
asc_module='mf79u_cs_asc'+(str(args.asc_instance) if args.asc_instance!=1 else '')
asc_output='cs-asc-watch'+(str(args.asc_instance) if args.asc_instance!=1 else '')
mo_output='cs-mo-probe'+(str(args.instance) if args.instance!=1 else '')
if (before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady')
        or json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall')):raise SystemExit('Idle production IMS required')
if radio.shell('test -e '+guard+' && echo PRESENT')=='PRESENT':raise SystemExit('Guard already owned')
if any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')) or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):raise SystemExit('Expected production flags/profile required')
if any(row.split()[0] in (module,asc_module) for row in radio.shell('cat /proc/modules').splitlines()):raise SystemExit('Pinned instance already used')
if radio.shell('test -e /sys/mf79u_cs/status || test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':raise SystemExit('Previous CS callback active')
stem='cs-mo'+str(args.instance)+('-clear-signaling' if args.signaling_only else '-clear-tone');call_report=stem+'-live.json'
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,
        'explicitly_authorized_single_dial':True,'number_saved':False,'speech_saved':False,
        'arm_i2s_enabled':False,'production_voice_backend':False,'remote_hangup_verified':False,
        'dsp_commands_enabled':not args.signaling_only}
guarded=False;asc_deadline=0;sample_start=0
try:
    options=['--mo','--instance',str(args.instance)]
    if not args.signaling_only:options.append('--dsp-tone-candidate')
    run('build-cs-kernel-probe.py',*options,'--seconds','240')
    report['build']=json.loads((BUILD/(mo_output+'-build.json')).read_text())
    run('build-cs-kernel-probe.py','--asc','--instance',str(args.asc_instance),'--seconds','100')
    report['asc_build']=json.loads((BUILD/(asc_output+'-build.json')).read_text())
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard);guarded=True
    wait(lambda s:s.get('ringOnly'),20);report['before_route_audit']=audit()
    print('Preparing one '+('signaling-only' if args.signaling_only else 'DSP-tone')+' call with passive ASC clearing observation.',flush=True)
    run('prepare-cs-channel-test.py',timeout=150)
    old=BUILD/'cs-mo-outgoing-live.json'
    if old.exists():
        dest=BUILD/('cs-mo-outgoing-before-'+stem+'.json')
        if dest.exists():raise RuntimeError('Existing archive; refusing overwrite')
        dest.write_bytes(old.read_bytes());dest.chmod(0o600);old.unlink()
    sample_start=float(radio.shell('cat /proc/uptime').split()[0])
    # MO checks the original ASC callback. Install it first, then chain ASC.
    run('arm-cs-kernel-watch.py',*options,'--authorized-single-dial')
    report['armed']=json.loads((BUILD/(mo_output+'-armed.json')).read_text())
    asc_deadline=time.monotonic()+145
    run('arm-cs-kernel-watch.py','--asc','--instance',str(args.asc_instance))
    report['asc_armed']=json.loads((BUILD/(asc_output+'-armed.json')).read_text())
    subprocess.run(['afplay','/System/Library/Sounds/Glass.aiff'],check=True,timeout=10,stdin=subprocess.DEVNULL)
    print('DIALING: answer; '+('silence expected; observe the timer for45s.' if args.signaling_only else 'after tone stops leave the phone connected for30s to observe remote clearing.'),flush=True)
    try:report['dial_output']=run('dial-cs-mo-probe.py',timeout=135,input_bytes=number+b'\n')
    finally:number=b''
    if old.exists():
        (BUILD/call_report).write_bytes(old.read_bytes());(BUILD/call_report).chmod(0o600)
        report['call']=json.loads(old.read_text())
    if not report.get('call',{}).get('connected'):raise RuntimeError('Call not connected')
finally:
    number=b''
    try:
        if guarded:
            end=time.monotonic()+270
            while radio.shell('test -e /sys/mf79u_cs/status || test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':
                if time.monotonic()>=end:raise RuntimeError('CS callback active; retain guard')
                time.sleep(1)
            # ASC has its own bounded callback lifetime. Await its exact new
            # expiry before the independent route audit and production restore.
            if asc_deadline:
                while True:
                    rows=radio.shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_ASC | tail -n 250").splitlines()
                    fresh=[row for row in rows if (m:=re.search(r'\[\s*([0-9.]+)\]',row)) and float(m[1])>=sample_start]
                    report['asc_messages']=fresh
                    if any('expired seconds=100 ' in row and 'callback_restored=1' in row for row in fresh):break
                    if time.monotonic()>=asc_deadline:raise RuntimeError('ASC expiry unconfirmed; retain guard')
                    time.sleep(1)
            radio.radio(0);report['radio_off_route_audit']=audit()
            restore.main();radio.radio(1);wait(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            report['final_route_audit']=audit();radio.shell('rm -f '+guard);wait(lambda s:not s.get('ringOnly'),20)
            if not (BUILD/call_report).exists():(BUILD/call_report).write_text(json.dumps({'before':before,'boot_id':boot})+'\n')
            run('verify-cs-test-restored.py','--call-report',call_report,'--output',stem+'-restore.json')
            report['runtime_restored']=True
    except Exception as exc:report['restore_error']=str(exc);raise
    finally:
        report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        path=BUILD/(stem+'-test.json');path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
print('RESTORED: LTE/IMS, flags/profile, original callbacks/MM and guards independently verified.',flush=True)

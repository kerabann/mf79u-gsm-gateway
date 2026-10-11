#!/usr/bin/env python3
"""Correlate read-only B03 SRAM statistics with one authorized DSP-tone call.

The destination is read from stdin and passed only through a pipe. No sample,
hash, destination or speech recording is saved. The already audible DSP tone
is used without enabling an ARM audio port. Restore LTE/IMS after CC clearing.
"""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, re, subprocess, sys, time

BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--authorized-single-dial',action='store_true')
parser.add_argument('--instance',type=int,required=True)
args=parser.parse_args()
if not args.authorized_single_dial:parser.error('Explicit outgoing-call authorization required')
if not 2<=args.instance<=32:parser.error('Use a fresh pinned MO instance2..32')
number=sys.stdin.buffer.readline(34).strip()
if not re.fullmatch(rb'[0-9]{5,32}',number):raise SystemExit('Numeric authorized destination required on stdin')

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,BASE/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
radio=load('pcm_tone_radio','test-cs-reattach.py')
restore=load('pcm_tone_restore','restore-cs-test.py')
def run(filename,*arguments,timeout=60,input_bytes=None):
    p=subprocess.run(['python3',str(BASE/filename),*arguments],input=input_bytes,
                     stdin=subprocess.DEVNULL if input_bytes is None else None,
                     capture_output=True,timeout=timeout)
    if p.returncode:
        # Destination never appears in the called scripts' messages.
        raise RuntimeError(filename+' failed: '+(p.stderr or p.stdout).decode(errors='replace')[-1000:])
    return p.stdout.decode()
def wait_status(predicate,seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        state=radio.status()
        if predicate(state):return state
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')
def route_audit():
    run('test-cs-kernel-probe.py','--routing')
    r=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not r.get('restoration_verified'):raise RuntimeError('Original callbacks/MM not confirmed')
    return r

idle_path=BUILD/'cs-pcm-metadata-idle-live.json'
idle=json.loads(idle_path.read_text());sampler=json.loads((BUILD/'cs-channel-watch-build.json').read_text())
sampler_sha=hashlib.sha256((BUILD/'mf79u_cs_channels.ko').read_bytes()).hexdigest()
if (not all(idle.get(k) is True for k in ('layout_accepted','runtime_restored','no_sim_calls','no_dsp_commands'))
        or not sampler.get('dsp_pcm_metadata')
        or sampler_sha!=idle['armed']['build']['sha256']
        or sampler_sha!=sampler['sha256']
        or sampler['pcm_window_report_sha256']!=idle['armed']['build']['pcm_window_report_sha256']):
    raise SystemExit('Matching successful read-only idle sampler receipt required')
before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
guard='/mnt/userdata/mf79u/native-ring-only';module='mf79u_cs_mo'+str(args.instance)
if (before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady')
        or json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall')):
    raise SystemExit('Idle production IMS required')
if radio.shell('test -e '+guard+' && echo PRESENT')=='PRESENT':raise SystemExit('Guard already owned')
if (any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'))
        or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?')):
    raise SystemExit('Expected production flags/profile required')
modules=radio.shell('cat /proc/modules').splitlines()
if any(row.startswith(module+' ') or row.startswith('mf79u_cs_channels ') for row in modules):
    raise SystemExit('Pinned instance already used or sampler owned')
if radio.shell('test -e /sys/mf79u_cs/status || test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':
    raise SystemExit('Previous CS callback active')
stem='cs-mo'+str(args.instance)+'-pcm-metadata-tone';call_report=stem+'-live.json'
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,
        'explicitly_authorized_single_dial':True,'number_saved':False,'sample_bytes_saved':False,
        'pcm_verified':False,'new_dsp_commands':False,'arm_i2s_enabled':False,
        'idle_receipt_sha256':hashlib.sha256(idle_path.read_bytes()).hexdigest()}
guarded=False
try:
    options=['--mo','--instance',str(args.instance),'--dsp-tone-candidate']
    run('build-cs-kernel-probe.py',*options,'--seconds','240')
    report['mo_build']=json.loads((BUILD/('cs-mo-probe'+str(args.instance)+'-build.json')).read_text())
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard);guarded=True
    wait_status(lambda s:s.get('ringOnly'),20);report['before_route_audit']=route_audit()
    print('Preparing GSM for one DSP-tone call with read-only SRAM statistics.',flush=True)
    run('prepare-cs-channel-test.py',timeout=150)
    start=float(radio.shell('cat /proc/uptime').split()[0]);report['sample_start_uptime']=start
    run('arm-cs-kernel-watch.py','--channels','--dsp-pcm-metadata')
    report['sampler_armed']=json.loads((BUILD/'cs-channel-watch-armed.json').read_text())
    run('arm-cs-kernel-watch.py',*options,'--authorized-single-dial')
    report['mo_armed']=json.loads((BUILD/('cs-mo-probe'+str(args.instance)+'-armed.json')).read_text())
    time.sleep(3)
    old=BUILD/'cs-mo-outgoing-live.json'
    if old.exists():
        archive=BUILD/('cs-mo-outgoing-before-'+stem+'.json')
        if archive.exists():raise RuntimeError('Existing archive; refusing report overwrite')
        archive.write_bytes(old.read_bytes());archive.chmod(0o600);old.unlink()
    subprocess.run(['afplay','/System/Library/Sounds/Glass.aiff'],check=True,timeout=10)
    print('DIALING: answer once; known DSP tones, automatic hangup after 10 seconds.',flush=True)
    try:report['dial_output']=run('dial-cs-mo-probe.py',timeout=135,input_bytes=number+b'\n')
    finally:number=b''
    if old.exists():
        (BUILD/call_report).write_bytes(old.read_bytes());(BUILD/call_report).chmod(0o600)
        report['call']=json.loads(old.read_text())
    time.sleep(3)
    rows=radio.shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_CHANNEL | tail -n 600").splitlines()
    report['sampler_messages']=[row for row in rows if (m:=re.search(r'\[\s*([0-9.]+)\]',row))
                                and float(m.group(1))>=start]
    if not any('pcm_window ' in row for row in report['sampler_messages']):
        raise RuntimeError('Fresh sampler statistics missing')
    if not report.get('call',{}).get('connected'):raise RuntimeError('Call not connected; no tone correlation')
finally:
    number=b''
    try:
        if guarded:
            if any(row.startswith('mf79u_cs_channels ') for row in radio.shell('cat /proc/modules').splitlines()):
                radio.shell('rmmod mf79u_cs_channels')
            if any(row.startswith('mf79u_cs_channels ') for row in radio.shell('cat /proc/modules').splitlines()):
                raise RuntimeError('Sampler retained; guard stays')
            deadline=time.monotonic()+270
            while radio.shell('test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':
                if time.monotonic()>=deadline:raise RuntimeError('CS callback active; retain guard')
                time.sleep(1)
            radio.radio(0);report['radio_off_route_audit']=route_audit()
            restore.main();radio.radio(1)
            wait_status(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            report['final_route_audit']=route_audit();radio.shell('rm -f '+guard)
            wait_status(lambda s:not s.get('ringOnly'),20)
            if not (BUILD/call_report).exists():
                (BUILD/call_report).write_text(json.dumps({'before':before,'boot_id':boot})+'\n')
            run('verify-cs-test-restored.py','--call-report',call_report,'--output',stem+'-restore.json')
            report['runtime_restored']=True
    except Exception as exc:report['restore_error']=str(exc);raise
    finally:
        report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        path=BUILD/(stem+'-test.json');path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
print('RESTORED: sampler removed, LTE/IMS, flags/profile, callbacks/MM and guards verified.',flush=True)

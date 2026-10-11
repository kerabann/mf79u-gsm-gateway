#!/usr/bin/env python3
"""One authorized MT diagnostic with full voice API parameters and IMS restore.

The already-tested DSP-only tone is the first control. The new parameter set
then runs ARM TX silence/RX observation for six seconds. No speech is saved.
"""
from pathlib import Path
import argparse, datetime, importlib.util, json, subprocess, time

BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--authorized-single-answer',action='store_true')
args=parser.parse_args()
if not args.authorized_single_answer:parser.error('Explicit ordinary-SIM answer authorization required')

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,BASE/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
radio=load('full_call_radio','test-cs-reattach.py')
restore=load('full_call_restore','restore-cs-test.py')
def run(filename,*arguments,timeout=60):
    p=subprocess.run(['python3',str(BASE/filename),*arguments],capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError(filename+' failed: '+(p.stderr or p.stdout)[-1200:])
    return p.stdout
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

before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
guard='/mnt/userdata/mf79u/native-ring-only'
if (before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady')
        or json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall')):
    raise SystemExit('Idle production IMS required')
if radio.shell('test -e '+guard+' && echo PRESENT')=='PRESENT':raise SystemExit('Guard already owned')
if (any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'))
        or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?')):
    raise SystemExit('Expected production flags/profile required')
if radio.shell('test -e /sys/mf79u_cs/status && echo ACTIVE')=='ACTIVE':raise SystemExit('Previous CS callback active')
if any(row.startswith('mf79u_cs_connect32 ') for row in radio.shell('cat /proc/modules').splitlines()):
    raise SystemExit('Instance32 already used; do not reuse its pinned code')

header=BUILD/'cs-i2s-parameters.h';saved_header=header.read_bytes()
configuration=BUILD/'mf283u-voice-inner-init-configuration-emulation.json'
saved_configuration=configuration.read_bytes()
stem='cs-mt32-full-voice-open';call_report=stem+'-live.json'
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'before':before,'boot_id':boot,'explicitly_authorized_single_answer':True,
    'no_dial':True,'number_saved':False,'production_voice_backend':False}
guarded=False
try:
    # Bind to the exact archived idle configuration; do not regenerate a receipt
    # after it has served as physical acceptance evidence.
    header.write_bytes((BUILD/'cs-full-voice-open-parameters.h').read_bytes())
    configuration.write_bytes((BUILD/'cs-full-voice-open-configuration.json').read_bytes())
    options=['--connect-probe','--instance','32','--i2s-pcm-candidate',
             '--i2s-port-tone','--i2s-full-voice-open']
    run('build-cs-kernel-probe.py',*options,'--seconds','240')
    report['build']=json.loads((BUILD/'cs-connect-probe32-build.json').read_text())
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard)
    guarded=True;wait_status(lambda s:s.get('ringOnly'),20)
    report['before_route_audit']=route_audit()
    print('Preparing GSM for one authorized incoming call.',flush=True)
    run('prepare-cs-channel-test.py',timeout=150)
    run('arm-cs-kernel-watch.py',*options,'--authorized-single-answer')
    report['stage']='armed';(BUILD/(stem+'-test.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('READY: one auto-answer, DSP tone control then full voice API/ARM RX, automatic hangup after 10 seconds.',flush=True)
    print(run('collect-cs-mt-tone.py','--i2s-pcm','--report',call_report,timeout=390),flush=True)
    report['call']=json.loads((BUILD/call_report).read_text())
except Exception as exc:
    report['failure']=str(exc);raise
finally:
    header.write_bytes(saved_header);configuration.write_bytes(saved_configuration)
    report['previous_header_restored']=header.read_bytes()==saved_header
    report['previous_configuration_restored']=configuration.read_bytes()==saved_configuration
    try:
        if guarded:
            # The pinned kernel probe owns clearing and callback lifetime. Never
            # restore IMS while its CC callback is still installed.
            deadline=time.monotonic()+270
            while radio.shell('test -e /sys/mf79u_cs/status && echo ACTIVE')=='ACTIVE':
                if time.monotonic()>=deadline:raise RuntimeError('CS callback active; retain guard')
                time.sleep(1)
            radio.radio(0);report['radio_off_route_audit']=route_audit()
            restore.main();radio.radio(1)
            wait_status(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            report['final_route_audit']=route_audit()
            radio.shell('rm -f '+guard)
            wait_status(lambda s:not s.get('ringOnly'),20)
            # If failure happened before collection, retain enough runtime
            # identity for the independent restoration checker.
            if not (BUILD/call_report).exists():
                (BUILD/call_report).write_text(json.dumps({'before':before,'boot_id':boot,'test_failure':report.get('failure')},indent=2)+'\n')
            run('verify-cs-test-restored.py','--call-report',call_report,'--output',stem+'-restore.json')
            report['runtime_restored']=True
    except Exception as exc:
        report['restore_error']=str(exc);raise
    finally:
        report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        path=BUILD/(stem+'-test.json');path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
print('RESTORED: LTE/IMS, original flags/profile, callbacks/MM and temporary guards.',flush=True)

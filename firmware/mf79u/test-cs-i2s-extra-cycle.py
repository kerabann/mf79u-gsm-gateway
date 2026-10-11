#!/usr/bin/env python3
"""Paired, bounded B03 idle DSP loop: reference tTdmExtCycle1 versus0.

No SIM dial/answer, CC hooks, DSP program uploads or boot changes. GSM test
policy is restored to the saved production LTE/IMS profile in finally.
"""
from pathlib import Path
import datetime, hashlib, importlib.util, json, subprocess, time

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
BUILD=BASE/'build'

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,BASE/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

radio=load('cycle_radio','test-cs-reattach.py')
restore=load('cycle_restore','restore-cs-test.py')

def wait_status(predicate, seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=radio.status()
        if predicate(value):return value
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')

def run(filename, *arguments):
    value=subprocess.run(['python3',str(BASE/filename),*arguments],capture_output=True,text=True,timeout=60)
    if value.returncode:raise RuntimeError(filename+' failed: '+value.stderr[-1200:])

def route_audit():
    run('test-cs-kernel-probe.py','--routing')
    value=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not value.get('restoration_verified'):raise RuntimeError('Original callbacks/MM not confirmed')
    return value

before=radio.status()
boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
gateway=json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json'))
if before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady') or gateway.get('activeCall'):
    raise SystemExit('Idle production IMS runtime required')
if radio.shell('test -e /mnt/userdata/mf79u/native-ring-only && echo PRESENT')=='PRESENT':
    raise SystemExit('Existing ring guard is owned by another test')
if any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')) or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):
    raise SystemExit('Expected production flags/profile required')
header=BUILD/'cs-i2s-parameters.h'
saved_header=header.read_bytes()
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,
        'boot_id':boot,'no_sim_calls':True,'no_dsp_program_upload':True,
        'no_boot_changes':True,'cases':[]}
guarded=False
try:
    radio.shell('umask 077; : > /mnt/userdata/mf79u/native-ring-only; chmod 600 /mnt/userdata/mf79u/native-ring-only')
    guarded=True
    wait_status(lambda s:s.get('ringOnly'),20)
    report['before_route_audit']=route_audit()
    print('Guarded idle GSM preparation; no calls.',flush=True)
    load('cycle_prepare','prepare-cs-channel-test.py')
    for cycle in (1,0):
        run('prepare-cs-i2s-parameters.py','--idle-tone-loop','--driver-init','--tdm-extra-cycle',str(cycle))
        run('build-cs-kernel-probe.py','--i2s-dsp-loop')
        stem='cs-i2s-extra-cycle'+str(cycle)
        for src,suffix in (('cs-i2s-parameters.h','-parameters.h'),('mf79u_cs_i2s_dsp_loop.ko','.ko'),('cs-i2s-dsp-loop-probe-build.json','-build.json')):
            (BUILD/(stem+suffix)).write_bytes((BUILD/src).read_bytes())
        print('Four-second idle DSP loop, reference extra-cycle '+str(cycle),flush=True)
        run('test-cs-kernel-probe.py','--i2s-dsp-loop')
        value=json.loads((BUILD/'cs-i2s-dsp-loop-probe-live.json').read_text())
        (BUILD/(stem+'-live.json')).write_text(json.dumps(value,indent=2)+'\n')
        report['cases'].append({'reference_extra_cycle':cycle,'live_report':stem+'-live.json',
                               'sha256':value['module_sha256'],'messages':value['messages'],
                               'unloaded':value['unloaded']})
finally:
    header.write_bytes(saved_header)
    report['previous_header_restored']=hashlib.sha256(header.read_bytes()).hexdigest()==hashlib.sha256(saved_header).hexdigest()
    try:
        if guarded:
            modules=radio.shell('cat /proc/modules').splitlines()
            if any(line.startswith('mf79u_cs_i2s_dsp_loop ') for line in modules):
                raise RuntimeError('Loop probe remains loaded; retain ring guard and stop restoration')
            radio.radio(0)
            report['radio_off_route_audit']=route_audit()
            restore.main()
            radio.radio(1)
            wait_status(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            report['final_route_audit']=route_audit()
            radio.shell('rm -f /mnt/userdata/mf79u/native-ring-only')
            after=wait_status(lambda s:not s.get('ringOnly'),20)
            report['after']=after
            report['same_boot']=radio.shell('cat /proc/sys/kernel/random/boot_id')==boot
            report['same_native_sip_pids']=all(before[k]==after[k] for k in ('pid','sipPid'))
            report['voice_flags_restored']=all(radio.get_flag(n)==0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'))
            report['profile_restored']='^SYSCONFIG: 27,0,1,2' in radio.at('AT^SYSCONFIG?')
            report['runtime_restored']=all(report[k] for k in ('same_boot','same_native_sip_pids','voice_flags_restored','profile_restored')) and after.get('imsReady') and not after.get('csOnly') and not after.get('ringOnly')
    except Exception as exc:
        report['restore_error']=str(exc);raise
    finally:
        (BUILD/'cs-i2s-extra-cycle-pair-live.json').write_text(json.dumps(report,indent=2)+'\n')
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
print(json.dumps({k:report[k] for k in ('runtime_restored','same_boot','same_native_sip_pids','previous_header_restored','cases')},indent=2))

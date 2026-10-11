#!/usr/bin/env python3
"""Passive exact-B03 self-check observation across reversible radio profiles.

No SIM dial/answer or new DSP commands. Original production profiles/flags and
IMS are restored. The bounded observer remains inactive and pinned to reboot.
"""
from pathlib import Path
import datetime, hashlib, importlib.util, json, subprocess, time
from ram_transfer import ram_push

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
ADB=[str(ROOT/'outputs/adb')]
NAME='mf79u_cs_dsp_boot'
REMOTE='/dev/.mf79u-cs-dsp-boot-watch.ko'

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name, BASE/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

radio=load('radio', 'test-cs-reattach.py')
restore=load('restore', 'restore-cs-test.py')

def shell(cmd): return radio.shell(cmd)
def wait_status(predicate, seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=radio.status()
        if predicate(value): return value
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')
def logs():
    return shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_DSP_BOOT | tail -n 24").splitlines()
def route_audit():
    completed=subprocess.run(['python3',str(BASE/'test-cs-kernel-probe.py'),'--routing'],capture_output=True,timeout=40)
    if completed.returncode: raise RuntimeError('Read-only route audit failed')
    value=json.loads((BASE/'build/cs-route-probe-live.json').read_text())
    if not value.get('restoration_verified') or not any('dsp_selfcheck_original=1 ' in row for row in value.get('messages',[])):
        raise RuntimeError('Original callbacks/MM/self-check literal not confirmed')
    return value

before=radio.status()
boot=shell('cat /proc/sys/kernel/random/boot_id')
gateway=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
if before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady') or gateway.get('activeCall'):
    raise SystemExit('Idle normal IMS runtime required')
if shell('uname -r')!='3.4.110-rt140': raise SystemExit('Unrecognized kernel')
if shell('md5sum /lib/cpko/cpko.ko').split()[0]!='8138d03644b0417ec3fba9d7175200bc':
    raise SystemExit('Unrecognized CP binary')
modules=shell('cat /proc/modules').splitlines()
if not any(line.startswith('cpko 6397096 ') and '0xbf000000' in line for line in modules):
    raise SystemExit('Unrecognized CP placement')
if any(line.split()[0]==NAME for line in modules): raise SystemExit('Observer instance already loaded')
if any(radio.get_flag(n)!=0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')):
    raise SystemExit('Original voice flags must be zero')
if '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):
    raise SystemExit('Expected normal radio profile required')
local=BASE/'build'/f'{NAME}.ko'
metadata=json.loads((BASE/'build/cs-dsp-boot-watch-build.json').read_text())
if not metadata.get('live_arm_allowed') or metadata['sha256']!=hashlib.sha256(local.read_bytes()).hexdigest():
    raise SystemExit('Unverified observer build')
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'before':before,
        'boot_id':boot,'module_sha256':metadata['sha256'],'no_sim_calls':True,
        'new_dsp_commands':False,'dsp_program_patch':False,'raw_flash_written':False}
guarded=False
armed=False
try:
    shell('umask 077; : > /mnt/userdata/mf79u/native-ring-only; chmod 600 /mnt/userdata/mf79u/native-ring-only')
    guarded=True
    wait_status(lambda s:s.get('ringOnly'),20)
    route_audit()
    ram_push(ADB,local,REMOTE)
    result=shell('insmod '+REMOTE+'; echo MF79U_INSMOD_EXIT=$?')
    if 'MF79U_INSMOD_EXIT=0' not in result: raise RuntimeError('Observer did not arm')
    armed=True
    armed_at=time.monotonic()
    print('Passive DSP boot observer armed; switching to the saved GSM test profile.',flush=True)
    preparation=load('prepare', 'prepare-cs-channel-test.py')
    report['gsm_registered']=radio.status().get('csRegistration') in (1,5)
    print('GSM registration complete; waiting for the bounded observer to restore its literal.',flush=True)
    deadline=armed_at+metadata['seconds']+15
    while time.monotonic()<deadline:
        observed=logs()
        if any('expired seconds=' in line and 'literal_restored=1 ' in line for line in observed): break
        time.sleep(1)
    else: raise RuntimeError('Observer restoration evidence missing')
    report['messages']=observed
    report['observed_calls']=sum(' observed=' in row for row in observed)
    report['route_audit']=route_audit()
    report['literal_restored']=True
finally:
    try:
        if armed and not report.get('literal_restored'):
            deadline=time.monotonic()+metadata['seconds']+15
            while time.monotonic()<deadline:
                if any('expired seconds=' in line and 'literal_restored=1 ' in line for line in logs()):
                    report['route_audit']=route_audit();report['literal_restored']=True;break
                time.sleep(1)
            if not report.get('literal_restored'):raise RuntimeError('Observer restore not confirmed; ring guard retained')
        shell('rm -f '+REMOTE)
        if guarded:
            radio.radio(0)
            report['radio_off_route_audit']=route_audit()
            restore.main()
            radio.radio(1)
            after=wait_status(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            report['final_route_audit']=route_audit()
            shell('rm -f /mnt/userdata/mf79u/native-ring-only')
            after=wait_status(lambda s:not s.get('ringOnly'),20)
            report['after']=after
            report['same_boot']=shell('cat /proc/sys/kernel/random/boot_id')==boot
            report['same_native_sip_pids']=all(before[k]==after[k] for k in ('pid','sipPid'))
            report['voice_flags_restored']=all(radio.get_flag(n)==0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'))
            report['profile_restored']='^SYSCONFIG: 27,0,1,2' in radio.at('AT^SYSCONFIG?')
            report['runtime_restored']=all(report[k] for k in ('same_boot','same_native_sip_pids','voice_flags_restored','profile_restored')) and after.get('imsReady') and not after.get('ringOnly') and not after.get('csOnly')
    except Exception as exc:
        report['restore_error']=str(exc)
        raise
    finally:
        (BASE/'build/cs-dsp-boot-watch-live.json').write_text(json.dumps(report,indent=2)+'\n')
if not report.get('runtime_restored'): raise SystemExit('Runtime restoration failed')
print(json.dumps({k:report[k] for k in ('observed_calls','literal_restored','runtime_restored','same_boot','same_native_sip_pids','messages')},indent=2))

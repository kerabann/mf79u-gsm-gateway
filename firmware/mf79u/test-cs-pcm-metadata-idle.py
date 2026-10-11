#!/usr/bin/env python3
"""Short read-only GSM SRAM metadata preflight; no DSP command or SIM call."""
from pathlib import Path
import datetime,importlib.util,json,subprocess,time
BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
def load(name,filename):
    s=importlib.util.spec_from_file_location(name,BASE/filename)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
radio=load('pcm_idle_radio','test-cs-reattach.py');restore=load('pcm_idle_restore','restore-cs-test.py')
def run(filename,*args,timeout=60):
    r=subprocess.run(['python3',str(BASE/filename),*args],capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError(filename+': '+(r.stderr or r.stdout)[-1000:])
def wait(predicate,seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        state=radio.status()
        if predicate(state):return state
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')
def audit():
    run('test-cs-kernel-probe.py','--routing')
    r=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not r.get('restoration_verified'):raise RuntimeError('Original callbacks/MM absent')
    return r
before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
guard='/mnt/userdata/mf79u/native-ring-only'
if before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady') or json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise SystemExit('Idle production IMS required')
if radio.shell('test -e '+guard+' && echo PRESENT')=='PRESENT':raise SystemExit('Guard already owned')
if any(row.startswith('mf79u_cs_channels ') for row in radio.shell('cat /proc/modules').splitlines()):raise SystemExit('Sampler already owned')
r={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,
   'no_sim_calls':True,'no_dsp_commands':True,'sample_bytes_saved':False,'pcm_verified':False}
guarded=False
try:
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard);guarded=True
    wait(lambda s:s.get('ringOnly'),20);r['first_route_audit']=audit()
    run('prepare-cs-channel-test.py',timeout=150)
    run('arm-cs-kernel-watch.py','--channels','--dsp-pcm-metadata')
    r['armed']=json.loads((BUILD/'cs-channel-watch-armed.json').read_text())
    rows=r['armed']['messages'];start=next(row.split(']')[0] for row in reversed(rows) if 'armed seconds=' in row)
    time.sleep(3)
    rows=radio.shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_CHANNEL | tail -n 100").splitlines()
    # Collector retains statistics only; no raw SRAM values or hashes exist.
    r['messages']=[row for row in rows if 'pcm_window ' in row]
    if not r['messages']:raise RuntimeError('PCM window statistics missing')
    r['layout_accepted']=True
finally:
    try:
        if guarded:
            if any(row.startswith('mf79u_cs_channels ') for row in radio.shell('cat /proc/modules').splitlines()):
                radio.shell('rmmod mf79u_cs_channels')
            r['sampler_unloaded']=not any(row.startswith('mf79u_cs_channels ') for row in radio.shell('cat /proc/modules').splitlines())
            if not r['sampler_unloaded']:raise RuntimeError('Sampler retained; guard stays')
            radio.radio(0);r['radio_off_route_audit']=audit()
            restore.main();radio.radio(1);wait(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            r['final_route_audit']=audit();radio.shell('rm -f '+guard)
            after=wait(lambda s:not s.get('ringOnly'),20)
            r.update(after=after,same_boot=radio.shell('cat /proc/sys/kernel/random/boot_id')==boot,
                     same_native_sip_pids=all(before[k]==after[k] for k in ('pid','sipPid')),
                     flags_restored=all(radio.get_flag(k)==0 for k in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')),
                     profile_restored='^SYSCONFIG: 27,0,1,2' in radio.at('AT^SYSCONFIG?'))
            r['runtime_restored']=all(r[k] for k in ('sampler_unloaded','same_boot','same_native_sip_pids','flags_restored','profile_restored'))
    except Exception as exc:r['restore_error']=str(exc);raise
    finally:(BUILD/'cs-pcm-metadata-idle-live.json').write_text(json.dumps(r,indent=2)+'\n')
if not r.get('runtime_restored'):raise SystemExit('Restoration failed')
print(json.dumps({k:r.get(k) for k in ('layout_accepted','runtime_restored','no_sim_calls','no_dsp_commands')}))

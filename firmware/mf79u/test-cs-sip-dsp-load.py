#!/usr/bin/env python3
"""Overlap a proven idle DSP/I2S loop and synthetic SIP media; no SIM call."""
from pathlib import Path
import datetime, importlib.util, json, re, subprocess, time
from cs_kernel_failure_capture import KernelCapture
from cs_sip_media_diagnostic import Diagnostic
from ram_transfer import ram_push

BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,BASE/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
radio=load('load_radio','test-cs-reattach.py');restore=load('load_restore','restore-cs-test.py')
def run(file,*args,timeout=60):
    result=subprocess.run(['python3',str(BASE/file),*args],capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError(file+' failed: '+(result.stderr or result.stdout)[-1200:])
    return result.stdout
def wait(predicate,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        state=radio.status()
        if predicate(state):return state
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')
def audit():
    run('test-cs-kernel-probe.py','--routing')
    value=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not value.get('restoration_verified'):raise RuntimeError('CC/MM restoration not confirmed')
    return value

before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
guard='/mnt/userdata/mf79u/native-ring-only';remote='/dev/.mf79u-load-pcm-selftest'
if (before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady') or
    json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall')):raise SystemExit('Idle ordinary IMS required')
if radio.shell('test -e '+guard+' || test -e '+remote+'; if test $? -eq 0; then echo PRESENT; fi')=='PRESENT':raise SystemExit('Existing diagnostic owner')
if any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')) or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):raise SystemExit('Expected production flags/profile required')
header=BUILD/'cs-i2s-parameters.h';saved_header=header.read_bytes()
archived=(BUILD/'cs-full-voice-open-parameters.h').read_bytes()
match=re.search(rb'^#define CS_I2S_CONFIGURATION_REPORT "([a-z0-9-]+\.json)"$',archived,re.M)
if not match:raise SystemExit('Configuration basename absent')
configuration=BUILD/match[1].decode();saved_configuration=configuration.read_bytes()
flags=['--i2s-dsp-loop','--i2s-both-ports','--i2s-both-ports-signal','--i2s-arm1-rx-only']
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot_id':boot,'before':before,'no_sim_calls':True,'speech_saved':False,'no_cc_hooks':True}
guarded=False;capture=None;sip=None;loop=None;peer=None
try:
    header.write_bytes(archived);configuration.write_bytes((BUILD/'cs-full-voice-open-configuration.json').read_bytes())
    run('build-cs-kernel-probe.py',*flags)
    report['build']=json.loads((BUILD/'cs-i2s-dsp-loop-probe-build.json').read_text())
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard);guarded=True
    wait(lambda s:s.get('ringOnly'),20);report['before_route_audit']=audit()
    capture=KernelCapture(radio,BUILD/'cs-sip-dsp-load-kernel.json');capture.start()
    print('Preparing idle GSM audio/SIP load comparison; no SIM calls.',flush=True)
    run('prepare-cs-channel-test.py',timeout=150)
    sip=Diagnostic(radio);sip.prepare()
    clocks=[t for t in sip.result['threads_ready'] if t['name']=='clock']
    if len(clocks)!=1 or clocks[0]['policy']!=0 or clocks[0]['rt_priority']!=0:
        raise RuntimeError('Normal-priority diagnostic clock required before DSP overlap')
    report['normal_clock_verified']=True
    ram_push([radio.ADB],BUILD/'cs-sip-pcm-selftest',remote);radio.shell('chmod 700 '+remote)
    loop=subprocess.Popen(['python3',str(BASE/'test-cs-kernel-probe.py'),*flags],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    end=time.monotonic()+35
    while time.monotonic()<end:
        if any('MF79U_CS_I2S_DSP_LOOP configured no_calls=1' in line for line in capture.result['messages']):break
        if loop.poll() is not None:raise RuntimeError('Idle DSP probe exited before media startup')
        time.sleep(.02)
    else:raise RuntimeError('Idle DSP probe did not start')
    peer=subprocess.Popen([radio.ADB,'shell',remote],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if peer.stdout.readline().decode().strip()!='SIP_PCM_SYNTH_READY':raise RuntimeError('Synthetic peer not ready')
    sip.command('INCOMING');sip.expect('SIP_MEDIA_CONNECTED');report['sip_connected_during_i2s']=loop.poll() is None
    out,err=peer.communicate(timeout=15)
    rows=[line for line in out.decode().splitlines() if line.startswith('{')]
    if len(rows)!=1:raise RuntimeError('Synthetic media result missing')
    report['media']=json.loads(rows[0]);report['peer_exit']=peer.returncode
    out,err=loop.communicate(timeout=25);report['loop_exit']=loop.returncode
    if loop.returncode:raise RuntimeError('Idle DSP probe failed: '+err.decode(errors='replace')[-800:])
    report['loop']=json.loads(out)
    print('Idle I2S and SIP completed; restoring ordinary IMS.',flush=True)
except Exception as error:
    report['failure']=str(error);raise
finally:
    for name,process in (('peer',peer),('loop',loop)):
        if process and process.poll() is None:
            try:process.communicate(timeout=25)
            except subprocess.TimeoutExpired:report[name+'_cleanup_error']='StillRunning'
    if sip:report['sip']=sip.close()
    if capture:report['capture']=capture.close()
    header.write_bytes(saved_header);configuration.write_bytes(saved_configuration)
    try:
        radio.shell('rm -f '+remote)
        if guarded:
            if any(row.startswith('mf79u_cs_i2s_dsp_loop ') for row in radio.shell('cat /proc/modules').splitlines()):raise RuntimeError('Idle DSP probe still loaded')
            radio.radio(0);report['after_route_audit']=audit();restore.main();radio.radio(1)
            wait(lambda s:s.get('imsReady') and not s.get('csOnly'),100)
            radio.shell('rm -f '+guard);report['after']=wait(lambda s:not s.get('ringOnly'),20)
            report['runtime_restored']=boot==radio.shell('cat /proc/sys/kernel/random/boot_id') and all(before[k]==report['after'][k] for k in ('pid','sipPid'))
    except Exception as error:report['restore_error']=str(error)
    report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    path=BUILD/'cs-sip-dsp-load-live.json';path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
if not (report.get('runtime_restored') and report.get('sip_connected_during_i2s') and report.get('media',{}).get('passed') and report.get('loop',{}).get('unloaded') and not report.get('sip',{}).get('failure') and report.get('capture',{}).get('closed')):raise SystemExit('No-call load comparison or recovery failed; see receipt')
print('PASS: overlapping DSP/I2S and synthetic SIP, ordinary IMS restored.',flush=True)

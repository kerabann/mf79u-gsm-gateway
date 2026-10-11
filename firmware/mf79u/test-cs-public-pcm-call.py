#!/usr/bin/env python3
"""One authorized MO: known DSP control then public PCM RX or full-API ARM tone."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, re, subprocess, sys, time
from ram_transfer import ram_push

BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--authorized-single-dial',action='store_true');p.add_argument('--instance',type=int,required=True)
p.add_argument('--connected-seconds',type=int,help='Separate bounded call-clearing deadline from the PCM duration')
p.add_argument('--asc-instance',type=int,help='Optional passive clearing observer, fresh pinned instance1..64')
p.add_argument('--mm-release-delay',type=int,default=0,choices=(0,2),help='Diagnostic MM release delay after queued RELEASE COMPLETE')
p.add_argument('--arm-slave',action='store_true')
media=p.add_mutually_exclusive_group()
media.add_argument('--full-voice-arm-tone',action='store_true',help='Known full voice profile, DSP control then ARM-only three-tone transmission')
media.add_argument('--full-voice-arm-echo',action='store_true',help='Full voice: two-second ARM tone followed by four seconds of bounded RAM speech echo')
p.add_argument('--rx-start',action='store_true',help='Echo phase uses exact late ARM0 startup profile with restored idle receipt')
p.add_argument('--arm1-echo',action='store_true',help='Receive echo speech on ARM1, transmit on ARM0')
p.add_argument('--arm1-rx-only',action='store_true')
p.add_argument('--arm1-tx-switch',action='store_true')
p.add_argument('--userspace-pcm',action='store_true',help='Tone/echo through the 16 kHz userspace adapter, no SIP sockets')
p.add_argument('--sip-media',action='store_true',help='Isolated SIP/RTP endpoint to the laboratory PBX echo application')
p.add_argument('--sip-compare',action='store_true',help='Compare local echo3s with PBX echo in the same call')
p.add_argument('--allow-unregistered',action='store_true',help='Explicitly preserve an ordinary policy whose IMS was already unavailable')
p.add_argument('--streaming-pcm',action='store_true',help='No modem-generated tones or media deadline')
p.add_argument('--sip-controls-call',action='store_true',help='Route diagnostic SIP hangup to this owned CS call')
args=p.parse_args()
if args.streaming_pcm and not args.userspace_pcm:p.error('Streaming mode requires userspace PCM')
if args.streaming_pcm and (not args.sip_media or args.sip_compare):p.error('Streaming test requires SIP media without local tone/echo comparison')
if args.sip_controls_call and not (args.sip_media and args.streaming_pcm and args.connected_seconds==40):p.error('SIP hangup test requires streaming SIP with the 40s backup deadline')
if args.asc_instance is not None and not 1<=args.asc_instance<=64:p.error('ASC instance must be1..64')
if args.connected_seconds is not None and not 8<=args.connected_seconds<=40:p.error('Connected timeout must be 8..40 seconds')
if args.sip_compare and not args.sip_media:p.error('Echo comparison requires SIP media')
if args.sip_media and not args.userspace_pcm:p.error('SIP media requires userspace PCM')
if args.userspace_pcm and not args.arm1_tx_switch:p.error('Userspace PCM requires verified ARM1 TX/RX')
if args.arm1_tx_switch and not args.arm1_rx_only:p.error('TX switch requires ARM1 RX-only control')
if args.arm1_rx_only and not args.arm1_echo:p.error('RX only requires ARM1 echo')
if args.arm1_echo and (not args.full_voice_arm_echo or args.rx_start):p.error('ARM1 echo requires a separate full voice echo diagnostic')
if args.rx_start and not args.full_voice_arm_echo:p.error('Late profile requires full voice ARM echo')
full_voice=args.full_voice_arm_tone or args.full_voice_arm_echo
if not args.authorized_single_dial:p.error('Explicit outgoing-call authorization required')
if not 2<=args.instance<=64:p.error('Fresh MO instance2..64 required')
number=sys.stdin.buffer.readline(34).strip()
if not re.fullmatch(rb'[0-9]{5,32}',number):raise SystemExit('Numeric authorized destination required on stdin')
def load(name,file):
    s=importlib.util.spec_from_file_location(name,BASE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
radio=load('public_call_radio','test-cs-reattach.py');restore=load('public_call_restore','restore-cs-test.py')
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
guard='/mnt/userdata/mf79u/native-ring-only';module='mf79u_cs_mo'+str(args.instance)
if (before.get('ringOnly') or before.get('csOnly') or (not before.get('imsReady') and not args.allow_unregistered)
        or json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall')):raise SystemExit('Idle production IMS required')
if radio.shell('test -e '+guard+' && echo PRESENT')=='PRESENT':raise SystemExit('Guard already owned')
if any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')) or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):raise SystemExit('Expected production flags/profile required')
if any(row.startswith(module+' ') for row in radio.shell('cat /proc/modules').splitlines()):raise SystemExit('Pinned instance already used')
if radio.shell('test -e /sys/mf79u_cs/status || test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':raise SystemExit('Previous CS callback active')
variant='full-voice-arm-echo' if args.full_voice_arm_echo else ('full-voice-arm-tone' if full_voice else 'public-pcm')
if args.rx_start:variant+='-late-start'
if args.arm1_echo:variant+='-arm1-rx'
if args.arm1_rx_only:variant+='-only'
if args.arm1_tx_switch:variant+='-tx-switch'
if args.userspace_pcm:variant+='-userspace'
if args.sip_media:variant+='-sip'
if args.sip_compare:variant+='-compare'
if args.streaming_pcm:variant+='-streaming'
if args.sip_controls_call:variant+='-sip-control'
stem='cs-mo'+str(args.instance)+'-'+variant+('-arm-slave' if args.arm_slave else '')
call_report=stem+'-live.json';idle=('cs-full-voice-open' if full_voice else 'cs-public-pcm')+('-arm-slave' if args.arm_slave else '')
header=BUILD/'cs-i2s-parameters.h';saved_header=header.read_bytes()
archived=(BUILD/(idle+'-parameters.h')).read_text()
name=re.search(r'^#define CS_I2S_CONFIGURATION_REPORT "([a-z0-9-]+\.json)"$',archived,re.M)
if not name:raise SystemExit('Archived configuration basename absent')
cfg=BUILD/name[1];saved_cfg=cfg.read_bytes()
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,
        'explicitly_authorized_single_dial':True,'number_saved':False,'speech_saved':False,
        'public_pcm_route':not full_voice,'arm_pcm_tone':full_voice and not args.streaming_pcm,
        'arm_pcm_echo':args.full_voice_arm_echo and not args.userspace_pcm,
        'streaming_pcm':args.streaming_pcm,'sip_controls_call':args.sip_controls_call,
        'arm_clock_master':not args.arm_slave,'production_voice_backend':False}
guarded=False;bridge=None;sip_test=None;kernel_capture=None;bridge_remote='/dev/.mf79u-cs-pcm-bridge'
asc_deadline=0;asc_start=0
def hangup_owned():
    if radio.shell('cat /proc/sys/kernel/random/boot_id')!=boot:raise RuntimeError('CS call boot changed')
    if not report.get('armed') or not any(row.startswith(module+' ') for row in radio.shell('cat /proc/modules').splitlines()):raise RuntimeError('Owned CS module absent')
    # This diagnostic module has one call budget and no replacement sysfs
    # endpoint may be armed until this wrapper restores the original callback.
    state=radio.shell('test -e /sys/mf79u_cs_mo/status && cat /sys/mf79u_cs_mo/status')
    if not state:return
    fields=state.split()
    if len(fields)!=8 or fields[:2]!=['MF79U_CS','1']:raise RuntimeError('Unexpected CS status ABI')
    if fields[3]=='0':return
    radio.shell("printf 'stop\\n' > /sys/mf79u_cs_mo/control")
def collect_bridge():
    global bridge
    if bridge is None:return
    try:output,error=bridge.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        # Terminate only the process whose command path we own and verified.
        pid=radio.shell('cat /dev/.mf79u-cs-pcm-bridge.pid')
        if pid.isdigit() and bridge_remote in radio.shell('cat /proc/'+pid+'/cmdline'):
            radio.shell('kill -TERM '+pid)
        output,error=bridge.communicate(timeout=5)
    report['userspace_bridge']={'exit':bridge.returncode,'messages':[line for line in output.decode(errors='replace').replace('\r','').splitlines() if line.startswith(('CS_PCM_BRIDGE ','MF79U_DIAG_FAULT '))]}
    bridge=None
try:
    header.write_text(archived);cfg.write_bytes((BUILD/(idle+'-configuration.json')).read_bytes())
    options=['--mo','--instance',str(args.instance),'--i2s-pcm-candidate','--i2s-port-tone']+(['--i2s-full-voice-open','--i2s-arm-tone'] if full_voice else ['--i2s-public-pcm'])
    if args.connected_seconds is not None:options+=['--connected-seconds',str(args.connected_seconds)]
    if args.mm_release_delay:options+=['--mm-release-delay',str(args.mm_release_delay)]
    if args.full_voice_arm_echo:options.append('--i2s-arm-echo')
    if args.rx_start:options.append('--i2s-rx-start')
    if args.arm1_echo:options.append('--i2s-arm1-echo')
    if args.arm1_rx_only:options.append('--i2s-arm1-rx-only')
    if args.arm1_tx_switch:options.append('--i2s-arm1-tx-switch')
    if args.userspace_pcm:options.append('--i2s-userspace-pcm')
    if args.streaming_pcm:options.append('--i2s-streaming-pcm')
    run('build-cs-kernel-probe.py',*options,'--seconds','240')
    report['build']=json.loads((BUILD/('cs-mo-probe'+str(args.instance)+'-build.json')).read_text())
    if args.asc_instance is not None:
        run('build-cs-kernel-probe.py','--asc','--instance',str(args.asc_instance),'--seconds','150')
        asc_output='cs-asc-watch'+(str(args.asc_instance) if args.asc_instance!=1 else '')
        report['asc_build']=json.loads((BUILD/(asc_output+'-build.json')).read_text())
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard);guarded=True
    wait(lambda s:s.get('ringOnly'),20);report['before_route_audit']=audit()
    from cs_kernel_failure_capture import KernelCapture
    kernel_capture=KernelCapture(radio,BUILD/(stem+'-kernel.json'));kernel_capture.start()
    print('Preparing one outgoing audio comparison; no incoming auto-answer.',flush=True)
    run('prepare-cs-channel-test.py',timeout=150)
    if args.sip_media:
        # Radio transitions have their own memory peak. Start the extra
        # diagnostic SIP process only after GSM has registered and IMS exited.
        from cs_sip_media_diagnostic import Diagnostic
        sip_test=Diagnostic(radio,hangup_owned if args.sip_controls_call else None);sip_test.prepare()
        clocks=[t for t in sip_test.result['threads_ready'] if t['name']=='clock']
        if len(clocks)!=1 or clocks[0]['policy']!=0 or clocks[0]['rt_priority']!=0:
            raise RuntimeError('Normal-priority SIP clock required before arming CS')
        report['normal_sip_clock_verified']=True
    old=BUILD/'cs-mo-outgoing-live.json'
    if old.exists():
        dest=BUILD/('cs-mo-outgoing-before-'+stem+'.json')
        if dest.exists():raise RuntimeError('Existing archive; refusing overwrite')
        dest.write_bytes(old.read_bytes());dest.chmod(0o600);old.unlink()
    run('arm-cs-kernel-watch.py',*options,'--authorized-single-dial')
    report['armed']=json.loads((BUILD/('cs-mo-probe'+str(args.instance)+'-armed.json')).read_text())
    if args.asc_instance is not None:
        # MO checks the original ASC callback; chain the observer afterwards.
        asc_start=float(radio.shell('cat /proc/uptime').split()[0])
        asc_deadline=time.monotonic()+195
        run('arm-cs-kernel-watch.py','--asc','--instance',str(args.asc_instance))
        report['asc_armed']=json.loads((BUILD/(asc_output+'-armed.json')).read_text())
    if args.userspace_pcm:
        adapter=BUILD/('cs-pcm-bridge-sip-test' if args.sip_media else 'cs-pcm-bridge');report['userspace_bridge_sha256']=hashlib.sha256(adapter.read_bytes()).hexdigest()
        ram_push([radio.ADB],adapter,bridge_remote);radio.shell('chmod 700 '+bridge_remote)
        bridge=subprocess.Popen([radio.ADB,'shell','umask 077; echo $$ > /dev/.mf79u-cs-pcm-bridge.pid; exec '+bridge_remote+(' --stream' if args.streaming_pcm else ' --compare-sip' if args.sip_compare else ' --udp' if args.sip_media else ' --tone-echo')],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        time.sleep(.3)
        if bridge.poll() is not None:collect_bridge();raise RuntimeError('PCM bridge exited before dial')
    if sip_test:sip_test.start()
    subprocess.run(['afplay','/System/Library/Sounds/Glass.aiff'],check=True,timeout=10,stdin=subprocess.DEVNULL)
    print('DIALING: answer once; '+('streaming SIP/PBX echo; SIP hangup25s, CS backup40s' if args.sip_controls_call else 'DSP/ARM control then SIP/PBX tone and echo20s' if args.sip_media else 'userspace tones2s and echo18s' if args.userspace_pcm else 'PCM stage6s')+'.',flush=True)
    try:report['dial_output']=run('dial-cs-mo-probe.py',timeout=135,input_bytes=number+b'\n')
    finally:
        number=b''
        if old.exists():
            (BUILD/call_report).write_bytes(old.read_bytes());(BUILD/call_report).chmod(0o600)
            report['call']=json.loads(old.read_text())
    if not report.get('call',{}).get('connected'):raise RuntimeError('Call not connected')
    if args.userspace_pcm:
        collect_bridge()
        if report['userspace_bridge']['exit'] or not any('finished=1 failed=0' in line for line in report['userspace_bridge']['messages']):raise RuntimeError('PCM bridge did not finish cleanly')
except Exception as exc:report['failure']=str(exc);raise
finally:
    try:
        if bridge is not None:collect_bridge()
        if args.userspace_pcm:radio.shell('rm -f '+bridge_remote+' /dev/.mf79u-cs-pcm-bridge.pid')
    except Exception as exc:report['bridge_cleanup_error']=str(exc)
    try:
        if sip_test:report['sip_media']=sip_test.close()
    except Exception as exc:report['sip_cleanup_error']=str(exc)
    if kernel_capture:report['kernel_capture']=kernel_capture.close()
    number=b'';header.write_bytes(saved_header);cfg.write_bytes(saved_cfg)
    report['previous_header_restored']=header.read_bytes()==saved_header
    report['previous_configuration_restored']=cfg.read_bytes()==saved_cfg
    try:
        if guarded:
            end=time.monotonic()+270
            while radio.shell('test -e /sys/mf79u_cs/status || test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE':
                if time.monotonic()>=end:raise RuntimeError('CS callback active; retain guard')
                time.sleep(1)
            if asc_deadline:
                # Keep radio unchanged until this observer's bounded expiry;
                # cleanup must never race a callback still owning ASC.
                while True:
                    rows=radio.shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_ASC | tail -n 250").splitlines()
                    fresh=[row for row in rows if (m:=re.search(r'\[\s*([0-9.]+)\]',row)) and float(m[1])>=asc_start]
                    report['asc_messages']=fresh
                    if any('expired seconds=150 ' in row and 'callback_restored=1' in row for row in fresh):break
                    if time.monotonic()>=asc_deadline:raise RuntimeError('ASC expiry unconfirmed; retain guard')
                    time.sleep(1)
            radio.radio(0);report['radio_off_route_audit']=audit()
            restore.main();radio.radio(1)
            require_ims=bool(before.get('imsReady')) or not args.allow_unregistered
            wait(lambda s:not s.get('csOnly') and (s.get('imsReady') if require_ims else s.get('epsRegistration') in (1,5)),240)
            report['final_route_audit']=audit();radio.shell('rm -f '+guard);wait(lambda s:not s.get('ringOnly'),20)
            if not (BUILD/call_report).exists():(BUILD/call_report).write_text(json.dumps({'before':before,'boot_id':boot})+'\n')
            run('verify-cs-test-restored.py','--call-report',call_report,'--output',stem+'-restore.json',*([] if require_ims else ['--allow-unregistered']))
            report['ims_ready_after']=bool(radio.status().get('imsReady'))
            report['ims_was_already_unavailable']=not before.get('imsReady')
            report['runtime_restored']=True
    except Exception as exc:report['restore_error']=str(exc);raise
    finally:
        report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        path=BUILD/(stem+'-test.json');path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
if report.get('bridge_cleanup_error'):raise SystemExit('PCM process cleanup could not be confirmed')
if report.get('sip_cleanup_error'):raise SystemExit('SIP diagnostic cleanup could not be confirmed')
if not report.get('kernel_capture',{}).get('closed'):raise SystemExit('Kernel capture cleanup could not be confirmed')
if args.sip_media and (report.get('sip_media',{}).get('failure') or not all(report.get('sip_media',{}).get(k) for k in ('sip_media_connected','pbx_extension_removed','pbx_idle'))):raise SystemExit('SIP diagnostic or restoration failed; see sanitized report')
if args.sip_controls_call and not all(report.get('sip_media',{}).get(k) for k in ('sip_hangup_received','cs_hangup_requested')):raise SystemExit('SIP-to-CS hangup not verified')
print('RESTORED: local parameters, flags/profile, callbacks/MM and guards verified; IMS ready='+str(report['ims_ready_after'])+'.',flush=True)

#!/usr/bin/env python3
"""One bounded idle audio test to observe B03 DSP command replies, no SIM call."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,re,subprocess,time
from cs_i2s_signal import analyze as analyze_signal

BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
parser=argparse.ArgumentParser(description=__doc__)
variant=parser.add_mutually_exclusive_group()
variant.add_argument('--full-voice-open',action='store_true',help='No-call test of complete reference Open/Enable parameters')
variant.add_argument('--public-pcm',action='store_true',help='No-call full Open/public PCM paths and clock-matched real mode builder')
parser.add_argument('--arm-slave',action='store_true',help='With full voice API: actual alternative DSP-master profile')
parser.add_argument('--both-ports',action='store_true',help='Read both ARM FIFOs using actual full voice start profiles')
parser.add_argument('--rx-start',action='store_true',help='Full voice: compare initial and late startup ARM0 profile')
parser.add_argument('--rx-slots',action='store_true',help='With full voice: bounded mono/stereo RX comparison, no call')
parser.add_argument('--both-ports-signal',action='store_true',help='Tone on/off/on with bounded FIFO signal statistics')
parser.add_argument('--arm1-rx-only',action='store_true')
args=parser.parse_args()
if args.arm1_rx_only and not args.both_ports_signal:parser.error('RX only requires signal test')
if args.both_ports_signal and not args.both_ports:parser.error('Signal metadata requires both port diagnostic')
if args.both_ports and (not args.full_voice_open or args.arm_slave or args.rx_start or args.rx_slots):parser.error('Both ports requires a separate full voice ARM master test')
if args.rx_start and (not args.full_voice_open or args.arm_slave or args.rx_slots):parser.error('RX start requires separate full voice ARM master test')
if args.rx_slots and (not args.full_voice_open or args.arm_slave):parser.error('RX slots requires full voice ARM master')
if args.arm_slave and not (args.full_voice_open or args.public_pcm):parser.error('--arm-slave requires --full-voice-open or --public-pcm')
stem=('cs-public-pcm' if args.public_pcm else 'cs-full-voice-open')+('-arm-slave' if args.arm_slave else '') if args.full_voice_open or args.public_pcm else 'cs-audio-mailbox-ack'
if args.rx_slots:stem='cs-full-voice-rx-slots'
if args.rx_start:stem='cs-full-voice-rx-start'
if args.both_ports:stem='cs-full-voice-both-ports'
if args.both_ports_signal:stem+='-signal'
if args.arm1_rx_only:stem+='-rx-only'
def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,BASE/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
radio=load('ack_radio','test-cs-reattach.py')
restore=load('ack_restore','restore-cs-test.py')
def wait_status(predicate,seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=radio.status()
        if predicate(value):return value
        time.sleep(.5)
    raise RuntimeError('Runtime transition timeout')
def run(filename,*arguments):
    value=subprocess.run(['python3',str(BASE/filename),*arguments],capture_output=True,text=True,timeout=60)
    if value.returncode:raise RuntimeError(filename+' failed: '+value.stderr[-1000:])
def route_audit():
    run('test-cs-kernel-probe.py','--routing')
    value=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not value.get('restoration_verified'):raise RuntimeError('Original callbacks/MM not confirmed')
    return value
before=radio.status();boot=radio.shell('cat /proc/sys/kernel/random/boot_id')
if before.get('csOnly') or before.get('ringOnly') or not before.get('imsReady') or json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):
    raise SystemExit('Idle production IMS required')
guard='/mnt/userdata/mf79u/native-ring-only'
if radio.shell('test -e '+guard+' && echo PRESENT')=='PRESENT':raise SystemExit('Ring guard already owned')
if any(radio.get_flag(n) for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')) or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):
    raise SystemExit('Expected production flags/profile required')
header=BUILD/'cs-i2s-parameters.h';saved_header=header.read_bytes()
configuration=BUILD/('mf283u-public-pcm'+('-arm-slave' if args.arm_slave else '')+'-configuration-emulation.json' if args.public_pcm else 'mf283u-voice-inner'+('-slave' if args.arm_slave else '')+'-init-configuration-emulation.json')
saved_configuration=configuration.read_bytes() if (args.full_voice_open or args.public_pcm) and configuration.exists() else None
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'before':before,'boot_id':boot,'no_sim_calls':True,'no_boot_changes':True,
    'dsp_program_uploaded':False,'reply_observation_only':True}
report['fifo_sample_rate_hz']=8000
guarded=False
try:
    if args.public_pcm:
        root=BASE.parents[1];python=str(root/'work/jffs2-venv/bin/python')
        options=['--arm-slave'] if args.arm_slave else []
        p=subprocess.run([python,str(root/'work/zte/voice/emulate-mf283u-public-pcm.py'),*options],capture_output=True,text=True,timeout=30)
        if p.returncode:raise RuntimeError('Public PCM emulation failed: '+p.stderr[-1000:])
        run('prepare-cs-public-pcm.py',*options)
        report.update(public_pcm_route=True,pcm_tail_active=True,arm_clock_master=not args.arm_slave,
                      unsupported_input_warning=True,production_voice_backend=False)
    elif args.full_voice_open:
        root=BASE.parents[1];python=str(root/'work/jffs2-venv/bin/python')
        ref=root/'work/zte/voice'
        options=['--arm-slave'] if args.arm_slave else []
        for script,arguments in [(ref/'emulate-mf283u-voice-open.py', ['--port-tone',*options]),
                                 (ref/'emulate-mf283u-i2s.py', ['--voice-inner','--driver-init',*options])]:
            p=subprocess.run([python,str(script),*arguments],capture_output=True,text=True,timeout=30)
            if p.returncode:raise RuntimeError(script.name+' failed: '+p.stderr[-1200:])
        run('prepare-cs-full-voice-parameters.py',*options)
        report.update(full_reference_voice_api=True,pcm_tail_inactive=True,
                      reference_afe_route_only=True,arm_clock_master=not args.arm_slave)
    else:
        run('prepare-cs-i2s-parameters.py','--idle-tone-loop','--driver-init')
    run('build-cs-kernel-probe.py','--i2s-dsp-loop',*(['--i2s-both-ports','--i2s-both-ports-signal','--i2s-arm1-rx-only'] if args.arm1_rx_only else ['--i2s-both-ports','--i2s-both-ports-signal'] if args.both_ports_signal else ['--i2s-both-ports'] if args.both_ports else ['--i2s-rx-slots'] if args.rx_slots else ['--i2s-rx-start'] if args.rx_start else []))
    if args.full_voice_open or args.public_pcm:(BUILD/(stem+'-configuration.json')).write_bytes(configuration.read_bytes())
    for source,suffix in [('mf79u_cs_i2s_dsp_loop.ko','.ko'),('cs-i2s-dsp-loop-probe-build.json','-build.json'),('cs-i2s-parameters.h','-parameters.h')]:
        (BUILD/(stem+suffix)).write_bytes((BUILD/source).read_bytes())
    radio.shell('umask 077; : > '+guard+'; chmod 600 '+guard)
    guarded=True;wait_status(lambda s:s.get('ringOnly'),20)
    report['before_route_audit']=route_audit()
    print('Preparing guarded idle GSM; no SIM calls.',flush=True)
    load('ack_prepare','prepare-cs-channel-test.py')
    print('Observing DSP replies and FIFO metadata during the bounded idle loop.',flush=True)
    run('test-cs-kernel-probe.py','--i2s-dsp-loop',*(['--i2s-both-ports','--i2s-both-ports-signal','--i2s-arm1-rx-only'] if args.arm1_rx_only else ['--i2s-both-ports','--i2s-both-ports-signal'] if args.both_ports_signal else ['--i2s-both-ports'] if args.both_ports else ['--i2s-rx-slots'] if args.rx_slots else ['--i2s-rx-start'] if args.rx_start else []))
    report['probe']=json.loads((BUILD/'cs-i2s-dsp-loop-probe-live.json').read_text())
    if args.rx_slots:report['rx_slot_comparison']=True
    if args.rx_start:report['rx_start_comparison']=True
    if args.both_ports:report['both_ports']=True
    if args.arm1_rx_only:report['arm1_rx_only']=True
    if args.both_ports_signal:
        report['both_ports_signal']=True
        report.update(analyze_signal(report['probe']['messages']))
        if not report['arm1_tone_signal_verified']:raise RuntimeError('ARM1 tone on/off/on signal not verified')
    report['responses']=[{'command':m[1],'response':m[2],'negative_ack':m[3]=='1','rejected_zero':m[4]=='1'}
        for row in report['probe']['messages'] if (m:=re.search(r'dsp_audio_command=([0-9a-f]{2}).*response=([0-9a-f]{4}) negative_ack=([01]) rejected_zero=([01])',row))]
    if len(report['responses'])<10:raise RuntimeError('Fresh DSP response observations missing')
    report['all_commands_negative_ack']=all(r['negative_ack'] for r in report['responses'])
    totals=[m for row in report['probe']['messages'] if (m:=re.search(r'i2s_stopped=1.*tx_words=(\d+) rx_words=(\d+) rx_nonzero=(\d+) failed=(\d+)',row))]
    if len(totals)!=1:raise RuntimeError('Fresh FIFO totals missing')
    report['fifo_totals']=dict(zip(('tx_words','rx_words','rx_nonzero','failed'),map(int,totals[0].groups())))
    print('DSP negative ACK for every observed command: '+str(report['all_commands_negative_ack']),flush=True)
finally:
    header.write_bytes(saved_header)
    report['previous_header_restored']=header.read_bytes()==saved_header
    if args.full_voice_open or args.public_pcm:
        if saved_configuration is None:configuration.unlink(missing_ok=True)
        else:configuration.write_bytes(saved_configuration)
        report['previous_configuration_restored']=(not configuration.exists() if saved_configuration is None else configuration.read_bytes()==saved_configuration)
    try:
        if guarded:
            if any(row.startswith('mf79u_cs_i2s_dsp_loop ') for row in radio.shell('cat /proc/modules').splitlines()):
                raise RuntimeError('Audio probe remains loaded; retain guard')
            radio.radio(0);report['radio_off_route_audit']=route_audit()
            restore.main();radio.radio(1)
            wait_status(lambda s:s.get('imsReady') and not s.get('csOnly'),90)
            report['final_route_audit']=route_audit()
            radio.shell('rm -f '+guard)
            after=wait_status(lambda s:not s.get('ringOnly'),20)
            report.update(after=after,same_boot=radio.shell('cat /proc/sys/kernel/random/boot_id')==boot,
                same_native_sip_pids=all(before[k]==after[k] for k in ('pid','sipPid')),
                voice_flags_restored=all(radio.get_flag(n)==0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')),
                profile_restored='^SYSCONFIG: 27,0,1,2' in radio.at('AT^SYSCONFIG?'))
            report['runtime_restored']=all(report[k] for k in ('same_boot','same_native_sip_pids','voice_flags_restored','profile_restored','previous_header_restored')) and report.get('previous_configuration_restored',True) and after.get('imsReady') and not after.get('csOnly') and not after.get('ringOnly')
    except Exception as exc:
        report['restore_error']=str(exc);raise
    finally:(BUILD/(stem+'-live.json')).write_text(json.dumps(report,indent=2)+'\n')
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
print(json.dumps({k:report[k] for k in ('runtime_restored','all_commands_negative_ack','fifo_totals')},indent=2))

#!/usr/bin/env python3
"""Guarded reversible B03 read-only kernel probe; never dials/answers or patches CP."""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess
from ram_transfer import ram_push
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];ADB=[str(ROOT/'outputs/adb')]
parser=argparse.ArgumentParser(description=__doc__)
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--routing',action='store_true')
mode.add_argument('--sysfs',action='store_true')
mode.add_argument('--i2s-loop',action='store_true')
mode.add_argument('--i2s-dsp-loop',action='store_true')
mode.add_argument('--i2s-preflight',action='store_true')
mode.add_argument('--module-layout',action='store_true')
parser.add_argument('--i2s-both-ports',action='store_true')
parser.add_argument('--i2s-rx-start',action='store_true')
parser.add_argument('--i2s-rx-slots',action='store_true')
parser.add_argument('--i2s-both-ports-signal',action='store_true',help='Tone on/off/on with bounded FIFO signal statistics')
parser.add_argument('--i2s-arm1-rx-only',action='store_true',help='Enable ARM1 RX without its unused transmitter')
args=parser.parse_args()
if args.i2s_arm1_rx_only and not args.i2s_both_ports_signal:parser.error('RX only requires idle signal test')
if args.i2s_both_ports_signal and not args.i2s_both_ports:parser.error('Signal metadata requires both port diagnostic')
if args.i2s_both_ports and (not args.i2s_dsp_loop or args.i2s_rx_start or args.i2s_rx_slots):raise SystemExit('Both ports requires separate idle test')
if args.i2s_rx_start and (not args.i2s_dsp_loop or args.i2s_rx_slots):raise SystemExit('RX start is a separate no-call variant')
if args.i2s_rx_slots and not args.i2s_dsp_loop:raise SystemExit('RX slots is no-call only')
NAME='mf79u_cs_route' if args.routing else ('mf79u_cs_sysfs' if args.sysfs else 'mf79u_cs_probe')
OUTPUT='cs-route-probe' if args.routing else ('cs-sysfs-probe' if args.sysfs else 'cs-kernel-probe')
PREFIX='MF79U_CS_ROUTE' if args.routing else ('MF79U_CS_SYSFS' if args.sysfs else 'MF79U_CS_KPROBE')
if args.i2s_preflight:NAME='mf79u_cs_i2s';OUTPUT='cs-i2s-preflight';PREFIX='MF79U_CS_I2S'
if args.i2s_loop:NAME='mf79u_cs_i2s_loop';OUTPUT='cs-i2s-loop-probe';PREFIX='MF79U_CS_I2S_LOOP'
if args.i2s_dsp_loop:NAME='mf79u_cs_i2s_dsp_loop';OUTPUT='cs-i2s-dsp-loop-probe';PREFIX='MF79U_CS_I2S_DSP_LOOP'
if args.module_layout:NAME='mf79u_cs_module_layout';OUTPUT='cs-module-layout-probe';PREFIX='MF79U_CS_MODULE_LAYOUT'
REMOTE='/dev/.mf79u-'+OUTPUT+'.ko'
def shell(command):
 return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def status():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def boot():return shell('cat /proc/sys/kernel/random/boot_id')
def loaded():return any(line.split()[0]==NAME for line in shell('cat /proc/modules').splitlines())
if loaded():raise SystemExit('Our probe is already loaded; refusing another owner')
if shell('uname -r')!='3.4.110-rt140':raise SystemExit('Unrecognized kernel')
for path,expected in [('/lib/cpko/cpko.ko','8138d03644b0417ec3fba9d7175200bc'),('/lib/modules/3.4.110-rt140/kernel/drivers/cfg/cfg.ko','62a4f0142042da52ea7e207c160f4dfe')]:
 if shell('md5sum '+path).split()[0]!=expected:raise SystemExit('Unrecognized B03 binary')
modules=shell('cat /proc/modules').splitlines()
if not any(line.startswith('cpko 6397096 ') and '0xbf000000' in line for line in modules):raise SystemExit('Unrecognized CP placement')
before=status();boot_id=boot();
if args.i2s_dsp_loop:
 build=json.loads((BASE/'build'/(OUTPUT+'-build.json')).read_text())
 if bool(build.get('arm1_rx_only'))!=args.i2s_arm1_rx_only:raise SystemExit('ARM1 RX only must be explicitly selected')
 if bool(build.get('both_ports_signal'))!=args.i2s_both_ports_signal:raise SystemExit('Signal metadata variant must be explicitly selected')
 if bool(build.get('both_ports'))!=args.i2s_both_ports:raise SystemExit('Both port variant must be explicitly selected')
 if bool(build.get('rx_start_comparison'))!=args.i2s_rx_start:raise SystemExit('RX start variant must be explicitly selected')
 if bool(build.get('rx_slot_comparison'))!=args.i2s_rx_slots:raise SystemExit('RX slot variant must be explicitly selected')
audio_loop=args.i2s_loop or args.i2s_dsp_loop
if audio_loop and (before.get('imsReady') or not before.get('csOnly')):raise SystemExit('I2S loop requires idle CS-only test policy')
taint=shell('cat /proc/sys/kernel/tainted')
if not before.get('ringOnly') or (not args.routing and not args.sysfs and not args.i2s_preflight and not audio_loop and (before.get('csOnly') or not before.get('imsReady'))):raise SystemExit('Stable ring-only runtime required')
if args.i2s_dsp_loop and (shell('test -e /sys/mf79u_cs/status && echo ACTIVE')=='ACTIVE' or shell('test -e /sys/mf79u_cs_mo/status && echo ACTIVE')=='ACTIVE'):
 raise SystemExit('Call diagnostic still active')
gateway=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
if gateway.get('activeCall'):raise SystemExit('Active call; refusing probe')
local=BASE/'build'/f'{NAME}.ko';result={}
build=json.loads((BASE/'build'/f'{OUTPUT}-build.json').read_text())
if build['sha256']!=hashlib.sha256(local.read_bytes()).hexdigest():raise SystemExit('Build metadata checksum mismatch')
try:
 ram_push(ADB,local,REMOTE)
 response=shell('insmod '+REMOTE+'; echo MF79U_INSMOD_EXIT=$?')
 result['insmod_ok']='MF79U_INSMOD_EXIT=0' in response
 result['loaded']=loaded()
 # Kernel log filtering happens on the device; no unrelated kernel logs are saved.
 log=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep '"+PREFIX+"' | tail -n 64").splitlines()
 starts=[i for i,s in enumerate(log) if ('cp_structure=' if args.module_layout else 'clock=i2s0_apb_clk' if args.i2s_preflight else ('configured no_calls=' if args.i2s_dsp_loop else 'configured clock=' if args.i2s_loop else 'name=CC ' if args.routing else ('object=' if args.sysfs else 'signature=verified cp_getters=verified'))) in s]
 result['messages']=log[starts[-1]:] if starts else log
 if not result['insmod_ok'] or not result['loaded']:raise RuntimeError('Kernel probe did not load: '+response)
 if not any(('layout_verified=1' if args.module_layout else 'preflight=verified' if args.i2s_preflight else ('completed=1 tone_started=1 tone_stopped=1' if args.i2s_dsp_loop else 'completed=1 registers_restored=1' if args.i2s_loop else 'send_signature=verified' if args.routing else ('own_object_removed=1' if args.sysfs else 'cp_getters=verified'))) in s for s in result['messages']):raise RuntimeError('Kernel verification evidence missing')
 if args.i2s_dsp_loop and not any('registers_restored=1 ' in s and 'saved_ap_fields_restored=1 ' in s for s in result['messages']):raise RuntimeError('Audio register restoration evidence missing')
finally:
 if loaded():
  result['unload_response']=shell('rmmod '+NAME+'; echo MF79U_RMMOD_EXIT=$?')
 result['unloaded']=not loaded();shell('rm -f '+REMOTE)
 after=status();result.update({'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'module_sha256':hashlib.sha256(local.read_bytes()).hexdigest(),'before':before,'after':after,
  'same_boot':boot()==boot_id,'boot_id':boot_id,'taint_before':taint,'taint_after':shell('cat /proc/sys/kernel/tainted'),
  'no_calls_or_cp_writes':not audio_loop,'no_sim_calls':True,'i2s_register_writes':audio_loop,'dsp_audio_commands':args.i2s_dsp_loop,'remote_file_removed':shell('test ! -e '+REMOTE+' && echo CLEAN')=='CLEAN'})
 if args.routing:
  result['diagnostic_modules']=sorted(row.split()[0] for row in shell('cat /proc/modules').splitlines() if row.startswith('mf79u_cs_'))
  result['restoration_verified']=any('callbacks_original=1 admission_original=1 mm_cc_references=0 ' in row and 'quiescent=1' in row for row in result.get('messages',[]))
 (BASE/'build'/f'{OUTPUT}-live.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if not result['unloaded'] or not result['same_boot'] or before['pid']!=after['pid'] or before['sipPid']!=after['sipPid'] or before.get('imsReady')!=after.get('imsReady'):raise SystemExit('Runtime preservation check failed')

#!/usr/bin/env python3
"""Observe a prepared one-answer MT tone candidate, saving sanitized metadata.

Does not arm, answer, dial, change radio or load another observer. The kernel
probe owns its single answer and bounded hangup; this tool only observes it.
"""
from pathlib import Path
import argparse,datetime,json,re,subprocess,time
BASE=Path(__file__).resolve().parent;ADB=[str(BASE.parents[1]/'outputs/adb')]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report',required=True)
parser.add_argument('--i2s-pcm',action='store_true')
args=parser.parse_args()
if Path(args.report).name!=args.report or not args.report.endswith('.json'):
 raise SystemExit('Plain JSON report basename required')
def shell(command):
 return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=15).decode().replace('\r','').strip()
def native():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def stamp(line):
 m=re.search(r'\[\s*([0-9.]+)\]',line)
 return float(m.group(1)) if m else -1
def log():
 return shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_KCONNECT | tail -n 160").splitlines()
before=native();boot=shell('cat /proc/sys/kernel/random/boot_id')
if not before.get('ringOnly') or not before.get('csOnly') or before.get('imsReady') or before.get('csRegistration') not in (1,5):
 raise SystemExit('Registered guarded CS-only runtime required')
initial=shell('cat /sys/mf79u_cs/status').split()
if len(initial)!=8 or initial[:4]!=['MF79U_CS','1','1','0'] or initial[-1]!='0':
 raise SystemExit('Fresh armed one-answer MT probe required')
rows=log();starts=[stamp(r) for r in rows if 'armed seconds=' in r]
if not starts or not any(('i2s_pcm_candidate=1 ' if args.i2s_pcm else 'dsp_audio_candidate=1 ') in r and stamp(r)>=starts[-1] for r in rows):
 raise SystemExit('Incoming DSP tone arming evidence absent')
start=starts[-1];path=BASE/'build'/args.report
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot_id':boot,'before':before,
 'initial_status':initial,'explicitly_authorized_single_answer':True,'no_dial':True,'number_saved':False,
 'audio_compatibility_verified':False,'status_samples':[],'messages':[]}
def save():path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
def update_log():
 for row in log():
  if stamp(row)>=start and row not in report['messages']:report['messages'].append(row)
save();last=None;deadline=time.monotonic()+360
try:
 while time.monotonic()<deadline:
  if shell('cat /proc/sys/kernel/random/boot_id')!=boot:report['reboot']=True;break
  update_log()
  if shell('test -e /sys/mf79u_cs/status && echo PRESENT')!='PRESENT':report['sysfs_removed']=True;break
  row=shell('cat /sys/mf79u_cs/status')
  if row!=last:
   report['status_samples'].append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':row});last=row
  save();time.sleep(1)
 else:report['observation_timeout']=True
except Exception as exc:
 report['failure']=str(exc);raise
finally:
 try:
  update_log();trace='\n'.join(report['messages'])
  report.update(connected='mt_state=3 ' in trace,setup_observed='message_type=05 ' in trace,
   generator_started='dsp_audio_tone_phase=0 ' in trace,
   all_tone_phases=all('dsp_audio_tone_phase='+str(i)+' ' in trace for i in range(3)),
   audio_commands_observed='dsp_audio_command=' in trace,
   ap_audio_fields_restored='saved_ap_fields_restored=1 ' in trace,
   mm_service_released='mm_cc_service_released=1 ' in trace or 'mm_release_indication=1 ' in trace,
   callback_restored='callback_restored=1 call_idle=1 ' in trace,
   after=native(),same_boot=shell('cat /proc/sys/kernel/random/boot_id')==boot)
  report['same_native_sip_pids']=all(before[k]==report['after'][k] for k in ['pid','sipPid'])
  if args.i2s_pcm:
   report.update(i2s_pcm_test=True,i2s_started='i2s_pcm_started=1 ' in trace,
     i2s_registers_restored='registers_restored=1 ' in trace,
     production_sip_audio_verified=False)
   if 'port_tone_stage=' in trace:
    report.update(connected_port_tone=True,
      dsp_only_control_observed='port_tone_stage=dsp_only ' in trace,
      dsp_and_arm_rx_observed='port_tone_stage=dsp_and_arm_rx ' in trace,
      tone_restored='port_tone_stopped=1 saved_tone_restored=1' in trace)
 except Exception as exc:report['postcheck_error']=str(exc)
 report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
print(json.dumps({k:report.get(k) for k in ['connected','generator_started','all_tone_phases','ap_audio_fields_restored','mm_service_released','callback_restored','same_boot','same_native_sip_pids']}))

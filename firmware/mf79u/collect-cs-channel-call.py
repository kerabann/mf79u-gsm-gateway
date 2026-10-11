#!/usr/bin/env python3
"""Collect only our sanitized CC/channel metadata during a supervised ring test.

Stops the unloadable channel sampler on completion/timeout/interruption. The CC
callback has its own bounded expiry and remains pinned until reboot.
"""
from pathlib import Path
import argparse,datetime,json,subprocess,time
from cs_observation_evidence import observation_evidence
BASE=Path(__file__).resolve().parent;ADB=str(BASE.parents[1]/'outputs/adb')
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--connect-probe',action='store_true')
parser.add_argument('--report',help='Evidence filename inside build; must be a plain .json basename')
args=parser.parse_args()
if args.report and (Path(args.report).name!=args.report or not args.report.endswith('.json')):
 raise SystemExit('Plain JSON report basename required')
def shell(c):return subprocess.check_output([ADB,'shell',c],stderr=subprocess.PIPE,timeout=12).decode().replace('\r','').strip()
def native():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def interrupts():
 return [r for r in shell('cat /proc/interrupts').splitlines()
         if any(n in r for n in ['RpMsgPHY','gp0_int_lisr','tint2_lisr','dsp_int0_lisr','dsp_int1_lisr','dsp_int7_lisr'])]
before=native();boot=shell('cat /proc/sys/kernel/random/boot_id')
if not before.get('ringOnly') or not before.get('csOnly') or (not args.connect_probe and not before.get('csSignalingReady')):
 raise SystemExit('Armed registered CS ring-only runtime required')
if not any(r.startswith('mf79u_cs_channels ') for r in shell('cat /proc/modules').splitlines()):
 raise SystemExit('Channel sampler is absent; arm it immediately before collection')
path=BASE/'build'/(args.report or ('cs-channel-connected-live.json' if args.connect_probe else 'cs-channel-incoming-live.json'))
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,
        'no_dial_or_answer':not args.connect_probe,'payload_read':False,'cursor_writes':False,'messages':[],'states':[],
        'interrupts_before':interrupts()}
seen=set();last=None;incoming=False;ended_at=None;end=time.monotonic()+540
def save():
 path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
save()
try:
 while time.monotonic()<end:
  tag='KCONNECT' if args.connect_probe else 'KRING'
  rows=shell("/mnt/userdata/mf79u/tools/busybox dmesg | /mnt/userdata/mf79u/tools/busybox grep -E 'MF79U_CS_(CHANNEL|"+tag+")' | /mnt/userdata/mf79u/tools/busybox tail -n 180").splitlines()
  # Trim historical modules, and the first sampler instance, from each prefix.
  for prefix in ['MF79U_CS_'+tag,'MF79U_CS_CHANNEL']:
   selected=[r for r in rows if prefix in r]
   starts=[i for i,r in enumerate(selected) if 'armed seconds=' in r]
   if starts:selected=selected[starts[-1]:]
   for r in selected:
    if r not in seen:seen.add(r);report['messages'].append(r)
  now=native();state=now.get('csCallState');armed=now.get('csSignalingReady')
  if args.connect_probe:
   raw=shell('cat /sys/mf79u_cs/status 2>/dev/null').split()
   if len(raw)==8 and raw[:2]==['MF79U_CS','1'] and raw[-1]=='0':
    armed=raw[2]=='1';state={'0':'idle','1':'alerting','2':'releasing'}.get(raw[3],'invalid')
   else:armed=False
  if (state,armed)!=last:
   last=(state,armed);report['states'].append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':state,'armed':last[1]})
  if state=='alerting' or any('tx_type=01 ' in r for r in report['messages']):incoming=True
  released=any('message_type=2a ' in r or 'tx_type=2a ' in r for r in report['messages'])
  if incoming and state=='idle' and released:
   if ended_at is None:ended_at=time.monotonic()
   if time.monotonic()-ended_at>=7:report['completed']=True;break
  if not armed and ended_at is None:break
  report['after']=now;save();time.sleep(1)
except Exception as exc:
 report['failure']=str(exc);raise
finally:
 report.update(finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),incoming_observed=incoming,
               evidence=observation_evidence(report['messages']))
 try:
  report['stop_response']=shell('rmmod mf79u_cs_channels; echo MF79U_CHANNEL_STOP=$?')
  report['channel_sampler_unloaded']=not any(r.startswith('mf79u_cs_channels ') for r in shell('cat /proc/modules').splitlines())
 except Exception as exc:report['cleanup_error']=str(exc)
 try:report.update(after=native(),same_boot=shell('cat /proc/sys/kernel/random/boot_id')==boot,interrupts_after=interrupts())
 except Exception as exc:report['postcheck_error']=str(exc)
 save()
print(json.dumps({k:report[k] for k in ['incoming_observed','same_boot','channel_sampler_unloaded']},indent=2))

#!/usr/bin/env python3
"""Read-only lifecycle check of the already armed bounded CS status module."""
from pathlib import Path
import datetime,json,subprocess,time
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];ADB=[str(ROOT/'outputs/adb')]
def shell(command):return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def native():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
before=native();boot=shell('cat /proc/sys/kernel/random/boot_id')
if not before.get('ringOnly') or not before.get('csOnly') or before.get('imsReady'):raise SystemExit('CS-only ring-only test runtime required')
if json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise SystemExit('Active SIP call')
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,
 'no_answer_or_dial':True,'no_cs_audio':True}
try:
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  armed=native()
  if armed.get('csSignalingReady') and armed.get('csCallState')=='idle':break
  time.sleep(.5)
 else:raise RuntimeError('Controller did not observe the live CS interface')
 report['armed']=armed;report['wire_status']=shell('cat /sys/mf79u_cs/status')
 if report['wire_status']!='MF79U_CS 1 1 0 0 0 0 1':raise RuntimeError('Unexpected call activity or status ABI')
 print('Live controller sees CS signaling ready; idle, audio unavailable, ring-only retained.',flush=True)
 deadline=time.monotonic()+110
 while time.monotonic()<deadline:
  after=native()
  if not after.get('csSignalingReady') and shell('test ! -e /sys/mf79u_cs/status && echo REMOVED')=='REMOVED':break
  time.sleep(1)
 else:raise RuntimeError('Bounded CS interface expiry not observed')
 report['after']=after
 report['messages']=shell("/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_KRING | tail -n 2").splitlines()
 report['same_boot']=shell('cat /proc/sys/kernel/random/boot_id')==boot
 report['pids_preserved']=before['pid']==after['pid'] and before['sipPid']==after['sipPid']
 report['callback_restored']=any('expired seconds=90 events=0 callback_restored=1' in line for line in report['messages'])
 if not report['same_boot'] or not report['pids_preserved'] or not report['callback_restored'] or after.get('csCallState')!='idle' or after.get('csAudioReady') is not False or not after.get('ringOnly'):raise RuntimeError('Lifecycle preservation failed')
finally:
 (BASE/'build/cs-status-lifecycle-live.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

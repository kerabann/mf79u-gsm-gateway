#!/usr/bin/env python3
"""Prepare an ordinary-SIM, ring-only channel observation; no dial or answer.

Uses the previously verified reversible CS-only/radio/voice-flag policy. Saved
original profiles remain unchanged. On failure attempts the existing restore.
"""
from pathlib import Path
import datetime,importlib.util,json,re,time
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('reattach',BASE/'test-cs-reattach.py')
at=importlib.util.module_from_spec(spec);spec.loader.exec_module(at)
before=at.status();gateway=json.loads(at.shell('cat /dev/.mf79u-gateway-status.json'))
if not before.get('ringOnly') or before.get('csOnly') or gateway.get('activeCall'):
 raise SystemExit('Idle normal ring-only runtime required')
if at.shell('test -e /sys/mf79u_cs/status && echo ACTIVE')=='ACTIVE':
 raise SystemExit('A CS handler is still armed')
if any(at.get_flag(n)!=0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')):
 raise SystemExit('Original voice flags must be zero')
boot=at.shell('cat /proc/sys/kernel/random/boot_id')
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,
        'no_dial_or_answer':True,'stage':'cs_only','resource_samples':[]}
def checkpoint():
 values={'stage':report['stage']}
 for line in at.shell('cat /proc/meminfo').splitlines():
  match=re.fullmatch(r'(MemFree|Cached|SwapFree|SwapTotal|Shmem):\s+(\d+) kB',line)
  if match:values[match[1]+'_kib']=int(match[2])
 report['resource_samples'].append(values)
 (BASE/'build/cs-channel-test-prepared.json').write_text(json.dumps(report,indent=2)+'\n')
try:
 checkpoint()
 at.shell('umask 077; : > /mnt/userdata/mf79u/native-cs-only; chmod 600 /mnt/userdata/mf79u/native-cs-only')
 deadline=time.monotonic()+30
 while time.monotonic()<deadline:
  s=at.status()
  if s.get('csOnly') and not s.get('imsReady') and s.get('state')=='sms_only':break
  time.sleep(.5)
 else:raise RuntimeError('IMS did not stop under CS-only policy')
 report['stage']='gsm_preference';checkpoint();at.at('AT^SYSCONFIG=13,0,1,2')
 if '^SYSCONFIG: 13,0,1,2' not in at.at('AT^SYSCONFIG?'):raise RuntimeError('GSM profile readback failed')
 report['stage']='radio_off';checkpoint();at.radio(0)
 for name in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'):at.flag(name,1)
 report['stage']='radio_on';checkpoint();at.radio(1)
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  s=at.status()
  checkpoint()
  if s.get('csRegistration') in (1,5) and s.get('epsRegistration') not in (1,5):break
  time.sleep(1)
 else:raise RuntimeError('GSM registration timeout')
 if any(at.get_flag(n)!=1 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')):raise RuntimeError('Voice flags changed')
 if at.shell('cat /proc/sys/kernel/random/boot_id')!=boot:raise RuntimeError('Boot changed')
 if s.get('pid')!=before['pid'] or s.get('sipPid')!=before['sipPid'] or not s.get('ringOnly'):
  raise RuntimeError('Runtime ownership or guard changed')
 report.update(stage='ready',after=s,voice_flags=[1,1],radio_profile=[13,0,1,2],same_boot=True)
except Exception as exc:
 report['failure']=str(exc)
 try:
  at.radio(1)
  spec=importlib.util.spec_from_file_location('restore',BASE/'restore-cs-test.py')
  restore=importlib.util.module_from_spec(spec);spec.loader.exec_module(restore);restore.main()
  report['recovery']='original profile/flags restored, ring-only retained'
 except Exception as failure:report['recovery_error']=str(failure)
 raise
finally:
 (BASE/'build/cs-channel-test-prepared.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

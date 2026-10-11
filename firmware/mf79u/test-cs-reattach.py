#!/usr/bin/env python3
"""Reversible ring-only CS capability test; never dials or answers.

Leaves flags=1 after successful reattach for a supervised passive incoming
check. On failure restores flags=0 and radio CFUN=1. IMS stays disabled.
"""
import subprocess,re,json,time,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ADB=str(ROOT/'outputs/adb');USB=str(ROOT/'firmware/mf79u/build/cs-at-wait')
def shell(cmd):
 # Read-only/preparation commands must never inherit a caller's destination
 # pipe. Only the explicit MO control writer passes stdin to ADB.
 return subprocess.check_output([ADB,'shell',cmd],stdin=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def at(cmd):
 p=subprocess.run([USB,cmd,'0','30'],capture_output=True,timeout=40);s=p.stdout.decode(errors='replace')
 if p.returncode or '\r\nOK\r\n' not in s:raise RuntimeError('AT operation failed: '+cmd.split('=')[0])
 return s
def flag(name,value):
 at(f'AT+ZSET="{name}",{value}')
 if get_flag(name)!=value:raise RuntimeError('Flag readback failed')
def status():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def get_flag(name):
 m=re.search(r'\+ZSET:\s*"'+name+r'",(\d+)',at(f'AT+ZSET="{name}"'))
 if not m:raise RuntimeError('Flag query has no value')
 return int(m[1])
def radio(value):
 # A delayed or missing terminal reply cannot tell whether CFUN applied.
 try:at(f'AT+CFUN={value}')
 except RuntimeError:pass
 m=re.search(r'\+CFUN:\s*(\d+)',at('AT+CFUN?'))
 if not m or int(m[1])!=value:raise RuntimeError('Radio readback failed')
def main():
 s=status()
 if not s.get('ringOnly') or not s.get('csOnly') or s.get('imsReady'):raise RuntimeError('Required test guards absent')
 if any(row.split()[:1]==['4131'] for row in shell('cat /proc/sysvipc/msg').splitlines()[1:]):raise RuntimeError('Stop CCAPP watcher before reattach')
 original={name:get_flag(name) for name in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')}
 if any(original.values()):raise RuntimeError('Both original flags must be0')
 boot=shell('cat /proc/sys/kernel/random/boot_id'); result={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'dial_or_answer_issued':False,'original':original}
 try:
  result['stage']='radio_off';radio(0)
  result['stage']='flags_on'
  for name in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'):flag(name,1)
  result['stage']='radio_on';radio(1)
  result['stage']='registration'
  deadline=time.monotonic()+90
  while time.monotonic()<deadline:
   time.sleep(3);s=status()
   if s.get('csRegistration') in (1,5):break
  else:raise RuntimeError('CS registration timeout')
  flags={}
  for name in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'):
   m=re.search(r'\+ZSET:\s*"'+name+r'",(\d+)',at(f'AT+ZSET="{name}"'))
   if not m or int(m[1])!=1:raise RuntimeError('Flag lost after reattach')
   flags[name]=int(m[1])
  if shell('cat /proc/sys/kernel/random/boot_id')!=boot:raise RuntimeError('Unexpected reboot')
  s=status()
  if not s.get('ringOnly') or not s.get('csOnly') or s.get('imsReady'):raise RuntimeError('Test guard changed')
  result.update(runtime=s,flags=flags,boot_unchanged=True,incoming_test_pending=True)
  result['stage']='ready_for_incoming'
 except Exception as exc:
  result['failure']=str(exc);result['recovery']={}
  for name in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'):
   try:flag(name,0);result['recovery'][name]=0
   except Exception as error:result['recovery'][name]={'error':str(error)}
  try:radio(1);result['recovery']['CFUN']=1
  except Exception as error:result['recovery']['CFUN']={'error':str(error)}
  raise
 finally:
  (ROOT/'firmware/mf79u/build/cs-reattach-live.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()

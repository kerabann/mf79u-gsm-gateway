#!/usr/bin/env python3
"""Explicit local capability experiment, no dial/answer/IMS daemon/reboot."""
import json,subprocess,re
from pathlib import Path
root=Path(__file__).resolve().parents[2]
helper=root/'outputs/zte-native-usb'
log=[]
def at(command):
 r=subprocess.run([str(helper),command],capture_output=True,timeout=40)
 response=r.stdout.decode(errors='replace').strip()
 log.append({'command':command,'response':response,'returncode':r.returncode})
 print(command,'->',response,flush=True)
 if r.returncode or not response: raise RuntimeError('AT transport failed')
 return response
original={}
try:
 for flag in ('OPEN_VOICE_FLAG','VOICE_SUPPORT'):
  response=at(f'AT+ZSET="{flag}"')
  value=re.search(r'\+ZSET:\s*"'+flag+r'",(\d+)',response)
  if not value or value.group(1)!='0': raise RuntimeError('Expected known baseline0; refusing experiment')
  original[flag]=int(value.group(1))
 for settings in ({'OPEN_VOICE_FLAG':1},{'VOICE_SUPPORT':1}):
  for flag,value in settings.items():
   if at(f'AT+ZSET="{flag}",{value}').splitlines()[-1].strip()!='OK': raise RuntimeError('Flag set failed')
   at(f'AT+ZSET="{flag}"')
  for command in ('AT+CLCC','AT+CLCC=?','AT+CHLD=?','AT+VTS=?','AT+ZAMRSUP?'):
   at(command)
finally:
 failures=[]
 for flag,value in reversed(list(original.items())):
  try:
   at(f'AT+ZSET="{flag}",{value}')
   response=at(f'AT+ZSET="{flag}"')
   if not re.search(r'\+ZSET:\s*"'+flag+f'",{value}',response):
    failures.append(flag)
  except Exception as exc: failures.append(str(exc))
 (root/'firmware/mf79u/build/voice-flags-combined-test.json').write_text(json.dumps(log,indent=2)+'\n')
 if failures: raise RuntimeError('Rollback verification failed: '+repr(failures))

#!/usr/bin/env python3
"""Isolated fake CP/IMS/SIP only. Never execute on the physical modem."""
from pathlib import Path
import json,subprocess,time
if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():raise SystemExit('Container fixture marker required')
b=Path('firmware/mf79u/build').resolve();marker=Path('/tmp/native-ring-only-test')
for name in ['charged-command','test-call','ims-crash','radio-search']:Path('/tmp/'+name).unlink(missing_ok=True)
for name in ['guard-test','radio-lte','ims-accept']:Path('/tmp/'+name).touch()
marker.touch();Path('/tmp/fixture-gateway.ini').write_text('role=SERVER\n')
cp=subprocess.Popen([str(b/'native-fallback-fixture'),'cp'],stdout=subprocess.PIPE,text=True);assert cp.stdout.readline().strip()=='FIXTURE_CP_READY'
with open('/tmp/native-ring-only.log','w') as log:
 p=subprocess.Popen([str(b/'native-ring-only-test'),str(b/'test-ims'),'/dev/null',str(b/'test-sip'),'/tmp/fixture-gateway.ini'],stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+45
  while time.monotonic()<deadline:
   assert p.poll() is None
   text=Path('/tmp/native-ring-only.log').read_text()
   if 'voice_answer_blocked' in text and 'outgoing_call_blocked' in text:break
   time.sleep(.2)
  else:raise AssertionError('Guard paths were not exercised')
  time.sleep(.5)
  assert not Path('/tmp/charged-command').exists(),'ATA or ATD reached fake IMS'
  state=json.loads(Path('/dev/.mf79u-native-status.json').read_text());assert state['ringOnly'] and state['sipPid']>0
  print('PASS ring-only guard blocks forged SIP DIAL and ANSWER with IMS ready; no ATA/ATD forwarded')
 finally:p.terminate();p.wait(timeout=15);cp.terminate();cp.wait();marker.unlink(missing_ok=True)

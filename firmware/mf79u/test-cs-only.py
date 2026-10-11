#!/usr/bin/env python3
"""Isolated fake LTE/IMS: reversible CS-only policy preserves SIP/SMS process."""
from pathlib import Path
import json,subprocess,time
if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():raise SystemExit('Isolated fixture required')
b=Path('firmware/mf79u/build').resolve();marker=Path('/tmp/native-cs-only-test')
for name in ['guard-test','test-call','ims-crash','radio-search','charged-command']:
 Path('/tmp/'+name).unlink(missing_ok=True)
for name in ['radio-lte','ims-accept']:Path('/tmp/'+name).touch()
marker.touch();Path('/tmp/fixture-gateway.ini').write_text('role=SERVER\n')
cp=subprocess.Popen([str(b/'native-fallback-fixture'),'cp'],stdout=subprocess.PIPE,text=True)
assert cp.stdout.readline().strip()=='FIXTURE_CP_READY'
with open('/tmp/native-cs-only.log','w') as log:
 p=subprocess.Popen([str(b/'native-cs-only-test'),str(b/'test-ims'),'/dev/null',str(b/'test-sip'),'/tmp/fixture-gateway.ini'],stdout=log,stderr=subprocess.STDOUT)
 def wait(check):
  deadline=time.monotonic()+35
  while time.monotonic()<deadline:
   assert p.poll() is None
   try:r=json.loads(Path('/dev/.mf79u-native-status.json').read_text())
   except (OSError,ValueError):time.sleep(.1);continue
   if r.get('pid')==p.pid and check(r):return r
   time.sleep(.1)
  raise AssertionError('Policy state timeout')
 try:
  r=wait(lambda r:r.get('csOnly') and r.get('epsRegistration')==5 and r.get('state')=='sms_only')
  sip=r['sipPid'];time.sleep(4)
  assert 'lte_ims_attempt' not in Path('/tmp/native-cs-only.log').read_text()
  marker.unlink();wait(lambda r:not r.get('csOnly') and r.get('imsReady') and r.get('sipPid')==sip)
  marker.touch();wait(lambda r:r.get('csOnly') and not r.get('imsReady') and r.get('sipPid')==sip)
  assert not Path('/tmp/charged-command').exists()
  print('PASS CS-only blocks IMS on LTE, restores IMS after marker removal, stops live IMS after rearming; stable SIP PID, no dial/answer')
 finally:p.terminate();p.wait(timeout=15);cp.terminate();cp.wait();marker.unlink(missing_ok=True)

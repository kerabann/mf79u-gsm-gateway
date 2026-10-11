#!/usr/bin/env python3
"""Isolated CS status lifecycle; never creates a real SIM or SIP call."""
from pathlib import Path
import json,socket,struct,subprocess,time
if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():raise SystemExit('Isolated fixture required')
b=Path('firmware/mf79u/build').resolve()
policy=Path('/tmp/native-cs-status-policy');guard=Path('/tmp/native-cs-status-guard');feed=Path('/tmp/native-cs-status')
led_path=Path('/dev/.mf79u-net-led/control.sock');led_path.parent.mkdir(exist_ok=True)
led=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);led.bind(str(led_path));led.settimeout(2)
for name in ['guard-test','test-call','ims-crash','radio-search','charged-command','radio-lte']:
 Path('/tmp/'+name).unlink(missing_ok=True)
policy.touch();guard.touch();Path('/tmp/fixture-gateway.ini').write_text('role=SERVER\n')
cp=subprocess.Popen([str(b/'native-fallback-fixture'),'cp'],stdout=subprocess.PIPE,text=True)
assert cp.stdout.readline().strip()=='FIXTURE_CP_READY'
with open('/tmp/native-cs-status.log','w') as log:
 p=subprocess.Popen([str(b/'native-cs-status-test'),str(b/'test-ims'),'/dev/null',str(b/'test-sip'),'/tmp/fixture-gateway.ini'],stdout=log,stderr=subprocess.STDOUT)
 def wait(armed,state):
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   assert p.poll() is None
   try:r=json.loads(Path('/dev/.mf79u-native-status.json').read_text())
   except (OSError,ValueError):time.sleep(.1);continue
   if r.get('pid')==p.pid and r.get('csSignalingReady')==armed and r.get('csCallState')==state:
    assert r['smsOnly'] and not r['imsReady'] and not r['csAudioReady'] and r['ringOnly']
    return r
   time.sleep(.1)
  raise AssertionError('CS state timeout')
 try:
  feed.write_text('MF79U_CS 1 1 0 0 0 0 1\n');first=wait(True,'idle');sip=first['sipPid']
  feed.write_text('MF79U_CS 1 1 1 1 2 0 1\n');wait(True,'alerting')
  feed.write_text('MF79U_CS 1 1 2 3 3 0 1\n');wait(True,'releasing')
  feed.write_text('MF79U_CS 1 1 0 4 3 0 1\n');wait(True,'idle')
  feed.write_text('MF79U_CS 1 1 1 6 5 0 1\n');wait(True,'alerting')
  feed.unlink();last=wait(False,'idle');assert last['sipPid']==sip
  feed.write_text('MF79U_CS 1 1 1 7 5 0 0\n');wait(False,'idle')
  assert not Path('/tmp/charged-command').exists()
  trace=Path('/tmp/native-cs-status.log').read_text()
  assert 'event=cs_incoming_alerting' in trace and 'event=cs_call_releasing' in trace and 'event=cs_call_idle' in trace
  assert 'autonomous_control_ready' not in trace and 'incoming_forwarded' not in trace
  expected=[(8,1,4),(8,0,6),(8,0,6),(8,1,4),(8,0,6)]
  for item in expected:
   magic,index,direction,state=struct.unpack('=Iiii',led.recv(64))
   assert magic==0x4d464c31 and (index,direction,state)==item
  print('PASS CS status: idle/alerting/clearing and LED events; expired/malformed feed clears state; SIP PID preserved, audio/IMS not ready, no dial/answer')
 finally:
  p.terminate();p.wait(timeout=15);cp.terminate();cp.wait()
  led.close();led_path.unlink()
  for path in [policy,guard,feed]:path.unlink(missing_ok=True)

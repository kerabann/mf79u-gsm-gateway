#!/usr/bin/env python3
"""Container-only CS child ownership and IMS promotion test; no modem access."""
from pathlib import Path
import json,os,socket,subprocess,time
if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():raise SystemExit('Isolated container required')
B=Path('firmware/mf79u/build').resolve()
for n in ['radio-lte','radio-search','ims-accept','ims-crash','test-call','cs-incoming','cs-crash','cs-commands','call-ended','sip-events']:
 Path('/tmp/'+n).unlink(missing_ok=True)
config=Path('/tmp/fixture-cs-gateway.ini');config.write_text('role=SERVER\n')
cp=subprocess.Popen([str(B/'native-fallback-fixture'),'cp'],stdout=subprocess.PIPE,text=True)
assert cp.stdout.readline().strip()=='FIXTURE_CP_READY'
log=open('/tmp/native-cs.log','w')
p=subprocess.Popen([str(B/'native-cs-backend-test'),str(B/'test-ims'),'/dev/null',str(B/'test-sip'),str(config),str(B/'test-cs')],stdout=log,stderr=subprocess.STDOUT)
def state():
 try:return json.loads(Path('/dev/.mf79u-native-status.json').read_text())
 except (ValueError,OSError):return {}
def wait(check,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if p.poll() is not None:raise AssertionError('Controller exited '+str(p.returncode)+' '+Path('/tmp/native-cs.log').read_text())
  s=state()
  if check(s):return s
  time.sleep(.1)
 raise AssertionError('Timeout '+str(state())+' '+Path('/tmp/native-cs.log').read_text())
def sip(command):
 with open('/proc/'+str(state()['sipPid'])+'/fd/0','wb',buffering=0) as f:f.write(command.encode()+b'\n')
def commands():
 try:return Path('/tmp/cs-commands').read_text()
 except OSError:return ''
try:
 s=wait(lambda s:s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 pid,sip_pid=s['pid'],s['sipPid']
 assert not s['imsReady'] and s['csAudioReady'] and s['csSignalingReady']
 sip('DIAL 1234567');wait(lambda s:s.get('callBackend')=='cs')
 Path('/tmp/radio-lte').touch();Path('/tmp/ims-accept').touch();time.sleep(3)
 assert state()['callBackend']=='cs' and not state()['imsReady'], 'IMS stole active CS dialog'
 before_connected=Path('/tmp/sip-events').read_text().count('CONNECTED\n')
 sip('HANGUP');wait(lambda s:s.get('callBackend')=='none')
 assert Path('/tmp/sip-events').read_text().count('CONNECTED\n')==before_connected, 'stale CONNECTED revived ended dialog'
 s=wait(lambda s:s.get('imsReady') and s.get('voiceBackend')=='ims',30)
 assert s['pid']==pid and s['sipPid']==sip_pid and 'SUSPEND 0' in commands()
 # Adapter socket released before IMS: a bind here must succeed.
 sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',46001));sock.close()
 Path('/tmp/radio-lte').unlink();wait(lambda s:s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 Path('/tmp/cs-incoming').touch();wait(lambda s:s.get('callBackend')=='cs')
 assert Path('/dev/.mf79u-incoming-caller').read_text()=='anonymous'
 sip('ANSWER');time.sleep(.5);assert 'ANSWER 2' in commands()
 # Loss ends only the owned call, then HELLO proves quiescence on restart.
 Path('/tmp/cs-crash').touch();wait(lambda s:not s.get('voiceReady'))
 assert Path('/tmp/call-ended').exists()
 Path('/tmp/cs-incoming').unlink();Path('/tmp/cs-crash').unlink()
 s=wait(lambda s:s.get('voiceReady') and s.get('callBackend')=='none',30)
 assert s['sipPid']==sip_pid and commands().count('DIAL ')==1, 'lost dialog was redialed'
 assert Path('/tmp/native-cs.log').read_text().count('event=cs_outgoing_call')==1
 p.terminate();assert p.wait(timeout=15)==0
 assert not Path('/proc/'+str(sip_pid)).exists()
 report={'isolated_fixture':True,'physical_modem_access':False,'physical_cs_audio_verified':False,
  'cs_incoming_outgoing_dispatch':True,'same_sip_pid':True,'active_call_owner_latched':True,
  'pcm_socket_exclusion':True,'idle_ims_promotion':True,'cs_loss_ends_sip':True,'no_redial':True,'stale_connected_ignored':True}
 (B/'native-cs-backend-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS CS adapter: incoming/outgoing/answer/hangup; stale events ignored; exclusive PCM; active owner; idle IMS promotion; crash/recovery preserve SIP, no redial')
finally:
 if p.poll() is None:p.kill();p.wait()
 cp.terminate();cp.wait();log.close()

#!/usr/bin/env python3
"""Actual native controller, isolated fake CP/IMS/CS; no physical access."""
import json,subprocess,time
from pathlib import Path
assert Path('/tmp/MF79U_ISOLATED_FIXTURE').exists()
B=Path('firmware/mf79u/build').resolve()
for n in ['radio-umts','radio-lte','radio-search','ims-accept','ims-crash','test-call','cs-incoming','cs-crash','cs-commands','call-ended','sip-events','cp-status-error']:
 Path('/tmp/'+n).unlink(missing_ok=True)
Path('/tmp/radio-lte').touch()
config=Path('/tmp/registration.ini');config.write_text('role=TRUNK\nvoice_mode=AUTO\n')
cp=subprocess.Popen([str(B/'native-fallback-fixture'),'cp'],stdout=subprocess.PIPE,text=True)
assert cp.stdout.readline().strip()=='FIXTURE_CP_READY'
log=open('/tmp/registration.log','w')
p=subprocess.Popen([str(B/'registration-test'),str(B/'test-ims'),'/dev/null',str(B/'test-sip'),str(config),str(B/'test-cs')],stdout=log,stderr=subprocess.STDOUT)
def state():
 try:return json.loads(Path('/dev/.mf79u-native-status.json').read_text())
 except (ValueError,OSError):return {}
def wait(check,seconds=50):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if p.poll() is not None:raise AssertionError('Exited '+Path('/tmp/registration.log').read_text())
  s=state()
  if check(s):return s
  time.sleep(.1)
 raise AssertionError('Timeout '+str(state())+' '+Path('/tmp/registration.log').read_text())
def mode(value):config.write_text('role=TRUNK\nvoice_mode='+value+'\n')
def sip(value):
 with open('/proc/'+str(state()['sipPid'])+'/fd/0','wb',buffering=0) as f:f.write(value.encode()+b'\n')
try:
 s=wait(lambda s:s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 assert s['fallbackReason']=='volte_registration_timeout' and s['registrationMode']=='CS'
 pid,sip_pid=s['pid'],s['sipPid']
 sip('DIAL 1234567');wait(lambda s:s.get('callBackend')=='cs')
 Path('/tmp/ims-accept').touch();mode('VOLTE');time.sleep(2)
 assert state()['callBackend']=='cs' and state()['effectiveVoiceMode']=='AUTO'
 sip('HANGUP');wait(lambda s:s.get('voiceBackend')=='ims' and s.get('imsReady'))
 assert state()['effectiveVoiceMode']=='VOLTE' and state()['sipPid']==sip_pid
 mode('CS')
 wait(lambda s:s.get('registrationMode')=='CS' and s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 Path('/tmp/cs-incoming').touch();wait(lambda s:s.get('callBackend')=='cs')
 sip('ANSWER');time.sleep(.3);assert 'ANSWER ' in Path('/tmp/cs-commands').read_text()
 sip('HANGUP');wait(lambda s:s.get('callBackend')=='none')
 Path('/tmp/cs-incoming').unlink();mode('AUTO')
 wait(lambda s:s.get('voiceBackend')=='ims' and s.get('imsReady'))
 sip('DIAL 1234567');wait(lambda s:s.get('callBackend')=='ims')
 Path('/tmp/ims-crash').touch();wait(lambda s:s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 assert state()['fallbackReason']=='ims_process_failed' and state()['pid']==pid and state()['callBackend']=='none'
 assert Path('/tmp/call-ended').exists() and Path('/tmp/cs-commands').read_text().count('DIAL ')==1
 Path('/tmp/ims-crash').unlink()
 wait(lambda s:s.get('voiceBackend')=='ims' and s.get('imsReady'),65)
 assert state()['sipPid']==sip_pid
 mode('CS');wait(lambda s:s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 Path('/tmp/cp-status-error').touch();mode('AUTO')
 wait(lambda s:s.get('registrationMode')=='CS' and s.get('fallbackReason')=='network_state_unavailable')
 Path('/tmp/cp-status-error').unlink();wait(lambda s:s.get('voiceBackend')=='cs' and s.get('voiceReady'))
 mode('VOWIFI');s=wait(lambda s:s.get('effectiveVoiceMode')=='VOWIFI' and s.get('registrationState')=='waiting_for_wifi')
 assert not s['voiceReady'] and s['voiceBackend']=='none' and not s['imsReady']
 commands=Path('/tmp/cs-commands').read_text();sip('DIAL 1234567');time.sleep(1)
 assert state()['callBackend']=='none' and Path('/tmp/cs-commands').read_text()==commands
 config.write_text('role=TRUNK\nvoice_mode=VOWIFI\nvowifi_uplink=USB\n')
 s=wait(lambda s:s.get('vowifiUplink')=='USB' and s.get('registrationState')=='waiting_for_usb')
 assert not s['voiceReady'] and s['sipPid']==sip_pid and s['callBackend']=='none'
 mode('VOWIFI');wait(lambda s:s.get('vowifiUplink')=='WIFI' and s.get('registrationState')=='waiting_for_wifi')
 mode('VOLTE');wait(lambda s:s.get('voiceBackend')=='ims' and s.get('imsReady'))
 p.terminate();assert p.wait(timeout=15)==0
 (B/'registration-fallback-fixture.json').write_text(json.dumps(dict(
  physical_device_access=False,auto_timeout_to_cs=True,manual_modes=True,
  active_call_pinned=True,cs_answer_dispatch=True,ims_crash_to_cs=True,
  idle_retry_to_ims=True,sip_process_preserved=True,active_ims_crash_clears_owner=True,
  failed_status_queries_keep_deadline=True,no_dial_replay=True,vowifi_only_without_wifi_blocks_lte_cs=True,usb_without_ready_blocks_lte_cs=True,usb_wifi_switch_preserves_sip=True),indent=2)+'\n')
 print('PASS actual controller: VoLTE timeout -> GSM; manual AUTO/VOLTE/CS; active call pinned; idle retry; SIP preserved')
finally:
 if p.poll() is None:p.kill();p.wait()
 cp.terminate();cp.wait();log.close()

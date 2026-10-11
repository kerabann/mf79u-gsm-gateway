#!/usr/bin/env python3
"""Container-only lifecycle: GSM, IMS timeout/crash/recovery, stable SIP PID."""
from pathlib import Path
import json,os,subprocess,time
if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():raise SystemExit('Requires isolated container fixture marker; never run on modem')
B=Path('firmware/mf79u/build').resolve()
def touch(name):Path('/tmp/'+name).touch()
def rm(name):Path('/tmp/'+name).unlink(missing_ok=True)
def state():
 try:return json.loads(Path('/dev/.mf79u-native-status.json').read_text())
 except (OSError,ValueError):return {}
def wait(check,seconds=25):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if proc.poll() is not None:raise AssertionError('Controller exited '+str(proc.returncode))
  r=state()
  if check(r):return r
  time.sleep(.1)
 raise AssertionError('State timeout '+str(state()))
for name in ['radio-lte','ims-accept','ims-crash','test-call','call-ended']:rm(name)
touch('radio-search')
cp=subprocess.Popen([str(B/'native-fallback-fixture'),'cp'],stdout=subprocess.PIPE,text=True)
assert cp.stdout.readline().strip()=='FIXTURE_CP_READY'
config=Path('/tmp/fixture-gateway.ini');config.write_text('role=SERVER\n')
log=open('/tmp/native-fallback.log','w')
proc=subprocess.Popen([str(B/'native-fallback-test'),str(B/'test-ims'),'/dev/null',str(B/'test-sip'),str(config)],stdout=log,stderr=subprocess.STDOUT)
try:
 r=wait(lambda r:r.get('state')=='sms_only' and r.get('sipPid',0)>0)
 pid,sip=r['pid'],r['sipPid']
 def stable(r):return r.get('pid')==pid and r.get('sipPid')==sip
 wait(lambda r:stable(r) and r.get('csRegistration')==2)
 rm('radio-search')
 wait(lambda r:stable(r) and r.get('cellularRegistered') and r.get('csRegistration')==5 and not r.get('imsReady'))
 time.sleep(5) # Beyond the fixture IMS timeout; GSM never starts IMS.
 assert stable(state()) and state()['state']=='sms_only'
 assert 'lte_ims_attempt' not in Path('/tmp/native-fallback.log').read_text()
 touch('radio-lte')
 wait(lambda r:stable(r) and r.get('state')=='registering')
 wait(lambda r:stable(r) and r.get('state')=='sms_only') # Actual IMS timeout preserves SIP.
 assert 'registration_timeout_sms_preserved' in Path('/tmp/native-fallback.log').read_text()
 touch('test-call');touch('ims-accept')
 wait(lambda r:stable(r) and r.get('imsReady'),40)
 touch('ims-crash')
 wait(lambda r:stable(r) and not r.get('imsReady'))
 assert Path('/tmp/call-ended').exists(), 'IMS loss did not end the simulated SIP call'
 rm('test-call');rm('ims-crash')
 wait(lambda r:stable(r) and r.get('imsReady'),40)
 rm('radio-lte')
 wait(lambda r:stable(r) and r.get('state')=='sms_only' and not r.get('imsReady'))
 proc.terminate();assert proc.wait(timeout=15)==0
 assert not Path('/proc/'+str(sip)).exists()
 print('PASS: searching/GSM roaming SMS mode; no IMS on GSM; IMS timeout/crash/recovery and LTE->GSM preserve SIP PID; owned cleanup')
finally:
 if proc.poll() is None:proc.kill();proc.wait()
 cp.terminate();cp.wait();log.close()

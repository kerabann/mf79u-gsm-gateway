import hashlib, json, subprocess, time
from pathlib import Path
root=Path('<historical-workspace>');fw=root/'firmware/mf79u';adb=[str(root/'outputs/adb')];base='/mnt/userdata/mf79u'
def sh(s): return subprocess.check_output(adb+['shell',s],stderr=subprocess.PIPE,timeout=10).decode().replace('\r','').strip()
s=json.loads(sh('cat /dev/.mf79u-native-status.json'));g=json.loads(sh('cat /dev/.mf79u-gateway-status.json'))
assert s['callBackend']=='none' and not g['activeCall']
settings=sh('md5sum '+base+'/settings.json '+base+'/gateway.ini');oldboot=sh('cat /proc/sys/kernel/random/boot_id')
hashes={}
for local,remote in [('mf79u-control','.mf79u-control'),('modem-sip-gateway','.mf79u-sip-gateway')]:
 digest=hashlib.md5((fw/'build'/local).read_bytes()).hexdigest()
 assert sh('md5sum '+base+'/'+remote).split()[0]==digest
 hashes[local]=digest
report={'artifacts':hashes,'bootBefore':oldboot,'preRebootIMSReady':s['imsReady'],'preRebootSIPRunning':g['running'],
        'preRebootIMSFailure':'operator REGISTER 500 after service restart','softwareReboot':True,'rawFlash':False,'testSMSOrCalls':False}
p=fw/'build/sms-submission-status-install-20261011.json';p.write_text(json.dumps(report,indent=2)+'\n')
try: subprocess.run(adb+['shell','sync; reboot'],capture_output=True,timeout=10)
except subprocess.TimeoutExpired: pass
start=last=time.monotonic()
while time.monotonic()-start<240:
 try:
  boot=sh('cat /proc/sys/kernel/random/boot_id')
  if boot!=oldboot:
   s=json.loads(sh('cat /dev/.mf79u-native-status.json'));g=json.loads(sh('cat /dev/.mf79u-gateway-status.json'))
   if s.get('imsReady') and g.get('running') and g.get('voiceReady'): break
 except (subprocess.SubprocessError,json.JSONDecodeError): pass
 if time.monotonic()-last>30: print('Waiting for ADB and autonomous IMS/SIP after deliberate reboot.',flush=True);last=time.monotonic()
 time.sleep(2)
else:
 report['postRebootVerified']=False;p.write_text(json.dumps(report,indent=2)+'\n');raise RuntimeError('Postboot recovery timeout')
assert settings==sh('md5sum '+base+'/settings.json '+base+'/gateway.ini')
for local,remote in [('mf79u-control','.mf79u-control'),('modem-sip-gateway','.mf79u-sip-gateway')]:
 assert sh('md5sum '+base+'/'+remote).split()[0]==hashes[local]
assert sh('md5sum '+base+'/.mf79u-cs-voice.ko').split()[0]=='b3440aadf8e7be2e2321d13e539ba078'
report.update({'postRebootVerified':True,'bootAfter':boot,'settingsPreserved':True,'imsReady':True,'imsAccess':s['imsAccess'],
               'sipRunning':True,'voiceReady':g['voiceReady'],'role':g['role'],'nativePid':s['pid'],'sipPid':g['pid'],
               'observedSeconds':round(time.monotonic()-start,1)})
p.write_text(json.dumps(report,indent=2)+'\n');print('PASS deliberate reboot, preserved settings/hashes, autonomous IMS/SIP ready.',flush=True)

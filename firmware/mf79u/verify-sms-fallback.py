#!/usr/bin/env python3
"""Read-only GSM fallback proof; aggregate SMS diagnostics only, no bodies/IDs."""
import argparse,datetime,hashlib,json,re,socket,struct,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ADB=[str(ROOT/'outputs/adb')]
def shell(c):return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def readall(s,n):
 b=b''
 while len(b)<n:
  p=s.recv(n-len(b))
  if not p:raise RuntimeError('Short SMS diagnostics response')
  b+=p
 return b
def diagnostics():
 with socket.create_connection(('127.0.0.1',18190),3) as s:
  s.settimeout(3);s.sendall(b'MSM1\x04'+struct.pack('!I',0));h=readall(s,9)
  n=struct.unpack('!I',h[5:])[0]
  if h[:5]!=b'MSM1\x00' or n>1024:raise RuntimeError('Invalid SMS diagnostics frame')
  return json.loads(readall(s,n))
def snapshot():
 r=json.loads(shell('cat /dev/.mf79u-native-status.json'));g=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
 if r.get('state')!='sms_only' or not r.get('smsOnly') or r.get('imsReady') or not g.get('running') or g.get('imsReady') or g.get('activeCall'):
  raise RuntimeError('Expected idle GSM SMS fallback')
 if r.get('csRegistration') not in (1,5):raise RuntimeError('GSM/3G circuit-switched registration not confirmed')
 if g.get('role') not in ('TRUNK','SERVER'):raise RuntimeError('SIP SMS is disabled')
 pid,sip=int(r['pid']),int(r['sipPid'])
 if sip!=g['pid'] or pid<2 or sip<2:raise RuntimeError('Invalid owned process IDs')
 if shell(f'test /proc/{pid}/exe -ef /mnt/userdata/mf79u/.mf79u-native-gateway && test /proc/{sip}/exe -ef /mnt/userdata/mf79u/.mf79u-sip-gateway && echo OWNED')!='OWNED':raise RuntimeError('Process identity changed')
 if int(re.search(r'^PPid:\s*(\d+)',shell(f'cat /proc/{sip}/status'),re.M)[1])!=pid:raise RuntimeError('SIP ancestry changed')
 sms=diagnostics()
 if not sms.get('enabled') or not sms.get('vendorReady'):raise RuntimeError('SMS worker/backend is unavailable')
 return {'native':r,'gateway':g,'sms':sms,'uptime_seconds':float(shell('cat /proc/uptime').split()[0])}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--observe-seconds',type=int,default=0);args=parser.parse_args()
 if not 0<=args.observe_seconds<=3600:raise SystemExit('Observe duration must be 0..3600 seconds')
 result=subprocess.run(ADB+['forward','tcp:18190','localfilesystem:/mnt/userdata/mf79u/sms-sip.sock'],check=True,capture_output=True)
 try:
  start=snapshot();last=start;began=time.monotonic();progress=began
  while time.monotonic()-began<args.observe_seconds:
   time.sleep(min(10,max(.1,args.observe_seconds-(time.monotonic()-began))))
   last=snapshot()
   if last['native']['pid']!=start['native']['pid'] or last['gateway']['pid']!=start['gateway']['pid']:raise RuntimeError('SMS services restarted during observation')
   if time.monotonic()-progress>25:print('GSM SMS fallback stable; IMS absent, native/SIP PID unchanged, vendor SMS ready.',flush=True);progress=time.monotonic()
  report_path=HERE/'build/gsm-sms-fallback-live.json';report=json.loads(report_path.read_text())
  report.update({'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime':last['native'],'gateway':last['gateway'],'sms_diagnostics':last['sms'],'stability_observation_seconds':round(time.monotonic()-began,1),'observed_native_sip_pids_unchanged':True,'stability_first_uptime_seconds':start['uptime_seconds'],'stability_last_uptime_seconds':last['uptime_seconds']})
  for name in ('mf79u-native-gateway','mf79u-control'):
   expected=hashlib.md5((HERE/'build'/name).read_bytes()).hexdigest()
   if shell('md5sum /mnt/userdata/mf79u/.'+name).split()[0]!=expected:raise RuntimeError('Installed artifact differs from build: '+name)
  report_path.write_text(json.dumps(report,indent=2)+'\n')
  print('PASS autonomous GSM SMS fallback: registered, IMS absent, SIP alive, vendor SMS ready, artifact checksums match; no SMS mutations.')
 finally:subprocess.run(ADB+['forward','--remove','tcp:18190'],capture_output=True)
if __name__=='__main__':main()

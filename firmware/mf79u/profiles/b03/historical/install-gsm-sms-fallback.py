from pathlib import Path
import hashlib,http.server,json,subprocess,threading,time,datetime
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1];BUILD=BASE/'build';DATA='/mnt/userdata/mf79u';ADB=[str(ROOT/'outputs/adb')]
BACKUP=BUILD/'pre-gsm-sms-fallback-20261008'
def shell(c):return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=25).decode().replace('\r','').strip()
def md5(p):return hashlib.md5(p.read_bytes()).hexdigest()
def runtime():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
artifacts={'mf79u-native-gateway':'.mf79u-native-gateway','mf79u-control':'.mf79u-control'}
for name,target in artifacts.items():
 if shell('md5sum '+DATA+'/'+target).split()[0]!=md5(BACKUP/name):raise RuntimeError('Installed binary changed: '+name)
old_settings=shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')
old_boot=shell('cat /proc/sys/kernel/random/boot_id')
old=runtime();assert not old['imsReady'] and not old['sipPid']
supervisor=shell('cat /dev/.mf79u-native-supervisor.pid');assert supervisor.isdigit() and int(supervisor)>1
assert shell('grep -F -q start-native.sh /proc/'+supervisor+'/cmdline && echo OWNED')=='OWNED'
ip=subprocess.check_output(['ipconfig','getifaddr','en10']).decode().strip();assert ip=='192.168.0.169'
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  name=self.path[1:]
  if name not in artifacts:self.send_error(404);return
  b=(BUILD/name).read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer((ip,18089),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 for name,target in artifacts.items():
  stage=DATA+'/'+target+'.gsm-next'
  shell('set -e; '+DATA+'/tools/busybox wget -q -O '+stage+' http://'+ip+':18089/'+name+'; chmod 700 '+stage)
  assert shell('md5sum '+stage).split()[0]==md5(BUILD/name)
 current=runtime();assert not current['imsReady'] and not current['sipPid']
 pid=int(current['pid']);assert pid>1
 owned=shell('test /proc/'+str(pid)+'/exe -ef '+DATA+'/.mf79u-native-gateway && echo OWNED')
 if owned=='OWNED':
  shell('kill -TERM '+str(pid))
  for _ in range(40):
   if shell('test -e /proc/'+str(pid)+'/exe && echo PRESENT')!='PRESENT':break
   time.sleep(.25)
  else:raise RuntimeError('Native cleanup did not finish')
 else:assert current['state']=='stopped'
 for name,target in artifacts.items():
  assert shell('md5sum '+DATA+'/'+target).split()[0]==md5(BACKUP/name)
  shell('set -e; mv '+DATA+'/'+target+'.gsm-next '+DATA+'/'+target+'; sync')
  assert shell('md5sum '+DATA+'/'+target).split()[0]==md5(BUILD/name)
 assert shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')==old_settings
 print('Native/control installed and checksummed; settings preserved. Rebooting for autonomous fallback proof.',flush=True)
finally:server.shutdown();server.server_close()
try:subprocess.run(ADB+['shell','sync; reboot'],capture_output=True,timeout=8)
except subprocess.TimeoutExpired:pass
end=time.monotonic()+180;last=time.monotonic()
while time.monotonic()<end:
 try:
  if shell('cat /proc/sys/kernel/random/boot_id')!=old_boot:
   current=runtime();g=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
   if current['state']=='sms_only' and current.get('smsOnly') and g['running'] and not g['imsReady']:break
 except (subprocess.SubprocessError,ValueError,KeyError):pass
 if time.monotonic()-last>25:print('Waiting for on-device GSM/SIP SMS startup.',flush=True);last=time.monotonic()
 time.sleep(2)
else:raise RuntimeError('Autonomous fallback not confirmed')
assert shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')==old_settings
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifacts':{n:{'md5':md5(BUILD/n),'sha256':hashlib.sha256((BUILD/n).read_bytes()).hexdigest()} for n in artifacts},'real_reboot':True,'settings_unchanged':True,'runtime':current,'gateway':g,'outgoing_calls_or_sms_issued':False,'incoming_live_test_confirmed':False,'full_image_updated':False}
(BUILD/'gsm-sms-fallback-live.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'autonomous_sms_fallback':True,'native_pid':current['pid'],'sip_pid':g['pid'],'ims_ready':g['imsReady'],'settings_unchanged':True}),flush=True)

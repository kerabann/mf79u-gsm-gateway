from pathlib import Path
import hashlib,http.server,json,subprocess,threading,time,datetime,re
BUILD=Path(__file__).resolve().parent;ROOT=BUILD.parents[2];ADB=[str(ROOT/'outputs/adb')];DATA='/mnt/userdata/mf79u'
def shell(c):return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def md5(p):return hashlib.md5(p.read_bytes()).hexdigest()
def owned_leds():
 return [int(p.rsplit('/',1)[1]) for p in shell('for p in /proc/[0-9]*/exe; do if test "$p" -ef /mnt/userdata/mf79u/.mf79u-net-led; then echo "${p%/exe}"; fi; done').splitlines()]
backup=BUILD/'pre-yellow-led-20261008/mf79u-net-led';candidate=BUILD/'mf79u-net-led'
assert shell('md5sum '+DATA+'/.mf79u-net-led').split()[0]==md5(backup)
pids=owned_leds();assert len(pids)==1 and pids[0]>1
pid=pids[0];native=json.loads(shell('cat /dev/.mf79u-native-status.json'));gateway=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
assert not gateway['activeCall']
old_settings=shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')
old=shell(DATA+'/.mf79u-net-led --status');assert not json.loads(old)['demo']
sources={'led':candidate,'detach':BUILD/'detach-led'}
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path[1:] not in sources:self.send_error(404);return
  b=sources[self.path[1:]].read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass
ip=subprocess.check_output(['ipconfig','getifaddr','en10']).decode().strip();assert ip=='192.168.0.169'
server=http.server.ThreadingHTTPServer((ip,18089),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 for name,target in [('led',DATA+'/.mf79u-net-led.next'),('detach','/dev/.mf79u-detach-led')]:
  shell('set -e; '+DATA+'/tools/busybox wget -q -O '+target+' http://'+ip+':18089/'+name+'; chmod 700 '+target)
  assert shell('md5sum '+target).split()[0]==md5(sources[name])
 assert shell(DATA+'/.mf79u-net-led.next --selftest')=='LED policy selftest=0'
 assert shell('test /proc/'+str(pid)+'/exe -ef '+DATA+'/.mf79u-net-led && echo OWNED')=='OWNED'
 shell('kill -TERM '+str(pid))
 for _ in range(30):
  if shell('test -e /proc/'+str(pid)+'/exe && echo PRESENT')!='PRESENT':break
  time.sleep(.2)
 else:raise RuntimeError('Old LED cleanup did not finish')
 shell('set -e; mv '+DATA+'/.mf79u-net-led.next '+DATA+'/.mf79u-net-led; sync; /dev/.mf79u-detach-led')
 for _ in range(25):
  try:
   status=json.loads(shell(DATA+'/.mf79u-net-led --status'))
   if status.get('registered') and status.get('ims_registered') is False and status['color_mask']==3 and status['hardware_mask']==3 and not status['demo']:break
  except (ValueError,subprocess.SubprocessError):pass
  time.sleep(1)
 else:raise RuntimeError('Actual registered/no-IMS yellow state not observed')
 new=owned_leds();assert len(new)==1 and new[0]!=pid
 assert re.search(r'^PPid:\s*1\s*$',shell('cat /proc/'+str(new[0])+'/status'),re.M)
 assert shell('md5sum '+DATA+'/.mf79u-net-led').split()[0]==md5(candidate)
 assert json.loads(shell('cat /dev/.mf79u-native-status.json'))['pid']==native['pid']
 assert json.loads(shell('cat /dev/.mf79u-gateway-status.json'))['pid']==gateway['pid']
 assert shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')==old_settings
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'installed_md5':md5(candidate),'installed_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'before':json.loads(old),'after':status,'led_pid':new[0],'led_parent_init':True,'native_pid_unchanged':True,'sip_pid_unchanged':True,'settings_unchanged':True,'physical_arm_selftest_passed':True,'yellow_red_green_mask':3,'visual_color_confirmation_by_user':False,'full_image_updated':False}
 (BUILD/'yellow-led-live.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'after':status,'native_sip_settings_preserved':True,'led_parent_init':True}))
finally:server.shutdown();server.server_close();shell('rm -f /dev/.mf79u-detach-led')

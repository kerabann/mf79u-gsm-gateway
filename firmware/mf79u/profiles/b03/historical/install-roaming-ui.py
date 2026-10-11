from pathlib import Path
import hashlib,http.server,json,subprocess,threading,time
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1];ADB=[str(ROOT/'outputs/adb')];DATA='/mnt/userdata/mf79u';BUILD=BASE/'build'
def shell(command):
 return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=25).decode().replace('\r','').strip()
def md5(path): return hashlib.md5(path.read_bytes()).hexdigest()
backup=BUILD/'pre-roaming-sysinfo-20261008';old=backup/'mf79u-control'
if not old.exists():
 subprocess.run(ADB+['pull',DATA+'/.mf79u-control',str(old)],check=True,capture_output=True,timeout=30);old.chmod(0o700)
assert shell('md5sum '+DATA+'/.mf79u-control').split()[0]==md5(old)
old_settings=shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')
native=json.loads(shell('cat /dev/.mf79u-native-status.json'));assert not native['imsReady'] and native['sipPid']==0
pid=shell('cat /dev/.mf79u-control.pid');assert pid.isdigit() and int(pid)>1
assert shell('test /proc/'+pid+'/exe -ef '+DATA+'/.mf79u-control && echo OWNED')=='OWNED'
ip=subprocess.check_output(['ipconfig','getifaddr','en10']).decode().strip();assert ip=='192.168.0.169'
sources={'control':BUILD/'mf79u-control','detach':BUILD/'detach-control'}
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path[1:] not in sources:self.send_error(404);return
  b=sources[self.path[1:]].read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer((ip,18089),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 for name,target in [('control',DATA+'/.mf79u-control.roaming-next'),('detach','/dev/.mf79u-detach-control')]:
  shell('set -e; '+DATA+'/tools/busybox wget -q -O '+target+' http://'+ip+':18089/'+name+'; chmod 700 '+target)
  assert shell('md5sum '+target).split()[0]==md5(sources[name])
 assert shell('md5sum '+DATA+'/.mf79u-control').split()[0]==md5(old)
 shell('set -e; mv '+DATA+'/.mf79u-control.roaming-next '+DATA+'/.mf79u-control; sync; kill -TERM '+pid)
 for _ in range(40):
  if shell('test -e /proc/'+pid+'/exe && echo PRESENT')!='PRESENT' and shell('test -f /dev/.mf79u-control.pid && echo PRESENT')!='PRESENT':break
  time.sleep(.25)
 else:raise RuntimeError('Old control wrapper cleanup incomplete')
 shell('/dev/.mf79u-detach-control')
 for _ in range(30):
  new=shell('cat /dev/.mf79u-control.pid 2>/dev/null')
  if new.isdigit() and new!=pid and shell('test /proc/'+new+'/exe -ef '+DATA+'/.mf79u-control && echo OWNED')=='OWNED':break
  time.sleep(1)
 else:raise RuntimeError('New control did not start')
 assert shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')==old_settings
 assert shell('md5sum '+DATA+'/.mf79u-control').split()[0]==md5(sources['control'])
 current=json.loads(shell('cat /dev/.mf79u-native-status.json'));assert current['pid']==native['pid']
 report={'installed_md5':md5(sources['control']),'installed_sha256':hashlib.sha256(sources['control'].read_bytes()).hexdigest(),'settings_unchanged':True,'native_pid_unchanged':True,'ui_pid':int(new),'native_pid':current['pid'],'roaming_values_supported':['International','Internal','Home','1','0'],'unknown_value_is_not_home':True,'unregistered_is_not_home':True,'real_sim_registration_pending':True}
 (BUILD/'roaming-ui-live.json').write_text(json.dumps(report,indent=2)+'\n')
 print('UI installed and checksum verified; settings and native PID preserved; new control PID='+new)
finally:
 server.shutdown();server.server_close();shell('rm -f /dev/.mf79u-detach-control')

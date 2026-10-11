#!/usr/bin/env python3
"""Install the native System UI/tools with backups and atomic checksum-verified writes."""
import hashlib,http.server,json,subprocess,threading,time
from pathlib import Path
from ram_transfer import ram_push
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BUILD=HERE/'build';DATA='/mnt/userdata/mf79u';ADB=[str(ROOT/'outputs/adb'),'-s','123456789ABCDEF']
ARTIFACTS={'mf79u-control':DATA+'/.mf79u-control','busybox-extended':DATA+'/tools/busybox','dropbearmulti':DATA+'/tools/dropbearmulti','system-imei':DATA+'/tools/system-imei','ssh-shell.sh':DATA+'/tools/ssh-shell'}
def shell(cmd):return subprocess.check_output(ADB+['shell',cmd],stderr=subprocess.PIPE,timeout=30).decode().replace('\r','').strip()
def md5(path):return hashlib.md5(path.read_bytes()).hexdigest()
def status():return json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
def main():
 if status().get('activeCall') is not False:raise RuntimeError('An active call prevents installation')
 sources={n:(HERE/n if n.endswith('.sh') else BUILD/n) for n in ARTIFACTS}
 assert all(p.is_file() for p in sources.values())
 backup=BUILD/'pre-system-20261008';backup.mkdir(exist_ok=True)
 current=shell('md5sum '+DATA+'/.mf79u-control').split()[0]
 prior=json.loads((BUILD/'system-install-verification.json').read_text()) if (BUILD/'system-install-verification.json').exists() else {}
 if not (backup/'mf79u-control').exists():
  subprocess.run(ADB+['pull',DATA+'/.mf79u-control',str(backup/'mf79u-control')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 if md5(backup/'mf79u-control')!=current and current!=md5(sources['mf79u-control']) and current!=prior.get('installed',{}).get('mf79u-control',{}).get('md5'):raise RuntimeError('Current control binary changed; check backup before installation')
 manifest={'oldControlMD5':md5(backup/'mf79u-control'),'installed':{n:{'md5':md5(p),'bytes':p.stat().st_size} for n,p in sources.items()}}
 old_settings=shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini');old_sip=status()['pid'];ip=subprocess.check_output(['ipconfig','getifaddr','en10']).decode().strip();assert ip=='192.168.0.169'
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   name=self.path.removeprefix('/')
   if name not in sources:self.send_error(404);return
   b=sources[name].read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer((ip,18089),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  ram_push(ADB,BUILD/'ram-http-get','/dev/.mf79u-system-http-get');shell('mkdir -p '+DATA+'/tools '+DATA+'/ssh-home; chmod 700 '+DATA+'/tools '+DATA+'/ssh-home')
  pid=shell("cat /dev/.mf79u-control.pid");assert pid.isdigit() and int(pid)>1
  for name,target in ARTIFACTS.items():
   if name != "mf79u-control" and shell("md5sum "+target+" 2>/dev/null").split()[:1] == [md5(sources[name])]:
    print(name+" already current; kept.",flush=True);continue
   stage=target+'.system-next';result=shell('set -e; /dev/.mf79u-system-http-get '+ip+' '+name+' '+stage+'; md5sum '+stage)
   if result.split()[-2]!=md5(sources[name]):raise RuntimeError('Staged checksum mismatch')
   if status().get('activeCall') is not False:raise RuntimeError('A call began; installation postponed')
   shell('set -e; chmod 700 '+stage+'; mv '+stage+' '+target+'; sync')
   if shell('md5sum '+target).split()[0]!=md5(sources[name]):raise RuntimeError('Installed checksum mismatch')
   print(name+' installed and checked.',flush=True)
   if name=='mf79u-control':
    owned=shell('grep -F -q '+DATA+'/.mf79u-control /proc/'+pid+'/cmdline && echo OWNED');assert owned=='OWNED'
    shell('kill -TERM '+pid)
    for _ in range(30):
     if shell('test -e /proc/'+pid+'/exe && echo PRESENT')!='PRESENT':break
     time.sleep(.2)
    else:raise RuntimeError('Owned UI process did not stop')

  shell('set -e; ln -sf dropbearmulti '+DATA+'/tools/dropbear; ln -sf dropbearmulti '+DATA+'/tools/dropbearkey; mkdir -p '+DATA+'/tools/bin; '+DATA+'/tools/busybox --install -s '+DATA+'/tools/bin; ln -sf ../busybox '+DATA+'/tools/bin/busybox; touch '+DATA+'/control-internal-preferred; chmod 600 '+DATA+'/control-internal-preferred')
  # Start management only after every tool is verified. Voice was never stopped.
  subprocess.Popen(ADB+['shell','sh '+DATA+'/start-control.sh --no-bootstrap'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  for _ in range(30):
   new=shell('cat /dev/.mf79u-control.pid 2>/dev/null')
   if new.isdigit() and new!=pid and shell('test -e /proc/'+new+'/exe && echo PRESENT')=='PRESENT':break
   time.sleep(1)
  else:raise RuntimeError('New control process did not start')
  manifest.update({'settingsUnchanged':shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')==old_settings,'sipPIDUnchanged':status().get('pid')==old_sip,'imsReady':status().get('imsReady'),'uiPID':int(new),'sshInitiallyDisabled':shell('test -e '+DATA+'/ssh.json && echo EXISTS')!='EXISTS'})
  (BUILD/'system-install-verification.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({k:v for k,v in manifest.items() if k not in ('oldControlMD5','installed')},indent=2))
 finally:server.shutdown();server.server_close();shell('rm -f /dev/.mf79u-system-http-get')
if __name__=='__main__':main()

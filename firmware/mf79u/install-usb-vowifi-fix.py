#!/usr/bin/env python3
"""Install public Control/SIP candidates one at a time with bounded RAM staging."""
import argparse,gzip,hashlib,http.server,json,secrets,subprocess,threading,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];fw=root/'firmware/mf79u';build=fw/'build';base='/mnt/userdata/mf79u';bb=base+'/tools/busybox';adb=[str(root/'outputs/adb'),'-s','1234567890ABCDEF']
def sh(command):return subprocess.check_output(adb+['shell',command],timeout=45).decode().replace('\r','').strip()
def md5(data):return hashlib.md5(data).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--control-only',action='store_true');args=parser.parse_args()
status=json.loads(sh('cat /dev/.mf79u-native-status.json'));assert status['callBackend']=='none'
boot=sh('cat /proc/sys/kernel/random/boot_id');supervisor=int(sh('cat /dev/.mf79u-native-supervisor.pid'));control=int(sh('cat /dev/.mf79u-control.pid'))
assert 'start-native.sh' in sh(f'cat /proc/{supervisor}/cmdline');assert '.mf79u-control' in sh(bb+f' readlink /proc/{control}/exe')
if not args.control_only:
 sh(f'kill -TERM {supervisor}')
 for _ in range(100):
  if not sh(bb+f' readlink /proc/{supervisor}/exe'):break
  time.sleep(.3)
 assert not sh(bb+f' readlink /proc/{supervisor}/exe')
sh(f'kill -TERM {control}');time.sleep(2)
assert not sh(bb+f' readlink /proc/{control}/exe')
# Explicit public artifact names only. Never transfer settings or credentials.
sh('rm -f /dev/mf79u/usb-control* /dev/mf79u/usb-native /dev/mf79u/usb-media /dev/mf79u/usb-vowifi')
hashes={};peak=0
files=[('.mf79u-control','mf79u-control')] if args.control_only else [('.mf79u-sip-gateway','modem-sip-gateway'),('.mf79u-control','mf79u-control')]
for remote,local in files:
 data=(build/local).read_bytes();packed=gzip.compress(data);peak=max(peak,len(packed));token=secrets.token_hex(16)
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   if self.path!='/'+token:self.send_error(404);return
   self.send_response(200);self.send_header('Content-Length',str(len(packed)));self.end_headers();self.wfile.write(packed)
  def log_message(self,*args):pass
 server=http.server.HTTPServer(('192.168.0.169',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();stage='/dev/mf79u/usb-fix.gz'
 try:
  sh(bb+' wget -q -T 30 -O '+stage+' http://192.168.0.169:'+str(server.server_port)+'/'+token)
  assert sh('md5sum '+stage).split()[0]==md5(packed)
  # Expand directly into flash, never retain an uncompressed copy in RAM.
  sh('set -e; gzip -dc '+stage+' > '+base+'/'+remote+'.next; chmod 700 '+base+'/'+remote+'.next')
  assert sh('md5sum '+base+'/'+remote+'.next').split()[0]==md5(data)
  sh('mv '+base+'/'+remote+'.next '+base+'/'+remote);hashes[remote]=md5(data)
 finally:
  sh('rm -f '+stage);server.shutdown();server.server_close()
 print('Installed and verified '+local,flush=True)
sh(bb+' setsid sh '+base+'/start-control.sh --no-bootstrap </dev/null >/dev/null 2>&1 & sleep 3')
assert sh('cat /proc/sys/kernel/random/boot_id')==boot
assert sh('md5sum '+base+'/.mf79u-cs-voice.ko').split()[0]=='b3440aadf8e7be2e2321d13e539ba078'
(build/('vowifi-usb-control-boot-fix-install-20261011.json' if args.control_only else 'vowifi-usb-sip-config-fix-install-20261011.json')).write_text(json.dumps({'boot':boot,'artifacts':hashes,'maxCompressedStageBytes':peak,'uncompressedRAMStaging':False,'rootfsFlashed':False,'callsOrSMS':False},indent=2)+'\n')
print('Services restarted on the same boot; staging removed')

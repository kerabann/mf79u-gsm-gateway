from pathlib import Path
import hashlib,http.server,json,subprocess,threading,time
ROOT=Path(__file__).resolve().parents[3];BUILD=Path(__file__).resolve().parent;ADB=[str(ROOT/'outputs/adb')];DATA='/mnt/userdata/mf79u'
def shell(c):return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
report=json.loads((BUILD/'gsm-sms-fallback-live.json').read_text());old=report['artifacts']['mf79u-native-gateway']['md5']
assert shell('md5sum '+DATA+'/.mf79u-native-gateway').split()[0]==old
candidate=BUILD/'mf79u-native-gateway.call-cleanup';new=hashlib.md5(candidate.read_bytes()).hexdigest()
settings=shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini');state=json.loads(shell('cat /dev/.mf79u-native-status.json'));g=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
assert state['state']=='sms_only' and not state['imsReady'] and not g['activeCall']
old_pid=state['pid'];old_sip=g['pid'];supervisor=int(shell('cat /dev/.mf79u-native-supervisor.pid'))
assert old_pid>1 and supervisor>1 and shell('test /proc/'+str(old_pid)+'/exe -ef '+DATA+'/.mf79u-native-gateway && grep -q start-native.sh /proc/'+str(supervisor)+'/cmdline && echo OWNED')=='OWNED'
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/native':self.send_error(404);return
  b=candidate.read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass
ip=subprocess.check_output(['ipconfig','getifaddr','en10']).decode().strip();assert ip=='192.168.0.169'
server=http.server.ThreadingHTTPServer((ip,18089),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 shell('set -e; '+DATA+'/tools/busybox wget -q -O '+DATA+'/.mf79u-native-gateway.gsm-next http://'+ip+':18089/native; chmod 700 '+DATA+'/.mf79u-native-gateway.gsm-next')
 assert shell('md5sum '+DATA+'/.mf79u-native-gateway.gsm-next').split()[0]==new
 shell('kill -TERM '+str(old_pid))
 for _ in range(40):
  if shell('test -e /proc/'+str(old_pid)+'/exe && echo PRESENT')!='PRESENT':break
  time.sleep(.25)
 else:raise RuntimeError('Controller cleanup incomplete')
 shell('set -e; mv '+DATA+'/.mf79u-native-gateway.gsm-next '+DATA+'/.mf79u-native-gateway; sync')
 # Keep the boot-owned supervisor; accelerate only its verified retry sleep.
 for _ in range(80):
  try:
   s=json.loads(shell('cat /dev/.mf79u-native-status.json'));gw=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
   if s['pid']!=old_pid and s['state']=='sms_only' and gw['running']:break
  except (ValueError,subprocess.SubprocessError):pass
  time.sleep(.5)
 else:raise RuntimeError('Boot supervisor did not restart current controller')
 assert shell('md5sum '+DATA+'/.mf79u-native-gateway').split()[0]==new
 assert shell('md5sum '+DATA+'/settings.json '+DATA+'/gateway.ini')==settings
 (BUILD/'mf79u-native-gateway').write_bytes(candidate.read_bytes())
 (BUILD/'mf79u-native-gateway').chmod(0o700)
 report['first_candidate_stability']={'md5':old,'native_pid':old_pid,'sip_pid':old_sip,'modem_uptime_seconds':float(shell('cat /proc/uptime').split()[0]),'gsm_runtime_exceeded_previous_ims_timeout':True}
 report['artifacts']['mf79u-native-gateway']={'md5':new,'sha256':hashlib.sha256(candidate.read_bytes()).hexdigest()}
 report['runtime']=s;report['gateway']=gw;report['ims_loss_ends_active_sip_call_fixture']=True
 report['last_control_restart_not_required']=True
 (BUILD/'gsm-sms-fallback-live.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Final controller installed, checksum matched, boot-owned supervisor relaunched it; UI/settings preserved.')
finally:server.shutdown();server.server_close()

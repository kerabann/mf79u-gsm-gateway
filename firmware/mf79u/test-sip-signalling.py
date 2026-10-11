#!/usr/bin/env python3
"""Native SIP integration against an isolated USB-LAN fixture. No CP, SIM calls or raw SIP logs."""
import hashlib,json,os,re,selectors,socket,ssl,subprocess,tempfile,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADB=[str(ROOT/'outputs/adb')];HOST='192.168.0.169';MODEM='192.168.0.1'
def shell(cmd):return subprocess.run(ADB+['shell',cmd],capture_output=True,check=True,timeout=10).stdout

def run_case(transport,port,cert,key,ca,codecs=('OPUS','G722','PCMA','PCMU','G729'),reject_certificate=False):
 registered=threading.Event();invited=threading.Event();stop=threading.Event();report={'transport':transport};errors=[]
 def handle(msg,send):
  text=msg.decode(errors='replace');head,_,body=text.partition('\r\n\r\n');first=head.split('\r\n')[0]
  if first.startswith('ACK '):return
  headers={}
  for line in head.split('\r\n')[1:]:
   k,_,v=line.partition(':');headers.setdefault(k.lower(),[]).append(v.strip())
  def reply(code,extra=''):
   out='SIP/2.0 '+code+'\r\n'
   for k in ('via','from','to','call-id','cseq'):
    for v in headers.get(k,[]):out+=k+': '+v+(';tag=lab' if k=='to' and ';tag=' not in v else '')+'\r\n'
   send((out+extra+'Content-Length: 0\r\n\r\n').encode())
  if first.startswith('REGISTER '):
   auth=headers.get('authorization',[''])[0]
   if not auth:
    reply('401 Unauthorized','WWW-Authenticate: Digest realm="mf79u-lab", nonce="0123456789abcdef", algorithm=MD5\r\n');return
   params=dict(re.findall(r'(\w+)="([^"]*)"',auth));a1=hashlib.md5(b'account-test:mf79u-lab:lab-only').hexdigest();a2=hashlib.md5(('REGISTER:'+params.get('uri','')).encode()).hexdigest();expected=hashlib.md5((a1+':0123456789abcdef:'+a2).encode()).hexdigest()
   if params.get('username')!='account-test' or params.get('response')!=expected:raise ValueError('Digest authentication failed')
   reply('200 OK','Contact: '+headers.get('contact',[''])[0]+';expires=300\r\nExpires: 300\r\n');report['digest']=True;registered.set()
  elif first.startswith('INVITE '):
   report['callerFrom']=bool(re.search(r'sips?:\+123456789@',headers.get('from',[''])[0]));report['callerPAI']=bool(re.search(r'sips?:\+123456789@',headers.get('p-asserted-identity',[''])[0]))
   payloads=re.search(r'^m=audio \d+ RTP/AVP (.*)$',body,re.M)
   maps={pt:name.upper() for pt,name in re.findall(r'^a=rtpmap:(\d+) ([^/\r\n]+)/',body,re.M)}
   names=[maps.get(p,{'9':'G722','8':'PCMA','0':'PCMU','18':'G729'}.get(p,p)) for p in (payloads[1].strip().split() if payloads else [])];report['codecs']=[n for n in names if n in ('OPUS','G722','PCMA','PCMU','G729')]
   report['routeSelectedAddress']=bool(re.search(r'^c=IN IP4 '+re.escape(MODEM)+r'\r?$',body,re.M))
   reply('486 Busy Here');invited.set()
  else:reply('200 OK')
 def serve():
  s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM if transport=='UDP' else socket.SOCK_STREAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind((HOST,port));s.settimeout(.3)
  conn=None
  try:
   if transport!='UDP':
    s.listen(1)
    while not stop.is_set():
     try:conn,peer=s.accept();break
     except socket.timeout:continue
    if conn is None:return
    if peer[0]!=MODEM:raise ValueError('Unexpected fixture peer')
    if transport=='TLS':
     ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(cert,key);conn=ctx.wrap_socket(conn,server_side=True);report['tlsVersion']=conn.version()
    conn.settimeout(.3);buffer=b''
   while not stop.is_set():
    try:
     if transport=='UDP':
      msg,peer=s.recvfrom(65536)
      if peer[0]==MODEM:handle(msg,lambda b:s.sendto(b,peer))
     else:
      part=conn.recv(65536)
      if not part:break
      buffer+=part
      while b'\r\n\r\n' in buffer:
       h=buffer.index(b'\r\n\r\n')+4;m=re.search(br'(?im)^Content-Length:\s*(\d+)',buffer[:h]);size=h+(int(m[1]) if m else 0)
       if len(buffer)<size:break
       msg,buffer=buffer[:size],buffer[size:];handle(msg,conn.sendall)
    except socket.timeout:continue
  except Exception as e:errors.append(type(e).__name__+': '+str(e))
  finally:
   if conn:conn.close()
   s.close()
 thread=threading.Thread(target=serve,daemon=True);thread.start();time.sleep(.1)
 subprocess.run(ADB+['push','-Z',str(ca),'/mnt/userdata/mf79u/lab-ca.pem'],capture_output=True,check=True,timeout=10)
 config=f'server={HOST}\nport={port}\ntransport={transport}\nusername=account-test\npassword=lab-only\nrealm=mf79u-lab\nregister=1\nincoming_user=fixture\nlocal_port=15080\nbind=0.0.0.0\ntrusted_peers={HOST}\ncodecs={",".join(codecs)}\nca_file=/mnt/userdata/mf79u/lab-ca.pem\n'
 with tempfile.NamedTemporaryFile() as f:
  f.write(config.encode());f.flush();subprocess.run(ADB+['push','-Z',f.name,'/mnt/userdata/mf79u/lab.ini'],capture_output=True,check=True,timeout=10)
 shell('chmod 600 /mnt/userdata/mf79u/lab.ini')
 process=subprocess.Popen(ADB+['shell','/dev/.mf79u-sip-gateway --wideband --config /mnt/userdata/mf79u/lab.ini'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 try:
  if reject_certificate:
   selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ);buffer=b'';deadline=time.monotonic()+10
   try:
    while time.monotonic()<deadline and b'SIP_TLS_CERTIFICATE_REJECTED' not in buffer:
     for selected,_ in selector.select(.25):
      part=os.read(selected.fileobj.fileno(),4096)
      if part:buffer=(buffer+part)[-8192:]
      else:deadline=0;break
   finally:selector.close()
   if registered.is_set() or b'SIP_TLS_CERTIFICATE_REJECTED' not in buffer:raise RuntimeError('Untrusted TLS certificate rejection not confirmed')
   report['untrustedCertificateRejected']=True;print(json.dumps(report),flush=True);return report
  if not registered.wait(15):raise RuntimeError('Registration timed out '+str(errors))
  shell("printf '%s' '+123456789' > /dev/.mf79u-incoming-caller; chmod 600 /dev/.mf79u-incoming-caller")
  process.stdin.write(b'READY\nINCOMING\n');process.stdin.flush()
  if not invited.wait(10):raise RuntimeError('INVITE timed out '+str(errors))
  assert report['callerFrom'] and report['callerPAI'],report
  assert report['codecs']==list(codecs) and report['routeSelectedAddress'],report
  print(json.dumps(report),flush=True);return report
 finally:
  if process.poll() is None:
   try:process.communicate(b'QUIT\n',timeout=5)
   except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
  stop.set();thread.join(2)

with tempfile.TemporaryDirectory(prefix='mf79u-sip-lab-') as d:
 cert=Path(d)/'cert.pem';key=Path(d)/'key.pem'
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=MF79U fixture','-addext','subjectAltName=IP:'+HOST],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True);os.chmod(key,0o600)
 subprocess.run(ADB+['push','-Z',str(cert),'/mnt/userdata/mf79u/lab-ca.pem'],capture_output=True,check=True,timeout=10)
 try:
  reports=[run_case(t,15060+i,cert,key,cert) for i,t in enumerate(('UDP','TCP','TLS'))]
  reports.append(run_case('UDP',15063,cert,key,cert,('G729','PCMA')))
  untrusted=Path(d)/'untrusted.pem';untrusted_key=Path(d)/'untrusted.key'
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(untrusted_key),'-out',str(untrusted),'-days','1','-subj','/CN=Untrusted lab CA'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True);os.chmod(untrusted_key,0o600)
  reports.append(run_case('TLS',15064,cert,key,untrusted,reject_certificate=True))
  (ROOT/'firmware/mf79u/build/sip-signalling-native.json').write_text(json.dumps({'simCalls':False,'tests':reports},indent=2)+'\n')
 finally:shell('rm -f /mnt/userdata/mf79u/lab.ini /mnt/userdata/mf79u/lab-ca.pem /dev/.mf79u-incoming-caller')

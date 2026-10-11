#!/usr/bin/env python3
"""Read-only live SMS IPC/status proof; never emits message bodies/numbers/IDs."""
import datetime, hashlib, json, re, socket, struct, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ADB=[str(HERE.parents[1]/'outputs/adb')]
def shell(c):
 return subprocess.check_output(ADB+['shell',c],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def read(s,n):
 b=b''
 while len(b)<n:
  p=s.recv(n-len(b))
  if not p: raise RuntimeError('Short IPC reply')
  b+=p
 return b
def ipc(op,payload=b''):
 with socket.create_connection(('127.0.0.1',18191),3) as s:
  s.settimeout(3);s.sendall(b'MSM1'+bytes([op])+struct.pack('!I',len(payload))+payload)
  h=read(s,9);assert h[:4]==b'MSM1'
  n=struct.unpack('!I',h[5:])[0];assert n<4096
  return h[4],read(s,n)
subprocess.run(ADB+['forward','tcp:18191','localfilesystem:/mnt/userdata/mf79u/sms-sip.sock'],check=True,capture_output=True)
try:
 n=json.loads(shell('cat /dev/.mf79u-native-status.json'))
 g=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
 assert g['running'] and not g['activeCall']
 code,data=ipc(4);assert code==0
 d=json.loads(data);assert d['enabled'] and d['vendorReady'] and d['queued']==0
 # Retained transaction hashes only, used locally; never save or print IDs.
 ids=re.findall(r'"ID":"([a-f0-9]{32})"',shell("/mnt/userdata/mf79u/tools/busybox grep -o '\"ID\":\"[a-f0-9]*\"' /mnt/userdata/mf79u/sms-sip-state.json"))
 # Read only the Delivered hash array; never copy job fields or SMS text.
 delivered=shell(r"/mnt/userdata/mf79u/tools/busybox sed -n 's/.*\"Delivered\":\(\[[^]]*\]\).*/\1/p' /mnt/userdata/mf79u/sms-sip-state.json")
 delivered=json.loads(delivered or '[]')
 notices=sum(hashlib.sha256(('status:'+id).encode()).hexdigest()[:32] in delivered for id in ids)
 results=[]
 for id in ids:
  code,body=ipc(5,id.encode());assert not body and code in (0,5,6)
  results.append(code)
 unknown='0'*32
 if unknown not in ids: assert ipc(5,unknown.encode())==(2,b'')
 report={'verifiedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'imsReady':n['imsReady'],
         'sipRunning':g['running'],'localRegistered':g['localRegistered'],
         'smsVendorReady':d['vendorReady'],'queued':d['queued'], 'confirmedSubmissions':results.count(0),
         'uncertainSubmissions':results.count(6),'unknownNeverConfirmed':True,'serviceNoticesAcknowledged':notices,
         'smsSentByVerifier':False,'nativePid':n['pid'],'sipPid':g['pid']}
 (HERE/'build/sms-submission-status-live-20261011.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,sort_keys=True))
finally:
 subprocess.run(ADB+['forward','--remove','tcp:18191'],capture_output=True)

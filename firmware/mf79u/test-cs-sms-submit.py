#!/usr/bin/env python3
"""One authorized SMS through installed SIP MESSAGE + B03 CS worker. RAM inputs."""
import argparse,datetime,hashlib,importlib.util,json,re,socket,subprocess,sys,time,uuid
from pathlib import Path
BASE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--label',default='cs-sms-submit-live');args=p.parse_args()
assert re.fullmatch('[a-z0-9-]{1,48}',args.label)
receipt=BASE/'build'/(args.label+'.json');assert not receipt.exists(), 'Preserve previous SMS receipt'
number=sys.stdin.buffer.readline(34).strip()
assert re.fullmatch(rb'[0-9]{5,32}',number)
text=b'MF79U UMTS SMS test' if args.label.startswith('umts') else b'MF79U CS SMS test'
payload_hash=hashlib.sha256(number+b'\x00'+text).hexdigest()[:32]
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=json.loads(t.shell('cat /dev/.mf79u-native-status.json'));assert s['voiceBackend']=='cs' and not s['imsReady'] and s['csRegistration'] in (1,5) and s['epsRegistration'] not in (1,5)
before=json.loads(t.shell('cat /mnt/userdata/mf79u/sms-sip-state.json'));existing={j['ID'] for j in before.get('Jobs',[])};before.clear()
target=('192.168.0.1',5080);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.connect(target);host=sock.getsockname()[0];sock.settimeout(10)
id=uuid.uuid4().hex;port=sock.getsockname()[1]
data=(b'MESSAGE sip:'+number+b'@192.168.0.1:5080 SIP/2.0\r\n'+f'Via: SIP/2.0/UDP {host}:{port};branch=z9hG4bK{id};rport\r\nFrom: <sip:cs-sms-test@{host}>;tag={id[:12]}\r\nTo: <sip:'.encode()+number+b'@192.168.0.1:5080>\r\n'+f'Call-ID: {id}@cs-sms-test\r\nCSeq: 1 MESSAGE\r\nMax-Forwards: 70\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: {len(text)}\r\n\r\n'.encode()+text)
sock.send(data);response=sock.recv(8192);sock.close();code=int(response.split(b' ',2)[1]);data=response=b''
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'attempts':1,'destination_saved':False,'content_saved':False,'ims_ready':s['imsReady'],'eps_registration':s['epsRegistration'],'cs_registration':s['csRegistration'],'registration_mode':s.get('registrationMode'),'sip_response':code,'submission_state':'unconfirmed'}
if code==202:
 for _ in range(100):
  queue=json.loads(t.shell('cat /mnt/userdata/mf79u/sms-sip-state.json'))
  # Completed jobs erase Text. Hash retains the transaction's payload identity.
  jobs=[j for j in queue.get('Jobs',[]) if j['ID'] not in existing and j['Number']==number.decode() and j['Hash']==payload_hash]
  if len(jobs)==1 and jobs[0]['State'] not in ('queued','sending'):
   report['submission_state']=jobs[0]['State'];queue.clear();jobs.clear();break
  queue.clear();jobs.clear();time.sleep(.3)
number=text=b''
receipt.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert code==202 and report['submission_state']=='sent', 'No confirmed modem submission; do not retry automatically'

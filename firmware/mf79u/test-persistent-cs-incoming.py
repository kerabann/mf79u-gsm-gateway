#!/usr/bin/env python3
"""One supervised incoming SIM->SIP/PBX echo; restore only owned test route."""
import argparse,datetime,importlib.util,json,re,struct,subprocess,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='live');p.add_argument('--talk-seconds',type=int,default=22);args=p.parse_args()
assert re.fullmatch('[a-z0-9-]{1,40}',args.label)
assert 22<=args.talk_seconds<=90
receipt=BASE/'build'/('persistent-cs-incoming-'+args.label+'.json')
assert not receipt.exists(), 'Preserve previous incoming receipt; choose a new label'
context='SIP-TRUNK-51091984-incoming';extension='cs-echo-test'
def cli(command):return subprocess.check_output(['docker','exec','mf79u-mikopbx','asterisk','-rx',command],timeout=15).decode()
def state():return json.loads(t.shell('cat /dev/.mf79u-native-status.json'))
before=state();assert before['voiceBackend']=='cs' and before['callBackend']=='none'
assert not json.loads(t.shell('cat /dev/.mf79u-gateway-status.json'))['activeCall']
assert '1.' not in cli('dialplan show '+extension+'@'+context)
old=t.shell("grep '^incoming_user=' /mnt/userdata/mf79u/gateway.ini")
assert re.fullmatch('incoming_user=[A-Za-z0-9_.+~-]{1,64}',old)
boot=t.shell('cat /proc/sys/kernel/random/boot_id');report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'speech_saved':False,'caller_saved':False,'pbx_talk_seconds':args.talk_seconds,'before':before};owned=False;route=False;capture=None
def capture_events(data):
 events=[]
 if len(data)<24:return events
 endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';pos=24
 while pos+16<=len(data):
  _,_,n,_=struct.unpack(endian+'IIII',data[pos:pos+16]);pos+=16;p=data[pos:pos+n];pos+=n
  if len(p)<42 or p[12:14]!=b'\x08\x00' or p[23]!=17:continue
  start=14+4*(p[14]&15);body=p[start+8:]
  if not re.match(rb'(SIP/2\.0|INVITE |ACK |BYE |CANCEL )',body):continue
  method=body.split(b' ',1)[0].decode();entry={'method':method}
  if method=='SIP/2.0':entry['code']=int(body.split(b' ',2)[1])
  if method=='INVITE':entry['expected_target']=body.split(b' ',2)[1].startswith(b'sip:'+extension.encode()+b'@')
  events.append(entry)
 return events
try:
 for i,app in enumerate(('Answer()',f'Set(TIMEOUT(absolute)={args.talk_seconds})','PlayTones(700)','Wait(3)','StopPlayTones()','Echo()','Hangup()'),1):
  owned=True;cli('dialplan add extension '+extension+','+str(i)+','+app+' into '+context)
  assert re.search(r'\b'+str(i)+r'\.\s+'+re.escape(app),cli('dialplan show '+extension+'@'+context))
 log_before=t.shell('cat /dev/.mf79u-native.log')
 incoming_before=log_before.count('event=incoming_forwarded')
 reloads=log_before.count('event=sip_reloaded')
 t.shell("sed 's/^incoming_user=.*/incoming_user="+extension+"/' /mnt/userdata/mf79u/gateway.ini > /mnt/userdata/mf79u/gateway.incoming-next; chmod 600 /mnt/userdata/mf79u/gateway.incoming-next; mv /mnt/userdata/mf79u/gateway.incoming-next /mnt/userdata/mf79u/gateway.ini; kill -HUP "+str(before['sipPid']));route=True
 for _ in range(40):
  if t.shell('cat /dev/.mf79u-native.log').count('event=sip_reloaded')>reloads:break
  time.sleep(.2)
 else:raise RuntimeError('SIP configuration reload was not acknowledged; no incoming test')
 capture=subprocess.Popen(['docker','exec','mf79u-mikopbx','sh','-c','umask 077; echo $$ > /tmp/mf79u-cs-capture.pid; exec tcpdump -i eth0 -n -s 0 -U -w - udp port 5060'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 time.sleep(.5);subprocess.run(['afplay','/System/Library/Sounds/Glass.aiff'],check=True)
 print(f'READY: incoming CS -> installed SIP/PBX tone/echo; auto end{args.talk_seconds}s after answer.',flush=True)
 seen=False;connected=False;connected_at=None;deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  s=state()
  if s['pid']!=before['pid'] or s['sipPid']!=before['sipPid']:raise RuntimeError('Runtime restarted')
  driver=t.shell('cat /sys/mf79u_cs_voice/session').split()
  if s['callBackend']=='cs' or t.shell('cat /dev/.mf79u-native.log').count('event=incoming_forwarded')>incoming_before:seen=True
  if len(driver)==11 and driver[5]=='5':
   connected=True
   if connected_at is None:connected_at=time.monotonic()
  if seen and s['callBackend']=='none' and driver[5]=='0' and driver[6]=='0':break
  time.sleep(.3)
 else:raise RuntimeError('Incoming call/clearing deadline expired')
 report.update(incoming_seen=seen,connected_seen=connected,connected_seconds=round(time.monotonic()-connected_at,3) if connected_at else 0,after=state(),same_boot=t.shell('cat /proc/sys/kernel/random/boot_id')==boot)
 if not connected or report['connected_seconds']<17:raise RuntimeError('Incoming call ended before its echo duration; inspect receipt')
except BaseException as error:
 report.update(incoming_seen=locals().get('seen',False),connected_seen=locals().get('connected',False),failure=type(error).__name__,after=state(),same_boot=t.shell('cat /proc/sys/kernel/random/boot_id')==boot)
 raise
finally:
 if capture:
  subprocess.run(['docker','exec','mf79u-mikopbx','sh','-c','p=$(cat /tmp/mf79u-cs-capture.pid); test -n "$p" && test /proc/"$p"/exe -ef /usr/bin/tcpdump && kill -TERM "$p"; rm -f /tmp/mf79u-cs-capture.pid'],capture_output=True,check=True,timeout=10)
  data,_=capture.communicate(timeout=10);report['sip_packet_events']=capture_events(data);data=b'';report['packet_contents_saved']=False
 s=state()
 if s['callBackend']!='none':
  driver=t.shell('cat /sys/mf79u_cs_voice/session').split()
  if len(driver)==11 and driver[6]!='0':t.shell("printf 'HANGUP "+driver[2]+' '+driver[6]+"\\n' > /sys/mf79u_cs_voice/control")
 if route:
  t.shell("sed 's/^incoming_user=.*/"+old+"/' /mnt/userdata/mf79u/gateway.ini > /mnt/userdata/mf79u/gateway.incoming-next; chmod 600 /mnt/userdata/mf79u/gateway.incoming-next; mv /mnt/userdata/mf79u/gateway.incoming-next /mnt/userdata/mf79u/gateway.ini; kill -HUP "+str(before['sipPid']))
 if owned:cli('dialplan remove extension '+extension+'@'+context)
 report['incoming_route_restored']=t.shell("grep '^incoming_user=' /mnt/userdata/mf79u/gateway.ini")==old
 report['pbx_extension_removed']='1.' not in cli('dialplan show '+extension+'@'+context)
 receipt.write_text(json.dumps(report,indent=2)+'\n')
print('Incoming test finished; owned PBX extension and incoming route restored.',flush=True)

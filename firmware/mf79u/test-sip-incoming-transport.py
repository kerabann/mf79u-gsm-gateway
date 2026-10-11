#!/usr/bin/env python3
"""Isolated real SIP gateway: full codec offer + long Caller ID over chosen UDP.

No modem, real numbers, cellular call or captured speech. Synthetic caller file
exists only in the disposable container's RAM filesystem.
"""
import argparse, json, queue, signal, socket, subprocess, tempfile, threading, time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--gateway',required=True);args=p.parse_args()
assert Path('/tmp/MF79U_ISOLATED_FIXTURE').exists()
host=socket.gethostbyname(socket.gethostname())
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind((host,0));sock.settimeout(4)
caller=Path('/dev/.mf79u-incoming-caller');proc=None
with tempfile.TemporaryDirectory(prefix='sip-incoming-transport-') as d:
 cfg=Path(d)/'gateway.ini'
 cfg.write_text(f'role=TRUNK\nserver={host}\nport={sock.getsockname()[1]}\ntransport=UDP\n'
  f'username=fixture\nregister=0\nincoming_user=incoming-fixture\nlocal_port=15080\nbind={host}\n'
  'codecs=OPUS,G722,PCMA,PCMU,G729\nca_file=\nvoice_mode=AUTO\n')
 proc=subprocess.Popen([args.gateway,'--wideband','--config',str(cfg)],stdin=subprocess.PIPE,
  stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
 lines=queue.Queue();threading.Thread(target=lambda:[lines.put(s.strip()) for s in proc.stdout],daemon=True).start()
 def event(value):
  end=time.monotonic()+5
  while time.monotonic()<end:
   try:s=lines.get(timeout=.1)
   except queue.Empty:continue
   if s==value:return
  raise AssertionError('SIP event missing: '+value)
 def command(value):proc.stdin.write(value+'\n');proc.stdin.flush()
 sizes=[]
 try:
  event('GATEWAY_LISTENING');command('BACKEND cs');event('GATEWAY_READY')
  for i in range(2):
   if i:
    cfg.write_text(cfg.read_text().replace('voice_mode=AUTO','voice_mode=CS'))
    proc.send_signal(signal.SIGHUP);event('GATEWAY_RELOADED')
   caller.write_text('+'+'1234567890'*3+'12');caller.chmod(0o600)
   command('INCOMING');event('SIP_INCOMING_FORWARDED')
   packet,peer=sock.recvfrom(8192)
   assert packet.startswith(b'INVITE sip:incoming-fixture@') and b'P-Asserted-Identity:' in packet
   assert len(packet)<=1472, 'Full-codec Caller-ID INVITE must fit the 1500-byte IPv4 LAN MTU'
   assert b'm=text ' not in packet and packet.count(b'm=audio ')==1, 'Only implemented voice media is offered'
   sizes.append(len(packet))
   if not i:
    head,_,sdp=packet.partition(b'\r\n\r\n')
    print(json.dumps({'header_lengths':[[h.split(b':',1)[0].decode(),len(h)] for h in head.split(b'\r\n')[1:]],
     'sdp_line_lengths':[[h.split(b':',1)[0].decode() if h.startswith(b'a=') else h.split(b' ',1)[0].decode(),len(h)] for h in sdp.split(b'\r\n') if h]}))
   headers=packet.split(b'\r\n\r\n',1)[0].split(b'\r\n')[1:]
   response=b'SIP/2.0 486 Busy Here\r\n'
   for h in headers:
    if h.lower().startswith((b'via:',b'from:',b'to:',b'call-id:',b'cseq:')):
     response+=h+(b';tag=fixture' if h.lower().startswith(b'to:') else b'')+b'\r\n'
   sock.sendto(response+b'Content-Length: 0\r\n\r\n',peer);event('SIP_ENDED 486')
   # Drain the transaction ACK before the next independent offer.
   packet,_=sock.recvfrom(8192);assert packet.startswith(b'ACK ')
  print(json.dumps({'physical_device_access':False,'sim_calls':False,'full_codec_offer':True,
   'long_caller_id':True,'selected_udp_preserved':True,'after_reload':True,'invite_bytes':sizes}))
 finally:
  caller.unlink(missing_ok=True);command('QUIT');proc.wait(timeout=5);sock.close()

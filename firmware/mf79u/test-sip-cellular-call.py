#!/usr/bin/env python3
"""One authorized SIP -> installed cellular backend call, with RAM-only RTP.

Destination is read once from stdin. No SIP packets, identities or voice are
written to a file. No radio, settings, production process or PBX changes.
"""
from pathlib import Path
import argparse, datetime, importlib.util, json, math, re, select, socket, struct, subprocess, sys, time, uuid

BASE=Path(__file__).resolve().parent

def parse(data):
    text=data.decode('ascii',errors='replace');head,_,body=text.partition('\r\n\r\n')
    lines=head.split('\r\n');headers={}
    for line in lines[1:]:
        k,sep,v=line.partition(':')
        if sep:headers.setdefault(k.lower(),[]).append(v.strip())
    return lines[0],headers,body

def ulaw(value):
    sign=0x80 if value<0 else 0;value=min(abs(value),32635)+132
    exponent=max(0,value.bit_length()-8);mantissa=(value>>(exponent+3))&15
    return (~(sign|(exponent<<4)|mantissa))&255

def rtp_payload(data):
    if len(data)<12 or data[0]>>6!=2 or data[1]&127:return None
    offset=12+4*(data[0]&15)
    if len(data)<offset:return None
    if data[0]&16:
        if len(data)<offset+4:return None
        offset+=4+4*struct.unpack('!H',data[offset+2:offset+4])[0]
    end=len(data)
    if data[0]&32:
        padding=data[-1]
        if not padding or padding>end-offset:return None
        end-=padding
    return data[offset:end] if end-offset==160 else None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorized-single-dial',action='store_true')
    p.add_argument('--expect-backend',choices=('ims','cs'),required=True)
    p.add_argument('--label',required=True)
    p.add_argument('--talk-seconds',type=int,default=18)
    args=p.parse_args()
    if not 10<=args.talk_seconds<=90:p.error('Test duration must be between10 and90 seconds')
    if not args.authorized_single_dial:p.error('Single outgoing-call authorization required')
    if not re.fullmatch('[a-z0-9-]{1,48}',args.label):p.error('Invalid report label')
    number=sys.stdin.buffer.readline(34).strip()
    if not re.fullmatch(rb'[0-9]{5,32}',number):p.error('Numeric destination required on stdin')
    spec=importlib.util.spec_from_file_location('sip_call_radio',BASE/'test-cs-reattach.py')
    radio=importlib.util.module_from_spec(spec);spec.loader.exec_module(radio)
    def snapshot():
        native=radio.status();sip=json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json'))
        return {'boot':radio.shell('cat /proc/sys/kernel/random/boot_id'),
                'native':{k:native.get(k) for k in ('pid','sipPid','csPid','imsReady','ringOnly','csOnly','voiceBackend','voiceMode','callBackend')},
                'sip':{k:sip.get(k) for k in ('activeCall','voiceReady','codec','voiceBackend')}}
    before=snapshot()
    if before['sip']['activeCall'] or before['native']['ringOnly'] or (before['native']['csOnly'] and not (args.expect_backend=='cs' and before['native']['voiceMode'] == 'CS')):
        raise RuntimeError('Idle ordinary runtime required')
    if args.expect_backend=='ims' and not before['native']['imsReady']:raise RuntimeError('IMS is not ready')
    if args.expect_backend=='cs' and before['sip']['voiceBackend']!='cs':raise RuntimeError('CS is not ready')
    target=('192.168.0.1',5080)
    route=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);route.connect(target);host=route.getsockname()[0];route.close()
    sig=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sig.bind((host,0));sig.setblocking(False)
    media=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);media.bind((host,0));media.setblocking(False)
    port=sig.getsockname()[1];rtp_port=media.getsockname()[1]
    uid=uuid.uuid4().hex;call_id=uid+'@mf79u-lab';branch='z9hG4bK'+uid
    origin='<sip:cs-baseline@'+host+':'+str(port)+'>;tag='+uid[:12]
    request_uri='sip:'+number.decode()+'@'+target[0]+':'+str(target[1]);number=b''
    to='<'+request_uri+'>';remote_uri=request_uri;connected_at=None;bye_at=None;bye_ok=False;peer=None
    report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,
            'expected_backend':args.expect_backend,'attempted_calls':0,'destination_saved':False,'audio_saved':False,
            'radio_or_configuration_changed':False,'talk_seconds':args.talk_seconds,
            'events':[],'rtp_received':0,'rtp_sent':0}
    path=BASE/'build'/('sip-cellular-'+args.label+'.json')
    if path.exists():raise RuntimeError('Refusing to overwrite previous call receipt')
    def save():path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
    def event(name,**fields):report['events'].append({'elapsed':round(time.monotonic()-started,3),'event':name,**fields});save()
    def request(method,cseq,body='',initial=False):
        uri=request_uri if initial else remote_uri
        b=branch if method in ('INVITE','CANCEL') else branch+'-'+method
        data=(method+' '+uri+' SIP/2.0\r\nVia: SIP/2.0/UDP '+host+':'+str(port)+';branch='+b+';rport\r\n'
              'Max-Forwards: 70\r\nFrom: '+origin+'\r\nTo: '+to+'\r\nCall-ID: '+call_id+'\r\nCSeq: '+str(cseq)+' '+method+'\r\n'
              'Contact: <sip:cs-baseline@'+host+':'+str(port)+'>\r\n'+('Content-Type: application/sdp\r\n' if body else '')+
              'Content-Length: '+str(len(body.encode()))+'\r\n\r\n'+body)
        sig.sendto(data.encode(),target)
    def response(headers):
        data='SIP/2.0 200 OK\r\n'
        for key in ('via','from','to','call-id','cseq'):
            for value in headers.get(key,[]):data+=key+': '+value+'\r\n'
        sig.sendto((data+'Content-Length: 0\r\n\r\n').encode(),target)
    sdp=('v=0\r\no=mf79u 1 1 IN IP4 '+host+'\r\ns=MF79U baseline\r\nc=IN IP4 '+host+'\r\nt=0 0\r\n'
         'm=audio '+str(rtp_port)+' RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\na=ptime:20\r\na=sendrecv\r\n')
    started=time.monotonic();next_frame=0;sequence=0;timestamp=0;ssrc=int(uid[:8],16);echo=b'\xff'*160;echo_time=0
    next_bye=0;remote_ended=False;rejected=False
    save()
    try:
        subprocess.run(['afplay','/System/Library/Sounds/Glass.aiff'],stdin=subprocess.DEVNULL,check=True,timeout=10)
        request('INVITE',1,sdp,True);report['attempted_calls']=1;event('invite_sent')
        print(f'DIALING: one SIP/cellular call; three-second tone, echo, SIP BYE at{args.talk_seconds}s.',flush=True)
        while time.monotonic()-started<130:
            now=time.monotonic()
            if connected_at and now-connected_at>=95:break
            if rejected:break
            if bye_ok and bye_at and now-bye_at>2 and radio.status().get("callBackend","none")=="none":break
            if not connected_at and now-started>=30:
                request('CANCEL',1);event('invite_cancelled');break
            if connected_at and bye_at is None and now-connected_at>=args.talk_seconds:
                request('BYE',2);bye_at=now;next_bye=now+1;event('bye_sent',connected_seconds=round(now-connected_at,3))
            if bye_at and not bye_ok and now>=next_bye and now-bye_at<8:
                request('BYE',2);next_bye=now+1
            for sock in select.select([sig,media],[],[],.005)[0]:
                data,address=sock.recvfrom(8192)
                if address[0]!=target[0]:continue
                if sock is media:
                    payload=rtp_payload(data)
                    if payload is not None and peer==address:
                        echo=payload;echo_time=now;report['rtp_received']+=1
                    continue
                if address!=target:continue
                first,headers,body=parse(data)
                if headers.get('call-id')!=[call_id]:continue
                cseq=headers.get('cseq',[''])[0]
                if first.startswith('SIP/2.0 '):
                    code=int(first.split()[1])
                    if cseq=='1 INVITE' and code==200:
                        to=headers['to'][0]
                        contact=re.search(r'<(sip:[^>]+)>',headers.get('contact',[''])[0])
                        first_answer=connected_at is None
                        if first_answer:connected_at=now
                        if not contact or not re.fullmatch(r'sip:[^@<>\s]+@192\.168\.0\.1(?::5080)?(?:;transport=UDP)?',contact[1],re.I):
                            request('ACK',1)
                            raise RuntimeError('Unexpected dialog target')
                        remote_uri=contact[1];request('ACK',1)
                        if first_answer:
                            ip=re.search(r'^c=IN IP4 ([0-9.]+)\r?$',body,re.M);audio=re.search(r'^m=audio (\d+) RTP/AVP ([0-9 ]+)\r?$',body,re.M)
                            if not ip or ip[1]!=target[0] or not audio or '0' not in audio[2].split() or not 1024<=int(audio[1])<=65535:
                                raise RuntimeError('Expected local PCMU media answer')
                            peer=(target[0],int(audio[1]));connected_at=now;next_frame=now;event('connected');print(f'CONNECTED: tone then echo; hangup deadline{args.talk_seconds}s.',flush=True)
                    elif cseq=='1 INVITE' and code>=300:
                        to=headers.get('to',[to])[0];request('ACK',1);event('invite_rejected',status=code);rejected=True;break
                    elif cseq=='2 BYE' and code==200 and not bye_ok:bye_ok=True;event('bye_acknowledged')
                elif first.startswith('BYE '):
                    response(headers);event('remote_bye');remote_ended=True;bye_ok=True;break
                elif first.startswith('OPTIONS '):response(headers)
            if connected_at and bye_at is None and not remote_ended and peer and now>=next_frame:
                elapsed=now-connected_at
                payload=bytes(ulaw(round(6000*math.sin(2*math.pi*700*(timestamp+i)/8000))) for i in range(160)) if elapsed<3 else echo if now-echo_time<.2 else b'\xff'*160
                media.sendto(struct.pack('!BBHII',0x80,0,sequence&65535,timestamp&0xffffffff,ssrc)+payload,peer)
                sequence+=1;timestamp+=160;report['rtp_sent']+=1;next_frame=max(next_frame+.02,now)
    finally:
        if connected_at and bye_at is None and not remote_ended:
            request('BYE',2);event('cleanup_bye_sent')
        # Allow the installed controller to process the dialog teardown before
        # reading its status; this never sends a global or unrelated hangup.
        cleanup_deadline=time.monotonic()+10
        while time.monotonic()<cleanup_deadline:
            if not json.loads(radio.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):break
            time.sleep(.25)
        report['connected']=connected_at is not None;report['sip_bye_acknowledged']=bye_ok
        report['after']=snapshot();report['same_boot']=report['after']['boot']==before['boot']
        report['same_production_pids']=all(report['after']['native'][k]==before['native'][k] for k in ('pid','sipPid','csPid'))
        report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        echo=b'';request_uri=remote_uri=to='';sig.close();media.close();save()
    completed_duration=any(e['event']=='bye_sent' and e.get('connected_seconds',0)>=args.talk_seconds for e in report['events'])
    report['completed_test_duration']=completed_duration;save()
    if not report['connected'] or not completed_duration or report['rtp_received']<args.talk_seconds*35 or not bye_ok or report['after']['sip']['activeCall'] or not report['same_boot']:
        raise RuntimeError('Call or cleanup not verified; inspect sanitized receipt')
    print('FINISHED: SIP dialog cleared; production runtime unchanged. Handset timing requires user report.',flush=True)

if __name__=='__main__':main()

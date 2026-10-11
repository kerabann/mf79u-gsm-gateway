#!/usr/bin/env python3
"""Isolated real SIP/RTP <-> PCM2 test with a synthetic cellular peer.

Runs only in the disposable build container. No modem, CP, SIM, saved
credentials or captured speech. This verifies the software media contract;
it cannot establish that the physical GSM audio port works.
"""
import argparse
import audioop
import json
import math
from pathlib import Path
import queue
import re
import socket
import struct
import subprocess
import tempfile
import threading
import time


def signal_frame(rate, frequency, amplitude=8000):
    return struct.pack('<'+'h'*(rate//50), *(
        round(amplitude*math.sin(2*math.pi*frequency*i/rate))
        for i in range(rate//50)))


def energy_at(samples, rate, frequency):
    """Phase-independent fraction of energy in a prescribed synthetic tone."""
    if not samples:
        return 0.0
    total=sum(v*v for v in samples)
    if not total:
        return 0.0
    real=sum(v*math.cos(2*math.pi*frequency*i/rate) for i,v in enumerate(samples))
    imag=sum(v*math.sin(2*math.pi*frequency*i/rate) for i,v in enumerate(samples))
    return 2*(real*real+imag*imag)/(len(samples)*total)


def header(data, name):
    m=re.search(r'(?im)^'+re.escape(name)+r':\s*([^\r\n]+)',data)
    if not m:
        raise AssertionError('Missing SIP header '+name)
    return m.group(1)


def run_case(binary, codec, direction):
    host=socket.gethostbyname(socket.gethostname())
    payload_type=0 if codec=='PCMU' else 8
    encode=audioop.lin2ulaw if codec=='PCMU' else audioop.lin2alaw
    decode=audioop.ulaw2lin if codec=='PCMU' else audioop.alaw2lin
    sip=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    rtp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    pcm=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sip.bind((host,0));sip.settimeout(.2)
    rtp.bind((host,0));rtp.setblocking(False)
    pcm.bind(('127.0.0.1',46001));pcm.setblocking(False)
    process=None
    with tempfile.TemporaryDirectory(prefix='mf79u-cs-media-') as temporary:
        config=Path(temporary)/'gateway.ini'
        config.write_text(f'role=TRUNK\nserver={host}\nport={sip.getsockname()[1]}\n'
            f'transport=UDP\nusername=fixture\npassword=\nrealm=*\nregister=0\n'
            f'incoming_user=fixture\nlocal_port=15080\nbind={host}\n'
            f'trusted_peers={host}\ncodecs={codec}\nca_file=\n')
        lines=queue.Queue()
        process=subprocess.Popen([binary,'--wideband','--config',str(config)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,bufsize=1)
        threading.Thread(target=lambda:[lines.put(s.rstrip()) for s in process.stdout],daemon=True).start()

        def command(value):
            process.stdin.write(value+'\n');process.stdin.flush()

        def expect(prefix, seconds=6):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if process.poll() is not None:
                    raise AssertionError('Gateway exited '+str(process.returncode))
                try:
                    value=lines.get(timeout=.1)
                    if value.startswith(prefix):
                        return value
                except queue.Empty:
                    pass
            raise AssertionError('Gateway event timeout: '+prefix)

        def request(method,cseq,to,body='',call_id=None):
            call_id=call_id or 'cs-media-'+codec
            uri=f'sip:1234567@{host}:15080'
            return (f'{method} {uri} SIP/2.0\r\n'
                f'Via: SIP/2.0/UDP {host}:{sip.getsockname()[1]};branch=z9hG4bK-cs-{codec}-{cseq}-{method};rport\r\n'
                f'Max-Forwards: 70\r\nFrom: <sip:fixture@{host}>;tag=fixture\r\n'
                f'To: {to}\r\nCall-ID: {call_id}\r\nCSeq: {cseq} {method}\r\n'
                f'Contact: <sip:fixture@{host}:{sip.getsockname()[1]}>\r\n'
                + ('Content-Type: application/sdp\r\n' if body else '')
                + f'Content-Length: {len(body.encode())}\r\n\r\n'+body).encode()

        def final_response(method,seconds=6):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                try:
                    data,_=sip.recvfrom(65535)
                except socket.timeout:
                    continue
                text=data.decode(errors='replace')
                m=re.match(r'SIP/2.0 (\d{3})',text)
                if m and int(m[1])>=200 and header(text,'CSeq').endswith(method):
                    return int(m[1]),text
            raise AssertionError('SIP final response timeout')

        def received_request(method,seconds=6):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                try:
                    data,peer=sip.recvfrom(65535)
                except socket.timeout:
                    continue
                text=data.decode(errors='replace')
                if text.startswith(method+' '):
                    return text,peer
            raise AssertionError('SIP request timeout: '+method)

        def reply(text,peer,body=''):
            result='SIP/2.0 200 OK\r\n'
            for name in ('Via','From','To','Call-ID','CSeq'):
                value=header(text,name)
                if name=='To' and ';tag=' not in value:
                    value+=';tag=fixture'
                result+=name+': '+value+'\r\n'
            result+=f'Contact: <sip:fixture@{host}:{sip.getsockname()[1]}>\r\n'
            if body:
                result+='Content-Type: application/sdp\r\n'
            result+=f'Content-Length: {len(body.encode())}\r\n\r\n'+body
            sip.sendto(result.encode(),peer)

        try:
            expect('GATEWAY_LISTENING');command('BACKEND cs');expect('GATEWAY_READY')
            sdp=(f'v=0\r\no=fixture 1 1 IN IP4 {host}\r\ns=synthetic\r\nc=IN IP4 {host}\r\n'
                f't=0 0\r\nm=audio {rtp.getsockname()[1]} RTP/AVP {payload_type}\r\n'
                f'a=rtpmap:{payload_type} {codec}/8000\r\na=sendrecv\r\n')
            to=f'<sip:1234567@{host}>'
            target=(host,15080)
            if direction=='sip_to_cs':
                sip.sendto(request('INVITE',1,to,sdp),target)
                expect('DIAL ');command('ALERT');command('CONNECTED')
                code,offer=final_response('INVITE')
                assert code==200,code
                to=header(offer,'To')
                sip.sendto(request('ACK',1,to),target)
                expect('SIP_MEDIA_CONNECTED')
            else:
                command('INCOMING')
                offer,peer=received_request('INVITE')
                assert 'Privacy: id' in offer or 'Privacy:  id' in offer,'Anonymous caller privacy missing'
                reply(offer,peer,sdp)
                expect('SIP_MEDIA_CONNECTED');expect('ANSWER')
            m=re.search(r'(?m)^m=audio (\d+) RTP/AVP',offer)
            address=re.search(r'(?m)^c=IN IP4 ([^\r\n]+)',offer)
            assert m and address,'No RTP endpoint in answer'
            media_peer=(address[1],int(m[1]))
            incoming_rtp=encode(signal_frame(8000,1000),2)
            cellular_pcm=b'PCM2'+signal_frame(16000,500)
            frames=rtp_count=pcm_count=0
            rtp_samples=[];pcm_samples=[]
            end=time.monotonic()+2.5;next_frame=time.monotonic()
            while time.monotonic()<end:
                now=time.monotonic()
                if now>=next_frame:
                    rtp.sendto(struct.pack('!BBHII',0x80,payload_type,frames&65535,
                        frames*160,0x12345678)+incoming_rtp,media_peer)
                    pcm.sendto(cellular_pcm,('127.0.0.1',46000))
                    frames+=1;next_frame+=.02
                for sock in (pcm,rtp):
                    for _ in range(32):
                        try:
                            data,_=sock.recvfrom(4096)
                        except BlockingIOError:
                            break
                        if sock is pcm:
                            assert len(data)==644 and data[:4]==b'PCM2','PCM contract changed'
                            pcm_count+=1
                            if any(data[4:]):
                                pcm_samples.extend(struct.unpack('<320h',data[4:]))
                        elif len(data)>=12 and data[0]>>6==2 and data[1]&127==payload_type:
                            start=12+4*(data[0]&15)
                            if data[0]&16:
                                start+=4+4*struct.unpack_from('!H',data,start+2)[0]
                            length=len(data)-(data[-1] if data[0]&32 else 0)
                            decoded=decode(data[start:length],2)
                            rtp_count+=1
                            if any(decoded):
                                rtp_samples.extend(struct.unpack('<'+'h'*(len(decoded)//2),decoded))
                time.sleep(.001)
            receive_energy=energy_at(pcm_samples[-16000:],16000,1000)
            send_energy=energy_at(rtp_samples[-8000:],8000,500)
            assert pcm_count>=60 and rtp_count>=60,'Insufficient duplex frames'
            assert receive_energy>.6 and send_energy>.6,(receive_energy,send_energy)
            status=json.loads(Path('/dev/.mf79u-gateway-status.json').read_text())
            assert status['voiceBackend']=='cs' and status['voiceReady'] and not status['imsReady']
            assert status['activeCall'] and status['codec']==codec
            if direction=='sip_to_cs':
                sip.sendto(request('BYE',2,to),target)
                assert final_response('BYE')[0]==200
            else:
                command('ENDED')
                bye,peer=received_request('BYE')
                reply(bye,peer)
            expect('SIP_ENDED ')
            command('BACKEND none')
            end=time.monotonic()+3
            while time.monotonic()<end:
                if json.loads(Path('/dev/.mf79u-gateway-status.json').read_text()).get('voiceBackend')=='none':
                    break
                time.sleep(.02)
            else:
                raise AssertionError('Backend did not become unavailable')
            # A new dialog gets a new Call-ID; an ended dialog cannot be
            # reused as a registration-independent readiness probe.
            sip.sendto(request('INVITE',3,f'<sip:1234567@{host}>',sdp,'cs-unavailable-'+codec),target)
            assert final_response('INVITE')[0]==503,'Unavailable CS accepted a new call'
            return {'codec':codec,'direction':direction,'backend':'cs','ims_ready':False,'rtp_frames':rtp_count,
                'pcm_frames':pcm_count,'pcm_rate':16000,'pcm_samples':320,'pcm_frame_bytes':640,'udp_packet_bytes':644,
                'rtp_to_pcm_tone_energy':round(receive_energy,4),
                'pcm_to_rtp_tone_energy':round(send_energy,4),
                'duplex_media_verified':True,'unavailable_backend_rejected':True}
        finally:
            if process.poll() is None:
                try:
                    command('QUIT');process.wait(timeout=8)
                except (BrokenPipeError,subprocess.TimeoutExpired):
                    process.kill();process.wait()
            for sock in (sip,rtp,pcm):
                sock.close()


def main():
    if not Path('/tmp/MF79U_ISOLATED_FIXTURE').exists():
        raise SystemExit('Disposable isolated build container required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway',required=True)
    args=parser.parse_args()
    cases=[run_case(args.gateway,codec,direction) for codec in ('PCMU','PCMA')
        for direction in ('sip_to_cs','cs_to_sip')]
    report={'isolated_fixture':True,'physical_modem_access':False,'sim_calls':False,
        'physical_cs_audio_verified':False,'pcm_contract_unchanged':True,'cases':cases}
    Path('firmware/mf79u/build/sip-cs-media-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()

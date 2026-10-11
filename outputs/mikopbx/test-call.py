#!/usr/bin/env python3
"""One authorized PBX→SIM test with synthetic tones and a 45s watchdog.
No recordings. Never hangs up channels that predate this test.
"""
import io
import math
import struct
import subprocess
import time
import wave
import json
from pathlib import Path
directory=Path(__file__).resolve().parent
connection=json.loads((directory/'connection.json').read_text())
provider=connection['provider_id']
def cli(command):
    return subprocess.check_output(['docker','exec','mf79u-mikopbx','asterisk','-rx',command],timeout=8).decode()
def channels():
    return {line.split('!')[0] for line in cli('core show channels concise').splitlines() if '!' in line}
before=channels()
if before:raise RuntimeError('Existing PBX channels: test skipped')
spool_line=next(line for line in cli('core show settings').splitlines() if 'Spool directory:' in line)
spool=spool_line.split(':',1)[1].strip()
if spool!='/storage/usbdisk1/mikopbx/astspool':raise RuntimeError('Unexpected PBX spool directory')
output=io.BytesIO()
with wave.open(output,'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000)
    data=[]
    for i in range(8000*18):
        on=(i//4000)%2==0
        value=int(6000*math.sin(2*math.pi*700*i/8000)) if on else 0
        data.append(struct.pack('<h',value))
    w.writeframes(b''.join(data))
subprocess.run(['docker','exec','-i','mf79u-mikopbx','sh','-c',
                'cat > /tmp/mf79u-test-tone.wav'],input=output.getvalue(),check=True)
started=time.monotonic();seen=False;owned=set()
try:
    # MikoPBX does not ship the res_clioriginate CLI module. Use Asterisk's
    # standard atomic call-file submission; never retry this call.
    call_file=('Channel: PJSIP/TEST_DESTINATION_LOCAL@'+provider+'\nMaxRetries: 0\n'
               'WaitTime: 25\nCallerid: MF79U lab <201>\n'
               'Application: Playback\nData: /tmp/mf79u-test-tone\nArchive: no\n')
    subprocess.run(['docker','exec','-i','mf79u-mikopbx','sh','-c',
        'test ! -e /storage/usbdisk1/mikopbx/astspool/outgoing/mf79u-lab-test.call && '
        'cat > /tmp/mf79u-lab-test.call && chmod 600 /tmp/mf79u-lab-test.call && '
        'mv /tmp/mf79u-lab-test.call /storage/usbdisk1/mikopbx/astspool/outgoing/mf79u-lab-test.call'],
        input=call_file.encode(),check=True)
    print('One authorized test initiated from MikoPBX; 45 second watchdog',flush=True)
    while time.monotonic()-started<45:
        current=channels();created=current-before
        owned|={name for name in created if name.startswith('PJSIP/'+provider+'-')}
        seen|=bool(owned)
        if seen and not (owned & current):break
        time.sleep(.5)
finally:
    current=channels()
    for name in owned & current:cli('channel request hangup '+name)
    subprocess.run(['docker','exec','mf79u-mikopbx','rm','-f','/tmp/mf79u-test-tone.wav'],check=True)
    report={'attempted_calls':1,'pbx_channel_created':seen,'duration_s':round(time.monotonic()-started,2),
            'remaining_owned_channels':len(owned & channels()),'audio_recorded':False}
    (directory/'call-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)

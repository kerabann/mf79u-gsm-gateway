#!/usr/bin/env python3
"""Arm one user-initiated SIM call, record its receive audio, restore routing.
No outbound dialing. Answer + synthetic beep, up to 45s of recording.
"""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import wave
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
CONTAINER='mf79u-mikopbx'
PROVIDER=json.loads((HERE/'connection.json').read_text())['provider_id']
stamp=datetime.datetime.now(ZoneInfo('Asia/Nicosia')).strftime('%Y%m%d-%H%M%S')
name='mf79u-incoming-'+stamp
REMOTE_DIR='/storage/usbdisk1/mikopbx/media/mf79u-quality'
wideband='--wideband' in sys.argv
suffix='.wav16' if wideband else '.wav'
receive=REMOTE_DIR+'/'+name+'-receive'+suffix
mixed=REMOTE_DIR+'/'+name+'-mixed'+suffix
local=HERE/'recordings'/name
local.mkdir(parents=True,mode=0o700);os.chmod(local,0o700)
stopping=False

def signal_stop(signum,frame):
    global stopping
    stopping=True
signal.signal(signal.SIGINT,signal_stop);signal.signal(signal.SIGTERM,signal_stop)

def cli(command):
    return subprocess.check_output(['docker','exec',CONTAINER,'asterisk','-rx',command],timeout=10).decode()

def api(path,data=None,method=None):
    cmd=['docker','exec','-i',CONTAINER,'curl','-sS','--max-time','40',
         'http://127.0.0.1/pbxcore/api/v3/'+path]
    if method is not None:cmd+=['-X',method]
    elif data is not None:cmd+=['-X','POST']
    if data is not None:cmd+=['-H','Content-Type: application/json','--data-binary','@-']
    result=json.loads(subprocess.check_output(cmd,input=json.dumps(data).encode() if data is not None else None,timeout=45))
    if not result.get('result'):raise RuntimeError(path+': '+str(result.get('messages')))
    return result['data']

def channels():
    return [line.split('!')[0] for line in cli('core show channels concise').splitlines() if '!' in line]

route=None;application=None;owned=set();seen=False;armed=False;collected=[]
try:
    if channels():raise RuntimeError('Existing PBX channels; did not arm recording')
    routes=api('incoming-routes')
    route=next(item for item in routes if item['providerid']==PROVIDER and item['rulename']=='MF79U SIM')
    route=api('incoming-routes/'+str(route['id']))
    if any(item['extension']=='880' for item in api('dialplan-applications')):
        raise RuntimeError('Extension 880 is occupied; did not overwrite it')
    subprocess.run(['docker','exec',CONTAINER,'mkdir','-p',REMOTE_DIR],check=True)
    subprocess.run(['docker','exec',CONTAINER,'chmod','700',REMOTE_DIR],check=True)
    logic='\n'.join([
        '1,GotoIf($["${DB(MF79UQuality/armed)}" != "'+name+'"]?12)',
        '2,Set(DB(MF79UQuality/armed)=0)',
        '3,Answer()',
        '4,Wait(2)',
        '5,PlayTones(900)',
        '6,Wait(0.25)',
        '7,StopPlayTones()',
        '8,MixMonitor('+mixed+',r('+receive+')i(MF79U_RECORDING))',
        '9,Wait(45)',
        '10,StopMixMonitor(${MF79U_RECORDING})',
        '11,Hangup()',
        '12,Hangup()'])
    application=api('dialplan-applications',{'extension':'880','name':'MF79U one-call quality recording',
        'type':'plaintext','applicationlogic':logic,'description':'Temporary user-requested test; auto-answer, beep, receive WAV, 45s limit'})
    (local/'dialplan.txt').write_text(logic+'\n')
    cli('database put MF79UQuality armed '+name)
    api('incoming-routes/'+str(route['id']),{'extension':'880'},'PATCH');armed=True
    for _ in range(60):
        text=cli('dialplan show SIP-TRUNK-51091984-incoming')
        test=cli('dialplan show 880@internal')
        if 'Local/880@internal' in text and ('MF79UQuality' in test or application['id'] in test):break
        time.sleep(.5)
    else:raise RuntimeError('Recording dialplan has not been generated')
    (HERE/'recording-ready.json').write_text(json.dumps({'armed':True,'session':name,
       'max_record_seconds':45,'local_directory':str(local),'host_pid':os.getpid()},indent=2)+'\n')
    print(json.dumps({'event':'RECORDING_READY','session':name,'max_record_seconds':45}),flush=True)
    start=time.monotonic();last_notice=start;seen_at=None
    while not stopping:
        elapsed=time.monotonic()-(seen_at if seen_at is not None else start)
        if elapsed>=(60 if seen_at is not None else 600):break
        current=set(channels())
        owned|={channel for channel in current if channel.startswith('PJSIP/'+PROVIDER+'-')}
        if owned and not seen:
            seen=True;seen_at=time.monotonic();print(json.dumps({'event':'INCOMING_PBX_CHANNEL'}),flush=True)
        if seen and not (current & owned):break
        if time.monotonic()-last_notice>=30:
            print(json.dumps({'event':'WAITING_FOR_USER_CALL' if not seen else 'RECORDING_ACTIVE'}),flush=True)
            last_notice=time.monotonic()
        time.sleep(.5)
finally:
    if armed and route:
        current=api('incoming-routes/'+str(route['id']))
        if current['extension']=='880':api('incoming-routes/'+str(route['id']),{'extension':route['extension']},'PATCH')
    cli('database del MF79UQuality armed')
    for channel in owned & set(channels()):cli('channel request hangup '+channel)
    time.sleep(1)
    for remote in [receive,mixed]:
        filename=local/(Path(remote).stem+'.wav')
        result=subprocess.run(['docker','cp',CONTAINER+':'+remote,str(filename)],capture_output=True)
        if result.returncode==0:
            os.chmod(filename,0o600);collected.append(str(filename))
    if application:api('dialplan-applications/'+application['id'],method='DELETE')
    report={'incoming_channel_seen':seen,'recording_files':collected,
            'route_restored':armed,'session':name,'max_record_seconds':45,'outbound_calls':0}
    for filename in collected:
        with wave.open(filename,'rb') as recording:
            report.setdefault('wav',[]).append({'path':filename,'sample_rate':recording.getframerate(),
                'channels':recording.getnchannels(),'sample_width':recording.getsampwidth(),
                'duration_s':recording.getnframes()/recording.getframerate()})
    (local/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    (HERE/'recording-ready.json').write_text(json.dumps({'armed':False,'session':name,'result':str(local/'result.json')},indent=2)+'\n')
    print(json.dumps({'event':'RECORDING_FINISHED',**report}),flush=True)

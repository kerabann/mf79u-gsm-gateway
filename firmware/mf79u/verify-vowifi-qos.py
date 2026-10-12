"""Read-only VoWiFi readiness and fixed B03 QoS scalars; no calls or changes."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import time

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--wait',type=int,default=0)
parser.add_argument('--require-ready',action='store_true')
parser.add_argument('--output',default='reports/vowifi-qos-live.json')
args=parser.parse_args()
target=(ROOT/args.output).resolve()
if target.parent!=ROOT/'reports' or target.suffix!='.json' or not 0<=args.wait<=300:
    raise SystemExit('Use an ignored reports/*.json file and a wait of 0..300 seconds')
adb=[os.environ.get('ADB','adb')]
def shell(command):
    result=subprocess.run(adb+['shell',command],capture_output=True,timeout=12)
    if result.returncode:raise RuntimeError('Read-only device query failed; raw output omitted')
    return result.stdout.decode(errors='replace').replace('\r','').strip()
fields=('pid','sipPid','csPid','state','imsReady','voiceReady','voiceMode','effectiveVoiceMode',
        'imsAccess','vowifiUplink','vowifiTunnelReady','registrationState','fallbackReason','callBackend',
        'ringOnly','csOnly','csRegistration','csSignalingReady','csAudioReady')
def state():
    raw=json.loads(shell('cat /dev/.mf79u-native-status.json'))
    return {k:raw[k] for k in fields if k in raw}
start=time.monotonic();last=None
while True:
    native=state()
    if native.get('voiceReady') or time.monotonic()-start>=args.wait:break
    key=(native.get('registrationState'),native.get('fallbackReason'))
    if key!=last:print(json.dumps({'waiting':key}),flush=True);last=key
    time.sleep(2)
gateway=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
out={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'readOnly':True,'realCallsSmsMade':False,
     'boot':shell('cat /proc/sys/kernel/random/boot_id'),'native':native,
     'sip':{k:gateway[k] for k in ('pid','localRegistered','activeCall','voiceReady','role') if k in gateway}}
out['installedMD5']={name:shell('md5sum /mnt/userdata/mf79u/'+name).split()[0] for name in
    ('.mf79u-native-gateway','.mf79u-volte-private','.mf79u-ims-userspace-ipsec.so','.mf79u-sip-gateway')}
owned=[]
for line in shell('for p in /proc/[0-9]*/comm; do c=$(cat "$p"); case "$c" in .mf79u-volte-pr) echo "$p";; esac; done').splitlines():
    match=re.fullmatch(r'/proc/(\d+)/comm',line)
    if not match:continue
    pid=int(match[1]);raw=shell('cat /proc/'+str(pid)+'/status')
    parent=re.search(r'^PPid:\s*(\d+)',raw,re.M)
    if parent and int(parent[1])==native['pid']:owned.append(pid)
if len(owned)==1:
    pid=owned[0]
    assert shell('/mnt/userdata/mf79u/tools/busybox readlink /proc/'+str(pid)+'/exe')=='/mnt/userdata/mf79u/.mf79u-volte-private'
    checksum=shell('/mnt/userdata/mf79u/tools/busybox sha256sum /proc/'+str(pid)+'/exe').split()[0]
    assert checksum==json.loads((BASE/'profiles/b03/private-ims-patch.json').read_text())['result_sha256']
    values={}
    for name,at in (('preconditionsEnabled',0xc5e98),('normalAccountBearerReady',0xc6f1c),
                    ('emergencyAccountBearerReady',0xc6fe4),('qosTimerCallback',0xc6e10),('qosTimerHeapIndex',0xc6e14)):
        value=shell('/mnt/userdata/mf79u/tools/busybox dd if=/proc/'+str(pid)+'/mem bs=1 skip='+str(at)+' count=4 2>/dev/null | /mnt/userdata/mf79u/tools/busybox od -An -tu4')
        if not re.fullmatch(r'\d+',value):raise RuntimeError('Fixed scalar read unavailable')
        values[name]=int(value)
    out['qosScalars']=values
    out['privateImsPid']=pid
log=shell('cat /dev/.mf79u-native.log')
out['safeEvents']=[line for line in log.splitlines() if re.fullmatch(
    r'NATIVE_GATEWAY elapsed=\d+ event=[a-z_]+|VOWIFI_MANAGER_EXIT code=-?\d+ signal=\d+|VOWIFI_ATTEMPT_ENDED tunnel=\d+ registered=\d+ ims=\d+|IMS_SIP_RESPONSE code=\d+ bytes=\d+|IMS_SIP_METHOD direction=(TX|RX) method=[A-Z]+ bytes=\d+',line)][-65:]
out['nativePidStable']=state().get('pid')==native['pid']
target.write_text(json.dumps(out,indent=2)+'\n');target.chmod(0o600)
print(json.dumps(out,indent=2))
if args.require_ready:
    assert native.get('imsReady') and native.get('voiceReady') and native.get('vowifiTunnelReady')
    assert out.get('qosScalars',{}).get('normalAccountBearerReady')==1 and out['nativePidStable']

#!/usr/bin/env python3
"""Start one RAM-only isolated IMS instance, retaining its ADB connection."""
import json
import re
from pathlib import Path
import subprocess
import sys
import time
from ram_transfer import ram_push
root=Path(__file__).resolve().parents[2]
adb=[str(root/'outputs/adb'),'-s','123456789ABCDEF']
build=root/'firmware/mf79u/build'
def shell(text):
    return subprocess.run(adb+['shell',text],check=True,capture_output=True,timeout=8).stdout
ps=shell('ps').decode()
if any(x.split()[-1:] in [['/dev/.mf79u-volte-private'],['/bin/zte_volte_main']] for x in ps.splitlines()):
    raise RuntimeError('An IMS test daemon is already running')
before=shell('cat /proc/sysvipc/msg')
old={int(x.split()[1]) for x in before.decode().splitlines()[1:] if x.split()}
if any(int(x.split()[0]) in (0x701e,0x700f,5181,-2130378751)
       for x in before.decode().splitlines()[1:] if x.split()):
    raise RuntimeError('Old IMS resources remain; clean inventoried queues before restart')
for local,remote in [('volte-private-ipc','volte-private'),('volte-ipc-probe','volte-probe'),('ipc-cleanup','ipc-cleanup')]:
    ram_push(adb,build/local,'/dev/.mf79u-'+remote)
    shell('chmod 755 /dev/.mf79u-'+remote)
observe='--observe-sip' in sys.argv
userspace_ipsec='--userspace-ipsec' in sys.argv
software_media='--software-media' in sys.argv
network_media='--network-media' in sys.argv
prefer_high_amr='--prefer-high-amr' in sys.argv
adaptive_audio='--adaptive-audio' in sys.argv
legacy_codecs='--legacy-operator-codecs' in sys.argv
if network_media and not software_media:raise RuntimeError('Network PCM requires software media')
if software_media and not userspace_ipsec:raise RuntimeError('Software media requires userspace IMS transport')
if prefer_high_amr and not software_media:raise RuntimeError('AMR rate preference requires software media')
if adaptive_audio and not network_media:raise RuntimeError('Adaptive audio requires network media')
command='/dev/.mf79u-volte-private </dev/null >/dev/null 2>&1'
output=subprocess.DEVNULL
if observe or userspace_ipsec:
    library='ims-userspace-ipsec' if userspace_ipsec else 'ims-sip-observer'
    ram_push(adb,build/(library+'.so'),'/dev/.mf79u-'+library+'.so')
    command='LD_PRELOAD=/dev/.mf79u-'+library+'.so /dev/.mf79u-volte-private 3>&1 </dev/null >/dev/null 2>&1'
    if software_media:command='MF79U_SOFTWARE_MEDIA=1 '+command
    if network_media:command='MF79U_PCM_NETWORK=1 '+command
    if prefer_high_amr:command='MF79U_AMR_PREFER_HIGH=1 '+command
    if adaptive_audio:
        preferred='auto'
        if '--operator-codec' in sys.argv:
            preferred=sys.argv[sys.argv.index('--operator-codec')+1]
        if preferred not in ('auto','amr-nb'):raise RuntimeError('Invalid operator codec preference')
        command=('MF79U_OPERATOR_CODECS=1 MF79U_OPERATOR_CODEC='+preferred+' ' if not legacy_codecs else '')+'MF79U_PCM_WIDEBAND=1 '+command
    output=(build/'ims-sip-metadata.log').open('wb')
process=subprocess.Popen(adb+['shell',command],
                         stdin=subprocess.DEVNULL,stdout=output,
                         stderr=subprocess.DEVNULL,start_new_session=True)
if observe or userspace_ipsec:output.close()
time.sleep(1)
if process.poll() is not None:
    raise RuntimeError('Native IMS startup failed')
after=shell('cat /proc/sysvipc/msg').decode().splitlines()[1:]
created=[x.split() for x in after if x.split() and int(x.split()[1]) not in old]
if not any(int(x[0])==0x701e for x in created):
    raise RuntimeError('Private IMS queue has not appeared')
pids=[int(x.split()[0]) for x in shell('ps').decode().splitlines()
      if x.split()[-1:]==['/dev/.mf79u-volte-private']]
if len(pids)!=1:raise RuntimeError('Expected one private native process after launch')
(build/'ims-queues-before.txt').write_bytes(before)
(build/'ims-created-queues.json').write_text(json.dumps(created,indent=2)+'\n')
report={'host_adb_pid':process.pid,'native_pid':pids[0],
        'flash_written':False,'sip_metadata_observer':observe,'userspace_ipsec':userspace_ipsec,
        'software_media':software_media,'network_pcm':network_media,
        'prefer_high_amr':prefer_high_amr,
        'adaptive_audio':adaptive_audio,
        'uptime':shell('cat /proc/uptime').decode().strip(),
        'created_queue_ids':[int(x[1]) for x in created]}
(build/'private-ims-launch.json').write_text(json.dumps(report,indent=2)+'\n')
if adaptive_audio and not legacy_codecs:
    metadata=(build/'ims-sip-metadata.log').read_text(errors='replace')
    report['operator_codecs']=bool(re.search(r'OPERATOR WB/NB factory enabled result=1\b',metadata))
    (build/'private-ims-launch.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['operator_codecs']:
        shell('kill '+str(pids[0]))
        raise RuntimeError('Verified operator codec factory was not installed')
print(json.dumps(report,indent=2))

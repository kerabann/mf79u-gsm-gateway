#!/usr/bin/env python3
"""Stop our RAM-only daemon and remove only its inventoried IPC resources."""
import json
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import time
root=Path(__file__).resolve().parents[2]
adb=[str(root/'outputs/adb'),'-s','123456789ABCDEF']
def shell(text):
    return subprocess.run(adb+['shell',text],check=True,capture_output=True,timeout=8).stdout.decode(errors='replace')
lines=shell('ps').splitlines()
if len(sys.argv)==3 and sys.argv[1]=='--cleanup-only':
    pid=int(sys.argv[2])
    if pid<2 or any(line.split()[0:1]==[str(pid)] for line in lines):
        raise RuntimeError('Cleanup requires the inventoried test process to be absent')
else:
    if sys.argv[1:] not in ([],['--terminate-only']):raise RuntimeError('Unexpected arguments')
    pids=[int(line.split()[0]) for line in lines if line.split()[-1:] == ['/dev/.mf79u-volte-private']]
    if len(pids)!=1:
        raise RuntimeError('Expected exactly one test daemon, found '+str(pids))
    pid=pids[0]
    listing=re.sub(r'\x1b\[[0-9;]*m','',shell('ls -l /proc/'+str(pid)+'/exe'))
    exe=listing.strip().partition(' -> ')[2]
    if exe not in ('/dev/.mf79u-volte-private','/mnt/userdata/mf79u/.mf79u-volte-private'):
        raise RuntimeError('Process identity changed')
    expected=hashlib.md5((root/'firmware/mf79u/build/volte-private-ipc').read_bytes()).hexdigest()
    actual=shell('md5sum /proc/'+str(pid)+'/exe').split()[0]
    if actual != expected:
        raise RuntimeError('Running private IMS executable differs from the verified build')
    shell('kill -15 '+str(pid))
    # A fatal-signal observer may leave our process in a group stop. SIGTERM
    # is already pending; resume it so normal termination can complete.
    state=shell('cat /proc/'+str(pid)+'/status 2>/dev/null')
    if re.search(r'^State:\s*T',state,re.M):
        shell('kill -18 '+str(pid))
    print('Stopped test PID '+str(pid),flush=True)
    for attempt in range(30):
        if not any(line.split()[0:1]==[str(pid)] for line in shell('ps').splitlines()):break
        time.sleep(.1)
    else:raise RuntimeError('Test daemon has not stopped; queues preserved')
    if '--terminate-only' in sys.argv:sys.exit(0)
queues=json.loads((root/'firmware/mf79u/build/ims-created-queues.json').read_text())
for row in queues:
    key,qid,stamp=int(row[0]),int(row[1]),int(row[13])
    # The transient response queue is owned by the probe, which cleans itself.
    if key==0x700f:
        continue
    result=shell('/dev/.mf79u-ipc-cleanup '+str(qid)+' '+str(key)+' '+str(stamp)+' '+str(pid)+'; echo CLEANUP_EXIT=$?')
    print(result.strip())
    if 'CLEANUP_EXIT=0' not in result:
        raise RuntimeError('Queue cleanup was refused; do not restart the daemon')
print('RAM test daemon stopped and inventoried queues cleaned')

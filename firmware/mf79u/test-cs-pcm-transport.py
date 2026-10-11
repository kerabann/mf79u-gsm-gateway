#!/usr/bin/env python3
"""RAM-only synthetic PCM transport test on exact B03; never touches CP/radio."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,subprocess
from ram_transfer import ram_push
from b03_kernel_relocations import audit_module
BASE=Path(__file__).resolve().parent;BUILD=BASE/'build';ADB=[str(BASE.parents[1]/'outputs/adb')]
def shell(c):return subprocess.check_output(ADB+['shell',c],stdin=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def snapshot():
 s=json.loads(shell('cat /dev/.mf79u-native-status.json'));g=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
 return {'boot':shell('cat /proc/sys/kernel/random/boot_id'),'native':{k:s.get(k) for k in ('pid','imsReady','ringOnly','csOnly','csRegistration','epsRegistration')},'sip':{k:g.get(k) for k in ('pid','activeCall')}}
name='mf79u_pcm_loop';remote='/dev/.mf79u-pcm-loop.ko';exe='/dev/.mf79u-pcm-transport-test';local=BUILD/(name+'.ko')
if shell('uname -r')!='3.4.110-rt140' or shell('md5sum /mnt/imagefs/ap_cpuap.bin').split()[0]!='4a29280dfa9e0c522de9e38091ea2533':raise RuntimeError('Unexpected kernel')
if any(x.startswith(name+' ') for x in shell('cat /proc/modules').splitlines()) or shell('test -e /sys/mf79u_pcm_probe && echo PRESENT')=='PRESENT':raise RuntimeError('Test already owned')
before=snapshot()
if not before['native']['imsReady'] or before['sip']['activeCall']:raise RuntimeError('Idle IMS runtime required')
build=json.loads((BUILD/'cs-pcm-loop-probe-build.json').read_text())
if not build.get('pcm_stream_loop') or build['sha256']!=hashlib.sha256(local.read_bytes()).hexdigest() or not audit_module(local)['safe']:raise RuntimeError('Build identity mismatch')
for n,h in build['source_headers_sha256'].items():
 if hashlib.sha256((BASE/'src'/n).read_bytes()).hexdigest()!=h:raise RuntimeError('Header changed')
r={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'module_sha256':build['sha256'],'test_sha256':hashlib.sha256((BUILD/'cs-pcm-transport-selftest-arm').read_bytes()).hexdigest(),'no_calls':True,'no_cp_io':True}
loaded=False
try:
 ram_push(ADB,local,remote);ram_push(ADB,BUILD/'cs-pcm-transport-selftest-arm',exe)
 shell('chmod 600 '+remote+'; chmod 700 '+exe)
 if 'OK' not in shell('insmod '+remote+' && echo OK'):raise RuntimeError('Module load failed')
 loaded=True
 r['result']=json.loads(shell(exe))
 if not r['result'].get('passed'):raise RuntimeError('Binary transport failed')
finally:
 if loaded:
  shell('rmmod '+name)
  r['unloaded']=not any(x.startswith(name+' ') for x in shell('cat /proc/modules').splitlines())
  r['object_removed']=shell('test -e /sys/mf79u_pcm_probe && echo PRESENT')!='PRESENT'
  r['log']=shell('/mnt/userdata/mf79u/tools/busybox dmesg | grep -E "MF79U_CS_PCM(_LOOP)? " | tail -n 4').splitlines()
 shell('rm -f '+remote+' '+exe)
 r['after']=snapshot();r['runtime_unchanged']=before==r['after']
 r['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (BUILD/'cs-pcm-transport-live.json').write_text(json.dumps(r,indent=2)+'\n')
if not all(r.get(k) for k in ('unloaded','object_removed','runtime_unchanged')):raise RuntimeError('Restoration failed')
print(json.dumps(r))

#!/usr/bin/env python3
"""One-shot guarded CS-only test install; expects pre-cs-only backup and staged ARM binary."""
from pathlib import Path
import subprocess,hashlib,json,time,datetime
base=Path(__file__).resolve().parents[2];build=base/'firmware/mf79u/build';data='/mnt/userdata/mf79u';adb=[str(base/'outputs/adb')]
def shell(c):return subprocess.check_output(adb+['shell',c],stderr=subprocess.PIPE,timeout=25).decode().replace('\r','').strip()
def state():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
old=state();assert old['ringOnly'];pid=int(old['pid']);assert pid>1
assert not json.loads(shell('cat /dev/.mf79u-gateway-status.json'))['activeCall']
assert shell(f'test /proc/{pid}/exe -ef {data}/.mf79u-native-gateway && echo OWNED')=='OWNED'
backup=build/'pre-cs-only-20261008/mf79u-native-gateway'
assert shell(f'md5sum {data}/.mf79u-native-gateway').split()[0]==hashlib.md5(backup.read_bytes()).hexdigest()
settings=shell(f'md5sum {data}/settings.json {data}/gateway.ini')
new=build/'mf79u-native-gateway';expected=hashlib.md5(new.read_bytes()).hexdigest()
assert shell('md5sum /dev/.mf79u-native-cs-next').split()[0]==expected
shell(f'set -e; cp /dev/.mf79u-native-cs-next {data}/.mf79u-native-gateway.cs-next; chmod 700 {data}/.mf79u-native-gateway.cs-next; umask 077; echo 1 > {data}/native-cs-only; chmod 600 {data}/native-cs-only; sync')
assert shell(f'md5sum {data}/.mf79u-native-gateway.cs-next').split()[0]==expected
shell(f'kill -TERM {pid}')
for _ in range(50):
 if shell(f'test -e /proc/{pid}/exe && echo PRESENT')!='PRESENT':break
 time.sleep(.2)
else:raise RuntimeError('Native cleanup timeout; staged binary untouched')
shell(f'set -e; mv {data}/.mf79u-native-gateway.cs-next {data}/.mf79u-native-gateway; sync')
print('Native CS-only candidate installed; waiting for existing supervisor.',flush=True)
for _ in range(50):
 r=state()
 if r.get('pid')!=pid and r.get('csOnly') and r.get('smsOnly') and r.get('sipPid',0)>1 and not r.get('imsReady'):break
 time.sleep(1)
else:raise RuntimeError('CS-only startup not verified; keep guard and inspect')
assert shell(f'md5sum {data}/settings.json {data}/gateway.ini')==settings
assert shell(f'md5sum {data}/.mf79u-native-gateway').split()[0]==expected
assert r['ringOnly']
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime':r,'old_pid':pid,'sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'md5':expected,'settings_preserved':True,'real_reboot':False,'gsm_audio_implemented':False,'answer_or_dial_issued':False}
(build/'cs-only-install-live.json').write_text(json.dumps(report,indent=2)+'\n')
shell('rm -f /dev/.mf79u-native-cs-next')
print(json.dumps(r),flush=True)

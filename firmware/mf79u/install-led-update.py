#!/usr/bin/env python3
"""Replace only the owned userdata LED service, with a checked binary backup."""
import base64,datetime,gzip,hashlib,importlib.util,json,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;B=BASE/'build';DATA='/mnt/userdata/mf79u'
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
remote=DATA+'/.mf79u-net-led';new=B/'mf79u-net-led'
oldhash=t.shell('md5sum '+remote).split()[0]
backup=B/('pre-led-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(mode=0o700)
old=backup/'mf79u-net-led'
old.write_bytes(gzip.decompress(base64.b64decode(t.shell(DATA+'/tools/busybox gzip -c '+remote+' | '+DATA+'/tools/busybox base64'))));old.chmod(0o700)
assert hashlib.md5(old.read_bytes()).hexdigest()==oldhash
stage=B/'led-update.gz';stage.write_bytes(gzip.compress(new.read_bytes(),9,mtime=0));t.push(stage,'/dev/.mf79u-led-update.gz')
pid=int(t.shell('for p in /proc/[0-9]*/exe; do if [ "$p" -ef '+remote+' ]; then echo "$p"; fi; done').split('/')[2])
assert pid>1
t.shell(f'kill -TERM {pid}')
for _ in range(50):
    if t.shell(f'test -e /proc/{pid}/exe && echo YES')!='YES':break
    time.sleep(.2)
else:raise RuntimeError('LED cleanup did not finish')
digest=hashlib.md5(new.read_bytes()).hexdigest()
t.shell(f'set -e; rm -f {remote}; {DATA}/tools/busybox gzip -dc /dev/.mf79u-led-update.gz > {remote}; chmod 700 {remote}; rm /dev/.mf79u-led-update.gz')
assert t.shell('md5sum '+remote).split()[0]==digest
assert 'LED policy selftest=0' in t.shell(remote+' --selftest')
# No host relay. The background device-local process is reparented to init.
t.push(B/'detach-led','/dev/.mf79u-detach-led')
t.shell('chmod 700 /dev/.mf79u-detach-led; /dev/.mf79u-detach-led; rm /dev/.mf79u-detach-led')
time.sleep(3)
status=json.loads(t.shell(remote+' --status'))
(B/'led-gsm-lte-install.json').write_text(json.dumps({'installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup':str(backup),'previous_md5':oldhash,'installed_md5':digest,'status':status,'raw_flash':False},indent=2)+'\n')
print('LED installed, policy selftest passed; status '+json.dumps(status))

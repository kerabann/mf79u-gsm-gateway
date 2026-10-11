#!/usr/bin/env python3
"""Guarded userdata registration/CS upgrade; no settings, raw flash or secrets."""
from pathlib import Path
import argparse,base64,datetime,gzip,hashlib,importlib.util,json,shlex,subprocess,time
BASE=Path(__file__).resolve().parent;B=BASE/'build';DATA='/mnt/userdata/mf79u'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--reboot-new-driver',action='store_true',help='Install a checked new pinned-driver revision and software reboot; never unload it live')
args=p.parse_args()
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
def digest(p):return hashlib.md5(p.read_bytes()).hexdigest()
def wait_exit(pid):
 for _ in range(150):
  if t.shell('test -e /proc/'+str(pid)+'/exe && echo YES')!='YES':return
  time.sleep(.2)
 raise RuntimeError('Owned process still running')
state=json.loads(t.shell('cat /dev/.mf79u-native-status.json'))
gateway=json.loads(t.shell('cat /dev/.mf79u-gateway-status.json'))
assert not gateway['activeCall'] and state.get('callBackend','none')=='none'
boot=t.shell('cat /proc/sys/kernel/random/boot_id')
files={'.mf79u-native-gateway':B/'mf79u-native-gateway',
 '.mf79u-sip-gateway':B/'modem-sip-gateway', '.mf79u-cs-voice':B/'mf79u-cs-voice',
 '.mf79u-cs-pcm-bridge':B/'mf79u-cs-pcm-bridge','.mf79u-cs-voice.ko':B/'mf79u_cs_voice.ko',
 'start-native.sh':BASE/'start-native.sh'}
loaded=t.shell('test -d /sys/module/mf79u_cs_voice && echo YES')=='YES'
if loaded:
 loaded_digest=t.shell('cat /dev/.mf79u-cs-driver.md5')
 assert loaded_digest==t.shell('md5sum '+DATA+'/.mf79u-cs-voice.ko').split()[0], 'Loaded driver does not match the installed checked module'
 assert loaded_digest==digest(files['.mf79u-cs-voice.ko']) or args.reboot_new_driver, 'New pinned driver needs --reboot-new-driver; no service/file changes made'
backup=B/('pre-registration-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(mode=0o700)
original={}
changed=set()
for name,p in files.items():
 if not p.is_file():raise RuntimeError('Missing runtime artifact')
 remote=DATA+'/'+name
 old=t.shell('test -f '+shlex.quote(remote)+' && md5sum '+shlex.quote(remote))
 if old:
  saved=backup/name.lstrip('.')
  encoded=t.shell(DATA+'/tools/busybox gzip -c '+shlex.quote(remote)+' | '+DATA+'/tools/busybox base64')
  saved.write_bytes(gzip.decompress(base64.b64decode(encoded)));encoded=''
  saved.chmod(0o700);assert digest(saved)==old.split()[0];original[name]=digest(saved)
 if old and old.split()[0]==digest(p):continue
 changed.add(name)
 packed=B/('registration-stage-'+name.lstrip('.')+'.gz');packed.write_bytes(gzip.compress(p.read_bytes(),9,mtime=0))
 t.push(packed,'/dev/'+packed.name)
native=int(state['pid']);supervisor=int(t.shell('cat /dev/.mf79u-native-supervisor.pid'))
assert native>1 and supervisor>1
assert t.shell(f'test /proc/{native}/exe -ef {DATA}/.mf79u-native-gateway && grep -q start-native.sh /proc/{supervisor}/cmdline && echo OWNED')=='OWNED'
t.shell(f'kill -TERM {supervisor}; kill -TERM {native}')
wait_exit(native);wait_exit(supervisor)
assert t.shell('test -e /proc/'+str(gateway['pid'])+'/exe && echo YES')!='YES'
if loaded:
 session=t.shell('cat /sys/mf79u_cs_voice/session').split()
 assert session[:2]==['MF79U_CS_DRIVER','1'] and len(session)==11
 assert list(map(int,session[3:8]))==[0,0,0,0,0] and session[9:] == ['1','0'], 'Old driver must be idle, suspended and audio-restored before replacing files'
for name,p in files.items():
 if name not in changed:continue
 remote=DATA+'/'+name;packed='/dev/registration-stage-'+name.lstrip('.')+'.gz'
 # Old executable is closed. Backups are checksummed on Mac; free the old JFFS2
 # inode before expanding to avoid exhausting this device's small userdata.
 t.shell(f'set -e; rm -f {shlex.quote(remote)}; {DATA}/tools/busybox gzip -dc {shlex.quote(packed)} > {shlex.quote(remote)}; chmod 700 {shlex.quote(remote)}')
 assert t.shell('md5sum '+shlex.quote(remote)).split()[0]==digest(p)
 t.shell('rm '+shlex.quote(packed))
manifest=B/'cs-runtime.md5'
manifest.write_text(''.join(digest(files[n])+'  '+n+'\n' for n in ['.mf79u-cs-voice','.mf79u-cs-pcm-bridge','.mf79u-cs-voice.ko']))
t.push(manifest,DATA+'/cs-runtime.md5');t.shell('chmod 600 '+DATA+'/cs-runtime.md5')
if loaded and not args.reboot_new_driver:
 # This turn loaded exactly this module while suspended. Never label an unknown
 # pre-existing module as our installed version.
 assert t.shell('cat /dev/.mf79u-cs-driver.md5')==digest(files['.mf79u-cs-voice.ko']), 'Loaded driver revision is unknown; reboot with the checked installed module'
if args.reboot_new_driver:
 pending={'installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'raw_flash':False,
          'previous_boot':boot,'backup_directory':str(backup),'driver_reboot_pending':True,
          'original_md5':original,'new_driver_md5':digest(files['.mf79u-cs-voice.ko'])}
 (B/'registration-driver-upgrade.json').write_text(json.dumps(pending,indent=2)+'\n')
 try:t.shell('sync; reboot')
 except subprocess.SubprocessError:pass # USB disconnect is expected; fresh boot is checked below.
else:
 t.push(B/'detach-native','/dev/.mf79u-detach-native')
 t.shell('chmod 700 /dev/.mf79u-detach-native; /dev/.mf79u-detach-native; rm /dev/.mf79u-detach-native')
for _ in range(480):
 try:
  after=json.loads(t.shell('cat /dev/.mf79u-native-status.json'))
  current_boot=t.shell('cat /proc/sys/kernel/random/boot_id')
  fresh=current_boot!=boot if args.reboot_new_driver else after['pid']!=native
  if fresh and after.get('csPid',0)>0 and after.get('voiceReady'):break
 except (subprocess.SubprocessError,ValueError):pass
 time.sleep(.5)
else:raise RuntimeError('Runtime readiness missing; inspect native RAM log and checked backups')
assert (current_boot!=boot) if args.reboot_new_driver else (current_boot==boot)
assert t.shell('cat /dev/.mf79u-cs-driver.md5')==digest(files['.mf79u-cs-voice.ko'])
report={'installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'raw_flash':False,'boot_preserved':not args.reboot_new_driver,'previous_boot':boot,'boot':current_boot,'backup_directory':str(backup),
 'original_md5':original,'replaced_files':sorted(changed),'installed':{n:{'md5':digest(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for n,p in files.items()},
 'runtime':after,'physical_cs_calls_verified':False}
(B/'registration-runtime-install.json').write_text(json.dumps(report,indent=2)+'\n')
if args.reboot_new_driver:
 report['driver_reboot_pending']=False
 (B/'registration-driver-upgrade.json').write_text(json.dumps(report,indent=2)+'\n')
print('Registration runtime installed; selected voice backend ready; '+('checked fresh driver boot.' if args.reboot_new_driver else 'boot unchanged.'))

#!/usr/bin/env python3
"""Guarded Control-only upgrade, preserving SIP/native/settings."""
from pathlib import Path
import argparse,base64,importlib.util,subprocess,gzip,hashlib,time,json,datetime
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--require-sms-idle',action='store_true',help='Refuse SMS receive-policy updates while legacy forwarding jobs are pending')
args=parser.parse_args()
base=Path(__file__).resolve().parent;root=base.parents[1];build=base/'build';data='/mnt/userdata/mf79u'
spec=importlib.util.spec_from_file_location('transfer',base/'device-transfer.py');transfer=importlib.util.module_from_spec(spec);spec.loader.exec_module(transfer);shell=transfer.shell;push=transfer.push
backup=build/('pre-control-update-'+datetime.datetime.now().strftime('%Y%m%d'));backup.mkdir(mode=0o700,exist_ok=True)
def md5(p):return hashlib.md5(p.read_bytes()).hexdigest()
def wait_exit(pid):
 for _ in range(100):
  if shell('test -e /proc/'+str(pid)+'/exe && echo YES')!='YES':return
  time.sleep(.2)
 raise RuntimeError('Owned process cleanup did not finish')
def check_sms_idle():
 if not args.require_sms_idle:return
 for filename in ('sms-sip-state.json','sms-telegram-state.json'):
  value=shell('if [ -f '+data+'/'+filename+' ]; then cat '+data+'/'+filename+'; fi')
  state=json.loads(value) if value else {}
  pending=state.get('Jobs',[]) if filename.startswith('sms-telegram') else [job for job in state.get('Jobs',[]) if job.get('State') in ('queued','sending')]
  if pending or state.get('Inbox'):raise RuntimeError('Pending legacy SMS jobs must finish before this receive-policy update; services remain running')
check_sms_idle()
state=json.loads(shell('cat /dev/.mf79u-native-status.json'));gateway=json.loads(shell('cat /dev/.mf79u-gateway-status.json'))
if gateway.get('activeCall') or state.get('callBackend','none')!='none':raise RuntimeError('Modem call active')
settings=shell('md5sum '+data+'/settings.json '+data+'/gateway.ini')
oldhash=shell('md5sum '+data+'/.mf79u-control').split()[0];old=backup/('mf79u-control.'+oldhash)
if not old.exists():
 prior=build/'control-update.gz'
 saved=gzip.decompress(prior.read_bytes()) if prior.exists() else b''
 if hashlib.md5(saved).hexdigest()==oldhash:old.write_bytes(saved)
 else:
  # The project's USB adb shim has no pull command. Transfer only the checked
  # executable via the existing shell; encoded binary never reaches logs.
  packed_backup=shell(data+'/tools/busybox gzip -c '+data+'/.mf79u-control | '+data+'/tools/busybox base64')
  old.write_bytes(gzip.decompress(base64.b64decode(packed_backup)));packed_backup=''
 old.chmod(0o700)
if md5(old)!=oldhash:raise RuntimeError('Saved backup does not match installed Control')
# System info needs its persistent local reader as well as the embedded UI.
# Recover this dependency after userdata restoration without replacing a
# different installed helper or touching the modem identity.
imei_helper_restored=False
imei_helper=data+'/tools/system-imei'
if shell('test -x '+imei_helper+' && echo READY')!='READY':
 helper=build/'system-imei'
 if not helper.is_file():raise RuntimeError('Build the System IMEI helper before installing Control')
 if shell('test -e '+imei_helper+' && echo EXISTS')=='EXISTS':
  if shell('md5sum '+imei_helper).split()[0]!=md5(helper):raise RuntimeError('Unexpected non-executable IMEI helper; refusing replacement')
  shell('chmod 700 '+imei_helper)
 else:
  push(helper,imei_helper+'.update-next')
  shell('set -e; chmod 700 '+imei_helper+'.update-next; mv '+imei_helper+'.update-next '+imei_helper+'; sync')
 imei_helper_restored=True
imei_helper_md5=shell('md5sum '+imei_helper).split()[0]
new=build/'mf79u-control';packed=build/'control-update.gz';packed.write_bytes(gzip.compress(new.read_bytes(),9,mtime=0));push(packed,data+'/.mf79u-control.update-next.gz')
restore=backup/'restore.gz';restore.write_bytes(gzip.compress(old.read_bytes(),9,mtime=0));push(restore,'/dev/.mf79u-control.update-restore.gz')
pid=int(shell('cat /dev/.mf79u-control.pid'));parent=int(shell("sed -n 's/^PPid:[[:space:]]*//p' /proc/"+str(pid)+"/status"))
if pid<2 or parent<2 or shell('test /proc/'+str(pid)+'/exe -ef '+data+'/.mf79u-control && grep -q start-control.sh /proc/'+str(parent)+'/cmdline && echo OWNED')!='OWNED':raise RuntimeError('Unexpected Control owner')
check_sms_idle()
shell('kill -TERM '+str(pid));wait_exit(pid);wait_exit(parent)
shell(f'''set -e
base={data}
recover() {{ rm -f "$base/.mf79u-control.update-next"; "$base/tools/busybox" gzip -dc /dev/.mf79u-control.update-restore.gz > "$base/.mf79u-control"; chmod 700 "$base/.mf79u-control"; }}
trap recover EXIT
rm -f "$base/.mf79u-control"
"$base/tools/busybox" gzip -dc "$base/.mf79u-control.update-next.gz" > "$base/.mf79u-control.update-next"
chmod 700 "$base/.mf79u-control.update-next"
[ "$(md5sum "$base/.mf79u-control.update-next" | cut -d ' ' -f 1)" = "{md5(new)}" ]
mv "$base/.mf79u-control.update-next" "$base/.mf79u-control"
sync
trap - EXIT
rm -f "$base/.mf79u-control.update-next.gz" /dev/.mf79u-control.update-restore.gz
''')
push(build/'detach-control','/dev/.mf79u-detach-control');shell('chmod 700 /dev/.mf79u-detach-control; /dev/.mf79u-detach-control; rm /dev/.mf79u-detach-control')
for _ in range(60):
 try:
  newpid=int(shell('cat /dev/.mf79u-control.pid'))
  if newpid!=pid and shell('test /proc/'+str(newpid)+'/exe -ef '+data+'/.mf79u-control && echo YES')=='YES':break
 except (subprocess.SubprocessError,ValueError):pass
 time.sleep(.5)
else:raise RuntimeError('Updated Control not started')
if settings!=shell('md5sum '+data+'/settings.json '+data+'/gateway.ini'):raise RuntimeError('Settings changed')
newstate=json.loads(shell('cat /dev/.mf79u-native-status.json'))
if newstate['pid']!=state['pid'] or newstate['sipPid']!=state['sipPid']:raise RuntimeError('Native/SIP changed')
report={'installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'control_md5':md5(new),'control_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'control_pid':newpid,'settings_preserved':True,'native_sip_pids_preserved':True,'imei_helper_md5':imei_helper_md5,'imei_helper_restored':imei_helper_restored,'real_calls_sms_issued':False,'raw_flash':False}
(build/'control-update-install.json').write_text(json.dumps(report,indent=2)+'\n');print('Control installed; native/SIP PIDs and settings preserved.')

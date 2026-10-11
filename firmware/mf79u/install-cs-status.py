#!/usr/bin/env python3
"""Guarded controller update for read-only CS status; ring-only stays armed."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time
from ram_transfer import ram_push
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];ADB=[str(ROOT/'outputs/adb')]
DATA='/mnt/userdata/mf79u';REMOTE='/dev/.mf79u-native-cs-status-next'
def shell(command):return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=25).decode().replace('\r','').strip()
def status():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def digest(path):return hashlib.md5(path.read_bytes()).hexdigest()
old=status();pid=int(old['pid']);boot=shell('cat /proc/sys/kernel/random/boot_id')
if pid<2 or not old.get('ringOnly') or not old.get('csOnly') or old.get('imsReady'):raise SystemExit('Idle CS-only/ring-only runtime required')
if json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):raise SystemExit('Active SIP call')
if shell('test ! -e /sys/mf79u_cs/status && echo IDLE')!='IDLE':raise SystemExit('Wait for bounded CS handler expiry before controller update')
if shell(f'test /proc/{pid}/exe -ef {DATA}/.mf79u-native-gateway && echo OWNED')!='OWNED':raise SystemExit('Controller ownership mismatch')
previous=json.loads((BASE/'build/cs-only-install-live.json').read_text())
if shell(f'md5sum {DATA}/.mf79u-native-gateway').split()[0]!=previous['md5']:raise SystemExit('Unexpected installed controller; inspect before updating')
candidate=BASE/'build/mf79u-native-gateway';expected=digest(candidate)
backup=BASE/'build/pre-cs-status-20261008';backup.mkdir(mode=0o700,exist_ok=True)
old_file=backup/'mf79u-native-gateway'
if old_file.exists():raise SystemExit('Preserve the existing backup; this is a one-shot installer')
subprocess.run(ADB+['pull',DATA+'/.mf79u-native-gateway',str(old_file)],check=True,capture_output=True,timeout=25)
old_file.chmod(0o700)
if digest(old_file)!=previous['md5']:raise SystemExit('Backup checksum mismatch')
settings=shell(f'md5sum {DATA}/settings.json {DATA}/gateway.ini')
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':old,
 'sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'md5':expected,'backup_verified':True,
 'real_reboot':False,'no_answer_or_dial':True,'cs_audio_ready':False}
try:
 ram_push(ADB,candidate,REMOTE)
 test=shell(REMOTE+' --selftest');report['arm_selftest']=test
 if not test.startswith('PASS'):raise RuntimeError('ARM controller selftest failed')
 shell(f'set -e; cp {REMOTE} {DATA}/.mf79u-native-gateway.cs-status-next; chmod 700 {DATA}/.mf79u-native-gateway.cs-status-next; sync')
 if shell(f'md5sum {DATA}/.mf79u-native-gateway.cs-status-next').split()[0]!=expected:raise RuntimeError('Staged checksum mismatch')
 shell(f'kill -TERM {pid}')
 for _ in range(50):
  if shell(f'test -e /proc/{pid}/exe && echo PRESENT')!='PRESENT':break
  time.sleep(.2)
 else:raise RuntimeError('Owned controller cleanup timeout')
 shell(f'set -e; mv {DATA}/.mf79u-native-gateway.cs-status-next {DATA}/.mf79u-native-gateway; sync')
 for _ in range(60):
  after=status()
  if after.get('pid')!=pid and after.get('sipPid',0)>1 and after.get('csOnly') and after.get('ringOnly') and after.get('csAudioReady') is False and after.get('smsOnly'):break
  time.sleep(1)
 else:raise RuntimeError('New controller startup not verified; backup retained')
 report.update(after=after,same_boot=shell('cat /proc/sys/kernel/random/boot_id')==boot,
  settings_preserved=shell(f'md5sum {DATA}/settings.json {DATA}/gateway.ini')==settings,
  installed_checksum_verified=shell(f'md5sum {DATA}/.mf79u-native-gateway').split()[0]==expected)
 if not all(report[key] for key in ['same_boot','settings_preserved','installed_checksum_verified']):raise RuntimeError('Runtime preservation check failed')
finally:
 shell('rm -f '+REMOTE)
 (BASE/'build/cs-status-controller-install.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

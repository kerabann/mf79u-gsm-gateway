#!/usr/bin/env python3
"""Install a guarded B03 startup hook. No raw flashing; vendor executables untouched."""
import argparse,hashlib,subprocess
from pathlib import Path
from ram_transfer import ram_push
from adb_boot import patch_rc
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;DATA='/mnt/userdata/mf79u'
BASE_MD5='9b070d96d9bd752f579c8c00d9167204'
MARKER=b'\n# MF79U owned management service 0.7\nsh /mnt/userdata/mf79u/start-control.sh >/dev/null 2>&1 &\n'
def shell(cmd):return subprocess.check_output(ADB+['shell',cmd],timeout=20).decode().replace('\r','').strip()
def push(local,remote):subprocess.run(ADB+['push','-Z',str(local),remote],capture_output=True,check=True,timeout=20)
a=argparse.ArgumentParser();action=a.add_mutually_exclusive_group();action.add_argument('--install',action='store_true');action.add_argument('--restore',action='store_true');a.add_argument('--serial',default='1234567890ABCDEF');args=a.parse_args()
ADB=[str(ROOT/'outputs/adb'),'-s',args.serial]
base=HERE/'build/stock-rootfs/etc/rc';assert hashlib.md5(base.read_bytes()).hexdigest()==BASE_MD5
legacy_md5=hashlib.md5(base.read_bytes()+MARKER).hexdigest();adb_base=patch_rc(base.read_bytes());adb_base_md5=hashlib.md5(adb_base).hexdigest()
new=patch_rc(base.read_bytes()+MARKER);installed_md5=hashlib.md5(new).hexdigest();current=shell('md5sum /etc/rc').split()[0]
if not(args.install or args.restore):print('Use --install or --restore; guarded startup hook only');raise SystemExit(0)
if args.restore:
 if current not in (legacy_md5,installed_md5):raise SystemExit('Startup hook changed; refusing to overwrite /etc/rc')
 if shell(f'md5sum {DATA}/rc.vendor.b03').split()[0]!=BASE_MD5:raise SystemExit('Backup checksum mismatch')
 restored=adb_base if current==installed_md5 else base.read_bytes();expected=hashlib.md5(restored).hexdigest()
 staged=HERE/'build/rc-management-restored';staged.write_bytes(restored);push(staged,DATA+'/rc.management.new');source=DATA+'/rc.management.new'
else:
 if current not in (BASE_MD5,legacy_md5,adb_base_md5,installed_md5):raise SystemExit('Unexpected startup script; no changes made')
 helper=HERE/'build/mf79u-adb-boot'
 if not helper.exists():raise SystemExit('Run build-adb-boot.sh before installing the management hook')
 helper_md5=hashlib.md5(helper.read_bytes()).hexdigest();existing_helper=shell('md5sum /usr/zte/mf79u/adb-boot').split()
 if existing_helper[:1]!=[helper_md5]:
  if existing_helper and len(existing_helper[0])==32:raise SystemExit('ADB boot helper differs; refusing to overwrite it')
  ram_push(ADB,helper,'/dev/.mf79u-adb-helper')
  shell("set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; mkdir -p /usr/zte/mf79u; cp /dev/.mf79u-adb-helper /usr/zte/mf79u/adb-boot; chmod 755 /usr/zte/mf79u/adb-boot; sync")
  assert shell('md5sum /usr/zte/mf79u/adb-boot').split()[0]==helper_md5
  shell('rm -f /dev/.mf79u-adb-helper')
 ca=ROOT/'work/zte/voice/sip-deps/ca-bundle.pem';ca_md5=hashlib.md5(ca.read_bytes()).hexdigest();ca_target='/usr/zte/mf79u/ca-bundle.pem'
 existing=shell('md5sum '+ca_target).split()
 if not existing or existing[0]!=ca_md5:
  if existing and len(existing[0])==32:raise SystemExit('Existing CA bundle differs; refusing to overwrite it')
  ram_push(ADB,ca,'/dev/.mf79u-ca-bundle.pem')
  shell("set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; mkdir -p /usr/zte/mf79u; chmod 755 /usr/zte/mf79u; cp /dev/.mf79u-ca-bundle.pem "+ca_target+"; chmod 644 "+ca_target+"; sync")
  assert shell('md5sum '+ca_target).split()[0]==ca_md5
  shell('rm -f /dev/.mf79u-ca-bundle.pem')
 push(HERE/'start-control-userdata.sh',DATA+'/start-control.sh');shell(f'chmod 700 {DATA}/start-control.sh')
 if current==installed_md5:print('Management startup already installed');raise SystemExit(0)
 if current==BASE_MD5:shell(f'cp /etc/rc {DATA}/rc.vendor.b03; chmod 600 {DATA}/rc.vendor.b03')
 elif current==adb_base_md5:
  # The original vendor rc is public; do not back up the modified ADB rc as stock.
  push(base,DATA+'/rc.vendor.b03');shell(f'chmod 600 {DATA}/rc.vendor.b03')
 assert shell(f'md5sum {DATA}/rc.vendor.b03').split()[0]==BASE_MD5
 staged=HERE/'build/rc-with-management';staged.write_bytes(new);push(staged,DATA+'/rc.management.new');source=DATA+'/rc.management.new';expected=installed_md5
 if shell('md5sum '+source).split()[0]!=expected:raise SystemExit('Staging checksum mismatch')
# Background service starts after all vendor boot commands; an exit trap restores read-only mount.
result=shell(f"set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; cp {source} /etc/.mf79u-rc.new; chmod 744 /etc/.mf79u-rc.new; mv /etc/.mf79u-rc.new /etc/rc; sync; md5sum /etc/rc")
if result.split()[0]!=expected:raise SystemExit('Installed startup checksum mismatch')
print('Management boot hook '+('restored' if args.restore else 'installed')+'; root filesystem remounted read-only')

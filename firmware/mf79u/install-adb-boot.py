#!/usr/bin/env python3
"""Guarded B03 ADB startup installation; only rc and a small public helper."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from adb_boot import patch_rc, unpatch_rc, START
from ram_transfer import ram_push

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / 'build'
DATA = '/mnt/userdata/mf79u'
MARKER = b'\n# MF79U owned management service 0.7\nsh /mnt/userdata/mf79u/start-control.sh >/dev/null 2>&1 &\n'
parser = argparse.ArgumentParser(description=__doc__)
action = parser.add_mutually_exclusive_group(required=True)
action.add_argument('--install', action='store_true')
action.add_argument('--restore', action='store_true')
parser.add_argument('--serial', default='1234567890ABCDEF')
args = parser.parse_args()
adb = [str(ROOT / 'outputs/adb'), '-s', args.serial]


def shell(command):
    return subprocess.check_output(adb + ['shell', command], timeout=20).decode().replace('\r', '').strip()


def md5(data):
    return hashlib.md5(data).hexdigest()


def read_rc(path):
    # Stock B03 has non-UTF8 comments. Preserve their bytes exactly.
    return subprocess.check_output(adb + ['shell', 'cat ' + path], timeout=20).replace(b'\r\n', b'\n')


base = (BUILD / 'stock-rootfs/etc/rc').read_bytes()
if md5(base) != '9b070d96d9bd752f579c8c00d9167204':
    raise SystemExit('Unexpected stock B03 rc')
allowed = [base, base + MARKER, patch_rc(base), patch_rc(base + MARKER)]
current = read_rc('/etc/rc')
if current not in allowed:
    raise SystemExit('Unexpected startup script; no changes made')
for path, expected in [('/bin/adbd', 'f53e783e30da4505ecbb5111aecc5d2c'),
                       ('/bin/nv', '4cec1743becf58a89332816308970623'),
                       ('/lib/libnvram.so', 'd9ee601b7c8591e54742c4c17861b77a')]:
    if shell('md5sum ' + path).split()[:1] != [expected]:
        raise SystemExit('Unexpected B03 ABI: ' + path)
runtime = json.loads(shell('cat /dev/.mf79u-native-status.json'))
if runtime.get('callBackend') != 'none':
    raise SystemExit('Active call; no changes made')
before_boot = shell('cat /proc/sys/kernel/random/boot_id')
target = unpatch_rc(current) if args.restore else patch_rc(current)
helper = BUILD / 'mf79u-adb-boot'
if not args.restore and not helper.exists():
    raise SystemExit('Run build-adb-boot.sh first')
if target == current:
    if args.restore:
        print('ADB startup policy already absent')
    elif shell('md5sum /usr/zte/mf79u/adb-boot').split()[:1] == [md5(helper.read_bytes())]:
        print('ADB startup policy and helper already installed')
    else:
        raise SystemExit('Installed helper differs; refusing an unreviewed replacement')
    raise SystemExit(0)
if args.restore:
    backup = read_rc(DATA + '/rc.pre-adb-boot')
    if backup != target:
        raise SystemExit('Original startup backup differs; refusing restore')
else:
    shell('set -e; if [ ! -e ' + DATA + '/rc.pre-adb-boot ]; then cp /etc/rc ' + DATA + '/rc.pre-adb-boot; chmod 600 ' + DATA + '/rc.pre-adb-boot; fi')
    if shell('md5sum ' + DATA + '/rc.pre-adb-boot').split()[:1] != [md5(current)]:
        raise SystemExit('Original startup backup differs')
stage = BUILD / 'rc-adb-boot'
stage.write_bytes(target)
rc_ram = '/dev/.mf79u-adb-rc'
helper_ram = '/dev/.mf79u-adb-helper'
try:
    ram_push(adb, stage, rc_ram)
    if not args.restore:
        ram_push(adb, helper, helper_ram)
        # --check is strictly read-only. Test the ABI before modifying rootfs.
        checked = shell(helper_ram + ' --check; echo ADB_HELPER_EXIT:$?')
        if 'ADB_HELPER_EXIT:0' not in checked:
            raise SystemExit('Expected currently working debug profile; helper check failed')
    command = "set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; "
    if not args.restore:
        command += 'mkdir -p /usr/zte/mf79u; cp ' + helper_ram + ' /usr/zte/mf79u/.adb-boot.new; chmod 755 /usr/zte/mf79u/.adb-boot.new; mv /usr/zte/mf79u/.adb-boot.new /usr/zte/mf79u/adb-boot; '
    command += 'cp ' + rc_ram + ' /etc/.mf79u-rc.new; chmod 744 /etc/.mf79u-rc.new; mv /etc/.mf79u-rc.new /etc/rc; sync; echo ADB_INSTALL_OK'
    if 'ADB_INSTALL_OK' not in shell(command):
        raise SystemExit('Atomic installation failed')
    if shell('md5sum /etc/rc').split()[:1] != [md5(target)]:
        raise SystemExit('Installed rc checksum differs')
    if not args.restore and shell('md5sum /usr/zte/mf79u/adb-boot').split()[:1] != [md5(helper.read_bytes())]:
        raise SystemExit('Installed helper checksum differs')
    if ' / jffs2 ro,' not in shell('cat /proc/mounts'):
        raise SystemExit('Root filesystem did not return to read-only')
    if shell('cat /proc/sys/kernel/random/boot_id') != before_boot:
        raise SystemExit('Unexpected reboot during installation')
    receipt = {'action': 'restore' if args.restore else 'install', 'boot': before_boot,
               'beforeRcMD5': md5(current), 'rcMD5': md5(target),
               'helperMD5': None if args.restore else md5(helper.read_bytes()),
               'helperBytes': None if args.restore else helper.stat().st_size,
               'rootReadOnly': True, 'partitionImageFlashed': False,
               'callsInitiated': False, 'usbReenumerated': False}
    (BUILD / 'adb-boot-install-20261011.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('ADB startup policy ' + ('restored' if args.restore else 'installed') + '; rootfs read-only')
finally:
    shell('rm -f ' + rc_ram + ' ' + helper_ram)

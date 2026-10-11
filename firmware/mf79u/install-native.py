#!/usr/bin/env python3
"""Install device-local voice startup and a reversible B03 service policy.
No raw flashing. Preserve radio/SIM/SMS/WLAN/router/watchdog dependencies.
"""
import argparse
import hashlib
from pathlib import Path
import shlex
import subprocess
from ram_transfer import ram_push

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADB = [str(ROOT / 'outputs/adb'), '-s', '123456789ABCDEF']
DATA = '/mnt/userdata/mf79u'
UNUSED_SERVICES = (b'zte_topsw_data_stat', b'zte_topsw_ussd', b'zte_topsw_pbm')
BUILD = HERE / 'build'

def md5(data):
    return hashlib.md5(data).hexdigest()

def shell(command):
    return subprocess.check_output(ADB + ['shell', command], timeout=25).decode().replace('\r', '').strip()

def policy():
    vendor = BUILD / 'stock-rootfs/usr/zte/zte_conf'
    daemon = (vendor / 'config/zte_topsw_daemon.conf').read_bytes()
    debug = (vendor / 'scripts/zte_debug.sh').read_bytes()
    if md5(daemon) != 'c77d275ae5617de23689c1827ab9d4f2':
        raise RuntimeError('Unexpected B03 daemon configuration')
    kept = []
    for line in daemon.splitlines(keepends=True):
        words = line.split()
        if len(words) >= 3 and words[0] in (b'run', b'sync') and words[2] in (b'zte_topsw_led', b'zte_topsw_self_regist') + UNUSED_SERVICES:
            continue
        kept.append(line)
    custom = b''.join(kept)
    for command in (b'prestartdua &', b'zte_dm &'):
        if debug.splitlines().count(command) != 1:
            raise RuntimeError('Unexpected B03 debug startup')
    custom_debug = debug.replace(b'prestartdua &', b'# MF79U: stock FOTA disabled; custom firmware owns updates.').replace(
        b'\nzte_dm &', b'\n# MF79U: stock remote device-management agent disabled.')
    daemon_out, debug_out = BUILD / 'zte_topsw_daemon.custom.conf', BUILD / 'zte_debug.custom.sh'
    daemon_out.write_bytes(custom)
    debug_out.write_bytes(custom_debug)
    return [('/usr/zte/zte_conf/config/zte_topsw_daemon.conf', 'daemon.vendor.b03.conf', daemon, daemon_out),
            ('/usr/zte/zte_conf/scripts/zte_debug.sh', 'debug.vendor.b03.sh', debug, debug_out),
            ('/usr/zte_web/web/index.html', 'index.vendor.b03.html',
             (BUILD / 'stock-rootfs/usr/zte_web/web/index.html').read_bytes(), HERE / 'boot-wait.html')]

def install():
    files = policy()
    # The LED-only intermediate policy from the same verified B03 base is allowed.
    original = files[0][2]
    led_only = b''.join(line for line in original.splitlines(keepends=True)
                        if not (line.split()[:1] in ([b'run'], [b'sync']) and b'zte_topsw_led' in line.split()))
    for target, backup, stock, candidate in files:
        current = shell('md5sum ' + shlex.quote(target)).split()[0]
        allowed = {md5(stock), md5(candidate.read_bytes())}
        if 'daemon.conf' in target:
            allowed.add(md5(led_only))
            previous_native = b''.join(line for line in original.splitlines(keepends=True)
                if not (line.split()[:1] in ([b'run'], [b'sync']) and
                        any(name in line.split() for name in (b'zte_topsw_led', b'zte_topsw_self_regist'))))
            allowed.add(md5(previous_native))
        if current not in allowed:
            raise RuntimeError('Unexpected device service file: ' + target)
        backup_path = DATA + '/' + backup
        if shell('test -f ' + shlex.quote(backup_path) + ' && echo PRESENT') != 'PRESENT':
            if current != md5(stock):
                # The previous LED-only installer already saved the stock config.
                raise RuntimeError('Original B03 service backup missing')
            shell('cp ' + shlex.quote(target) + ' ' + shlex.quote(backup_path) + '; chmod 600 ' + shlex.quote(backup_path))
        if shell('md5sum ' + shlex.quote(backup_path)).split()[0] != md5(stock):
            raise RuntimeError('Vendor service backup checksum mismatch')
        ram = '/dev/.mf79u-' + candidate.name
        ram_push(ADB, candidate, ram)
        mode = '755' if target.endswith('.sh') else '644'
        shell("set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; cp " +
              shlex.quote(ram) + ' ' + shlex.quote(target + '.mf79u-next') + '; chmod ' + mode + ' ' +
              shlex.quote(target + '.mf79u-next') + '; mv ' + shlex.quote(target + '.mf79u-next') + ' ' + shlex.quote(target) + '; sync')
        if shell('md5sum ' + shlex.quote(target)).split()[0] != md5(candidate.read_bytes()):
            raise RuntimeError('Service policy installation checksum mismatch')
    if shell('test -f ' + DATA + '/start-control.pre-native.sh && echo PRESENT') != 'PRESENT':
        shell('cp ' + DATA + '/start-control.sh ' + DATA + '/start-control.pre-native.sh; chmod 700 ' + DATA + '/start-control.pre-native.sh')
    artifacts = [(BUILD / 'mf79u-native-gateway', '.mf79u-native-gateway'),
                 (BUILD / 'mf79u-net-led', '.mf79u-net-led'),
                 (HERE / 'start-native.sh', 'start-native.sh'),
                 (HERE / 'start-control-userdata.sh', 'start-control.sh')]
    for source, name in artifacts:
        ram = '/dev/.mf79u-install-' + name.lstrip('.')
        ram_push(ADB, source, ram)
        target = DATA + '/' + name
        shell('set -e; cp ' + shlex.quote(ram) + ' ' + shlex.quote(target + '.next') + '; chmod 700 ' +
              shlex.quote(target + '.next') + '; mv ' + shlex.quote(target + '.next') + ' ' + shlex.quote(target))
        if shell('md5sum ' + shlex.quote(target)).split()[0] != md5(source.read_bytes()):
            raise RuntimeError('Native artifact checksum mismatch: ' + name)
    shell("printf '1\\n' > " + DATA + '/native-enabled; chmod 600 ' + DATA + '/native-enabled; sync')
    print('Native voice boot enabled; stock LED, self-registration, FOTA and DM startup disabled. Reboot verification pending.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if args.install:
        install()
    else:
        policy()
        print('Prepared reversible B03 service policy; device unchanged.')

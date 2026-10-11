#!/usr/bin/env python3
"""Exact B03 one-boot passive initial DSP observer with automatic rc rollback.

Default validates/prepares offline only. --run installs a bounded one-shot boot
hook, reboots to observe original self-check calls, then reboots normally and
verifies IMS/original CP callbacks. No raw flash, DSP commands/programs or calls.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,re,shlex,subprocess,time
from ram_transfer import ram_push

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];BUILD=BASE/'build'
ADB=[str(ROOT/'outputs/adb')];DATA='/mnt/userdata/mf79u'
REMOTE_MODULE=DATA+'/dsp-load-watch.once.ko'
REMOTE_HELPER=DATA+'/dsp-load-watch-once.sh'
REMOTE_BACKUP=DATA+'/rc.before-dsp-load-watch'
REMOTE_MARKER=DATA+'/dsp-load-watch.once'
CP_MD5='8138d03644b0417ec3fba9d7175200bc'
RC_MD5='b98c87a5d44b5c8b847ca5ad3125b5d7'

def shell(command,timeout=20):
    return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=timeout).decode().replace('\r','').strip()
def status():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def md5(data):return hashlib.md5(data).hexdigest()
def remote_md5(path):return shell('md5sum '+shlex.quote(path)).split()[0]
def boot():return shell('cat /proc/sys/kernel/random/boot_id',6)
def load_radio():
    spec=importlib.util.spec_from_file_location('initial_load_radio',BASE/'test-cs-reattach.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def wait_runtime(previous_boot,seconds=180):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            current=boot();value=status()
            if current!=previous_boot and value.get('sipPid') and value.get('imsReady'):return current,value
        except (subprocess.SubprocessError,ValueError,IndexError):pass
        time.sleep(2)
    raise RuntimeError('Reboot/IMS runtime did not recover in time')
def wait_guard(enabled):
    for _ in range(40):
        value=status()
        if value.get('ringOnly')==enabled:return value
        time.sleep(.5)
    raise RuntimeError('Ring guard transition timeout')
def reboot():
    # B03 adbd acknowledges its reboot service without rebooting. Use the
    # project's live-verified shell path; disconnect/timeout is expected.
    try:subprocess.run(ADB+['shell','sync; reboot'],capture_output=True,timeout=10)
    except subprocess.TimeoutExpired:pass
def install_rc(source,expected_current,expected_new):
    if remote_md5('/etc/rc')!=expected_current:raise RuntimeError('Boot script changed; refuse overwrite')
    command="set -e; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; cp "+shlex.quote(source)+" /etc/.mf79u-rc.new; chmod 744 /etc/.mf79u-rc.new; mv /etc/.mf79u-rc.new /etc/rc; sync; md5sum /etc/rc"
    if shell(command).split()[0]!=expected_new:raise RuntimeError('Boot script install checksum failed')
def route_audit():
    value=subprocess.run(['python3',str(BASE/'test-cs-kernel-probe.py'),'--routing'],capture_output=True,text=True,timeout=40)
    if value.returncode:raise RuntimeError('Original callback audit failed')
    report=json.loads((BUILD/'cs-route-probe-live.json').read_text())
    if not report.get('restoration_verified'):raise RuntimeError('Original CP state not confirmed')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    original=(BUILD/'stock-rootfs/etc/rc').read_bytes()+b'\n# MF79U owned management service 0.7\nsh /mnt/userdata/mf79u/start-control.sh >/dev/null 2>&1 &\n'
    if md5(original)!=RC_MD5:raise RuntimeError('Unrecognized offline production rc')
    meta=json.loads((BUILD/'cs-dsp-load-watch-build.json').read_text())
    module=BUILD/'mf79u_cs_dsp_load.ko'
    if meta.get('notifications_only') or not meta.get('live_arm_allowed') or meta.get('seconds')!=180 or meta['sha256']!=hashlib.sha256(module.read_bytes()).hexdigest():
        raise RuntimeError('Exact audited 180-second initial-load build required')
    preflight=json.loads((BUILD/'cs-module-notifier-live.json').read_text())
    if not preflight.get('all_three_notifications_verified') or not preflight.get('runtime_restored'):
        raise RuntimeError('Live notifier ABI preflight required')
    anchor=b'insmod /lib/cpko/cpko.ko\n'
    if original.count(anchor)!=1 or original.index(b'fs_check "normal"')>original.index(anchor):
        raise RuntimeError('Unexpected userdata/CP boot order')
    hook=b'# MF79U temporary one-shot DSP initialization observer\nif [ -r /mnt/userdata/mf79u/dsp-load-watch.once ]; then\n    sh /mnt/userdata/mf79u/dsp-load-watch-once.sh\nfi\n'
    candidate=original.replace(anchor,hook+anchor)
    candidate_md5=md5(candidate)
    helper=f'''#!/bin/sh
# Consumed before every other operation; never retries on the next boot.
set -u
rm -f {REMOTE_MARKER}
if [ "$(md5sum {REMOTE_BACKUP} | cut -d ' ' -f 1)" != "{RC_MD5}" ]; then
    echo MF79U_DSP_BOOT_BACKUP_REJECTED
    exit 0
fi
if [ "$(md5sum /etc/rc | cut -d ' ' -f 1)" != "{candidate_md5}" ]; then
    echo MF79U_DSP_BOOT_CURRENT_RC_REJECTED
    exit 0
fi
if ! mount -o remount,rw /; then exit 0; fi
if ! cp {REMOTE_BACKUP} /etc/.mf79u-rc.new; then mount -o remount,ro /; exit 0; fi
chmod 744 /etc/.mf79u-rc.new
if ! mv /etc/.mf79u-rc.new /etc/rc; then mount -o remount,ro /; exit 0; fi
sync
mount -o remount,ro /
if [ "$(md5sum /etc/rc | cut -d ' ' -f 1)" != "{RC_MD5}" ]; then exit 0; fi
echo MF79U_DSP_BOOT_RC_RESTORED
if [ "$(md5sum /lib/cpko/cpko.ko | cut -d ' ' -f 1)" != "{CP_MD5}" ]; then exit 0; fi
if [ "$(md5sum {REMOTE_MODULE} | cut -d ' ' -f 1)" != "{md5(module.read_bytes())}" ]; then exit 0; fi
insmod {REMOTE_MODULE} || true
'''.encode()
    prepared={'original_rc_md5':RC_MD5,'candidate_rc_md5':candidate_md5,'module_sha256':meta['sha256'],
              'watch_seconds':180,'one_shot_consumed_before_load':True,'rc_restored_before_cp':True,
              'no_raw_flash':True,'no_sim_calls':True,'no_new_dsp_commands':True,'dynamic_cp_base':True}
    for name,data in (('rc.before-dsp-load-watch',original),('rc.with-dsp-load-watch',candidate),('dsp-load-watch-once.sh',helper)):
        path=BUILD/name;path.write_bytes(data);path.chmod(0o700 if name.endswith('.sh') else 0o600)
        subprocess.run(['/bin/sh','-n',str(path)],check=True,capture_output=True)
    (BUILD/'cs-dsp-initial-load-prepared.json').write_text(json.dumps(prepared,indent=2)+'\n')
    if not args.run:print(json.dumps(prepared,indent=2));return
    before=status();original_boot=boot();radio=load_radio()
    if before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady') or json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):
        raise RuntimeError('Idle production IMS runtime required')
    if remote_md5('/etc/rc')!=RC_MD5 or remote_md5('/lib/cpko/cpko.ko')!=CP_MD5 or shell('uname -r')!='3.4.110-rt140':
        raise RuntimeError('Unrecognized live B03 startup/kernel/CP')
    if boot()!=preflight['boot_id']:raise RuntimeError('Notifier preflight boot differs')
    if any(radio.get_flag(n)!=0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG')) or '^SYSCONFIG: 27,0,1,2' not in radio.at('AT^SYSCONFIG?'):
        raise RuntimeError('Production flags/profile required')
    for path in (REMOTE_MODULE,REMOTE_HELPER,REMOTE_BACKUP,REMOTE_MARKER,DATA+'/native-ring-only'):
        if shell('test -e '+shlex.quote(path)+' && echo PRESENT')=='PRESENT':raise RuntimeError('Another test owns '+path)
    if any(row.startswith('mf79u_cs_dsp_load ') for row in shell('cat /proc/modules').splitlines()):raise RuntimeError('Observer already loaded')
    report=dict(prepared,tested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),before=before,original_boot=original_boot)
    guarded=False;installed=False;first_reboot=False
    try:
        shell('umask 077; : > '+DATA+'/native-ring-only; chmod 600 '+DATA+'/native-ring-only')
        guarded=True;wait_guard(True);report['before_route_audit']=route_audit()
        shell('cp /etc/rc '+REMOTE_BACKUP+'; chmod 600 '+REMOTE_BACKUP)
        if remote_md5(REMOTE_BACKUP)!=RC_MD5:raise RuntimeError('Live rc backup verification failed')
        transfers=[(module,REMOTE_MODULE),(BUILD/'dsp-load-watch-once.sh',REMOTE_HELPER),(BUILD/'rc.with-dsp-load-watch','/dev/.mf79u-dsp-load-rc')]
        for local,target in transfers:
            stage='/dev/.mf79u-dsp-load-transfer'
            ram_push(ADB,local,stage)
            if target!=stage:shell('cp '+stage+' '+target+'; chmod 700 '+target+'; rm -f '+stage)
            if remote_md5(target)!=md5(local.read_bytes()):raise RuntimeError('Staging checksum failed')
        shell('/bin/sh -n '+REMOTE_HELPER+' && /bin/sh -n /dev/.mf79u-dsp-load-rc')
        shell('umask 077; : > '+REMOTE_MARKER+'; chmod 600 '+REMOTE_MARKER+'; sync')
        installed=True
        install_rc('/dev/.mf79u-dsp-load-rc',RC_MD5,candidate_md5)
        shell('rm -f /dev/.mf79u-dsp-load-rc')
        report['stage']='one_shot_installed'
        (BUILD/'cs-dsp-initial-load-live.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Verified one-shot rc/backup installed; rebooting to observe unchanged CP initialization.',flush=True)
        first_reboot=True;reboot()
        observed_boot,observed_status=wait_runtime(original_boot)
        report.update(observed_boot=observed_boot,observed_status=observed_status,observed_modules=shell('cat /proc/modules').splitlines())
        if not observed_status.get('ringOnly') or observed_status.get('csOnly'):
            raise RuntimeError('Boot voice guard/policy not preserved')
        report['rc_automatically_restored']=remote_md5('/etc/rc')==RC_MD5
        report['one_shot_consumed']=shell('test ! -e '+REMOTE_MARKER+' && echo CLEAN')=='CLEAN'
        if not report['rc_automatically_restored'] or not report['one_shot_consumed']:
            raise RuntimeError('Boot rollback not confirmed')
        print('Initial boot recovered, original rc already restored; collecting bounded observer evidence.',flush=True)
        rows=[];deadline=time.monotonic()+210
        while time.monotonic()<deadline:
            current=shell('/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_DSP_LOAD | tail -n 64').splitlines()
            rows=list(dict.fromkeys(rows+current))
            if any('expired seconds=180 ' in row for row in rows):break
            time.sleep(2)
        report['messages']=rows
        report['observer_expired']=any('expired seconds=180 ' in row and 'notifier_removed=1 ' in row for row in rows)
        report['literal_restored']=any('expired seconds=180 ' in row and 'literal_restored=1 ' in row for row in rows)
        report['observed_vendor_calls']=sum(' saved_observed=' in row for row in rows)
        report['stage']='initial_observation_complete'
    finally:
        try:
            # No force unloading of either pinned observer or CP. Restore boot
            # script if needed, then a normal reboot clears all diagnostics.
            if installed and remote_md5('/etc/rc')==candidate_md5:
                shell('rm -f '+REMOTE_MARKER+'; sync')
                install_rc(REMOTE_BACKUP,candidate_md5,RC_MD5)
            if first_reboot:
                current_boot=boot()
                if remote_md5('/etc/rc')!=RC_MD5:raise RuntimeError('Normal rc not restored; refuse further reboot')
                print('Rebooting normally to restore original CP placement and clear pinned observer.',flush=True)
                reboot();final_boot,after=wait_runtime(current_boot)
                report['final_boot']=final_boot
                modules=shell('cat /proc/modules').splitlines()
                report['original_cp_placement']=any(row.startswith('cpko 6397096 ') and '0xbf000000' in row for row in modules)
                report['diagnostic_modules_cleared']=not any(row.startswith('mf79u_cs_') for row in modules)
                if not report['original_cp_placement'] or not report['diagnostic_modules_cleared']:
                    raise RuntimeError('Original CP placement/diagnostic cleanup failed')
            if guarded:
                report['final_route_audit']=route_audit()
                if remote_md5('/etc/rc')!=RC_MD5:raise RuntimeError('Original rc not confirmed')
                shell('rm -f '+DATA+'/native-ring-only')
                after=wait_guard(False)
                report['after']=after
                report['flags_preserved']=all(radio.get_flag(n)==0 for n in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'))
                report['profile_preserved']='^SYSCONFIG: 27,0,1,2' in radio.at('AT^SYSCONFIG?')
                report['root_readonly']=any(row.startswith('/dev/root / jffs2 ro,') for row in shell('cat /proc/mounts').splitlines())
                report['runtime_restored']=after.get('imsReady') and not after.get('ringOnly') and not after.get('csOnly') and report['flags_preserved'] and report['profile_preserved'] and report['root_readonly']
                for path in (REMOTE_MODULE,REMOTE_HELPER,REMOTE_BACKUP,REMOTE_MARKER,'/dev/.mf79u-dsp-load-rc','/dev/.mf79u-dsp-load-transfer'):
                    shell('rm -f '+shlex.quote(path))
                report['temporary_boot_files_removed']=all(shell('test ! -e '+shlex.quote(path)+' && echo CLEAN')=='CLEAN' for path in (REMOTE_MODULE,REMOTE_HELPER,REMOTE_BACKUP,REMOTE_MARKER))
        except Exception as exc:
            report['restore_error']=str(exc);raise
        finally:
            (BUILD/'cs-dsp-initial-load-live.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report.get('runtime_restored'):raise RuntimeError('Production runtime restoration failed')
    print(json.dumps({k:report.get(k) for k in ('observed_vendor_calls','observer_expired','literal_restored','rc_automatically_restored','runtime_restored','diagnostic_modules_cleared','temporary_boot_files_removed','messages')},indent=2))

if __name__=='__main__':main()

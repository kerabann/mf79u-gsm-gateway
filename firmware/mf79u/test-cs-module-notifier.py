#!/usr/bin/env python3
"""Reversible exact-B03 module-notifier preflight; no CP hooks or DSP access."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time
from ram_transfer import ram_push
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];BUILD=BASE/'build'
ADB=[str(ROOT/'outputs/adb')]
NAME='mf79u_cs_dsp_load';REMOTE='/dev/.mf79u-cs-dsp-load-notify.ko'
def shell(command):return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=20).decode().replace('\r','').strip()
def status():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def loaded():return any(row.startswith(NAME+' ') for row in shell('cat /proc/modules').splitlines())
def wait_guard(value):
    for _ in range(40):
        s=status()
        if s.get('ringOnly')==value:return s
        time.sleep(.5)
    raise RuntimeError('Ring guard transition timeout')
before=status();boot=shell('cat /proc/sys/kernel/random/boot_id')
if before.get('ringOnly') or before.get('csOnly') or not before.get('imsReady') or json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):
    raise SystemExit('Idle normal IMS runtime required')
if loaded():raise SystemExit('Notifier instance already loaded')
if shell('test -e /mnt/userdata/mf79u/native-ring-only && echo PRESENT')=='PRESENT':raise SystemExit('Ring guard owned by another test')
local=BUILD/(NAME+'.ko');meta=json.loads((BUILD/'cs-dsp-load-watch-build.json').read_text())
if not meta.get('notifications_only') or not meta.get('live_arm_allowed') or meta['sha256']!=hashlib.sha256(local.read_bytes()).hexdigest():raise SystemExit('Exact audited notification-only build required')
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,'sha256':meta['sha256'],'no_cp_hooks':True,'no_dsp_access':True,'no_sim_calls':True,'no_boot_changes':True}
guarded=False
try:
    shell('umask 077; : > /mnt/userdata/mf79u/native-ring-only; chmod 600 /mnt/userdata/mf79u/native-ring-only')
    guarded=True;wait_guard(True)
    ram_push(ADB,local,REMOTE)
    result=shell('insmod '+REMOTE+'; echo MF79U_INSMOD_EXIT=$?')
    if 'MF79U_INSMOD_EXIT=0' not in result or not loaded():raise RuntimeError('Notifier failed to load')
    result=subprocess.run(['python3',str(BASE/'test-cs-kernel-probe.py'),'--module-layout'],capture_output=True,text=True,timeout=40)
    if result.returncode:raise RuntimeError('Read-only target module failed')
    rows=shell('/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_DSP_LOAD | tail -n 24').splitlines()
    starts=[i for i,row in enumerate(rows) if 'registered=1 notifications_only=1 ' in row]
    report['messages']=rows[starts[-1]:] if starts else rows
    report['all_three_notifications_verified']=all(any('notifier_probe_state='+str(n)+' structure_state='+str(n)+' ' in row for row in report['messages']) for n in (1,0,2))
    report['target_module']=json.loads((BUILD/'cs-module-layout-probe-live.json').read_text())
    if not report['all_three_notifications_verified']:raise RuntimeError('Module notification ABI evidence missing')
finally:
    if loaded():report['unload_response']=shell('rmmod '+NAME+'; echo MF79U_RMMOD_EXIT=$?')
    report['unloaded']=not loaded();shell('rm -f '+REMOTE)
    if guarded and report['unloaded']:
        shell('rm -f /mnt/userdata/mf79u/native-ring-only')
        after=wait_guard(False)
    else:after=status()
    report['after']=after;report['same_boot']=shell('cat /proc/sys/kernel/random/boot_id')==boot
    report['same_native_sip_pids']=all(before[k]==after[k] for k in ('pid','sipPid'))
    report['runtime_restored']=report['unloaded'] and report['same_boot'] and report['same_native_sip_pids'] and after.get('imsReady') and not after.get('ringOnly') and not after.get('csOnly')
    (BUILD/'cs-module-notifier-live.json').write_text(json.dumps(report,indent=2)+'\n')
if not report.get('runtime_restored'):raise SystemExit('Runtime restoration failed')
print(json.dumps(report,indent=2))

#!/usr/bin/env python3
"""Read B03 I2S/LSP/GSM clocks with no radio transition or register writes."""
from pathlib import Path
import datetime,json,re,subprocess,time

BASE=Path(__file__).resolve().parent
ADB=[str(BASE.parents[1]/'outputs/adb')]
GUARD='/mnt/userdata/mf79u/native-ring-only'
def shell(command):
    return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,
        timeout=20).decode().replace('\r','').strip()
def status():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def wait_guard(enabled):
    for _ in range(40):
        value=status()
        if value.get('ringOnly')==enabled:return value
        time.sleep(.5)
    raise RuntimeError('Ring guard transition timeout')
before=status();boot=shell('cat /proc/sys/kernel/random/boot_id')
if before.get('csOnly') or before.get('ringOnly') or not before.get('imsReady') or json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'):
    raise SystemExit('Idle production IMS required')
if shell('test -e '+GUARD+' && echo PRESENT')=='PRESENT':
    raise SystemExit('Ring guard already owned')
report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'before':before,'boot_id':boot,'no_radio_transition':True,
    'no_register_writes':True,'no_sim_calls':True,'no_dsp_commands':True}
guarded=False
try:
    shell('umask 077; : > '+GUARD+'; chmod 600 '+GUARD)
    guarded=True;wait_guard(True)
    result=subprocess.run(['python3',str(BASE/'test-cs-kernel-probe.py'),'--i2s-preflight'],
        capture_output=True,text=True,timeout=40)
    if result.returncode:raise RuntimeError('Read-only probe failed: '+result.stderr[-1000:])
    value=json.loads((BASE/'build/cs-i2s-preflight-live.json').read_text())
    report['probe']=value
    report['registers']={m[1]:m[2] for row in value['messages']
        if (m:=re.search(r'address=([0-9a-f]{8}) value=([0-9a-f]{8})',row))}
    # Every added register must have a fresh measurement from this binary.
    if not all(a in report['registers'] for a in ('f8a00060','f8a00064','f8a00068','f843b068')):
        raise RuntimeError('Expanded clock measurements missing')
    if not any('cp_clock_index=53 ' in row for row in value['messages']):
        raise RuntimeError('GSM48 clock record missing')
finally:
    unloaded=not any(row.startswith('mf79u_cs_i2s ') for row in shell('cat /proc/modules').splitlines())
    report['unloaded']=unloaded
    if guarded and unloaded:
        shell('rm -f '+GUARD);after=wait_guard(False)
    else:after=status()
    report.update(after=after,same_boot=shell('cat /proc/sys/kernel/random/boot_id')==boot,
        same_native_sip_pids=all(before[k]==after[k] for k in ('pid','sipPid')),
        guard_removed=shell('test ! -e '+GUARD+' && echo CLEAN')=='CLEAN')
    report['runtime_restored']=unloaded and report['same_boot'] and report['same_native_sip_pids'] and report['guard_removed'] and after.get('imsReady') and not after.get('ringOnly') and not after.get('csOnly')
    (BASE/'build/cs-i2s-extended-clock-live.json').write_text(json.dumps(report,indent=2)+'\n')
if not report['runtime_restored']:raise SystemExit('Runtime restoration failed')
print(json.dumps({k:report[k] for k in ('runtime_restored','same_boot','same_native_sip_pids','registers')},indent=2))

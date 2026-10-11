#!/usr/bin/env python3
"""Read-only verification of the saved ordinary-SIM profile after a CS test.

Requires the temporary guards to have been removed separately. Does not change
radio policy, dial, answer, restart services, or write to the modem.
"""
from pathlib import Path
import argparse,datetime,importlib.util,json,re,time

BASE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--call-report',required=True,help='Existing JSON basename in build/')
parser.add_argument('--output',required=True,help='New verification JSON basename in build/')
parser.add_argument('--allow-unregistered',action='store_true',help='Verify ordinary LTE policy while explicitly reporting unavailable IMS')
args=parser.parse_args()
for name in (args.call_report,args.output):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.json',name):
        raise SystemExit('Only a build report basename is accepted')
spec=importlib.util.spec_from_file_location('restore_cs',BASE/'restore-cs-test.py')
cp=importlib.util.module_from_spec(spec);spec.loader.exec_module(cp)
call=json.loads((BASE/'build'/args.call_report).read_text())
deadline=time.monotonic()+30
while True:
    state=json.loads(cp.shell('cat /dev/.mf79u-native-status.json'))
    if (state.get('imsReady') or (args.allow_unregistered and state.get('epsRegistration') in (1,5))) and not state.get('ringOnly') and not state.get('csOnly'):break
    if time.monotonic()>=deadline:raise SystemExit('Ordinary-SIM LTE/IMS policy did not become ready')
    time.sleep(1)
boot=cp.shell('cat /proc/sys/kernel/random/boot_id')
expected=json.loads(cp.shell('cat /mnt/userdata/mf79u/native-cs-radio-profile.json'))['sysconfig']
expected_flags=json.loads(cp.shell('cat /mnt/userdata/mf79u/native-cs-voice-flags.json'))['original']
profile_match=re.search(r'\^SYSCONFIG:\s*(\d+),(\d+),(\d+),(\d+)',cp.at('AT^SYSCONFIG?'))
if not profile_match:raise SystemExit('Radio profile readback absent')
profile=[int(v) for v in profile_match.groups()]
flags={}
for name in ('VOICE_SUPPORT','OPEN_VOICE_FLAG'):
    match=re.search(r'\+ZSET:\s*"'+name+r'",(\d+)\b',cp.at('AT+ZSET="'+name+'"'))
    if not match:raise SystemExit('Voice flag readback absent')
    flags[name]=int(match.group(1))
modules=sorted(row.split()[0] for row in cp.shell('cat /proc/modules').splitlines() if row.startswith('mf79u_cs_'))
route=json.loads((BASE/'build/cs-route-probe-live.json').read_text())
checks={
    'same_boot':boot==call['boot_id'],
    'same_native_sip_pids':all(state[k]==call['before'][k] for k in ('pid','sipPid')),
    'radio_profile_restored':profile==expected,
    'voice_flags_restored':flags==expected_flags,
    'temporary_ring_guard_removed':not state['ringOnly'],
    'cs_only_removed':not state['csOnly'],
    'ims_ready':state['imsReady'],
    'sip_idle':not json.loads(cp.shell('cat /dev/.mf79u-gateway-status.json')).get('activeCall'),
    'cs_sysfs_absent':cp.shell('test ! -e /sys/mf79u_cs/status && test ! -e /sys/mf79u_cs_mo/status && echo ABSENT')=='ABSENT',
    'channel_sampler_unloaded':'mf79u_cs_channels' not in modules,
    'original_callbacks_admission_and_mm_verified':route.get('boot_id')==boot and route.get('diagnostic_modules')==modules and all(route.get(k) is True for k in ('same_boot','unloaded','no_calls_or_cp_writes','restoration_verified')),
}
required={k:v for k,v in checks.items() if k!='ims_ready' or not args.allow_unregistered}
if not all(required.values()):raise SystemExit('Restoration verification failed: '+','.join(k for k,v in required.items() if not v))
route_name=args.output.removesuffix('.json')+'-route.json'
(BASE/'build'/route_name).write_text(json.dumps(route,indent=2)+'\n')
report={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'call_report':args.call_report,'after':state,'boot_id':boot,'radio_profile':profile,'voice_flags':flags,**checks,'inactive_pinned_modules':modules,'route_audit':route_name,'production_cs_audio_or_fallback':False,'pcm_contract_changed':False,'raw_flash_written':False}
report['ims_unregistered_explicitly_allowed']=args.allow_unregistered
path=BASE/'build'/args.output;path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
(BASE/'build'/route_name).chmod(0o600)
print(json.dumps(checks))

#!/usr/bin/env python3
"""Offline safety regression: rotated MT logs require an exact fresh route audit."""
from pathlib import Path
import importlib.util, json, tempfile

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('restore_guard',BASE/'restore-cs-test.py')
restore=importlib.util.module_from_spec(spec);spec.loader.exec_module(restore)
with tempfile.TemporaryDirectory() as directory:
    restore.ROOT=Path(directory);build=restore.ROOT/'firmware/mf79u/build';build.mkdir(parents=True)
    boot='fixture-current-boot';calls=[]
    audit={'same_boot':True,'unloaded':True,'no_calls_or_cp_writes':True,
           'restoration_verified':True,'boot_id':boot,'diagnostic_modules':['mf79u_cs_connect32']}
    profile=[27,0,1,2];flags={'VOICE_SUPPORT':0,'OPEN_VOICE_FLAG':0}
    def shell(command):
        if command=='cat /dev/.mf79u-gateway-status.json':return '{"activeCall":false}'
        if command.startswith('test -e /sys/'):return ''
        if command=='cat /proc/modules':return 'mf79u_cs_connect32 26119 1 - Live 0xbf655000'
        if command=='cat /proc/sys/kernel/random/boot_id':return boot
        if 'dmesg' in command:return '' # Earlier MT32 expiry rotated out.
        if command=='cat /proc/sysvipc/msg':return 'key msqid perms'
        if command.endswith('/native-cs-radio-profile.json'):return json.dumps({'sysconfig':profile})
        if command.endswith('/native-cs-voice-flags.json'):return json.dumps({'original':flags})
        if command=='cat /dev/.mf79u-native-status.json':return '{"ringOnly":true}'
        if command.startswith('rm -f '):calls.append('remove_cs_only');return ''
        raise AssertionError('Unexpected shell operation: '+command)
    def at(command):
        calls.append(command)
        if command=='AT^SYSCONFIG?':return '^SYSCONFIG: 27,0,1,2\r\nOK\r\n'
        for name in flags:
            if command=='AT+ZSET="'+name+'"':return '+ZSET: "'+name+'",0\r\nOK\r\n'
        return '\r\nOK\r\n'
    restore.shell=shell;restore.at=at
    cases=[('current_verified',{},True),('different_boot',{'boot_id':'older'},False),
           ('different_modules',{'diagnostic_modules':[]},False),
           ('active_or_changed_route',{'restoration_verified':False},False)]
    for name,changes,accepted in cases:
        (build/'cs-route-probe-live.json').write_text(json.dumps(dict(audit,**changes)))
        calls.clear()
        try:restore.main();outcome=True
        except RuntimeError:outcome=False
        assert outcome==accepted,(name,outcome)
        if not accepted:assert not calls,(name,'policy changed before rejection')
        else:assert 'AT^SYSCONFIG=27,0,1,2' in calls and calls[-1]=='remove_cs_only'
    report={'offline_only':True,'device_access':False,'rotated_mt_log':True,
            'current_verified_route_accepted':True,'wrong_boot_rejected_before_policy_change':True,
            'wrong_modules_rejected_before_policy_change':True,'unverified_route_rejected_before_policy_change':True}
    (BASE/'build/cs-restore-route-guard-selftest.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: rotated MT log, current audit, wrong boot/modules and unsafe route')

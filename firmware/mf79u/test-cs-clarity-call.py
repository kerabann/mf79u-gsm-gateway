#!/usr/bin/env python3
"""One authorized CS clarity comparison; test marker/stats removed on all exits."""
import argparse, datetime, importlib.util, json, re, subprocess, sys
from pathlib import Path
BASE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='live');args=p.parse_args()
assert re.fullmatch('[a-z0-9-]{1,40}',args.label)
receipt=BASE/'build'/('cs-clarity-call-'+args.label+'.json')
assert not receipt.exists(), 'Preserve the previous quality-test receipt'
# Read the private destination before any adb shell subprocess can inherit and
# consume stdin. Keep it in RAM and supply it explicitly to the single dialer.
destination=sys.stdin.buffer.readline(34)
assert re.fullmatch(rb'[0-9]{5,32}\n?',destination), 'Numeric destination required on stdin'
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
marker='/dev/.mf79u-cs-clarity-test';stats='/dev/.mf79u-cs-clarity-result.json'
assert t.shell('test -e '+marker+' && echo EXISTS')!='EXISTS'
assert t.shell('test -e '+stats+' && echo EXISTS')!='EXISTS'
n=json.loads(t.shell('cat /dev/.mf79u-native-status.json'))
assert n['callBackend']=='none' and n['voiceBackend']=='cs' and n['voiceReady']
baseline=json.loads((BASE/'build/cs-audio-quality-check.json').read_text())['ims_audio_baseline']
for name,remote in [('ims-userspace-ipsec.so','.mf79u-ims-userspace-ipsec.so'),('volte-private-ipc','.mf79u-volte-private')]:
    assert t.shell('md5sum /mnt/userdata/mf79u/'+remote).split()[0]==baseline[name]['device_md5']
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'profile':'cs-only +2.60dB at3kHz','ims_audio_unchanged':True,'speech_saved':False}
try:
    assert t.shell('umask 077; : > '+marker+'; echo ARMED')=='ARMED'
    result=subprocess.run([sys.executable,str(BASE/'test-sip-cellular-call.py'),
        '--authorized-single-dial','--expect-backend','cs','--label','cs-clarity-'+args.label,
        '--talk-seconds','25'],input=destination)
    destination=b''
    report['call_tool_exit']=result.returncode
    report['pcm_startup_error']=t.shell('cat /dev/.mf79u-cs-pcm-error.log')
    report['adapter_trace']=t.shell('cat /dev/.mf79u-cs-adapter-trace.log')
    if result.returncode:raise RuntimeError('CS comparison did not finish normally')
    report['levels']=json.loads(t.shell('cat '+stats))
finally:
    destination=b''
    t.shell('rm -f '+marker+' '+stats+' /dev/.mf79u-cs-adapter-trace.log')
    report['test_marker_removed']=t.shell('test -e '+marker+' && echo EXISTS')!='EXISTS'
    receipt.write_text(json.dumps(report,indent=2)+'\n')
print('CS-only clarity comparison complete; diagnostic marker/statistics removed. Listening result required.')

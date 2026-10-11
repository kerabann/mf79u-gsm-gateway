#!/usr/bin/env python3
"""Read-only fresh-boot proof for the installed B03 registration runtime."""
import argparse, datetime, hashlib, importlib.util, json, re, subprocess
from pathlib import Path

BASE=Path(__file__).resolve().parent
DATA='/mnt/userdata/mf79u'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--previous-boot',required=True)
p.add_argument('--label',default='live')
args=p.parse_args()
assert re.fullmatch('[0-9a-f-]{36}',args.previous_boot)
assert re.fullmatch('[a-z0-9-]{1,40}',args.label)
receipt=BASE/'build'/('registration-autoboot-'+args.label+'.json')
assert not receipt.exists(), 'Preserve previous boot proof; choose a new label'
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
boot=t.shell('cat /proc/sys/kernel/random/boot_id')
assert boot!=args.previous_boot, 'A fresh physical modem boot is required'
n=json.loads(t.shell('cat /dev/.mf79u-native-status.json'))
s=json.loads(t.shell('cat /dev/.mf79u-gateway-status.json'))
assert n['voiceMode']=='AUTO' and n['imsReady'] and n['voiceBackend']=='ims'
assert n['callBackend']=='none' and not s['activeCall'] and s['imsReady']
assert n['csPid']>1
assert json.loads(t.shell('cat '+DATA+'/settings.json'))['voiceMode']=='AUTO'
assert t.shell("grep '^voice_mode=' "+DATA+'/gateway.ini')=='voice_mode=AUTO'

def parent(pid):
    return int(re.search(r'^PPid:\s*(\d+)',t.shell(f'cat /proc/{pid}/status'),re.M)[1])
def owned(pid,path):
    assert t.shell(f'test /proc/{pid}/exe -ef {path} && echo OWNED')=='OWNED'
def rooted(pid):
    ancestors=[]
    for _ in range(8):
        assert pid>0
        command=t.shell(f'cat /proc/{pid}/cmdline').replace('\0',' ')
        assert not any(v in command for v in ('adbd','adb shell','/bin/sh -c'))
        ancestors.append(pid)
        if pid==1:return ancestors
        pid=parent(pid)
    raise AssertionError('Startup does not reach init')

owned(n['pid'],DATA+'/.mf79u-native-gateway')
owned(n['sipPid'],DATA+'/.mf79u-sip-gateway')
owned(n['csPid'],DATA+'/.mf79u-cs-voice')
assert parent(n['sipPid'])==n['pid'] and parent(n['csPid'])==n['pid']
supervisor=int(t.shell('cat /dev/.mf79u-native-supervisor.pid'))
assert parent(n['pid'])==supervisor
control=int(t.shell('cat /dev/.mf79u-control.pid'))
owned(control,DATA+'/.mf79u-control')
ancestry={'native':rooted(n['pid']),'control':rooted(control)}
artifacts={
 'native':(BASE/'build/mf79u-native-gateway',DATA+'/.mf79u-native-gateway'),
 'sip':(BASE/'build/modem-sip-gateway',DATA+'/.mf79u-sip-gateway'),
 'cs_adapter':(BASE/'build/mf79u-cs-voice',DATA+'/.mf79u-cs-voice'),
 'cs_pcm':(BASE/'build/mf79u-cs-pcm-bridge',DATA+'/.mf79u-cs-pcm-bridge'),
 'cs_driver':(BASE/'build/mf79u_cs_voice.ko',DATA+'/.mf79u-cs-voice.ko'),
 'ims_audio':(BASE/'build/ims-userspace-ipsec.so',DATA+'/.mf79u-ims-userspace-ipsec.so'),
 'ims':(BASE/'build/volte-private-ipc',DATA+'/.mf79u-volte-private'),
 'control':(BASE/'build/mf79u-control',DATA+'/.mf79u-control'),
 'start_native':(BASE/'start-native.sh',DATA+'/start-native.sh'),
}
hashes={}
for name,(local,remote) in artifacts.items():
    data=local.read_bytes();digest=t.shell('md5sum '+remote).split()[0]
    assert digest==hashlib.md5(data).hexdigest(), name+' differs from the current build'
    hashes[name]={'sha256':hashlib.sha256(data).hexdigest(),'device_md5':digest}
assert t.shell('cat /dev/.mf79u-cs-driver.md5')==hashes['cs_driver']['device_md5']
driver=t.shell('cat /sys/mf79u_cs_voice/session').split()
assert driver[:2]==['MF79U_CS_DRIVER','1'] and len(driver)==11
assert int(driver[2])>0 and list(map(int,driver[3:8]))==[0,0,0,0,0]
assert int(driver[9])==1 and int(driver[10])==0
assert 'mf79u_cs_voice ' in t.shell('cat /proc/modules')
assert 'MF79U_FBK_TEST' not in t.shell('iptables -S')
host=subprocess.check_output(['ps','-axo','command']).decode()
assert not any(re.search(r'\bpython\S* .*run-(usb|pbx)-gateway\.py',line) for line in host.splitlines())
log=t.shell('cat /dev/.mf79u-native.log')
events={k:int(v) for v,k in re.findall(r'NATIVE_GATEWAY elapsed=(\d+) event=([a-z_]+)',log)}
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'passed':True,'previous_boot':args.previous_boot,'boot':boot,'startup_ancestors':ancestry,
 'native':{k:n[k] for k in ('pid','sipPid','csPid','voiceMode','voiceBackend','imsReady','registrationState')},
 'cs_loaded_suspended':True,'temporary_filter_absent':True,'mac_relay_running':False,
 'artifact_hashes':hashes,'startup_events_seconds':events,'calls_or_sms_sent':False}
receipt.write_text(json.dumps(report,indent=2)+'\n')
print('PASS fresh boot: AUTO/IMS ready, verified CS loaded suspended, Control/native descendants of init, no Mac relay.')

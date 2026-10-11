#!/usr/bin/env python3
"""Bounded UMTS-only registration probe, with radio and supervisor restoration."""
import argparse, datetime, json, re, subprocess, time
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
p=argparse.ArgumentParser();p.add_argument('--label',default='20261010');args=p.parse_args()
assert re.fullmatch('[a-z0-9-]+',args.label)
RECEIPT=BASE/'build'/('umts-registration-live-'+args.label+'.json')
assert not RECEIPT.exists(), 'Preserve prior receipt'
def shell(c):
    return subprocess.check_output([str(ROOT/'outputs/adb'),'shell',c],timeout=20).decode().replace('\r','').strip()
def state(): return json.loads(shell('cat /dev/.mf79u-native-status.json'))
def at(c):
    p=subprocess.run([str(BASE/'build/cs-at-wait'),c,'0','8'],capture_output=True,timeout=15)
    s=p.stdout.decode(errors='replace').replace('\r','')
    lines=[x.strip() for x in s.splitlines() if x.strip().startswith(('+COPS:', '+CREG:', '+CGREG:', '+CEREG:', '^SYSINFO:', '^SYSCONFIG:', '+CFUN:', '+CSQ:')) or x.strip() in ('OK','ERROR') or x.strip().startswith('+CME ERROR:')]
    value='\n'.join(lines)
    report.setdefault('commands',[]).append({'command':c,'reply':value,'exit':p.returncode})
    checkpoint()
    return value
def checked(c,expected=None):
    s=at(c)
    if 'OK' not in s.splitlines() or (expected and expected not in s): raise RuntimeError('Failed command/readback: '+c)
    return s
def radio(v):
    at('AT+CFUN='+str(v))
    checked('AT+CFUN?', '+CFUN: '+str(v))
def checkpoint(): RECEIPT.write_text(json.dumps(report,indent=2)+'\n')
before=state()
assert before['imsReady'] and before['callBackend']=='none' and not before['csOnly'] and not before['ringOnly']
assert not json.loads(shell('cat /dev/.mf79u-gateway-status.json'))['activeCall']
supervisor=int(shell('cat /dev/.mf79u-native-supervisor.pid'))
pid=before['pid']
assert shell(f'test /proc/{pid}/exe -ef /mnt/userdata/mf79u/.mf79u-native-gateway && echo YES')=='YES'
assert 'start-native.sh' in shell(f'cat /proc/{supervisor}/cmdline')
boot=shell('cat /proc/sys/kernel/random/boot_id')
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before':before,'boot_id':boot,'no_dial_answer_sms':True,'samples':[]}
profile=checked('AT^SYSCONFIG?')
m=re.search(r'\^SYSCONFIG:\s*(\d+,\d+,\d+,\d+)',profile)
assert m and m[1]=='27,0,1,2'
original=m[1]
paused=False
try:
    shell(f'kill -STOP {supervisor}')
    paused=True
    shell(f'kill -TERM {pid}')
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        process=shell(f'cat /proc/{pid}/status 2>/dev/null')
        if not process or re.search(r'^State:\s+Z\b',process,re.M): break
        time.sleep(1)
    else: raise RuntimeError('Native cleanup did not complete')
    report['stopped']=state()
    assert report['stopped']['state']=='stopped'
    assert shell('cat /sys/mf79u_cs_voice/status')=='MF79U_CS 1 0 0 0 0 0 0'
    radio(0)
    checked('AT^SYSCONFIG=14,0,1,2')
    checked('AT^SYSCONFIG?', '^SYSCONFIG: 14,0,1,2')
    radio(1)
    start=time.monotonic()
    while time.monotonic()-start<90:
        sample={'elapsed':round(time.monotonic()-start,1)}
        for c in ('AT+CREG?','AT+CGREG?','AT+COPS?','AT^SYSINFO','AT+CSQ'):
            sample[c]=at(c)
        report['samples'].append(sample); checkpoint()
        cops=re.search(r'\+COPS:\s*\d+,\d+,"(\d+)",([2456])\b', sample['AT+COPS?'])
        reg=re.search(r'\+CREG:\s*\d+,([15])\b',sample['AT+CREG?'])
        if cops and reg:
            report['umts_registered']=True
            report['umts_serving_plmn']=cops[1]
            report['primetel_own_umts_registered']=cops[1]=='28020'
            break
        time.sleep(5)
    report.setdefault('umts_registered',False)
    report['test_profile_final']=checked('AT^SYSCONFIG?', '^SYSCONFIG: 14,0,1,2')
except Exception as e:
    report['test_error']=str(e)
finally:
    if paused:
        try:
            radio(0)
            checked('AT^SYSCONFIG='+original)
            checked('AT^SYSCONFIG?', '^SYSCONFIG: '+original)
            radio(1)
            report['profile_restored']=True
        except Exception as e: report['restore_error']=str(e)
        finally: shell(f'kill -CONT {supervisor}')
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            s=state()
            if s.get('imsReady') and s.get('state')=='ready' and s['pid']!=pid:
                report['after']=s; report['ims_restored']=True; break
            time.sleep(2)
        report.setdefault('ims_restored',False)
    report['same_boot']=shell('cat /proc/sys/kernel/random/boot_id')==boot
    report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    checkpoint()
print(json.dumps({k:report.get(k) for k in ('umts_registered','test_error','profile_restored','restore_error','ims_restored','same_boot')}))

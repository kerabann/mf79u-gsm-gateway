#!/usr/bin/env python3
"""Supervised physical AUTO fallback: block only operator IMS IPv4, no calls/SMS.

An owned temporary filter is removed on success or error. Successful fallback
leaves AUTO selected with CS ready; no permanent bearer/firewall change.
"""
import argparse, datetime, importlib.util, json, re, subprocess, time
from pathlib import Path

BASE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--label',default='live')
args=p.parse_args()
assert re.fullmatch('[a-z0-9-]{1,48}',args.label)
receipt=BASE/'build'/('registration-fallback-'+args.label+'.json')
assert not receipt.exists(), 'Preserve the preceding physical test receipt'
spec=importlib.util.spec_from_file_location('transfer',BASE/'device-transfer.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
def state():return json.loads(t.shell('cat /dev/.mf79u-native-status.json'))
def mode(value):subprocess.run(['python3',str(BASE/'set-registration-mode.py'),value],check=True,capture_output=True)

before=state();assert before['callBackend']=='none' and before['voiceBackend']=='cs'
assert not json.loads(t.shell('cat /dev/.mf79u-gateway-status.json'))['activeCall']
boot=t.shell('cat /proc/sys/kernel/random/boot_id')
chain='MF79U_FBK_TEST'
assert chain not in t.shell('iptables -S')
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'calls_or_sms_sent':False,'before':before,'states':[],'filter_removed':False}
owned=False;success=False
try:
 owned=True
 assert t.shell('set -e; iptables -N '+chain+'; iptables -A '+chain+' -j REJECT; iptables -I OUTPUT 2 -o wan5 -j '+chain+'; echo CREATED')=='CREATED'
 mode('AUTO');start=time.monotonic();last=None;attempt=False
 while time.monotonic()-start<210:
  s=state()
  assert (s['pid'],s['sipPid'],s['csPid'])==(before['pid'],before['sipPid'],before['csPid'])
  assert s['callBackend']=='none'
  scalar={k:s[k] for k in ('voiceMode','registrationMode','registrationState','voiceBackend','imsReady','fallbackReason')}
  if scalar!=last:
   report['states'].append(dict(elapsed=round(time.monotonic()-start,1),**scalar));last=scalar
  if s['registrationMode']=='VOLTE':attempt=True
  if attempt and s['voiceMode']=='AUTO' and s['voiceBackend']=='cs' and s['voiceReady']:
   assert s['fallbackReason']=='volte_registration_timeout', 'Expected failed IMS registration, not missing LTE'
   report['fallback']=s;break
  time.sleep(.5)
 else:raise RuntimeError('Physical fallback deadline exceeded')
 counters=t.shell('iptables -L '+chain+' -n -v -x')
 rows=[r.split() for r in counters.splitlines() if 'REJECT' in r]
 assert len(rows)==1 and int(rows[0][0])>0, 'The temporary rule did not reject any IMS traffic'
 report['ims_packets_rejected']=int(rows[0][0]);report['same_boot']=t.shell('cat /proc/sys/kernel/random/boot_id')==boot
 assert report['same_boot'];success=True
finally:
 if owned:
  t.shell('iptables -D OUTPUT -o wan5 -j '+chain+'; iptables -F '+chain+'; iptables -X '+chain)
 report['filter_removed']=chain not in t.shell('iptables -S')
 if not success:mode(before['voiceMode'])
 report['passed']=success and report['filter_removed']
 receipt.write_text(json.dumps(report,indent=2)+'\n')
print('PASS physical AUTO: failed VoLTE registration -> GSM CS, same boot/PIDs; temporary IMS filter removed.')

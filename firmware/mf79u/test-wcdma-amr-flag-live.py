#!/usr/bin/env python3
"""One bounded vendor-AMR hypothesis test; restore parameter and AUTO/IMS."""
from pathlib import Path
import argparse,subprocess,importlib.util,time,json,datetime,re,sys
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--label',required=True)
parser.add_argument('--amr-flag',choices=('0','1'),default='1')
parser.add_argument('--authorized-single-dial',action='store_true')
args=parser.parse_args()
assert args.authorized_single_dial and re.fullmatch('[a-z0-9-]{1,40}',args.label)
number=sys.stdin.buffer.readline(34).strip()
assert re.fullmatch(rb'[0-9]{5,32}',number), 'Numeric destination required on stdin'
number+=b'\n'
b=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('t',b/'device-transfer.py');t=importlib.util.module_from_spec(sp);sp.loader.exec_module(t)
def at(c):
 p=subprocess.run([str(b/'build/cs-at-wait'),c,'0','8'],capture_output=True,timeout=20)
 s=p.stdout.decode(errors='replace');assert '\r\nOK\r\n' in s,c
 return '\n'.join(x.strip() for x in s.splitlines() if x.startswith('+ZAMRSUP:') or x=='OK')
def mode(m):subprocess.run(['python3',str(b/'set-registration-mode.py'),m],check=True)
def ready(m):
 end=time.monotonic()+140
 while time.monotonic()<end:
  s=json.loads(next(x for x in t.shell('cat /dev/.mf79u-native-status.json').splitlines() if x.startswith('{')))
  g=json.loads(next(x for x in t.shell('cat /dev/.mf79u-gateway-status.json').splitlines() if x.startswith('{')))
  if s['voiceMode']==m and s['voiceReady'] and g.get('voiceReady') and g.get('voiceBackend')==('ims' if m=='AUTO' else 'cs') and (m!='AUTO' or s['imsReady']):return s
  time.sleep(1)
 raise RuntimeError('Registration deadline')
receipt=b/'build'/('wcdma-amr-flag-'+args.label+'.json')
assert not receipt.exists(), 'Preserve prior receipt'
r={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original':at('AT+ZAMRSUP?'),'hypothesis_only':True,'numbers_audio_saved':False}
assert '+ZAMRSUP: 0,0' in r['original']
s=json.loads(next(x for x in t.shell('cat /dev/.mf79u-native-status.json').splitlines() if x.startswith('{')));assert s['callBackend']=='none'
try:
 at('AT+ZAMRSUP='+args.amr_flag+',0');r['candidate']=at('AT+ZAMRSUP?');assert '+ZAMRSUP: '+args.amr_flag+',0' in r['candidate']
 mode('UMTS');r['registered']=ready('UMTS')
 print('READY: WCDMA native and SIP backend verified; one DIAL now.',flush=True)
 p=subprocess.run(['python3',str(b/'test-sip-cellular-call.py'),'--authorized-single-dial','--expect-backend','cs','--label','wcdma-amr-flag-'+args.label,'--talk-seconds','18'],input=number,capture_output=True,timeout=145);number=b''
 print(p.stdout.decode(),flush=True);r['call_test_exit']=p.returncode
 r['call_receipt_created']=(b/'build'/('sip-cellular-wcdma-amr-flag-'+args.label+'.json')).exists()
 r['attempted_calls']=int(r['call_receipt_created'])
 r['kernel_metadata']=t.shell('/mnt/userdata/mf79u/tools/busybox dmesg | grep MF79U_CS_MO | tail -100')
finally:
 # The call tester owns clearing; require idle before modifying radio/config.
 end=time.monotonic()+35
 while time.monotonic()<end:
  s=json.loads(next(x for x in t.shell('cat /dev/.mf79u-native-status.json').splitlines() if x.startswith('{')))
  if s['callBackend']=='none':break
  time.sleep(1)
 else:raise RuntimeError('Call still owned; no radio switch')
 at('AT+ZAMRSUP=0,0');r['restored_parameter']=at('AT+ZAMRSUP?');assert '+ZAMRSUP: 0,0' in r['restored_parameter']
 mode('AUTO');r['after']=ready('AUTO')
 receipt.write_text(json.dumps(r,indent=2)+'\n')
 print('AMR parameter and AUTO/IMS restored.',flush=True)

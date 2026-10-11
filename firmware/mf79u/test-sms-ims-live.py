#!/usr/bin/env python3
"""One explicitly authorized UI/REST SMS. Secrets/recipient stay in RAM.
The receipt is an at-most-once guard: never automatically retry this script.
No calls, radio changes, packet bodies, private queues or full log capture.
"""
import base64,datetime,getpass,json,subprocess,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BUILD=ROOT/'firmware/mf79u/build'
RECEIPT=BUILD/'sms-ims-live-send-once-20261011.json'
ADB=[str(ROOT/'outputs/adb')]
def shell(command):return subprocess.check_output(ADB+['shell',command],stderr=subprocess.PIPE,timeout=8).decode().replace('\r','').strip()
def probe():return json.loads(shell('/dev/.mf79u-ims-sms-probe --status'))
def runtime():return json.loads(shell('cat /dev/.mf79u-native-status.json'))
if RECEIPT.exists():raise SystemExit('Receipt exists: this authorized SMS must not be submitted again.')
pre=probe();r=runtime();assert pre['ready'] and r['voiceMode']=='VOWIFI' and r['imsAccess']=='WIFI' and r['callBackend']=='none'
password=getpass.getpass('Modem administrator password: ')
number=getpass.getpass('Authorized SMS recipient (not logged): ')
assert number.isdigit() and 3<=len(number)<=20
header='Basic '+base64.b64encode(('admin:'+password).encode()).decode();password=''
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def request(method,payload=None):
 req=urllib.request.Request('http://192.168.0.1/api/v1/sms/messages'+('?storage=modem' if method=='GET' else ''),method=method,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':header,'Content-Type':'application/json'})
 with opener.open(req,timeout=65) as response:return response.status,json.load(response)
_,view=request('GET');assert view['transport']=='SMSoIP'
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot':shell('cat /proc/sys/kernel/random/boot_id'),'authorizedSingleSMS':True,'transportBefore':pre,'imsAccess':r['imsAccess'],'uplink':r['vowifiUplink'],'httpSubmissionIssued':True,'rawFlash':False,'callInitiated':False,'recipientOrBodyRecorded':False}
with RECEIPT.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
print('Issuing the single authorized SMS through the firmware REST dispatcher.',flush=True)
started=time.monotonic()
try:
 code,result=request('POST',{'number':number,'text':'MF79U VoWiFi SMS test'})
 report['httpStatus']=code;report['submissionAccepted']=result.get('ok') is True
except urllib.error.HTTPError as e:
 report['httpStatus']=e.code;report['submissionAccepted']=False
 try:report['error']=json.loads(e.read()).get('error','Request failed')
 except Exception:report['error']='Request failed'
except Exception:
 report['submissionAccepted']=False;report['error']='HTTP completion unconfirmed; no retry performed'
number='';header='';report['elapsedSeconds']=round(time.monotonic()-started,3)
report['transportAfter']=probe();after=runtime();report['imsStillReady']=after['imsReady'];report['nativePidPreserved']=after['pid']==r['pid'];report['sipPidPreserved']=after['sipPid']==r['sipPid']
RECEIPT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

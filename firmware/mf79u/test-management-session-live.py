#!/usr/bin/env python3
"""Read-only management polling; credentials and cookies remain in process RAM."""
import getpass,http.cookiejar,json,subprocess,time,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
jar=http.cookiejar.CookieJar()
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def request(path,body=None):
 data=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request('http://192.168.0.1/api/'+path,data=data,headers={'Content-Type':'application/json','Origin':'http://192.168.0.1'})
 with client.open(req,timeout=15) as r:
  value=json.load(r)
  return value,r.headers
password=getpass.getpass('Existing modem administrator password: ')
request('login',{'password':password});password=None
adb=[str(ROOT/'outputs/adb'),'shell','cat /dev/.mf79u-control.pid']
def pid():return subprocess.check_output(adb,timeout=10).decode().strip()
initial=pid();start=time.monotonic();polls=0;renewed=True
while True:
 _,headers=request('session')
 renewed=renewed and 'Max-Age=1800' in headers.get('Set-Cookie','')
 request('status');polls+=1
 if time.monotonic()-start>=180:break
 time.sleep(8)
report={'seconds':round(time.monotonic()-start,1),'polls':polls,'allRequestsSucceeded':True,'browserCookieRenewed':renewed,'controlPIDStable':initial==pid(),'controlVersion':'0.10'}
(HERE/'build/management-session-live.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

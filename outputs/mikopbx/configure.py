#!/usr/bin/env python3
"""Configure this dedicated lab PBX via its API, inside the local container.
Credentials never appear on command lines or in printed API responses.
"""
import json
import ipaddress
import os
from pathlib import Path
import secrets
import subprocess

directory = Path(__file__).resolve().parent

def api(path, data=None, method=None):
    command = ['docker','exec','-i','mf79u-mikopbx','curl','-sS',
               '--max-time','45','http://127.0.0.1/pbxcore/api/v3/'+path]
    if data is not None:
        command += ['-X',method or 'POST','-H','Content-Type: application/json',
                    '--data-binary','@-']
    reply = subprocess.run(command, input=json.dumps(data).encode() if data is not None else None,
                           capture_output=True,check=True,timeout=50)
    result = json.loads(reply.stdout)
    if not result.get('result'):
        raise RuntimeError(path+': '+str(result.get('messages')))
    return result['data']

def list_records(path):
    data=api(path)
    return data['data'] if isinstance(data,dict) else data

net=api('network:getConfig')
flat={'internet_interface':str(net['internetInterfaceId']),'usenat':'1','disabled':'0',
      'extipaddr':'192.168.0.169','exthostname':'',
      'AUTO_UPDATE_EXTERNAL_IP':'0','EXTERNAL_SIP_PORT':'5060'}
for item in net['interfaces']:
    for key,value in item.items():
        if key.startswith('current') or key=='id':continue
        flat[f"{key}_{item['id']}"]=('1' if value else '0') if isinstance(value,bool) else str(value)
api('network:saveConfig',flat)
api('general-settings', {'RTPPortFrom':'10000','RTPPortTo':'10031',
                        'PBXFirewallEnabled':'0','PBXFail2BanEnabled':'0'},'PATCH')
providers=list_records('sip-providers')
existing=next((p for p in providers if p.get('description')=='MF79U USB'),None)
if existing:
    provider=api('sip-providers/'+existing['id'])
else:
    provider=api('sip-providers:getDefault')
provider.update(type='SIP',description='MF79U USB',host='192.168.0.1',port=5080,
                registration_type='none',username='mf79u',secret='',transport='udp',
                qualify=True,qualifyfreq=15,disabled=False,
                manualattributes='[endpoint]\nset_var=IGNORE_TIME=1\ndisallow=all\nallow=g722,ulaw\ndirect_media=no\nrtp_symmetric=yes\nforce_rport=yes\nrewrite_contact=yes')
# Docker Desktop presents modem-originated SIP as its current gateway IP.
# Keep the real modem host for outbound traffic; identify incoming NAT traffic.
hosts=provider.get('additionalHosts',[])
networks=json.loads(subprocess.check_output(['docker','inspect','--format',
                    '{{json .NetworkSettings.Networks}}','mf79u-mikopbx'],timeout=10))
for network in networks.values():
    gateway=network.get('Gateway')
    if not gateway:continue
    address=str(ipaddress.IPv4Address(gateway))+'/32'
    if not any(h.get('address')==address for h in hosts):hosts.append({'address':address})
provider['additionalHosts']=hosts
if existing:
    api('sip-providers/'+existing['id'],provider,'PUT')
else:
    provider.pop('id',None)
    provider=api('sip-providers',provider)
provider_id=provider['id']
routes=list_records('outbound-routes')
route=next((r for r in routes if r['rulename']=='MF79U authorized test'),None)
record={'rulename':'MF79U authorized test','providerid':provider_id,'priority':1,
        'numberbeginswith':'TEST_DESTINATION_LOCAL','restnumbers':0,'trimfrombegin':0,'prepend':'',
        'note':'Only the user-authorized test destination during development'}
if route:api('outbound-routes/'+str(route['id']),record,'PUT')
else:api('outbound-routes',record)
credentials_path=directory/'phone.json'
if credentials_path.exists():
    phone=json.loads(credentials_path.read_text())
else:
    phone={'username':'201','password':secrets.token_urlsafe(24),'host':'192.168.0.169','port':5060}
    fd=os.open(credentials_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(phone,f,indent=2);f.write('\n')
employee=next(e for e in list_records('employees') if e['number']=='201')
api('employees/'+str(employee['id']),{'user_username':'MF79U lab','sip_secret':phone['password'],
    'sip_enableRecording':False,'mobile_number':'','mobile_dialstring':'',
    'fwd_forwarding':'','fwd_forwardingonbusy':'','fwd_forwardingonunavailable':'',
    'sip_manualattributes':'[endpoint]\ndisallow=all\nallow=ulaw\ndirect_media=no'},'PATCH')
incoming=list_records('incoming-routes')
route=next((r for r in incoming if r['rulename']=='MF79U SIM'),None)
record={'rulename':'MF79U SIM','providerid':provider_id,'number':'','extension':'201',
        'priority':1,'timeout':30,'note':'Calls arriving from the SIM trunk'}
if route:api('incoming-routes/'+str(route['id']),record,'PUT')
else:api('incoming-routes',record)
report={'provider_id':provider_id,'modem':'192.168.0.1:5080','pbx':'192.168.0.169:5060',
        'extension':'201','codec':'G722','pcm_rate':16000,'rtp_clock':8000,
        'fallback_codec':'PCMU/8000','rtp_ports':'10000-10031',
        'web':'http://127.0.0.1:8180','sip_registration':'IP peer; no registration'}
(directory/'connection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

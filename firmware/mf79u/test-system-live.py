#!/usr/bin/env python3
"""Live System API/SSH checks; no real password, identity, call or SMS changes.
Temporary SSH credential is generated in RAM and removed in finally.
"""
import argparse,getpass,hashlib,http.cookiejar,json,re,secrets,subprocess,time,urllib.request,urllib.error
from pathlib import Path
import paramiko
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ADB=[str(ROOT/'outputs/adb'),'-s','123456789ABCDEF'];BASE='http://192.168.0.1';DATA='/mnt/userdata/mf79u'
def shell(cmd):return subprocess.check_output(ADB+['shell',cmd],stderr=subprocess.PIPE,timeout=25).decode().replace('\r','').strip()
def main(reboot):
 password=getpass.getpass('Existing administrator password: ');jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));csrf=''
 def api(path,method='GET',body=None):
  data=None if body is None else json.dumps(body).encode();r=urllib.request.Request(BASE+'/api/'+path,data=data,method=method,headers={'Origin':BASE,'Content-Type':'application/json','X-CSRF-Token':csrf})
  try:
   with client.open(r,timeout=35) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 code,result=api('login','POST',{'password':password});assert code==200,'Administrator login failed';csrf=result['csrf']
 code,info=api('system/info');assert code==200 and re.fullmatch(r'\d{15}',info.get('imei','')) and info['imeiWriteAvailable']
 assert info['gateway']['activeCall'] is False and info['gateway']['imsReady'] is True
 report={'login':True,'info':True,'localIMEIRead':True,'identityNotChanged':True,'adminPasswordNotChanged':True,'logs':{}}
 for source in ('native','ssh','kernel'):
  code,result=api('system/logs?source='+source);assert code==200 and len(result['text'])<30000;report['logs'][source]=True
 for path,method,body in [('password','POST',{'currentPassword':password,'newPassword':'fixture-mismatch','confirmPassword':'different'}),('imei','POST',{'imei':'0','confirm':True}),('reboot','POST',{'confirm':False}),('ssh','PUT',{'enabled':True,'password':'short','confirmPassword':'short'})]:
  code,_=api('system/'+path,method,body);assert code==400,'Validation failed: '+path
 assert not info['ssh']['enabled'] and not info['ssh']['passwordSet'],'Do not overwrite an existing SSH configuration'
 temporary=secrets.token_urlsafe(24);conn=None
 try:
  code,result=api('system/ssh','PUT',{'enabled':True,'password':temporary,'confirmPassword':temporary});assert code==200 and result['enabled'],'SSH enable failed'
  time.sleep(2)
  conn=paramiko.SSHClient();conn.set_missing_host_key_policy(paramiko.AutoAddPolicy());conn.connect('192.168.0.1',username='admin',password=temporary,allow_agent=False,look_for_keys=False,timeout=10,banner_timeout=10,auth_timeout=10)
  key=conn.get_transport().get_remote_server_key().asbytes();_,stdout,stderr=conn.exec_command('busybox --list');applets=stdout.read().decode().splitlines();assert stdout.channel.recv_exit_status()==0 and all(x in applets for x in ['vi','awk','find','tar','nc','ip','sha256sum','mkpasswd'])
  _,stdout,stderr=conn.exec_command("busybox ash -c 'echo $((2+3))'");assert stdout.read().strip()==b'5';report.update({'sshAuthenticated':True,'extendedBusyboxApplets':len(applets),'extendedShellArithmetic':True})
  bad=paramiko.SSHClient();bad.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  try:bad.connect('192.168.0.1',username='admin',password='invalid-fixture',allow_agent=False,look_for_keys=False,timeout=8,auth_timeout=8);raise RuntimeError('Wrong SSH password accepted')
  except paramiko.AuthenticationException:report['sshWrongPasswordRejected']=True
  finally:bad.close()
  if reboot:
   conn.close();conn=None;boot=shell('cat /proc/sys/kernel/random/boot_id');code,_=api('system/reboot','POST',{'confirm':True});assert code==202;start=time.monotonic();last=start
   while time.monotonic()-start<240:
    try:
     if shell('cat /proc/sys/kernel/random/boot_id')!=boot and json.loads(shell('cat /dev/.mf79u-gateway-status.json')).get('imsReady'):break
    except Exception:pass
    if time.monotonic()-last>25:print('Waiting for autonomous modem startup.',flush=True);last=time.monotonic()
    time.sleep(3)
   else:raise RuntimeError('Modem reboot did not become ready')
   code,result=api('login','POST',{'password':password});assert code==200;csrf=result['csrf']
   conn=paramiko.SSHClient();conn.set_missing_host_key_policy(paramiko.AutoAddPolicy());conn.connect('192.168.0.1',username='admin',password=temporary,allow_agent=False,look_for_keys=False,timeout=10,auth_timeout=10)
   assert conn.get_transport().get_remote_server_key().asbytes()==key;report.update({'rebootAPI':True,'autonomousSSHStartup':True,'persistentSSHHostKey':True,'autonomousIMSReady':True,'rebootSeconds':round(time.monotonic()-start,1)})
  # Leave a shell session open; disabling must terminate it too.
  channel=conn.get_transport().open_session();channel.exec_command('sleep 60')
  code,result=api('system/ssh','PUT',{'enabled':False,'password':'','confirmPassword':''});assert code==200 and not result['enabled'];time.sleep(2);assert not conn.get_transport().is_active(),'SSH session survived disabling';report['disableClosesSessions']=True
  rules=shell('iptables -S MF79U_WEB');rules6=shell('ip6tables -S MF79U_WEB');assert '--dport 22 -j REJECT' in rules and '--dport 22 -j DROP' in rules6;report['sshLANFirewall']=True
 finally:
  if conn:conn.close()
  try:api('system/ssh','PUT',{'enabled':False,'password':'','confirmPassword':''})
  finally:shell('rm -f '+DATA+'/ssh.password '+DATA+'/ssh.json')
 code,result=api('system/ssh');assert code==200 and not result['enabled'] and not result['passwordSet'];report['temporaryCredentialRemoved']=True
 (HERE/'build/system-live-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':p=argparse.ArgumentParser();p.add_argument('--reboot',action='store_true');main(p.parse_args().reboot)

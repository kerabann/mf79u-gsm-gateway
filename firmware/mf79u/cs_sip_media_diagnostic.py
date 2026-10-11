"""Owned diagnostic SIP endpoint and temporary PBX echo extension; no cellular dial.

The supervised CS wrapper owns the single authorized SIM call. This helper
only connects its already-active PCM to the existing laboratory PBX.
"""
from pathlib import Path
import hashlib,ipaddress,json,queue,re,subprocess,tempfile,threading,time
from ram_transfer import ram_push
BASE=Path(__file__).resolve().parent;BUILD=BASE/'build'
class Diagnostic:
 def __init__(self,radio,cellular_hangup=None):
  self.radio=radio;self.process=None;self.thread=None;self.events=queue.Queue();self.owned_extension=False;self.stop_event=threading.Event()
  self.context='SIP-TRUNK-51091984-incoming';self.extension='cs-audio-probe';self.remote='/dev/.mf79u-cs-sip-media-test';self.config='/dev/.mf79u-cs-sip-media.ini';self.files_owned=False
  self.result={'production_sip_unchanged':True,'synthetic_caller':True,'audio_saved':False,'control_is_diagnostic':True,'events':[]}
  self.cellular_hangup=cellular_hangup
 def hangup(self):
  if self.cellular_hangup and not self.result.get('cs_hangup_requested'):
   # The owner callback verifies the exact boot/module/single-call identity.
   # Never use global ATH or replay a dial after a failed SIP session.
   self.cellular_hangup();self.result['cs_hangup_requested']=True
 def cli(self,text):return subprocess.check_output(['docker','exec','mf79u-mikopbx','asterisk','-rx',text],timeout=10).decode()
 def command(self,text):
  if self.process and self.process.poll() is None:self.process.stdin.write((text+'\n').encode());self.process.stdin.flush()
 def read(self):
  for raw in self.process.stdout:
   line=raw.decode(errors='replace').strip()
   # Whitelist metadata; never preserve SIP messages, caller IDs or PCM.
   if line in ('GATEWAY_LISTENING','GATEWAY_READY','SIP_INCOMING_FORWARDED','SIP_MEDIA_CONNECTED','SIP_CONNECTED','ANSWER','HANGUP') or re.fullmatch(r'(?:SIP_ENDED \d+|PCM_(?:STATS|QUEUE|LEVEL) [a-z0-9_= ]+|GATEWAY_INIT_FAILED \d+|MF79U_DIAG_FAULT signal=[0-9a-f]{8} code=[0-9a-f]{8} pc=[0-9a-f]{8} lr=[0-9a-f]{8} sp=[0-9a-f]{8} address=[0-9a-f]{8})',line):
    self.result['events'].append(line);self.events.put(line)
    if line.startswith('MF79U_DIAG_FAULT '):self.result['failure']='Diagnostic SIP process fault; see address receipt'
 def expect(self,wanted,seconds=10):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if self.process.poll() is not None:raise RuntimeError('Diagnostic SIP exited')
   try:
    line=self.events.get(timeout=.1)
    if line==wanted:return
   except queue.Empty:pass
  raise RuntimeError('Diagnostic SIP event timeout: '+wanted)
 def scheduling(self):
  pid=self.radio.shell('cat /dev/.mf79u-cs-sip-media.pid')
  if not pid.isdigit():raise RuntimeError('Diagnostic SIP PID missing')
  rows=[]
  for line in self.radio.shell('cat /proc/'+pid+'/task/*/stat').splitlines():
   match=re.fullmatch(r'(\d+) \(([^)]*)\) (.*)',line)
   if not match:raise RuntimeError('Malformed thread metadata')
   fields=match[3].split()
   rows.append({'tid':int(match[1]),'name':match[2],'priority':int(fields[15]),'rt_priority':int(fields[37]),'policy':int(fields[38])})
  return rows
 def prepare(self):
  if '0 active channels' not in self.cli('core show channels count'):raise RuntimeError('Existing PBX call')
  if "'"+self.extension+"' =>" in self.cli('dialplan show '+self.extension+'@'+self.context):raise RuntimeError('PBX extension already owned')
  if self.radio.shell('test -e '+self.remote+' || test -e '+self.config+' || test -e /dev/.mf79u-cs-sip-media.pid; if test $? -eq 0; then echo EXISTS; fi')=='EXISTS':raise RuntimeError('Diagnostic SIP already owned')
  ports=self.radio.shell('/mnt/userdata/mf79u/tools/busybox netstat -lnu')
  if any(re.search(r':'+str(port)+r'\s',ports) for port in (5082,46010,46011,12004,12005)):raise RuntimeError('Diagnostic ports occupied')
  # Copy only non-secret routing fields, keeping the real gateway config intact.
  saved=dict(line.split('=',1) for line in self.radio.shell('cat /mnt/userdata/mf79u/gateway.ini').splitlines() if '=' in line)
  server=saved['server'];ipaddress.IPv4Address(server)
  if saved.get('role')!='TRUNK' or saved.get('transport')!='UDP':raise RuntimeError('This diagnostic requires the existing UDP PBX trunk')
  peers=saved.get('trusted_peers',server)
  for address in peers.split(','):ipaddress.IPv4Address(address)
  config='role=TRUNK\nserver='+server+'\nport='+str(int(saved['port']))+'\ntransport=UDP\nusername=cs-audio-probe\npassword=\nrealm=*\nregister=0\nincoming_user='+self.extension+'\nlocal_port=5082\nbind=192.168.0.1\ntrusted_peers='+peers+'\ncodecs=PCMU\n'
  saved.clear()
  for i,app in enumerate(('Answer()','Set(TIMEOUT(absolute)=25)','PlayTones(700)','Wait(2)','StopPlayTones()','Echo()','Hangup()'),1):
   self.owned_extension=True
   self.cli('dialplan add extension '+self.extension+','+str(i)+','+app+' into '+self.context)
   actual=self.cli('dialplan show '+self.extension+'@'+self.context)
   if not re.search(r'\b'+str(i)+r'\.\s+'+re.escape(app),actual):raise RuntimeError('PBX extension readback failed')
  self.files_owned=True
  with tempfile.TemporaryDirectory(prefix='mf79u-cs-sip-') as temp:
   p=Path(temp)/'config';p.write_text(config);p.chmod(0o600);ram_push([self.radio.ADB],p,self.config)
  binary=BUILD/'cs-sip-media-test';digest=hashlib.sha256(binary.read_bytes()).hexdigest()
  # /dev is tmpfs on this B03: the extra executable consumes RAM/swap.
  # A private userdata file lets Linux discard clean executable pages.
  cache='/mnt/userdata/mf79u/.cs-sip-diagnostic-'+digest[:12]
  expected=hashlib.md5(binary.read_bytes()).hexdigest()
  receipt=BUILD/'cs-sip-cache.json'
  if receipt.exists():
   old=json.loads(receipt.read_text());old_path=old.get('path','')
   owned_ram=re.fullmatch(r'/dev/\.mf79u-cs-sip-cache-[0-9a-f]{12}',old_path) and old.get('boot_id')==self.radio.shell('cat /proc/sys/kernel/random/boot_id')
   owned_file=re.fullmatch(r'/mnt/userdata/mf79u/\.cs-sip-diagnostic-[0-9a-f]{12}',old_path)
   if old_path!=cache and (owned_ram or owned_file):
    actual=self.radio.shell('md5sum '+old_path).split()
    if actual and actual[0]==old.get('md5'):self.radio.shell('rm -f '+old_path)
    else:raise RuntimeError('Previous diagnostic cache ownership could not be verified')
  actual=self.radio.shell('md5sum '+cache).split()
  if actual[:1]!=[expected]:
   if self.radio.shell('test -e '+cache+' && echo PRESENT')=='PRESENT':raise RuntimeError('Diagnostic code file checksum mismatch')
   space=self.radio.shell('df -k /mnt/userdata/mf79u').splitlines()[-1].split()
   if len(space)<6 or not space[-3].isdigit() or int(space[-3])<len(binary.read_bytes())//1024+1024:raise RuntimeError('Insufficient userdata space for diagnostic code')
   staging='/dev/.mf79u-cs-sip-staging';target=cache+'.tmp'
   if self.radio.shell('test -e '+target+' && echo PRESENT')=='PRESENT':raise RuntimeError('Diagnostic staging file already exists')
   try:
    ram_push([self.radio.ADB],binary,staging)
    self.radio.shell('umask 077; cp '+staging+' '+target+'; chmod 700 '+target+'; sync')
    if self.radio.shell('md5sum '+target).split()[:1]!=[expected]:raise RuntimeError('Diagnostic userdata code checksum mismatch')
    self.radio.shell('mv '+target+' '+cache+'; sync')
   finally:self.radio.shell('rm -f '+staging+' '+target)
  self.radio.shell('chmod 700 '+cache+'; ln -s '+cache+' '+self.remote)
  self.result['binary_cache']=cache;self.result['binary_storage']='userdata'
  receipt.write_text(json.dumps({'path':cache,'storage':'userdata','md5':expected,'boot_id':self.radio.shell('cat /proc/sys/kernel/random/boot_id')})+'\n')
  self.radio.shell('chmod 600 '+self.config+'; chmod 700 '+self.remote)
  self.result['sip_sha256']=hashlib.sha256((BUILD/'cs-sip-media-test').read_bytes()).hexdigest()
  self.process=subprocess.Popen([self.radio.ADB,'shell','umask 077; echo $$ > /dev/.mf79u-cs-sip-media.pid; exec '+self.remote+' --wideband --config '+self.config],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  threading.Thread(target=self.read,daemon=True).start();self.expect('GATEWAY_LISTENING');self.command('BACKEND cs');self.expect('GATEWAY_READY')
  self.result['threads_ready']=self.scheduling()
 def monitor(self):
  try:
   end=time.monotonic()+110;online=False
   while not self.stop_event.is_set() and time.monotonic()<end:
    state=self.radio.shell('test -e /sys/mf79u_cs_mo/pcm_info && cat /sys/mf79u_cs_mo/pcm_info')
    if state=='MF79U_CS_PCM 1 1 8000 160 320':online=True;break
    time.sleep(.2)
   if not online:raise RuntimeError('GSM PCM did not start')
   self.command('INCOMING');self.expect('SIP_MEDIA_CONNECTED',12);self.result['sip_media_connected']=True
   status=json.loads(self.radio.shell('cat /dev/.mf79u-cs-sip-status.json'))
   self.result['codec']=status.get('codec');self.result['voice_backend']=status.get('voiceBackend')
   end=time.monotonic()+(35 if self.cellular_hangup else 25)
   while not self.stop_event.is_set() and time.monotonic()<end:
    if self.cellular_hangup:
     while True:
      try:line=self.events.get_nowait()
      except queue.Empty:break
      if line=='HANGUP':
       self.result['sip_hangup_received']=True;self.hangup()
    if self.radio.shell('test -e /sys/mf79u_cs_mo/pcm_info && cat /sys/mf79u_cs_mo/pcm_info')!='MF79U_CS_PCM 1 1 8000 160 320':break
    time.sleep(.5)
   self.command('STATS');self.command('ENDED')
  except Exception as exc:
   self.result['failure']=str(exc);self.command('ENDED')
   try:self.hangup()
   except Exception:self.result['cs_hangup_cleanup_failed']=True
 def start(self):
  self.thread=threading.Thread(target=self.monitor,daemon=True);self.thread.start()
 def close(self):
  # Each resource is independent. USB loss must not skip PBX cleanup or
  # discard the SIP events already collected before a device reboot.
  errors={}
  def attempt(name,action):
   try:return action()
   except Exception as exc:errors[name]=type(exc).__name__;return None
  self.stop_event.set()
  if self.thread:self.thread.join(timeout=22)
  if self.thread and self.thread.is_alive():errors['monitor']='StillRunning'
  if self.process:
   for command in ('STATS','ENDED'):attempt(command,lambda command=command:self.command(command))
   time.sleep(.4);attempt('QUIT',lambda:self.command('QUIT'))
   try:self.process.wait(timeout=8)
   except subprocess.TimeoutExpired:
    def terminate_owned():
     pid=self.radio.shell('cat /dev/.mf79u-cs-sip-media.pid')
     if pid.isdigit() and self.remote in self.radio.shell('cat /proc/'+pid+'/cmdline'):self.radio.shell('kill -TERM '+pid)
     self.process.wait(timeout=5)
    attempt('process_stop',terminate_owned)
   self.result['sip_exit']=self.process.returncode
   attempt('stdin_close',self.process.stdin.close)
  if self.owned_extension:
   attempt('extension_remove',lambda:self.cli('dialplan remove extension '+self.extension+'@'+self.context))
   actual=attempt('extension_readback',lambda:self.cli('dialplan show '+self.extension+'@'+self.context))
   self.result['pbx_extension_removed']=actual is not None and "'"+self.extension+"' =>" not in actual
  if self.files_owned:attempt('ram_cleanup',lambda:self.radio.shell('rm -f '+self.remote+' '+self.config+' /dev/.mf79u-cs-sip-media.pid /dev/.mf79u-cs-sip-status.json /dev/.mf79u-cs-sip-status.tmp'))
  channels=attempt('pbx_idle',lambda:self.cli('core show channels count'))
  self.result['pbx_idle']=channels is not None and '0 active channels' in channels
  if errors:self.result['cleanup_errors']=errors;self.result.setdefault('failure','Diagnostic cleanup incomplete')
  return self.result

#!/usr/bin/env python3
"""Local UI layout fixture. No modem mutations or real credentials."""
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
BASE=Path(__file__).resolve().parent/'control/web'
settings={'version':1,'bootstrapSeconds':60,'voiceMode':'AUTO','internetSharing':False,'sip':{'role':'TRUNK','extension':'100','extensionPasswordSet':False,'server':'192.168.0.169','port':5060,'transport':'UDP','username':'fixture','passwordSet':False,'realm':'*','register':False,'incomingUser':'fixture','localPort':5080,'bind':'0.0.0.0','trustedPeers':['192.168.0.169'],'codecs':['PCMA'],'ca':''},'wifi':{'mode':'HOTSPOT','enabled':True,'hidden':False,'ssid':'UI fixture','security':'WPA2','passwordSet':False,'network':{'mode':'DHCP'}},'lan':{'mode':'STATIC','address':'192.168.0.1/24','subnet':'192.168.0.0/24','gateway':'192.168.0.1','poolStart':'192.168.0.2','poolEnd':'192.168.0.253','dns':[],'routes':[]}}
class H(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,v):
  data=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if self.path=='/api/session':return self.reply({'csrf':'fixture'})
  if self.path=='/api/settings':return self.reply(settings)
  if self.path=='/api/settings/credentials':return self.reply({'sipPassword':'','sipExtensionPassword':'','wifiPassword':''})
  if self.path=='/api/system/info':return self.reply({'model':'ZTE MF79U','controlVersion':'0.10','gateway':{'version':'0.8'},'runtime':{'version':'0.9'},'operatorCodecs':['AMR-WB','AMR-NB'],'sipCodecs':['Opus','G.722','PCMA','PCMU','G.729'],'pcm':'Mono PCM16LE 16000 Hz / 320 samples','native':True,'ssh':{'enabled':False,'running':False,'username':'admin','port':22,'passwordSet':False},'imei':'490154203237518','imeiWriteAvailable':True})
  if self.path.startswith('/api/sms?'):return self.reply({'messages':[],'capacity':{'sms_nv_total':100,'sms_nvused_total':0}})
  if self.path=='/api/status':
   cs=settings['voiceMode']=='CS'
   return self.reply({'radio':{'network_provider':'Layout fixture','network_type':'GSM' if cs else 'LTE','simcard_roam':'Home','modem_main_state':'modem_init_complete'},'gateway':{'running':True,'imsReady':not cs,'activeCall':False,'role':'TRUNK','registerMode':False},'runtime':{'voiceReady':True,'imsReady':not cs,'voiceBackend':'cs' if cs else 'ims','callBackend':'none','registrationMode':'CS' if cs else 'VOLTE','registrationState':'ready','voiceMode':settings['voiceMode'],'hostRelayRequired':False},'wifi':{'state':'ENABLED'},'interfaces':[],'internetSharing':False})
  path=BASE/('index.html' if self.path=='/' else self.path.lstrip('/'))
  if path.parent!=BASE or not path.is_file():self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',{'html':'text/html','js':'text/javascript','css':'text/css'}.get(path.suffix[1:],'text/plain'));self.end_headers();self.wfile.write(path.read_bytes())
 def do_PUT(self):
  if self.path=='/api/settings':settings.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))));return self.reply({'ok':True})
  self.send_error(404)
 def do_POST(self):self.rfile.read(int(self.headers.get('Content-Length',0)));return self.reply({'ok':True})
HTTPServer(('127.0.0.1',18091),H).serve_forever()

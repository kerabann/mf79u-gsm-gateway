#!/usr/bin/env python3
"""Checksummed USB artifact transfer for guarded device updates."""
from pathlib import Path
import hashlib,http.server,subprocess,threading,json,datetime
root=Path(__file__).resolve().parents[2];build=root/'firmware/mf79u/build';adb=[str(root/'outputs/adb')]
data='/mnt/userdata/mf79u';sd=data+'/sd'
def shell(c):return subprocess.check_output(adb+['shell',c],stderr=subprocess.PIPE,timeout=180).decode().replace('\r','').strip()
def push(p,target):
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   if self.path!='/artifact':self.send_error(404);return
   self.send_response(200);self.send_header('Content-Length',str(p.stat().st_size));self.end_headers()
   with p.open('rb') as f:
    while b:=f.read(65536):self.wfile.write(b)
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('192.168.0.169',18089),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:shell(data+'/tools/busybox wget -q -O '+target+' http://192.168.0.169:18089/artifact')
 finally:server.shutdown();server.server_close()
 if shell('md5sum '+target).split()[0]!=hashlib.md5(p.read_bytes()).hexdigest():raise RuntimeError('Checksum mismatch')

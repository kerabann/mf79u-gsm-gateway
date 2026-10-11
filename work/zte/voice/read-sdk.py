import io,urllib.request,tarfile,json,time
from pathlib import Path
URL='https://download.ztedevices.com/device/global/support/opensource/8/20181222_01/TSP7520V3_opensource_code.tgz'
SIZE=908902400
class Remote(io.RawIOBase):
 def __init__(self):self.pos=0;self.start=-1;self.buf=b'';self.requests=0
 def seekable(self):return True
 def readable(self):return True
 def tell(self):return self.pos
 def seek(self,n,whence=0):self.pos=n if whence==0 else self.pos+n if whence==1 else SIZE+n;return self.pos
 def read(self,n=-1):
  if n<0:n=SIZE-self.pos
  parts=[]
  while n and self.pos<SIZE:
   if not self.start<=self.pos<self.start+len(self.buf):
    self.start=self.pos//1048576*1048576
    req=urllib.request.Request(URL,headers={'Range':f'bytes={self.start}-{min(SIZE-1,self.start+1048575)}'})
    r=urllib.request.urlopen(req,timeout=30);assert r.status==206
    self.buf=r.read();self.requests+=1
   count=min(n,len(self.buf)-(self.pos-self.start));parts.append(self.buf[self.pos-self.start:self.pos-self.start+count]);self.pos+=count;n-=count
  return b''.join(parts)
root=Path('work/zte/voice/sdk-selected');root.mkdir(exist_ok=True)
remote=Remote();hits=[];total=0;last=time.monotonic()
with tarfile.open(fileobj=remote,mode='r:') as tf:
 for m in tf:
  low=m.name.lower()
  match=any(x in low for x in ['zte_audio','/voice','/volte','/amr','tinyalsa','/proslic','/slic/'])
  if match:
   hits.append({'name':m.name,'size':m.size});print(m.name,m.size,flush=True)
   if m.isfile() and m.size<2000000 and (low.endswith(('.c','.h','.config','.mk')) or low.endswith(('makefile','kconfig'))):
    target=root/m.name
    if '..' not in Path(m.name).parts and not Path(m.name).is_absolute():
     target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tf.extractfile(m).read());total+=m.size
  if time.monotonic()-last>30:print('progress',remote.pos,remote.requests,'requests',flush=True);last=time.monotonic()
Path('work/zte/voice/sdk-audio-index.json').write_text(json.dumps(hits,indent=2))
print('done',remote.requests,'requests',len(hits),'matches',total,'source bytes',flush=True)

import urllib.request,tarfile,json,time
from pathlib import Path
url='https://download.ztedevices.com/device/global/support/opensource/7/20200716_01/PTCL_MF79U_opensource_code.tgz'
root=Path('work/zte/voice/ptcl-selected');root.mkdir(exist_ok=True)
hits=[];index=[];last=time.monotonic()
r=urllib.request.urlopen(url,timeout=30)
with tarfile.open(fileobj=r,mode='r|gz') as tf:
 for m in tf:
  low=m.name.lower()
  index.append({'name':m.name,'size':m.size})
  if any(x in low for x in ['voice','volte','tinyalsa','/sound/','/audio','_audio','/amr','_amr','pcm','proslic','/slic']):
   hits.append({'name':m.name,'size':m.size})
   if m.isfile() and m.size<2000000 and (low.endswith(('.c','.h','.sh','.mk','.config')) or low.endswith(('makefile','kconfig'))):
    p=root/m.name
    if not Path(m.name).is_absolute() and '..' not in Path(m.name).parts:
     p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(tf.extractfile(m).read())
   if 'zte' in low or 'tsp' in low:print(m.name,m.size,flush=True)
  if time.monotonic()-last>30:
   print('progress',len(index),'members',m.name,flush=True);last=time.monotonic()
r.close()
Path('work/zte/voice/ptcl-member-index.json').write_text(json.dumps(index,indent=2))
Path('work/zte/voice/ptcl-audio-index.json').write_text(json.dumps(hits,indent=2))
print('DONE',len(index),'members',len(hits),'audio candidates',flush=True)

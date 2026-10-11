import urllib.request, tarfile, json, time
from pathlib import Path
url='https://download.ztedevices.com/device/global/support/opensource/7/20200716_01/PTCL_MF79U_opensource_code.tgz'
root=Path('work/zte/voice/platform-selected')
root.mkdir(exist_ok=True)
hits=[]; last=time.monotonic()
with urllib.request.urlopen(url, timeout=30) as response:
 with tarfile.open(fileobj=response, mode='r|gz') as tf:
  for m in tf:
   if m.isfile() and m.size<2000000 and ('/platform_sdk/' in m.name or '/cust/MF79U/MF79U/' in m.name) and ('config.linux' in m.name or '/linux_plat/' in m.name):
    rel=Path(m.name)
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('unsafe archive path')
    target=root/rel; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(tf.extractfile(m).read()); hits.append({'name':m.name,'size':m.size})
   if time.monotonic()-last>25:
    print('extracted',len(hits),'platform files',flush=True); last=time.monotonic()
(root/'index.json').write_text(json.dumps(hits,indent=2))
print('DONE',len(hits),'files',flush=True)

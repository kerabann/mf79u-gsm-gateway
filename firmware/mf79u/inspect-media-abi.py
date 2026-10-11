import re,json
from pathlib import Path
from elftools.elf.elffile import ELFFile
root=Path(__file__).resolve().parents[2]
binary=root/'work/zte/b03mod-extracted/bin/zte_volte_main'
with binary.open('rb') as f:
 e=ELFFile(f); sections=[(s['sh_addr'],s.data()) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_type']!='SHT_NOBITS']
def read(addr,n):
 for base,data in sections:
  if base<=addr and addr+n<=base+len(data): return data[addr-base:addr-base+n]
 return b''
def string(addr):
 for base,data in sections:
  if base<=addr<base+len(data):
   s=data[addr-base:addr-base+220].split(b'\0')[0]
   if len(s)>=5 and all(c==10 or c==13 or c==9 or 32<=c<=126 for c in s):return s.decode()
 return None
ls=(root/'firmware/mf79u/build/volte.disasm.txt').read_text().splitlines()
rows=json.load(open(root/'firmware/mf79u/build/voice-abi.json'))[1]['ioctls']
for row in rows:
 site=row['site']; idx=next(i for i,s in enumerate(ls) if s.strip()==site)
 hits=[]
 for line in ls[max(0,idx-45):idx+35]:
  m=re.search(r'\bldr(?:\.w)?\s+\w+,\s*\[pc[^]]*\].*\(([0-9a-f]+)',line)
  if not m:continue
  raw=read(int(m.group(1),16),4)
  if len(raw)!=4:continue
  ptr=int.from_bytes(raw,'little'); s=string(ptr)
  if s and s not in hits:hits.append(s)
 row['nearby_literal_strings']=hits
 print(row['request'],site.split(':')[0],hits)
(root/'firmware/mf79u/build/media-ioctl-context.json').write_text(json.dumps(rows,indent=2)+'\n')

"""Audit direct Thumb relocations against checksum-bound B03 kernel exports.

Linux 3.4 ARM's R_ARM_THM_CALL loader does not generate ARM/Thumb interworking.
Undefined NOTYPE symbols can otherwise bypass its function-mode rejection.
"""
from pathlib import Path
import hashlib,struct,json
ROOT=Path(__file__).resolve().parents[2]
KERNEL=ROOT/'work/zte/voice/ap_cpuap.bin'
KERNEL_SHA='a28f5ddbdeb3f4da80d367bd25fc7f6048222555057da2a2e3800364894c547f'
STRING_DELTA=0xc0047e40

def kernel_export(image,name):
 found=set();start=0;needle=name.encode()+b'\0'
 while True:
  start=image.find(needle,start)
  if start<0:break
  pointer=struct.pack('<I',start+STRING_DELTA);ref=0
  while True:
   ref=image.find(pointer,ref)
   if ref<0:break
   if 0x380004<=ref<0x38ee00 and not ref%4:
    value=struct.unpack_from('<I',image,ref-4)[0]
    if 0xc0000000<=value<0xc0640000:found.add(value)
   ref+=1
  start+=1
 if len(found)!=1:raise ValueError('Missing or ambiguous kernel export: '+name)
 return found.pop()

def mode_safe(relocation,target):
 return relocation not in (10,30) or bool(target&1)

def audit_module(path):
 profile=json.loads((ROOT/'firmware/mf79u/profiles/b03/kernel-abi.json').read_text())
 if profile['kernel_sha256']!=KERNEL_SHA:raise ValueError('Kernel profile differs')
 if KERNEL.exists():
  image=KERNEL.read_bytes()
  if hashlib.sha256(image).hexdigest()!=KERNEL_SHA:raise ValueError('Unrecognized B03 kernel image')
  resolve=lambda name:kernel_export(image,name)
 else:
  resolve=lambda name:profile['exports'][name]
 if resolve('memset')!=0xc010cb40 or resolve('__memzero')!=0xc010cc1d:
  raise ValueError('Kernel export anchors do not match')
 b=Path(path).read_bytes()
 if b[:7]!=b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H',b,18)[0]!=40:raise ValueError('ARM32 little-endian ELF required')
 off=struct.unpack_from('<I',b,32)[0];stride,count,names=struct.unpack_from('<HHH',b,46)
 if stride!=40 or count>256:raise ValueError('Unexpected ELF section table')
 sections=[struct.unpack_from('<10I',b,off+i*stride) for i in range(count)]
 pool=b[sections[names][4]:sections[names][4]+sections[names][5]]
 def section_name(s):return pool[s[0]:].split(b'\0',1)[0].decode()
 calls=[]
 for s in sections:
  if s[1]!=9:continue # SHT_REL
  symbols=sections[s[6]];strings=sections[symbols[6]];string_pool=b[strings[4]:strings[4]+strings[5]]
  for p in range(s[4],s[4]+s[5],8):
   at,info=struct.unpack_from('<II',b,p);kind=info&255
   if kind not in (10,30):continue
   symbol=struct.unpack_from('<IIIBBH',b,symbols[4]+(info>>8)*16)
   if symbol[5]!=0:continue
   name=string_pool[symbol[0]:].split(b'\0',1)[0].decode();target=resolve(name)
   calls.append({'section':section_name(s),'offset':hex(at),'symbol':name,
                 'symbol_type':symbol[3]&15,'relocation':kind,'target':hex(target),
                 'target_mode':'thumb' if target&1 else 'arm','safe':mode_safe(kind,target)})
 return {'kernel_sha256':KERNEL_SHA,'module_sha256':hashlib.sha256(b).hexdigest(),
         'direct_thumb_calls':calls,'safe':all(c['safe'] for c in calls)}

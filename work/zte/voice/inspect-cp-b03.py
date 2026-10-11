#!/usr/bin/env python3
"""Offline exact-B03 section mapping and bounded disassembly."""
from pathlib import Path
import struct,hashlib,argparse
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
root=Path(__file__).resolve().parents[3]
p=root/'work/zte/b03mod-extracted/lib/cpko/cpko.ko'
data=p.read_bytes()
assert hashlib.sha256(data).hexdigest()=='ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'
with p.open('rb') as f:
 e=ELFFile(f)
 sections={s.name:(s['sh_offset'],s['sh_size']) for s in e.iter_sections()}
bases={'.text':0xbf000000,'.rodata':0xbf4f5000,'.rodata.str1.1':0xbf53a000,'.data':0xbf55a000,'.bss':0xbf59e000}
def off(va):
 for n,b in bases.items():
  o,z=sections[n]
  if b<=va<b+z:return o+va-b
 raise ValueError(hex(va))
def string(va):
 try:
  o=off(va);end=data.index(0,o,min(len(data),o+180));s=data[o:end].decode('ascii')
  if s and all(32<=ord(c)<127 or c in '\r\n\t' for c in s):return repr(s)
 except (ValueError,UnicodeDecodeError):pass
 return ''
def refs(va):
 pat=struct.pack('<I',va);r=[];pos=0
 while True:
  pos=data.find(pat,pos)
  if pos<0:break
  r.append(hex(pos));pos+=1
 return r
parser=argparse.ArgumentParser();parser.add_argument('--slice',action='append',default=[]);parser.add_argument('--string',action='append',default=[]);parser.add_argument('--words',action='append',default=[]);args=parser.parse_args()
for s in args.string:
 pat=s.encode()+b'\0';pos=data.find(pat)
 while pos>=0:
  for n,b in bases.items():
   o,z=sections[n]
   if o<=pos<o+z: print(s,hex(pos),hex(b+pos-o),'refs',refs(b+pos-o))
  pos=data.find(pat,pos+1)
for s in args.words:
 a,z=[int(x,0) for x in s.split(':')]
 for va in range(a,a+z,4):
  v=struct.unpack_from('<I',data,off(va))[0];print(f'{va:08x}: {v:08x} {string(v)}')
for s in args.slice:
 a,z=[int(x,0) for x in s.split(':')];md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN);md.detail=True
 print(f'-- {a:08x} --')
 for ins in md.disasm(data[off(a):off(a)+z],a):
  extra=''
  if ins.mnemonic in ('ldr','ldr.w') and '[pc,' in ins.op_str:
   literal=((ins.address+4)&~3)+ins.operands[1].mem.disp
   try:
    v=struct.unpack_from('<I',data,off(literal))[0];extra=f' = {v:08x} {string(v)}'
   except ValueError:pass
  print(f'{ins.address:08x} {ins.mnemonic:<9} {ins.op_str}{extra}')

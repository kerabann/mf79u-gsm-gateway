#!/usr/bin/env python3
"""Extract bounded shared-RAM windows from exact B03 pointer initialization.

Only offline emulation. These ranges are unclassified and do not establish PCM
ownership. A window ends at the next pointer and is at most160 halfwords.
"""
from pathlib import Path
import hashlib,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'firmware/mf79u/build'
source=ROOT/'work/zte/b03mod-extracted/lib/cpko/cpko.ko'
sha=hashlib.sha256(source.read_bytes()).hexdigest()
assert sha=='ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0xbf000000,0x620000)
u.mem_map(0x30000000,0x10000);u.mem_map(0x31000000,0x1000)
with source.open('rb') as f:
    elf=ELFFile(f)
    for name,base in [('.text',0xbf000000),('.rodata',0xbf4f5000),
                      ('.rodata.str1.1',0xbf53a000),('.data',0xbf55a000)]:
        u.mem_write(base,elf.get_section_by_name(name).data())
u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_SP,0x30008000)
u.reg_write(UC_ARM_REG_LR,0x31000001)
u.emu_start(0xbf3e9f4d,0x31000000,count=2000)
assert u.reg_read(UC_ARM_REG_PC)==0x31000000
slots=[]
for i in range(68):
    slot=0xbf59f3f8+4+8*i
    address=struct.unpack('<I',u.mem_read(slot,4))[0]
    assert 0xfad01000<=address<0xfad02800 and address%2==0
    slots.append(dict(slot=hex(slot),address=hex(address)))
unique=sorted({int(s['address'],0) for s in slots})
windows=[]
for a,b in zip(unique,unique[1:]):
    if a<0xfad014ba:continue  # exclude mailboxes, controls and short encoded frames
    count=min((b-a)//2,160)
    if count<64:continue
    slot=next(int(s['slot'],0) for s in slots if int(s['address'],0)==a)
    windows.append(dict(slot=hex(slot),address=hex(a),halfwords=count,
                        next_pointer=hex(b),ownership_verified=False))
assert windows and len(windows)<=16
report=dict(offline_only=True,device_access=False,source_sha256=sha,
    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    initializer='0xbf3e9f4d',connection=0,pointer_slots=slots,
    windows=windows,pcm_classification_verified=False)
path=BUILD/'b03-dsp-pcm-windows.json';path.write_text(json.dumps(report,indent=2)+'\n')
rows=['/* Unclassified B03 SRAM, bounded by the next initialized pointer. */',
      '#define CS_PCM_WINDOW_COUNT '+str(len(windows))+'U',
      'static const unsigned int cs_pcm_windows[][3]={']
rows += ['{'+w['slot']+'U,'+w['address']+'U,'+str(w['halfwords'])+'U},' for w in windows]
rows += ['};','#define CS_PCM_WINDOW_REPORT_SHA256 "'+hashlib.sha256(path.read_bytes()).hexdigest()+'"','']
(BUILD/'cs-dsp-pcm-windows.h').write_text('\n'.join(rows))
print(json.dumps(dict(windows=windows,device_access=False)))

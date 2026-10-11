#!/usr/bin/env python3
"""Execute the exact B03 N(SD) allocator offline; no device or radio access."""
from pathlib import Path
import hashlib, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR

BASE=Path(__file__).resolve().parent
source=BASE.parents[1]/'work/zte/b03mod-extracted/lib/cpko/cpko.ko'
digest=hashlib.sha256(source.read_bytes()).hexdigest()
assert digest=='ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'
with source.open('rb') as f:
    code=ELFFile(f).get_section_by_name('.text').data()
helper=code[0x29be70:0x29bea8]
assert helper[:8]==bytes.fromhex('10b50b4b98470b4b')
assert struct.unpack('<II',helper[-8:])==(0xbf4c1801,0xbf5ffe9c)
results=[]
for sim in range(2):
    for initial in range(4):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for addr in (0xbf29b000,0xbf4c1000,0xbf5ff000,0xc1000000,0xc1001000,0xc2000000):
            u.mem_map(addr,0x1000)
        u.mem_write(0xbf29be70,helper)
        u.mem_write(0xbf4c1800,bytes.fromhex('7047')) # SIM context stub: bx lr
        u.mem_write(0xbf5ffda4,struct.pack('<II',0xc1000000,0xc1001000))
        for i in range(2):u.mem_write(0xc1000000+i*0x1000,bytes([initial,0xee]))
        u.reg_write(UC_ARM_REG_SP,0xc2000ff0)
        writes=[]
        def context(uc,address,size,_):
            if address==0xbf4c1800:uc.reg_write(UC_ARM_REG_R0,sim)
        def written(uc,access,address,size,value,_):
            if address<0xc2000000:writes.append((address,size,value))
        u.hook_add(UC_HOOK_CODE,context);u.hook_add(UC_HOOK_MEM_WRITE,written)
        observed=[]
        for count in range(6):
            u.reg_write(UC_ARM_REG_LR,0xc2000001)
            u.emu_start(0xbf29be71,0xc2000000,count=80)
            observed.append(u.reg_read(UC_ARM_REG_R0))
            assert observed[-1]==(initial+count)%4
        selected=0xc1000000+sim*0x1000
        assert all(a in (selected,selected+1) and s==1 for a,s,v in writes)
        assert bytes(u.mem_read(0xc1000000+(1-sim)*0x1000,2))==bytes([initial,0xee])
        results.append({'sim':sim,'initial':initial,'returned':observed,'isolated_context':True})
r={'passed':True,'device_access':False,'source_sha256':digest,
   'helper_sha256':hashlib.sha256(helper).hexdigest(),'helper':'0xbf29be71',
   'sim_context_stubbed':True,'cases':results}
(BASE/'build/cs-nsd-b03-offline.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(results),'device_access':False}))

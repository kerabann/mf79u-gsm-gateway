"""Execute checksum-bound B03 bearer/QoS paths offline. No device/network IO."""
import hashlib
import io
import json
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
binary = BASE / 'build/stock-rootfs/bin/zte_volte_main'
recipe = json.loads((BASE / 'profiles/b03/private-ims-patch.json').read_text())
digest = hashlib.sha256(binary.read_bytes()).hexdigest()
assert digest == recipe['source_sha256'], 'Unsupported B03 executable'
patched=bytearray(binary.read_bytes())
for patch in recipe['patches']:
    old,new=bytes.fromhex(patch['old']),bytes.fromhex(patch['new']);offset=patch['offset']
    assert patched[offset:offset+len(old)]==old and len(old)==len(new)
    patched[offset:offset+len(old)]=new
assert hashlib.sha256(patched).hexdigest()==recipe['result_sha256']
with io.BytesIO(patched) as stream:
    elf = ELFFile(stream)
    segments = [(s['p_vaddr'], s['p_memsz'], s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']

STOP, STACK, INPUT, OUTPUT, CONTEXT = 0x200000, 0x210000, 0x220000, 0x221000, 0x222000
CALL = 0xd4f10 + 0x8d8
TIMER = 0xc6e08

class B03:
    def __init__(self):
        self.u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self.u.mem_map(0x8000, 0x1f8000)
        self.u.mem_map(STOP, 0x40000)
        for at, size, data in segments:
            self.u.mem_write(at, data)
        self.calls = []
        self.stubs = {0x41e50:lambda:0, 0x6e618:lambda:0, 0x6e624:lambda:1,
                      0x38350:self.cid, 0x383a4:lambda:7,
                      0x9ea4:self.memset, 0x33034:self.copy, 0x9dc0:self.copy,
                      0x9cb0:self.strstr, 0xa25c:self.strlen, 0x9c3c:lambda:0}
        self.u.hook_add(UC_HOOK_CODE, self.hook)
        self.put(TIMER+12, 0xffffffff)
    def get(self, at):return struct.unpack('<I',self.u.mem_read(at,4))[0]
    def put(self, at, val):self.u.mem_write(at,struct.pack('<I',val&0xffffffff))
    def reg(self, n):return self.u.reg_read((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)[n])
    def cstr(self, at):
        out=bytearray()
        for i in range(4096):
            c=self.u.mem_read(at+i,1)[0]
            if not c:return bytes(out)
            out.append(c)
        raise AssertionError('Unbounded fixture string')
    def cid(self):self.put(self.reg(0),5);return 0
    def memset(self):
        self.u.mem_write(self.reg(0),bytes([self.reg(1)&255])*self.reg(2));return self.reg(0)
    def copy(self):
        self.u.mem_write(self.reg(0),bytes(self.u.mem_read(self.reg(1),self.reg(2))));return self.reg(0)
    def strstr(self):
        pos=self.cstr(self.reg(0)).find(self.cstr(self.reg(1)))
        return 0 if pos<0 else self.reg(0)+pos
    def strlen(self):return len(self.cstr(self.reg(0)))
    def hook(self, u, at, size, _):
        if at in self.stubs:
            value=self.stubs[at]()
            u.reg_write(UC_ARM_REG_R0,value&0xffffffff)
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        elif at < 0xb000:
            raise AssertionError('Unexpected external call '+hex(at))
    def run(self, at, *args, end=STOP):
        self.u.reg_write(UC_ARM_REG_SP,STACK+0xff00)
        self.u.reg_write(UC_ARM_REG_LR,STOP|1)
        for i,value in enumerate(args):self.u.reg_write(UC_ARM_REG_R0+i,value)
        self.u.emu_start(at|1,end,count=30000)
        assert self.u.reg_read(UC_ARM_REG_PC)==end, 'Fixture instruction limit'
        return self.reg(0)
    def event(self,text):
        value=text.encode();self.u.mem_write(INPUT,value+b'\0')
        return self.run(0xe390,0,INPUT,len(value))

results=[]
b=B03()
assert b.event('\r\n+CGEV: ME ACT 5,6\r\n')==0
assert b.get(0xc6f1c)==1 and b.get(0xc6fe4)==0 and b.get(0xc5b74)==6
assert b.event('\r\n+CGEV: ME DEACT 5,7\r\n')==0 and b.get(0xc6f1c)==1
assert b.event('\r\n+CGEV: ME DEACT 5,6\r\n')==0 and b.get(0xc6f1c)==0
assert b.event('\r\n+CGEV: ME ACT 4,6\r\n')==0 and b.get(0xc6f1c)==0
results.append('exact vendor CGEV parser/handler: primary CID, normal account, secondary CID and release matching')

# The real setter cancels an active timer and calls precondition completion.
b=B03();b.put(0xc5e98,1);b.put(TIMER+4,0);b.put(TIMER+12,1)
def cancel():b.calls.append('cancel_timer');b.put(b.reg(0)+12,0xffffffff);return 0
def complete():b.calls.append('complete_preconditions');return 0
b.stubs.update({0x77bac:cancel,0x16688:complete})
b.event('\r\n+CGEV: ME ACT 5,6\r\n')
assert b.calls==['cancel_timer','complete_preconditions'] and b.get(0xc6f1c)==1
results.append('real bearer setter cancels active QoS timer and enters precondition completion')

# Execute the exact 183 decision block, with fixture call-info getters.
for ready in (0,1):
    b=B03();b.put(0xc5e98,1);b.put(0xc6f1c,ready)
    b.put(CONTEXT+0x60,183);b.put(OUTPUT+0x4c,0)
    sp=STACK+0xff00;b.put(sp+0x1c,OUTPUT)
    b.u.reg_write(UC_ARM_REG_R6,CONTEXT);b.u.reg_write(UC_ARM_REG_R4,0)
    b.stubs[0x1d4b8]=lambda:1
    b.stubs[0x1d570]=lambda:0
    def schedule():b.calls.append(('schedule',b.reg(1)));return 0
    b.stubs[0x14480]=schedule
    b.run(0x1b802,end=0x1b878)
    assert b.calls==([] if ready else [('schedule',6000)])
results.append('real 183 branch: missing resources schedules 6000ms; ready resources skip that timer')

# PRACK completion calls the existing EPS/precondition completion even if
# readiness was announced before 183, so no timing-dependent URC is needed.
for ready in (0,1):
    b=B03();b.put(0xc5e98,1);b.put(0xc6f1c,ready)
    b.put(CONTEXT+0x6c,4);b.put(OUTPUT+0x4c,0)
    b.put(STACK+0xff00+0x1c,OUTPUT)
    b.u.reg_write(UC_ARM_REG_R6,CONTEXT);b.u.reg_write(UC_ARM_REG_R4,0)
    b.stubs[0x16688]=lambda:(b.calls.append('complete_preconditions') or 0)
    b.run(0x1c0c6,end=0x1c0e2)
    assert b.calls==(['complete_preconditions'] if ready else [])
results.append('real completed-transaction branch re-enters precondition completion for already-ready bearer')

# Execute the real precondition completion body with synthetic early-dialog
# data. Only the final SIP transport/UPDATE boundary is intercepted.
b=B03();b.put(0xc6f1c,1);b.put(0xc5e98,1)
table=0xd4f10
b.put(table+0x8f0,OUTPUT);b.put(OUTPUT+0x50,1)
b.put(table+0x924,0);b.put(table+0x1838,0)
b.put(table+0x1850,3);b.put(table+0x1870,3);b.put(table+0x187c,0)
b.put(table+0x1844,0);b.put(table+0x1860,3);b.put(table+0x1864,2)
b.put(CONTEXT+0x40,1)
b.stubs.update({0x14770:lambda:CONTEXT,0x13820:lambda:0,0x13844:lambda:0,
                0x76a1a:lambda:0,0x22814:lambda:0})
def info():
    b.put(b.reg(1)+4,0);b.put(b.reg(1)+0x44,3);return 0
def update():b.calls.append('send_update');return 0
b.stubs.update({0x73f2c:info,0x75abc:update})
b.run(0x16688,0)
assert b.calls==['send_update'] and b.get(table+0x1838)==3
assert b.get(CONTEXT+0x40)==0 and b.get(CONTEXT)==2
assert [b.get(table+off) for off in (0x1844,0x1860,0x1864)]==[0,3,2]
results.append('real precondition completion marks local sendrecv and sends UPDATE while preserving remote mandatory/unmet conditions')

report={'passed':True,'physicalDeviceAccess':False,'networkAccess':False,
        'sourceSHA256':digest,'privateSHA256':recipe['result_sha256'],'cases':results,
        'limits':'Vendor code fragments executed with explicit libc, account, call-info and completion boundary stubs; not an end-to-end call.'}
(ROOT/'reports/vowifi-qos-b03-offline.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

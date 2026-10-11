#!/usr/bin/env python3
"""Trace the real vp_VoiceI2sStart offline with explicit DMA/data simulation.

The frozen Open/Enable emulator and its receipt are not modified. Buffer
availability, IRQ registration and DMA transport are synthetic, never B03
hardware evidence. Actual driver control writes remain in the trace.
"""
from pathlib import Path
import ast, hashlib, json, sys

ROOT=Path(__file__).resolve().parents[3]
source=Path(__file__).with_name('emulate-mf283u-voice-open.py')
EXPECTED='369365d41e3dc2e3785deaba22e5689c0c60aba242a9faf2fc49f9cf464c4beb'
assert hashlib.sha256(source.read_bytes()).hexdigest()==EXPECTED
tree=ast.parse(source.read_text(),filename=str(source))
tree.body=[n for n in tree.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
    ((isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text')
     or (isinstance(n.value.func,ast.Name) and n.value.func.id=='print')))]
receipt=ROOT/'firmware/mf79u/build/mf283u-full-voice-open-port-tone-emulation.json'
receipt_sha=hashlib.sha256(receipt.read_bytes()).hexdigest()
patch=ast.parse('''
baseline_hook=hook
additional_stubs=[]
def hook(uc,pc,size,unused):
    a=[uc.reg_read(r) for r in regs]
    if pc in (0x23f026c8,0x23f026d8):
        # Reference bytes are BX LR: preserve arguments, execute the real stub.
        return
    if 0x23f141d8<=pc<0x23f14a00:
        # OS DMA/IRQ service region, separate from the real I2S driver.
        # No DMA-engine register writes are represented by this model.
        additional_stubs.append(dict(pc=hex(pc),args=a,kind='synthetic_os_dma_irq_service'))
        uc.reg_write(UC_ARM_REG_R0,0)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if pc in (0x24781704,0x24781acc,0x2478239c,0x24782408):
        # Expose a synthetic available block to finish the real startup path;
        # samples are not read from a physical peripheral.
        first=0 if pc in (0x2478239c,0x24782408) else 1
        uc.mem_write(a[first],struct.pack('<I',0x30080000))
        uc.mem_write(a[first+1],struct.pack('<I',320))
        additional_stubs.append(dict(pc=hex(pc),args=a,kind='synthetic_buffer_availability'))
        uc.reg_write(UC_ARM_REG_R0,0)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if pc in (0x24782370,0x247814e4):
        additional_stubs.append(dict(pc=hex(pc),args=a,kind='synthetic_buffer_commit'))
        uc.reg_write(UC_ARM_REG_R0,0)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    baseline_hook(uc,pc,size,unused)
''').body
index=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
           and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='hook_add')
tree.body[index:index]=patch
ast.fix_missing_locations(tree)
ns={'__file__':str(source),'__name__':'__voice_start_baseline__'};saved_argv=sys.argv
try:
    sys.argv=[str(source),'--port-tone'];exec(compile(tree,str(source),'exec'),ns)
finally:sys.argv=saved_argv
mmio_start=len(ns['mmio']);command_start=len(ns['commands']);error=None;result=None
try:result=ns['call']('full_voice_data_start',0x24783410)
except Exception as exc:error=str(exc)
assert hashlib.sha256(receipt.read_bytes()).hexdigest()==receipt_sha
report=dict(offline_only=True,device_access=False,source_sha256=ns['EXPECTED'],
    baseline_generator_sha256=EXPECTED,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    baseline_receipt_unchanged=True,synthetic_os_dma_and_buffers=True,
    b03_compatibility_verified=False,function_address='0x24783410',result=result,error=error,
    simulated_start_completed=result==0 and error is None,
    simulated_mmio_writes=ns['mmio'][mmio_start:],
    dsp_commands=ns['commands'][command_start:],additional_stubs=ns['additional_stubs'])
(ROOT/'firmware/mf79u/build/mf283u-full-voice-start-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(result=result,error=error,mmio_writes=len(report['simulated_mmio_writes']),
                     dsp_commands=report['dsp_commands'],last_writes=report['simulated_mmio_writes'][-6:])))
if error or result!=0:raise SystemExit(1)

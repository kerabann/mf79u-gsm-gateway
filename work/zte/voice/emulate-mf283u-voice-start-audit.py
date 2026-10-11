#!/usr/bin/env python3
"""Inspect actual configuration arguments in the frozen full voice startup model."""
from pathlib import Path
import ast,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
p=Path(__file__).with_name('emulate-mf283u-voice-start.py')
tree=ast.parse(p.read_text())
tree.body=[n for n in tree.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
 ((isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text') or
  (isinstance(n.value.func,ast.Name) and n.value.func.id=='print')))]
insert=ast.parse('''
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1
configurations=[]
def observe_configuration(uc,pc,size,unused):
 if pc==0x24780038:
  pointer=uc.reg_read(UC_ARM_REG_R1)
  configurations.append(dict(port=uc.reg_read(UC_ARM_REG_R0),pointer=hex(pointer),hex=bytes(uc.mem_read(pointer,28)).hex()))
ns['u'].hook_add(UC_HOOK_CODE,observe_configuration)
''').body
for index,node in enumerate(tree.body):
 if isinstance(node,ast.Try) and any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='result' for t in n.targets) for n in node.body):
  tree.body[index:index]=insert;break
else:raise AssertionError('Actual start call missing')
ast.fix_missing_locations(tree)
s={'__file__':str(p),'__name__':'__voice_start_audit__'};old=sys.argv
try:sys.argv=[str(p)];exec(compile(tree,str(p),'exec'),s)
finally:sys.argv=old
r=s['report'];r.update(configurations=s['configurations'],audit_generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),startup_generator_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
registers={w['address']:w['value'] for w in r['simulated_mmio_writes']}
r['final_registers']=registers
out=ROOT/'firmware/mf79u/build/mf283u-full-voice-start-config-audit.json';out.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'configurations':r['configurations'],'registers':registers,'no_device_access':True}))

#!/usr/bin/env python3
"""Offline RX slot alternatives through the exact reference I2S API; no device IO."""
from pathlib import Path
import ast, hashlib, json, sys
ROOT=Path(__file__).resolve().parents[3]
source=Path(__file__).with_name('emulate-mf283u-i2s.py')
expected='4afaf40e3cb81f511d11d431e6bd7cd27cd7ddee30e1cd1635d26e9a7a6f00ef'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
reports=[]
for selector in (0,1,2):
 tree=ast.parse(source.read_text(),filename=str(source))
 tree.body=[n for n in tree.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
  ((isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text') or
   (isinstance(n.value.func,ast.Name) and n.value.func.id=='print')))]
 for index,node in enumerate(tree.body):
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='mem_write' and isinstance(node.value.args[0],ast.Constant) and node.value.args[0].value==0x30010000:
   tree.body[index:index]=ast.parse('config[21]='+str(selector)).body
   break
 else:raise AssertionError('Configuration injection point missing')
 ast.fix_missing_locations(tree);ns={'__file__':str(source),'__name__':'__rx_slot_trace__'}
 previous=sys.argv
 try:
  sys.argv=[str(source),'--voice-inner','--driver-init'];exec(compile(tree,str(source),'exec'),ns)
 finally:sys.argv=previous
 out=ns['out'];writes={x['address']:int(x['value'],0) for x in out['register_writes']}
 assert all(v==0 for v in out['results'].values())
 reports.append({'selector':selector,'configuration_hex':out['configuration_hex'],'registers':{k:hex(v) for k,v in writes.items()},'reference_trace':out})
report={'device_access':False,'source_sha256':ns['sha'],'baseline_generator_sha256':expected,
 'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':reports}
path=ROOT/'firmware/mf79u/build/mf283u-rx-slots-emulation.json';path.write_text(json.dumps(report,indent=2)+'\n')
for r in reports:print(r['selector'],r['configuration_hex'],r['registers'])

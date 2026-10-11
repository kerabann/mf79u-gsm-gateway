#!/usr/bin/env python3
"""Offline matrix of the real public voice path setters; no device access.

Each row starts with the same complete Open/Enable baseline. The frozen
baseline script is executed with its final file-write/print expressions
removed, so its physically tested parameter receipt stays unchanged.
"""
from pathlib import Path
import ast, hashlib, json, sys

ROOT=Path(__file__).resolve().parents[3]
BASE=Path(__file__).resolve().parent
source=BASE/'emulate-mf283u-voice-open.py'
EXPECTED='369365d41e3dc2e3785deaba22e5689c0c60aba242a9faf2fc49f9cf464c4beb'
assert hashlib.sha256(source.read_bytes()).hexdigest()==EXPECTED
tree=ast.parse(source.read_text(),filename=str(source))
tree.body=[node for node in tree.body if not (
    isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and
    ((isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='write_text')
     or (isinstance(node.value.func,ast.Name) and node.value.func.id=='print')))]
code=compile(tree,str(source),'exec')
receipt=ROOT/'firmware/mf79u/build/mf283u-full-voice-open-port-tone-emulation.json'
receipt_sha=hashlib.sha256(receipt.read_bytes()).hexdigest()
rows=[];saved_argv=sys.argv
try:
    for input_path in range(4):
        for output_path in range(5):
            sys.argv=[str(source),'--port-tone']
            ns={'__file__':str(source),'__name__':'__voice_path_baseline__'}
            exec(code,ns)
            u=ns['u'];call=ns['call'];commands=ns['commands'];intercepted=ns['intercepted']
            command_start=len(commands);log_start=len(intercepted)
            u.mem_write(0x30010120,bytes([0,input_path,output_path,0,0,0,0,0]))
            result_in=call('matrix_input',0x2478c0c4,0x30010120)
            result_out=call('matrix_output',0x2478bf30,0x30010120)
            # Run the real resource/path refresh after the setters; the DSP
            # transport remains intercepted by the original emulator.
            call('matrix_refresh',0x24774f5c)
            vb=[c for c in commands[command_start:] if c['command']=='0xf']
            logs=[]
            for entry in intercepted[log_start:]:
                if entry['pc']!='0x23f15e90':continue
                address=entry['args'][1]
                if not 0x23f00000<=address<0x25f00000:continue
                value=bytes(u.mem_read(address,256)).split(b'\0',1)[0].decode('ascii',errors='replace')
                if 'voice_SetPa' in value:logs.append(value.strip())
            rows.append(dict(input_path=input_path,output_path=output_path,
                input_result=result_in,output_result=result_out,
                uplink_paths=list(u.mem_read(0x251a409c,3)),
                downlink_paths=list(u.mem_read(0x255b1b80,2)),
                vb_on=vb[-1] if vb else None,reference_logs=logs,
                pcm_tail_active=bool(vb and any(vb[-1]['payload'][18:]))))
finally:sys.argv=saved_argv
assert hashlib.sha256(receipt.read_bytes()).hexdigest()==receipt_sha
report=dict(offline_only=True,device_access=False,
    source_sha256=ns['EXPECTED'],baseline_generator_sha256=EXPECTED,
    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    baseline_receipt_unchanged=True,baseline_receipt_sha256=receipt_sha,
    b03_compatibility_verified=False,synthetic_os_buffers_and_dsp=True,
    input_conversion=list(u.mem_read(0x249aae6c,4)),
    output_conversion=list(u.mem_read(0x249aae64,5)),rows=rows)
output=ROOT/'firmware/mf79u/build/mf283u-voice-path-matrix-emulation.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('input_conversion','output_conversion','baseline_receipt_unchanged')}))
for r in rows:
    print(json.dumps({k:r[k] for k in ('input_path','output_path','input_result','output_result','uplink_paths','downlink_paths','pcm_tail_active')}))

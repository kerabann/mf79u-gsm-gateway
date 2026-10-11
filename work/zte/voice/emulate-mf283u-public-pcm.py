#!/usr/bin/env python3
"""Hash-bound real public PCM route after full Open; all hardware simulated."""
from pathlib import Path
import argparse, ast, hashlib, json, struct, sys

ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--arm-slave',action='store_true')
args=parser.parse_args()
source=BASE/'emulate-mf283u-voice-open.py'
EXPECTED='369365d41e3dc2e3785deaba22e5689c0c60aba242a9faf2fc49f9cf464c4beb'
assert hashlib.sha256(source.read_bytes()).hexdigest()==EXPECTED
tree=ast.parse(source.read_text(),filename=str(source))
tree.body=[node for node in tree.body if not (isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
    and ((isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='write_text')
      or (isinstance(node.value.func,ast.Name) and node.value.func.id=='print')))]
receipt=ROOT/'firmware/mf79u/build/mf283u-full-voice-open-port-tone-emulation.json'
receipt_sha=hashlib.sha256(receipt.read_bytes()).hexdigest();saved_argv=sys.argv
try:
    sys.argv=[str(source),'--port-tone']+(['--arm-slave'] if args.arm_slave else [])
    ns={'__file__':str(source),'__name__':'__public_pcm_baseline__'}
    exec(compile(tree,str(source),'exec'),ns)
finally:sys.argv=saved_argv
u=ns['u'];call=ns['call'];commands=ns['commands'];mmio=ns['mmio'];intercepted=ns['intercepted']
start=len(commands);log_start=len(intercepted);register_start=len(mmio)
config=bytearray(u.mem_read(0x24acca68,28))
assert struct.unpack_from('<I',config,8)[0]==8000 and config[23]==1
struct.pack_into('<I',config,0,0 if args.arm_slave else 1)
config[21]=6 # Actual reference mono PCM/TDM timing-table selector.
u.mem_write(0x30010300,bytes(config))
call('public_pcm_inner_config',0x24784cd8,0x30010300)
call('public_pcm_tx_prepare',0x24780b78,0,0x30010300)
call('public_pcm_rx_prepare',0x2478104c,0,0x30010300)
call('public_pcm_loop',0x24895858,0)
mode=0 if args.arm_slave else 1
u.mem_write(0x30010120,bytes([0,2,3,0,0,0,0,0]))
call('public_pcm_input',0x2478c0c4,0x30010120)
call('public_pcm_output',0x2478bf30,0x30010120)
call('public_pcm_refresh',0x24774f5c)
refresh_tail=list(commands[-1]['payload'][18:])
# Public refresh selects PCM0 from its path descriptor. Apply the real mode
# builder afterwards, then build VB_ON without another descriptor refresh.
call('public_pcm_profile_select',0x247863ac,mode)
call('public_pcm_clock_matched_builder',0x24774ebc,1)
enabled=list(commands)
sequence=[]
for cmd,selector in ((0x10,0),(0x10,1),(0x19,None),(0x11,None),(0x17,None),(0x18,None),(0xf,None)):
    rows=[c for c in enabled if int(c['command'],0)==cmd and (selector is None or c['payload'][0]==selector)]
    assert rows;sequence.append(rows[-1])
assert sequence[-1]['payload'][0]==3 and any(sequence[-1]['payload'][18:])
assert list(u.mem_read(0x251a409c,3))==[2,20,20]
assert list(u.mem_read(0x255b1b80,2))==[4,27]
call('public_pcm_disable',0x24774c48,0)
assert commands[-1]['command']=='0xf' and commands[-1]['payload'][0]==1
logs=[]
for entry in intercepted[log_start:]:
    if entry['pc']!='0x23f15e90' or not 0x23f00000<=entry['args'][1]<0x25f00000:continue
    text=bytes(u.mem_read(entry['args'][1],256)).split(b'\0',1)[0].decode('ascii',errors='replace')
    if 'voice_SetPa' in text:logs.append(text.strip())
registers={w['address']:w['value'] for w in mmio[register_start:]}
assert int(registers['0x140060'],0)==0x99
assert int(registers['0x1405008'],0)==(0x01ef0008 if args.arm_slave else 0x01ef0009)
assert hashlib.sha256(receipt.read_bytes()).hexdigest()==receipt_sha
report={'offline_only':True,'device_access':False,'source_sha256':ns['EXPECTED'],
    'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'baseline_generator_sha256':EXPECTED,'baseline_receipt_unchanged':True,
    'baseline_receipt_sha256':receipt_sha,'b03_compatibility_verified':False,
    'synthetic_os_buffers_and_dsp':True,'public_input_path':2,'public_output_path':3,
    'reference_logs':logs,'unsupported_input_warning':any('not support' in s for s in logs),
    'public_refresh_pcm_tail':refresh_tail,'pcm_profile_applied_after_public_refresh':True,
    'results':{k:v for k,v in ns['results'].items() if k.startswith('public_pcm')},
    'uplink_paths':[2,20,20],'downlink_paths':[4,27],
    'arm_clock_master':not args.arm_slave,'pcm_configuration_index':mode,
    'fifo_sample_rate_hz':8000,'configuration_hex':config.hex(),
    'register_writes':mmio[register_start:],'preparation_sequence':sequence,
    'disable_command':commands[-1],'disable_requires_scheduler_stop_0x15':True,
    'pcm_tail_active':True,'tone_both_mixers':True,'tone_volume':100}
stem='mf283u-public-pcm'+('-arm-slave' if args.arm_slave else '')
path=ROOT/'firmware/mf79u/build'/(stem+'-emulation.json')
path.write_text(json.dumps(report,indent=2)+'\n')
configuration={k:report[k] for k in ['source_sha256','generator_sha256','device_access','b03_compatibility_verified',
    'arm_clock_master','fifo_sample_rate_hz','configuration_hex','register_writes']}
configuration.update(reference_sha256=report['source_sha256'],mmio_simulated=True,results=report['results'],
                     driver_init=True,loop_owned_mask='0x1ff',public_pcm_route=True)
(path.parent/(stem+'-configuration-emulation.json')).write_text(json.dumps(configuration,indent=2)+'\n')
print(json.dumps({'results':report['results'],'registers':registers,
                  'vb_on':sequence[-1]['payload'],'unsupported_input_warning':report['unsupported_input_warning']}))

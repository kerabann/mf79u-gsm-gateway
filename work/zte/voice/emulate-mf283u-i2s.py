#!/usr/bin/env python3
"""Offline I2S configuration evidence; simulated MMIO, never device access."""
from pathlib import Path
import argparse, hashlib, json, struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--pcm-teak-i2s1', action='store_true', help='Reference timing selector 6 and PCM ARM0-to-Teak-I2S1 loop')
mode.add_argument('--voice-inner', action='store_true', help='Actual voice inner I2S configuration at 24ACCA68')
parser.add_argument('--driver-init', action='store_true', help='Emulate the actual I2S driver initialization before voice-inner configuration')
parser.add_argument('--arm-slave',action='store_true',help='Actual voice Init alternative: DSP supplies the inner-I2S clock')
parser.add_argument('--driver-start',action='store_true',help='Also execute real TX/RX Start in polling mode with synthetic buffers; offline only')
parser.add_argument('--tdm-extra-cycle',type=int,choices=(0,1),default=None,
                    help='Reference tTdmExtCycle enum: 0 sets timing bit5, 1 clears it; hardware meaning remains unverified')
args = parser.parse_args()
if args.driver_init and not args.voice_inner:
    parser.error('--driver-init requires --voice-inner')
if args.arm_slave and not (args.voice_inner and args.driver_init):parser.error('--arm-slave requires --voice-inner --driver-init')
if args.driver_start and not (args.voice_inner and args.driver_init):parser.error('--driver-start requires --voice-inner --driver-init')
if args.tdm_extra_cycle==0 and not (args.voice_inner and args.driver_init):parser.error('Extra-cycle alternative requires voice-inner driver initialization')
data = (ROOT/'work/zte/voice/mf283u-reference/partitions/evb_cpups.img.gzip-4150.raw').read_bytes()
sha = hashlib.sha256(data).hexdigest()
assert sha == '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
for base, size in ((0x23f00000,0x2000000),(0x30000000,0x40000),(0x31000000,0x1000),
                   (0x01400000,0x10000),(0x00140000,0x1000)):
    u.mem_map(base,size)
u.mem_write(0x23f00000,data)
regs = [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
trace, intercepted = [], []
heap = 0x30020000
stage = ''
def hook(uc, address, size, unused):
    global heap
    if address == 0x23f1544c or address == 0x23f332ac:
        raise RuntimeError('reference assert at '+hex(uc.reg_read(UC_ARM_REG_LR)))
    if not 0x23f00000 <= address < 0x23f40000:
        return
    args = [uc.reg_read(r) for r in regs]
    result = 0
    if address in (0x23f2b580,0x23f14ca8):
        result = heap; heap += 128
    elif address in (0x23f00080,0x23f154a0,0x23f29fc8):
        result = heap; heap += (args[0]+15)&~15
    elif address == 0x23f15e90:
        pass
    elif address in (0x23f05378,0x23f054cc,0x23f05534,0x23f2a5ec,
                     0x23f18c88,0x23f03a6c,0x23f03a60,0x23f18cc8,
                     0x23f2b630,0x23f2b6d8,0x23f14e04,
                     0x23f2b4b0,0x23f2b45c,0x23f2b3b4,0x23f033a0):
        pass
    else:
        raise RuntimeError('unhandled OS call '+hex(address)+' args '+str(args))
    intercepted.append({'stage':stage,'address':hex(address),'args':args,'result':result})
    uc.reg_write(UC_ARM_REG_R0,result)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def write(uc, access, address, size, value, unused):
    if 0x01400000 <= address < 0x01410000 or 0x00140000 <= address < 0x00141000:
        trace.append({'stage':stage,'pc':hex(uc.reg_read(UC_ARM_REG_PC)),
                      'address':hex(address),'size':size,'value':hex(value)})
u.hook_add(UC_HOOK_CODE,hook)
u.hook_add(UC_HOOK_MEM_WRITE,write)
def call(name, addr, args):
    global stage
    stage = name
    u.reg_write(UC_ARM_REG_SP,0x30018000)
    u.reg_write(UC_ARM_REG_LR,0x31000000)
    for r,v in zip(regs,args):u.reg_write(r,v)
    u.emu_start(addr,0x31000000,count=1000000)
    if u.reg_read(UC_ARM_REG_PC)!=0x31000000:raise RuntimeError('instruction budget at '+hex(u.reg_read(UC_ARM_REG_PC)))
    return u.reg_read(UC_ARM_REG_R0)

results = {}
if args.driver_init:
    # Init at 24782018 writes (ARM_I2S_LOOP_CFG & ~0x1ff) | 0xa9.
    # OS clock acquisition/association is intercepted, with no hardware access.
    results['driver_init'] = call('driver_init',0x24782018,())
results['open'] = call('open',0x24780310,(0,0 if args.driver_start else 2))
# Keep the exact selected configuration, explicitly choosing narrowband.
# The voice-inner literal already contains 8000; generic24ACC850 has16000.
config = bytearray(u.mem_read(0x24acca68 if args.voice_inner else 0x24acc850,28))
original_rate=struct.unpack_from('<I',config,8)[0]
struct.pack_into('<I',config,8,8000)
if args.arm_slave:struct.pack_into('<I',config,0,0)
if config[23]!=1:raise RuntimeError('Unexpected reference tTdmExtCycle default')
config[23]=1 if args.tdm_extra_cycle is None else args.tdm_extra_cycle
if args.pcm_teak_i2s1:
    config[21] = 6  # exact timing table: TDM, mono, lane 0, time slot 0
u.mem_write(0x30010000,bytes(config))
results['prepare_tx'] = call('prepare_tx',0x24780b78,(0,0x30010000))
results['prepare_rx'] = call('prepare_rx',0x2478104c,(0,0x30010000))
results['internal_loop'] = call('internal_loop',0x24895858,(0 if args.pcm_teak_i2s1 else 1,))
if args.driver_start:
    # Polling mode avoids OS IRQ/DMA ownership. Start helpers still execute
    # their actual FIFO thresholds, process bits and RAM queue initialization.
    u.mem_write(0x30010100,struct.pack('<3I',0,320,0))
    results['start_tx']=call('start_tx',0x24780d44,(0,0x30010100))
    results['start_rx']=call('start_rx',0x24781200,(0,0x30010100))
out = {'reference_sha256':sha,'device_access':False,'mmio_simulated':True,
       'physical_map_on_b03_verified':False,'results':results,
       'configuration_hex':bytes(config).hex(),'register_writes':trace,'intercepted_calls':intercepted,
       'timing_table_address':'0x249a2e08',
       'timing_table_rows':[list(data[0xaa2e08+5*i:0xaa2e08+5*i+5]) for i in range(8)],
       'pcm_teak_i2s1':args.pcm_teak_i2s1,'voice_inner':args.voice_inner,
       'reference_original_sample_rate_hz':original_rate,
       'fifo_sample_rate_hz':struct.unpack_from('<I',config,8)[0],
       'rate_overridden':original_rate!=8000,
       'driver_init':args.driver_init,'loop_owned_mask':'0x1ff' if args.driver_init else '0x1f8'}
out['arm_clock_master']=not args.arm_slave
if args.tdm_extra_cycle is not None:
    out.update(tdm_extra_cycle=args.tdm_extra_cycle,tdm_extra_cycle_config_offset=23,
               timing_bit5_reference_set_pc='0x247801c4',timing_bit5_reference_clear_pc='0x247802b4',
               timing_bit5_b03_semantics_verified=False)
if args.driver_start:
    out.update(driver_start=True,transfer_mode='polling',synthetic_buffer_parameters=True,
               start_addresses=['0x24780d44','0x24781200'])
if args.driver_init:
    out['driver_init_address']='0x24782018'
    out['driver_init_loop_write_pc']='0x247820c0'
    out['low_bit_meaning_verified']=False
path = ROOT/'firmware/mf79u/build'/('mf283u-voice-inner'+('-slave' if args.arm_slave else '')+'-init-start-configuration-emulation.json' if args.driver_start else 'mf283u-voice-inner-slave-init-configuration-emulation.json' if args.arm_slave else 'mf283u-voice-inner-init-configuration-emulation.json' if args.driver_init else 'mf283u-voice-inner-configuration-emulation.json' if args.voice_inner else 'mf283u-pcm-i2s1-configuration-emulation.json' if args.pcm_teak_i2s1 else 'mf283u-i2s-configuration-emulation.json')
if args.tdm_extra_cycle is not None:
    path=path.with_name(path.name.replace('-configuration-emulation','-extra-cycle'+str(args.tdm_extra_cycle)+'-configuration-emulation'))
path.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'results':results,'register_writes':trace},indent=2))

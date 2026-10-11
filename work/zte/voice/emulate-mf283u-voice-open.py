#!/usr/bin/env python3
"""Trace complete reference voice Open/Enable offline, with explicit OS stubs.

The DSP transport, timers, DMA and scheduler are simulated. This is evidence
about reference command construction; it does not establish B03 compatibility.
"""
from pathlib import Path
import argparse, hashlib, json, struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'work/zte/voice/mf283u-reference/partitions/evb_cpups.img.gzip-4150.raw'
EXPECTED = '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--arm-slave', action='store_true', help='Reference voice Init alternative, DSP master')
parser.add_argument('--port-tone', action='store_true', help='Enable reference tone resource on both mixers')
args = parser.parse_args()
raw = SOURCE.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
for base, size in ((0x23f00000, 0x2000000), (0x30000000, 0x100000),
                   (0x31000000, 0x1000), (0x01400000, 0x10000),
                   (0x00140000, 0x1000), (0xf4000000, 0x10000)):
    u.mem_map(base, size)
u.mem_write(0x23f00000, raw)
regs = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
stage = ''
heap = 0x30020000
commands, intercepted, mmio, queued, results = [], [], [], [], {}
os_zero = {
    0x23f15e90, 0x23f3d078, 0x23f37c2c, 0x23f18c88, 0x23f2a5ec,
    0x23f05378, 0x23f054cc, 0x23f05534, 0x23f03a6c, 0x23f03a60,
    0x23f18cc8, 0x23f2b630, 0x23f2b6d8, 0x23f14e04,
    0x23f2b4b0, 0x23f2b45c, 0x23f2b3b4, 0x23f033a0, 0x23f00140, 0x23f2bae4,
}
allocators = {0x23f00080, 0x23f154a0, 0x23f29fc8}
handles = {0x23f2b580, 0x23f14ca8, 0x23f2b314, 0x23f323c4}

def words(addr, count):
    return list(struct.unpack('<' + 'I'*count, u.mem_read(addr, count*4)))

def hook(uc, pc, size, unused):
    global heap
    a = [uc.reg_read(r) for r in regs]
    result = 0
    kind = None
    if pc in (0x246c4b94, 0x246c4a74):
        assert 1 <= a[1] <= 32
        commands.append(dict(stage=stage, command=hex(a[0]), count=a[1],
                             connection=a[3] if pc == 0x246c4a74 else 0,
                             payload=list(struct.unpack('<'+'H'*(a[1]-1),
                                 uc.mem_read(a[2], (a[1]-1)*2))) if a[1]>1 else []))
        kind = 'dsp_transport_intercept'
    elif pc in (0x248a013c, 0x248a08c4):
        assert 0 <= a[2] <= 0x80000
        uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2])) if pc == 0x248a013c
                     else bytes([a[1] & 255])*a[2])
        kind = 'memory_copy_or_fill'
    elif pc == 0x23f31a28:
        assert a[2] == 40
        queued.append((a[0], bytes(uc.mem_read(a[1], a[2]))))
        kind = 'queued_audio_message'
    elif pc in handles or pc in allocators:
        result = heap
        heap += ((a[0]+15)&~15) if pc in allocators else 128
        assert heap <= 0x30100000
        kind = 'synthetic_allocation_or_handle'
    elif pc == 0x2463a574:
        result = 1
        kind = 'synthetic_task_id'
    elif pc in os_zero:
        kind = 'os_success_stub'
    elif pc in (0x23f1544c, 0x23f332ac):
        raise RuntimeError('Reference assert ' + hex(uc.reg_read(UC_ARM_REG_LR)))
    elif 0x23f00000 <= pc < 0x23f40000:
        raise RuntimeError('Unhandled OS call '+hex(pc)+' args '+repr(a))
    else:
        return
    if kind != 'memory_copy_or_fill':
        intercepted.append(dict(stage=stage, pc=hex(pc), args=a, result=result, kind=kind))
    uc.reg_write(UC_ARM_REG_R0, result)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

def write(uc, access, addr, size, value, unused):
    if (0x01400000 <= addr < 0x01410000 or 0x00140000 <= addr < 0x00141000
            or 0xf4000000 <= addr < 0xf4010000):
        mmio.append(dict(stage=stage, pc=hex(uc.reg_read(UC_ARM_REG_PC)),
                         address=hex(addr), size=size, value=hex(value)))

u.hook_add(UC_HOOK_CODE, hook)
u.hook_add(UC_HOOK_MEM_WRITE, write)

def call(name, pc, *args, drain=True):
    global stage
    stage = name
    u.reg_write(UC_ARM_REG_SP, 0x30018000)
    u.reg_write(UC_ARM_REG_LR, 0x31000000)
    for reg, value in zip(regs, args):
        u.reg_write(reg, value)
    u.emu_start(pc, 0x31000000, count=1000000)
    if u.reg_read(UC_ARM_REG_PC) != 0x31000000:
        raise RuntimeError('Instruction budget at '+hex(u.reg_read(UC_ARM_REG_PC)))
    result = u.reg_read(UC_ARM_REG_R0)
    results[name] = result
    if drain:
        for i in range(64):
            if not queued:
                break
            ident, payload = queued.pop(0)
            u.mem_write(0x30010000, payload)
            call(name+'/message-'+hex(ident), 0x24775eb8, 2, ident, 0x30010000, drain=False)
        else:
            raise RuntimeError('Message queue budget exceeded')
    return result

# Keep the original narrowband reference configuration and default tables.
# These are real RAM builders, with synthetic buffers instead of NV ownership.
call('pointer_init', 0x246b45c0, 0)
u.mem_write(0x255b1c2c+0x18, struct.pack('<I', 0x251a4080))
u.mem_write(0x255b1c2c+0x60, struct.pack('<I', 0x251a40ec))
call('audio_defaults', 0x24775fb0)
call('audio_main_init', 0x247880ac)
call('volume_defaults', 0x24788be4)
call('driver_init', 0x24782018)
call('hal_callback_registration', 0x2477d9cc, 0x24a6a5c4)
call('voice_afe_profile', 0x24786adc, 0x24acc820 if args.arm_slave else 0x24acc838)
call('voice_pcm_profile', 0x24786bb0, 0x24a89ea8 if args.arm_slave else 0x24abf540)
inner = 0x24acca68
if args.arm_slave:
    inner = 0x30010200
    u.mem_write(inner, bytes(u.mem_read(0x24acca68, 28)))
    u.mem_write(inner, struct.pack('<I', 0))
call('inner_config', 0x24784cd8, inner)
call('external_config', 0x24784bc0, 0x24acc9ec, 0x24acca4c, 0x24acca08, 0x24acca38)
u.mem_write(0x30010100, struct.pack('<4I', 0x30040000, 0x30041000, 0x30042000, 0x30043000))
call('voice_buffers', 0x24784d94, 0x30010100, 0x280)
call('voice_callback_registration', 0x2478cce8, 0x24a66b58)
call('voice_open', 0x2478baa8)
u.mem_write(0x30010120, bytes(8))  # reference handset route, input/output0
call('voice_input_path', 0x2478c0c4, 0x30010120)
call('voice_output_path', 0x2478bf30, 0x30010120)
call('voice_enable', 0x2478c240)
u.mem_write(0x30010140, bytes([0, 2]))
call('voice_unmute', 0x2478c3a4, 0x30010140)
if args.port_tone:
    u.mem_write(0x251a4564+3, bytes([100]))
    call('tone_resource_enable', 0x24785c5c, 1, 1)
    call('tone_route_refresh', 0x24774f5c)

enabled = list(commands)
call('disable_builder', 0x24774c48, 0)
disable = commands[-1]
assert disable['command'] == '0xf' and disable['payload'][0] == 1
sequence = []
for cmd, selector in ((0x10, 0), (0x10, 1), (0x19, None), (0x11, None),
                       (0x17, None), (0x18, None), (0xf, None)):
    candidates = [c for c in enabled if int(c['command'], 0) == cmd
                  and (selector is None or c['payload'][0] == selector)]
    assert candidates, hex(cmd)
    sequence.append(candidates[-1])
assert sequence[-1]['payload'][0] == 2
assert sequence[-1]['payload'][18:] == [0]*9  # no active PCM route
if args.port_tone:
    assert words(0x255b3784+0x24, 1)[0] == 0x7fff7fff

out = dict(offline_only=True, device_access=False, source_sha256=EXPECTED,
           generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           synthetic_buffers=True, os_and_dsp_intercepted=True,
           b03_compatibility_verified=False, results=results,
           dsp_commands=commands, simulated_mmio_writes=mmio, intercepted_calls=intercepted,
           voice_variables=words(0x24a645f0, 10), arm_clock_master=not args.arm_slave,
           tone_volume=100 if args.port_tone else None, tone_both_mixers=args.port_tone,
           preparation_sequence=sequence, disable_command=disable,
           original_inner_configuration_hex=bytes(u.mem_read(0x24acca68, 28)).hex(),
           inner_configuration_hex=bytes(u.mem_read(inner, 28)).hex(),
           afe_profile_address=hex(0x24acc820 if args.arm_slave else 0x24acc838),
           pcm_tail_inactive=True, fifo_sample_rate_hz=8000,
           disable_switch=1, disable_requires_scheduler_stop_0x15=True,
           uplink_paths=list(u.mem_read(0x251a409c, 3)),
           downlink_paths=list(u.mem_read(0x255b1b80, 2)))
path = ROOT / 'firmware/mf79u/build'/('mf283u-full-voice-open'+('-arm-slave' if args.arm_slave else '')+('-port-tone' if args.port_tone else '')+'-emulation.json')
path.write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(dict(results=results, preparation_sequence=sequence, mmio_count=len(mmio)), indent=2))

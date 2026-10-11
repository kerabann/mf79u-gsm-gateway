#!/usr/bin/env python3
"""Create a RAM-test-only B03 VoLTE copy with private IPC queue IDs.

Only three verified Thumb MOVW instructions are changed. Never edits flash.
The private destination prevents test replies/requests reaching stock AT_CTL.
"""
import hashlib
import json
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile

root = Path(__file__).resolve().parents[2]
source = root / 'work/zte/b03mod-extracted/bin/zte_volte_main'
data = bytearray(source.read_bytes())
assert hashlib.sha256(data).hexdigest() == '3516bf3adfcfe97bbb029b1a89a1ada45b9b1bb578a08170d0141e15a96ab738'
with source.open('rb') as stream:
    elf = ELFFile(stream)
    segments = [(s['p_vaddr'], s['p_offset'], s['p_filesz'])
                for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']

def offset(address):
    return next(pos + address - base for base, pos, size in segments
                if base <= address < base + size)

def movw(register, value):
    return struct.pack('<HH', 0xf240 | ((value >> 12) & 15) |
                       (((value >> 11) & 1) << 10),
                       (((value >> 8) & 7) << 12) | (register << 8) | (value & 255))

patches = [(0x32454, 0, 0x101e, 0x701e),
           (0x32458, 1, 0x100f, 0x700f),
           (0x32502, 0, 0x101e, 0x701e)]
for address, register, original, replacement in patches:
    pos = offset(address)
    assert data[pos:pos + 4] == movw(register, original), hex(address)
    data[pos:pos + 4] = movw(register, replacement)
# Disable the verified cfg_set + cfg_save wrapper in this private RAM copy.
# Setters still update their in-process state, but cannot persist configuration.
pos = offset(0xad88)
assert data[pos:pos+6] == bytes.fromhex('08b5fff74ee9')
data[pos:pos+4] = bytes.fromhex('00207047')  # movs r0, #0; bx lr
# Silence the verified vendor log-level getter and its two logging wrappers.
# This allows SIM-related replies to stay in process memory during later tests.
for address, expected in [(0x41e50,'014b1868'),(0x42102,'0eb403b5'),(0x4211e,'0eb403b5')]:
    pos=offset(address)
    assert data[pos:pos+4] == bytes.fromhex(expected)
    data[pos:pos+4] = bytes.fromhex('00207047')
# Stock priorities already prefer AMR-WB (130) over AMR-NB (129).
target = root / 'firmware/mf79u/build/volte-private-ipc'
target.write_bytes(data)
report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'result_sha256': hashlib.sha256(data).hexdigest(),
          'patches': [{'address': hex(a), 'register': r,
                       'old': hex(o), 'new': hex(n)} for a, r, o, n in patches],
          'cfg_set_save_wrapper_disabled': '0xad88',
          'vendor_trace_disabled': ['0x41e50','0x42102','0x4211e'],
          'codec_priorities': {'WB':130, 'NB':129},
          'flash_written': False, 'test_only': True}
target.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

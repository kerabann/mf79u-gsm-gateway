#!/usr/bin/env python3
"""Offline disassembly of the hash-pinned MF283U reference CP; no device access."""
import argparse
import hashlib
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / 'work/zte/voice/mf283u-reference/partitions/evb_cpups.img.gzip-4150.raw'
DATA = PATH.read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'
BASE = 0x23f00000


def offset(address):
    result = address - BASE
    if not 0 <= result < len(DATA):
        raise ValueError(hex(address))
    return result


def word(address):
    return struct.unpack_from('<I', DATA, offset(address))[0]


def string(address):
    try:
        i = offset(address)
        value = DATA[i:i+200].split(b'\0')[0]
        if value and all(32 <= c <= 126 or c in (9, 10, 13) for c in value):
            return repr(value.decode('ascii'))
    except ValueError:
        pass
    return ''


def refs(value):
    result = []
    pattern = struct.pack('<I', value)
    i = DATA.find(pattern)
    while i >= 0:
        result.append(hex(BASE+i))
        i = DATA.find(pattern, i+1)
    return result


parser = argparse.ArgumentParser()
parser.add_argument('--slice', action='append', default=[])
parser.add_argument('--string', action='append', default=[])
parser.add_argument('--refs', action='append', default=[])
parser.add_argument('--callers', action='append', default=[])
parser.add_argument('--words', action='append', default=[])
args = parser.parse_args()
for text in args.string:
    i = DATA.find(text.encode())
    while i >= 0:
        print(repr(text), hex(BASE+i), 'refs', refs(BASE+i))
        i = DATA.find(text.encode(), i+1)
for value in args.refs:
    value = int(value, 0)
    print(hex(value), 'refs', refs(value), string(value))
for value in args.callers:
    target = int(value, 0)
    callers = []
    for i in range(0, len(DATA)-3, 4):
        instruction = struct.unpack_from('<I', DATA, i)[0]
        if (instruction & 0x0e000000) != 0x0a000000:
            continue
        delta = instruction & 0xffffff
        if delta & 0x800000:
            delta -= 0x1000000
        if BASE+i+8+4*delta == target:
            callers.append(hex(BASE+i))
    print(hex(target), 'branch/call refs', callers)
for section in args.words:
    start, size = [int(v, 0) for v in section.split(':')]
    for address in range(start, start+size, 4):
        value = word(address)
        print(f'{address:08x}: {value:08x} {string(value)}')
for section in args.slice:
    start, size = [int(v, 0) for v in section.split(':')]
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    print(f'-- {start:08x} --')
    for instruction in md.disasm(DATA[offset(start):offset(start)+size], start):
        extra = ''
        if instruction.mnemonic.startswith('ldr') and '[pc,' in instruction.op_str:
            try:
                value = word(instruction.address+8+instruction.operands[1].mem.disp)
                extra = f' = {value:08x} {string(value)}'
            except ValueError:
                pass
        print(f'{instruction.address:08x} {instruction.mnemonic:<9} {instruction.op_str}{extra}')

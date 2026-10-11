#!/usr/bin/env python3
"""Offline recovery of direct ioctl constants from objdump and ELF literals."""
import hashlib
import json
from pathlib import Path
import re
import struct
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]

def analyse(binary, disassembly):
    with binary.open('rb') as file:
        elf = ELFFile(file)
        def word(address):
            for segment in elf.iter_segments():
                start = segment['p_vaddr']
                if start <= address and address + 4 <= start + segment['p_filesz']:
                    file.seek(segment['p_offset'] + address - start)
                    return struct.unpack('<I', file.read(4))[0]
            raise ValueError(f'Literal address is not mapped: {address:x}')
        lines = disassembly.read_text().splitlines()
        results = []
        for i, line in enumerate(lines):
            if not re.search(r'\bblx?\s+[^<]+<ioctl@plt>', line):
                continue
            value, evidence = None, None
            for previous in reversed(lines[max(0, i-15):i]):
                # Crossing a prior call invalidates argument registers.
                if re.search(r'\bblx?\s', previous):
                    break
                instruction = re.search(r'\b(\w+(?:\.w)?)\s+r1,', previous)
                if not instruction:
                    continue
                literal = re.search(r'\bldr(?:\.w)?\s+r1,\s*\[pc[^]]*\].*\(([0-9a-f]+)', previous)
                immediate = re.search(r'\bmov(?:w|s|\.w)?\s+r1,\s*#(\d+)', previous)
                if literal:
                    value = word(int(literal.group(1), 16))
                elif immediate:
                    value = int(immediate.group(1))
                evidence = previous.strip()
                break
            if value is None:
                results.append({'site': line.strip(), 'resolved': False})
            else:
                results.append({'site': line.strip(), 'resolved': True,
                    'request': f'0x{value:08x}', 'direction': value >> 30,
                    'encoded_size': (value >> 16) & 0x3fff,
                    'type': (value >> 8) & 255, 'number': value & 255,
                    'evidence': evidence})
        return {'binary': str(binary.relative_to(WORK)),
                'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'ioctls': results}

reports = []
for binary, assembly in (
    ('lib/libvoice.so', 'libvoice.disasm.txt'),
    ('bin/zte_volte_main', 'volte.disasm.txt'),
):
    report = analyse(WORK / 'work/zte/b03mod-extracted' / binary, HERE / 'build' / assembly)
    reports.append(report)
    requests = sorted({entry['request'] for entry in report['ioctls'] if entry['resolved']})
    print(binary, 'direct ioctl constants:', ', '.join(requests))
(HERE / 'build/voice-abi.json').write_text(json.dumps(reports, indent=2) + '\n')

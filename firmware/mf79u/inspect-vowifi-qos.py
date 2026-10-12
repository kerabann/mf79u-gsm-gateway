"""Read-only, checksum-bound B03 call/QoS disassembly; no device access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from elftools.elf.elffile import ELFFile

base = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refs', nargs='+', type=lambda x: int(x, 0))
parser.add_argument('--range', nargs=2, type=lambda x: int(x, 0))
parser.add_argument('--strings', action='store_true')
args = parser.parse_args()
path = base / 'build/stock-rootfs/bin/zte_volte_main'
assert hashlib.sha256(path.read_bytes()).hexdigest() == json.loads((base / 'profiles/b03/private-ims-patch.json').read_text())['source_sha256']
with path.open('rb') as stream:
    elf = ELFFile(stream)
    text = elf.get_section_by_name('.text')
    raw, address = text.data(), text['sh_addr']
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    cs.skipdata = True
    def read(at, size):
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= at < segment['p_vaddr'] + segment['p_filesz']:
                stream.seek(segment['p_offset'] + at - segment['p_vaddr'])
                return stream.read(size)
        return b''
    if args.refs:
        for at in range(0, len(raw) - 3, 2):
            for ins in cs.disasm(raw[at:at+4], address+at, count=1):
                if ins.mnemonic in ('bl', 'blx', 'b.w') and ins.op_str.startswith('#') and int(ins.op_str[1:], 0) in args.refs:
                    print(hex(ins.address), ins.mnemonic, ins.op_str)
        for target in args.refs:
            found = [hex(address+i) for i in range(0, len(raw)-3, 2) if raw[i:i+4] == struct.pack('<I', target)]
            print('literal', hex(target), found)
    if args.range:
        start, end = args.range
        for ins in cs.disasm(read(start, end-start), start):
            annotation = ''
            match = re.search(r'\[pc(?:, #0x([0-9a-f]+))?\]', ins.op_str)
            if match:
                target = ((ins.address+4)&~3) + (int(match[1],16) if match[1] else 0)
                word = read(target,4)
                if len(word)==4:
                    pointer=struct.unpack('<I',word)[0]
                    value=read(pointer,140).split(b'\0')[0]
                    if len(value)>5 and all(32<=c<=126 for c in value) and not re.search(rb'\d{7,}',value):
                        annotation=' ; '+value.decode()
                    else:annotation=' ; literal '+hex(pointer)
            print(hex(ins.address),ins.mnemonic,ins.op_str,annotation)
    if args.strings:
        ro=elf.get_section_by_name('.rodata')
        for match in re.finditer(rb'[\x20-\x7e]{6,}\x00',ro.data()):
            value=match[0][:-1].decode()
            if re.search(r'(?i)(dedicated|bearer|qos|CGEV|ZGIPDNS|tqos)',value) and not re.search(r'\d{7,}',value):
                print(hex(ro['sh_addr']+match.start()),value)

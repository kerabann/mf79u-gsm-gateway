#!/usr/bin/env python3
"""Decode the pinned ZTE boot containers with the PMB887x Teakra fork offline.

No device access or program upload. This decoder is another ISA reference,
not verification of the ZTE ROM, memory map, or audio extension commands.
"""
from pathlib import Path
import datetime, hashlib, json, re, subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'work/zte/voice'
BUILD = ROOT / 'firmware/mf79u/build'
COMMIT = 'e563358d52ffd2fcf00875a3028c314aef222a7e'
COMPARISON_SHA = '0ade5d6905a93793d527b4d37d10e43d9ae51c6c4be5583d5a369a1819139a4b'
SOURCES = {
    'b03': (ROOT / 'work/zte/b03mod-extracted/lib/cpko/cpko.ko',
            'ab0f783acee6ac13833e8f8fac1ee8cf79f5ae5b8ba18f941b03155cd8cdd261'),
    'mf283u': (WORK / 'mf283u-reference/partitions/evb_cpups.img.gzip-4150.raw',
              '49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513'),
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

repo = WORK / 'teakra-pmb887x'
if subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip() != COMMIT:
    raise SystemExit('Unexpected PMB887x decoder revision')
if subprocess.check_output(['git', '-C', str(repo), 'diff', '--name-only'], text=True).strip():
    raise SystemExit('Modified PMB887x decoder source')
comparison_raw = (BUILD / 'mf283u-b03-gsm-dsp-boot-comparison.json').read_bytes()
if sha(comparison_raw) != COMPARISON_SHA:
    raise SystemExit('Boot comparison changed')
comparison = json.loads(comparison_raw)
decoder = WORK / 'teakra-pmb887x-build/src/teak_disassembler/teak-disassembler'
destination = WORK / 'gsm-teak-pmb887x'
destination.mkdir(exist_ok=True)
result = {
    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'offline_only': True, 'device_access': False, 'dsp_program_uploaded': False,
    'zte_isa_fully_verified': False, 'zte_rom_abi_verified': False,
    'decoder_url': 'https://github.com/siemens-mobile-hacks/teakra',
    'decoder_commit': COMMIT, 'decoder_binary_sha256': sha(decoder.read_bytes()),
    'comparison_sha256': COMPARISON_SHA, 'images': {},
}
for name, (source, expected) in SOURCES.items():
    raw = source.read_bytes()
    if sha(raw) != expected:
        raise SystemExit('Unexpected source ' + name)
    entry = comparison[name]
    start = int(entry['start'], 0)
    container = raw[start:start + entry['size']]
    if sha(container) != entry['sha256']:
        raise SystemExit('Container changed ' + name)
    terminal = entry['records'][-1]
    if not terminal.get('terminal') or terminal['command'] != 2 or terminal['target'] != '0x20':
        raise SystemExit('Unexpected terminal record ' + name)
    terminal_end = terminal['byte_offset'] - start + 4
    # The ZTE comparison range includes one trailing word after BRANCH. The
    # fork requires EOF immediately after its four-byte BRANCH record.
    trailing = container[terminal_end:]
    if len(trailing) != 2:
        raise SystemExit('Unexpected bytes after BRANCH ' + name)
    decoder_input = container[:terminal_end]
    binary = destination / (name + '-container.bin')
    listing = destination / (name + '-container.txt')
    binary.write_bytes(decoder_input)
    diagnostic = subprocess.check_output([str(decoder), str(binary), str(listing)], text=True)
    text = listing.read_text()
    instructions = [line for line in text.splitlines()
                    if re.match(r'^[0-9A-F]{8}  [0-9A-F]{4}         ', line)]
    uncertain = [line for line in instructions if '?' in line or '[unknown' in line]
    result['images'][name] = {
        'source': str(source.relative_to(ROOT)), 'source_sha256': expected,
        'container_sha256': sha(container), 'decoder_input_sha256': sha(decoder_input),
        'trailing_word_excluded_from_decoder': trailing.hex(),
        'instructions': len(instructions),
        'uncertain_instructions': uncertain,
        'listing': str(listing.relative_to(ROOT)), 'listing_sha256': sha(listing.read_bytes()),
        'decoder_summary': diagnostic.splitlines(),
    }
report = BUILD / 'gsm-teak-pmb887x-decoding.json'
report.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({name: {'instructions': item['instructions'],
                         'uncertain': item['uncertain_instructions']}
                  for name, item in result['images'].items()}, indent=2))

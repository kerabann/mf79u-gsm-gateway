"""Create link-only B03 ABI libraries. These shims MUST NEVER be installed."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / 'firmware/mf79u/build'
lib = build / 'link-sdk/lib'
lib.mkdir(parents=True, exist_ok=True)
abi = json.loads((root / 'firmware/mf79u/profiles/b03/link-abi.json').read_text())
commands = []
for name, metadata in abi.items():
    rows = ['.section .text', '.arm', '.balign 4']
    for symbol in metadata['symbols']:
        n = symbol['name']
        rows += [('.weak ' if symbol['weak'] else '.global ') + n,
                 '.type ' + n + (',%function' if symbol['type'] == 2 else ',%object'), n + ':']
    rows += ['.word 0', '.section .note.GNU-stack,"",%progbits', '']
    (lib / (name + '.S')).write_text('\n'.join(rows))
    commands.append('arm-linux-gnueabi-gcc -shared -nostdlib -march=armv7-a -mfloat-abi=soft -Wl,--hash-style=sysv -Wl,-soname,' + metadata['soname'] + ' firmware/mf79u/build/link-sdk/lib/' + name + '.S -o firmware/mf79u/build/link-sdk/lib/' + name)
subprocess.run(['docker', 'run', '--rm', '-v', str(root) + ':/work', '-w', '/work', 'mf79u-build-tools:local', 'sh', '-eu', '-c', '\n'.join(commands)], check=True)
print('PASS B03 link-only SDK generated; package builder excludes every shim.')

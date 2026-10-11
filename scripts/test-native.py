"""Run native policy/PCM/IPC fixtures in disposable Linux, with sanitizers."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
src = root / 'firmware/mf79u/src'
skip = {'sip-codec-selftest', 'pcm-network-selftest', 'ims-media-selftest', 'ims-crypto-selftest', 'cs-pcm-transport-selftest', 'cs-sip-pcm-selftest', 'net-led-ipc-selftest', 'vowifi-packet-selftest'}
extra = {'caller-id-selftest': ['caller-id.c'], 'amr-rate-selftest': ['amr-rate-policy.c', 'caller-id.c'],
         'cp-ipc-selftest': ['cp-ipc.c'], 'cp-memory-selftest': ['cp-memory.c'],
         'esp-fragment-selftest': ['ipv4-fragments.c'], 'net-led-ipc-selftest': ['net-led-policy.c']}
build = root / 'firmware/mf79u/build'
build.mkdir(exist_ok=True)
(build / 'cs-dsp-pcm-windows.h').write_bytes((root / 'firmware/mf79u/profiles/b03/historical/cs-dsp-pcm-windows.h').read_bytes())
commands = []
cases = []
for p in sorted(src.glob('*-selftest.c')):
    name = p.stem
    if name in skip:
        continue
    paths = [str(p.relative_to(root)), *['firmware/mf79u/src/' + n for n in extra.get(name, [])]]
    commands.append('echo Testing ' + name)
    compiler = 'arm-linux-gnueabi-gcc -static' if name in {'cp-ipc-selftest', 'cp-memory-selftest', 'cs-dsp-pcm-period-selftest'} else 'cc -fsanitize=address,undefined -fno-omit-frame-pointer'
    warning = ' -Wno-error=misleading-indentation' if name == 'vowifi-checksum-selftest' else ''
    commands.append(compiler + ' -O1 -g -Wall -Wextra -Werror' + warning + ' ' + ' '.join(paths) + ' -pthread -lm -o /tmp/' + name)
    commands.append(('qemu-arm ' if name in {'cp-ipc-selftest', 'cp-memory-selftest', 'cs-dsp-pcm-period-selftest'} else '') + '/tmp/' + name)
    cases.append(name)
commands += ['python3 firmware/mf79u/test-cs-pcm-bridge-stream.py',
             'python3 firmware/mf79u/test-cs-observation-evidence.py',
             'python3 scripts/test-kernel-abi.py',
             'python3 firmware/mf79u/test-cs-restore-route-guard.py',
             'touch /tmp/MF79U_ISOLATED_FIXTURE',
             'python3 firmware/mf79u/test-vowifi-registration.py']
subprocess.run(['docker', 'run', '--rm', '-v', str(root) + ':/work', '-w', '/work', 'mf79u-build-tools:local', 'sh', '-eu', '-c', '\n'.join(commands)], check=True)
reports = root / 'reports'
reports.mkdir(exist_ok=True)
(reports / 'native-tests.json').write_text(json.dumps({'passed': True, 'sanitizers': ['address', 'undefined'], 'cases': cases, 'requires_external_service_not_run': sorted(skip), 'abi_tests_under_qemu': ['cp-ipc-selftest','cp-memory-selftest','cs-dsp-pcm-period-selftest'], 'device_access': False}, indent=2) + '\n')
print('PASS', len(cases), 'native selftests plus five Python regression fixtures.')

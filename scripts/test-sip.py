"""Run the actual ARM SIP gateway against loopback peers under qemu."""
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[1]
wrapper = root / 'firmware/mf79u/build/sip-fixture-gateway'
wrapper.write_text('#!/bin/sh\nexec qemu-arm /work/firmware/mf79u/build/modem-sip-gateway "$@"\n')
wrapper.chmod(0o755)
commands = [
    "touch /tmp/MF79U_ISOLATED_FIXTURE",
    'qemu-arm firmware/mf79u/build/sip-codec-selftest',
    'qemu-arm firmware/mf79u/build/pcm-network-selftest',
    'python3 firmware/mf79u/test-sip-registrar.py --gateway /work/firmware/mf79u/build/sip-fixture-gateway',
    'python3 firmware/mf79u/test-sip-registrar.py --backend cs --gateway /work/firmware/mf79u/build/sip-fixture-gateway',
    'python3 firmware/mf79u/test-sip-sms.py --gateway /work/firmware/mf79u/build/sip-fixture-gateway',
    'python3 firmware/mf79u/test-sip-cs-media.py --gateway /work/firmware/mf79u/build/sip-fixture-gateway',
]
subprocess.run(['docker', 'run', '--rm', '-v', str(root) + ':/work', '-w', '/work', 'mf79u-build-tools:local', 'sh', '-eu', '-c', '\n'.join(commands)], check=True)
print('PASS ARM codecs, registrar, SIP SMS and bidirectional RTP/PCM fixtures.')

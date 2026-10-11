"""Build/run the preserved host USB AT utility; requires libusb/pkg-config."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
output = root / 'firmware/mf79u/build/zte-native-usb'
if sys.argv[1:] == ['--run']:
    args = shlex.split(os.environ.get('ARGS', ''))
    if not args:
        raise SystemExit('Set ARGS to an explicitly authorized AT command.')
    subprocess.run([str(output), *args], check=True)
else:
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which('pkg-config'):
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'libusb-1.0']).decode())
    else:
        prefix = next((p for p in [Path('/opt/homebrew/opt/libusb'), Path('/usr/local/opt/libusb')] if (p / 'include/libusb-1.0/libusb.h').is_file()), None)
        if prefix is None:
            raise SystemExit('Install host libusb development files and pkg-config before make build-host-tools.')
        flags = ['-I' + str(prefix / 'include/libusb-1.0'), '-L' + str(prefix / 'lib'), '-lusb-1.0']
    subprocess.run([os.environ.get('CC', 'cc'), '-Os', '-Wall', '-Wextra', str(root / 'outputs/zte-native-usb.c'), '-o', str(output), *flags], check=True)
    print('PASS host USB AT utility compiled; no device access.')

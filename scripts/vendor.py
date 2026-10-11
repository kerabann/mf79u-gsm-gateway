"""Optional private vendor inputs for historical emulation/raw-image workflows."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--import-inputs', action='store_true')
args = parser.parse_args()
if args.import_inputs:
    source = Path(os.environ.get('VENDOR_ROOT', '')).expanduser()
    if not str(os.environ.get('VENDOR_ROOT', '')) or not (source / 'bin/zte_volte_main').is_file():
        raise SystemExit('VENDOR_ROOT must point to your extracted B03 rootfs.')
    digest = hashlib.sha256((source / 'bin/zte_volte_main').read_bytes()).hexdigest()
    recipe = json.loads((root / 'firmware/mf79u/profiles/b03/private-ims-patch.json').read_text())
    if digest != recipe['source_sha256']:
        raise SystemExit('Unrecognized B03 source binary')
    target = root / 'firmware/mf79u/build/stock-rootfs'
    shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
    other = root / 'work/zte/b03mod-extracted'
    shutil.copytree(source, other, symlinks=True, dirs_exist_ok=True)
    if os.environ.get('KERNEL'):
        kernel = Path(os.environ['KERNEL'])
        profile = json.loads((root / 'firmware/mf79u/profiles/b03/kernel-abi.json').read_text())
        if hashlib.sha256(kernel.read_bytes()).hexdigest() != profile['kernel_sha256']:
            raise SystemExit('Unrecognized B03 kernel')
        dest = root / 'work/zte/voice/ap_cpuap.bin'
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kernel, dest)
    print('PASS private B03 inputs imported into ignored directories.')
else:
    abi = json.loads((root / 'firmware/mf79u/profiles/b03/link-abi.json').read_text())
    for name, metadata in abi.items():
        path = root / 'firmware/mf79u/build/stock-rootfs/lib' / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != metadata['vendor_sha256']:
            raise SystemExit('Missing/different optional private B03 library: ' + name)
    print('PASS optional private B03 library fingerprints.')

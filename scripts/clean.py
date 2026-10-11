"""Remove generated output only; preserve private vendor inputs and credentials."""
from pathlib import Path
import shutil
root = Path(__file__).resolve().parents[1]
build = root / 'firmware/mf79u/build'
if build.exists():
    for p in build.iterdir():
        if p.name == 'stock-rootfs':
            continue
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
if (root / 'dist').exists():
    shutil.rmtree(root / 'dist')
print('Generated artifacts removed; private inputs preserved.')

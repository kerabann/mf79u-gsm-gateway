"""Reject synthetic Thumb calls into ARM exports without a vendor dump."""
from pathlib import Path
import struct
import sys
import tempfile
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware/mf79u'))
from b03_kernel_relocations import audit_module, kernel_export, mode_safe

with tempfile.TemporaryDirectory(prefix='mf79u-relocations-') as temp:
    folder = Path(temp)
    for symbol, accepted in [('memset', False), ('probe_kernel_read', True)]:
        source = folder / (symbol + '.S')
        source.write_text('.syntax unified\n.thumb\n.text\n.global fixture\n.type fixture,%function\n.thumb_func\nfixture:\n bl ' + symbol + '\n bx lr\n')
        module = source.with_suffix('.ko')
        subprocess.run(['arm-linux-gnueabi-gcc', '-mthumb', '-c', str(source), '-o', str(module)], check=True)
        report = audit_module(module)
        assert report['safe'] is accepted
        assert len(report['direct_thumb_calls']) == 1
        assert report['direct_thumb_calls'][0]['symbol'] == symbol
    unknown = folder / 'unknown.S'
    unknown.write_text('.syntax unified\n.thumb\n.text\n.thumb_func\nfixture:\n bl mf79u_nonexistent_export\n bx lr\n')
    subprocess.run(['arm-linux-gnueabi-gcc', '-mthumb', '-c', str(unknown), '-o', str(unknown.with_suffix('.ko'))], check=True)
    try:
        audit_module(unknown.with_suffix('.ko'))
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError('Unknown kernel export accepted')
assert not mode_safe(10, 0xc010cb40) and not mode_safe(30, 0xc010cb40)
assert mode_safe(10, 0xc010cc1d) and mode_safe(30, 0xc010cc1d)
# Test suffix-shared export string parsing in a synthetic image.
image = bytearray(0x380100)
image[100:108] = b'xprintk\0'
struct.pack_into('<II', image, 0x380004, 0xc0323315, 101 + 0xc0047e40)
assert kernel_export(image, 'printk') == 0xc0323315
try:
    kernel_export(image, 'missing')
except ValueError:
    pass
else:
    raise AssertionError('Missing export accepted')
print('PASS synthetic Thumb/ARM relocation rejection, unknown exports and suffix-shared kernel export lookup.')

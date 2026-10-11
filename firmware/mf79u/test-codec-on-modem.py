#!/usr/bin/env python3
"""Explicit USB/RAM codec test using only a generated signal. No calls."""
from array import array
import json
import math
from pathlib import Path
import re
import shlex
import struct
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
RESULTS = HERE / 'build/codec-test'
RESULTS.mkdir(exist_ok=True)
adb = [str(WORK / 'outputs/adb'), '-s', '123456789ABCDEF']
suffix = uuid.uuid4().hex
remote_dir = '/tmp/mf79u-codec-' + suffix
remote_bin = '/dev/.mf79u-amr-' + suffix
def command(args):
    return subprocess.run(adb+args, check=True, capture_output=True, timeout=60)
def shell(text):
    return command(['shell', text]).stdout.decode(errors='replace')
def run_codec(operation, source, target):
    output = shell(' '.join(shlex.quote(x) for x in (remote_bin, operation, source, target)))
    match = re.search(r'\{"operation"[^\r\n]+\}', output)
    if not match:
        raise RuntimeError('Native codec failed to report: ' + output)
    return json.loads(match.group())

samples = [round(7000*math.sin(2*math.pi*200*i/8000) +
                 2000*math.sin(2*math.pi*600*i/8000)) for i in range(80000)]
source = RESULTS / 'generated.s16le'
source.write_bytes(struct.pack('<'+'h'*len(samples), *samples))
(RESULTS/'malformed.amr').write_bytes(b'#!AMR\n\x3c\x00')
try:
    shell('mkdir ' + shlex.quote(remote_dir))
    command(['push', str(HERE/'build/amr-tool'), remote_bin])
    shell('chmod 755 ' + shlex.quote(remote_bin))
    command(['push', str(source), remote_dir+'/input.s16le'])
    encode = run_codec('encode', remote_dir+'/input.s16le', remote_dir+'/output.amr')
    decode = run_codec('decode', remote_dir+'/output.amr', remote_dir+'/decoded.s16le')
    command(['pull', remote_dir+'/output.amr', str(RESULTS/'output.amr')])
    command(['pull', remote_dir+'/decoded.s16le', str(RESULTS/'decoded.s16le')])
    command(['push', str(RESULTS/'malformed.amr'), remote_dir+'/malformed.amr'])
    malformed = run_codec('decode', remote_dir+'/malformed.amr', remote_dir+'/invalid-output.s16le')
finally:
    # Both locations are freshly generated task-owned RAM files.
    shell('rm -f ' + shlex.quote(remote_bin) + '; rm -rf ' + shlex.quote(remote_dir))

encoded = (RESULTS/'output.amr').read_bytes()
pcm = (RESULTS/'decoded.s16le').read_bytes()
if not encoded.startswith(b'#!AMR\n') or len(encoded) != 16006 or len(pcm) != 160000:
    raise RuntimeError('Unexpected codec output length/header')
decoded = list(struct.unpack('<'+'h'*80000, pcm))
def correlation(lag):
    x = samples[1000:79000-lag]
    y = decoded[1000+lag:79000]
    mx, my = sum(x)/len(x), sum(y)/len(y)
    xx = sum((v-mx)**2 for v in x)
    yy = sum((v-my)**2 for v in y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/math.sqrt(xx*yy) if xx and yy else 0
candidates = [(correlation(lag),lag) for lag in range(161)]
quality, delay = max(candidates)
report = {'synthetic_audio': True, 'sample_rate': 8000, 'mode': 'AMR-NB MR122',
          'encode': encode, 'decode': decode, 'malformed_input': malformed,
          'amr_bytes': len(encoded), 'decoded_pcm_bytes': len(pcm),
          'best_correlation': quality, 'lag_samples': delay,
          'combined_processing_seconds': encode['elapsed_seconds'] + decode['elapsed_seconds']}
(RESULTS/'result.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2), flush=True)
if not encode['success'] or not decode['success'] or malformed['success'] or quality < 0.65:
    raise RuntimeError('Codec validation failed')

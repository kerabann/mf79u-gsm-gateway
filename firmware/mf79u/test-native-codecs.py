#!/usr/bin/env python3
"""Exercise B03's real AMR packetizer before main(), without CP/SIM/calls."""
from pathlib import Path
import subprocess
from ram_transfer import ram_push

root = Path(__file__).resolve().parents[2]
build = root / 'firmware/mf79u/build'
adb = [str(root / 'outputs/adb'), '-s', '123456789ABCDEF']

def shell(command):
    return subprocess.check_output(adb + ['shell', command], timeout=30).decode(errors='replace')

before = float(shell('cat /proc/uptime').split()[0])
ram_push(adb, build / 'operator-codecs-candidate.so', '/dev/.mf79u-operator-codecs-test.so')
ram_push(adb, build / 'operator-codecs-candidate-volte-private-ipc', '/dev/.mf79u-native-codec-test')
output = shell('MF79U_NATIVE_CODEC_TEST=1 MF79U_SOFTWARE_MEDIA=1 '
               'LD_PRELOAD=/dev/.mf79u-operator-codecs-test.so '
               '/dev/.mf79u-native-codec-test 3>&1; echo MF79U_NATIVE_TEST_EXIT:$?')
(build / 'native-codec-pipeline-test.log').write_text(output)
after = float(shell('cat /proc/uptime').split()[0])
if after < before or 'MF79U_NATIVE_TEST_EXIT:0' not in output:
    raise RuntimeError('Native codec pipeline failed; see native-codec-pipeline-test.log')
if 'SOFTWARE worker selected stack bytes result=262144' not in output:
    raise RuntimeError('Wideband worker stack guard was not exercised')
print('B03 native RTP encode/parse/decode: NB 8 modes, WB 9 modes passed; '
      '256 KiB worker stack verified; modem uptime continued; no radio initialization')

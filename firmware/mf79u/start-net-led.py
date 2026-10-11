#!/usr/bin/env python3
"""Run or stop the experimental network LED service in modem RAM, no flash."""
import json
from pathlib import Path
import subprocess
import sys
import time
from ram_transfer import ram_push

root = Path(__file__).resolve().parents[2]
build = root / 'firmware/mf79u/build'
adb = [str(root / 'outputs/adb'), '-s', '123456789ABCDEF']
remote = '/dev/.mf79u-net-led-app'

def shell(command):
    return subprocess.run(adb + ['shell', command], check=True, capture_output=True,
                          timeout=12).stdout.decode(errors='replace')

def pids():
    return [int(line.split()[0]) for line in shell('ps').splitlines()
            if line.split()[3:] == [remote]]

if sys.argv[1:] == ['--stop']:
    found = pids()
    if len(found) != 1:
        raise RuntimeError('Expected one RAM network LED service')
    pid = found[0]
    output = shell(f'if [ /proc/{pid}/exe -ef {remote} ]; then kill -TERM {pid}; '
                   'echo OWN_LED_SERVICE_STOPPED; fi')
    if 'OWN_LED_SERVICE_STOPPED' not in output:
        raise RuntimeError('Service identity changed; did not stop it')
    time.sleep(.3)
    if pids():
        raise RuntimeError('LED service has not finished its cleanup yet')
    print('RAM network LED service stopped; original GPIO paths restored')
elif not sys.argv[1:]:
    if pids():
        print(shell(remote + ' --status').strip())
        sys.exit(0)
    ram_push(adb, build / 'mf79u-net-led', remote)
    result = shell('chmod 755 ' + remote + '; ' + remote + ' --selftest')
    if 'LED policy selftest=0' not in result:
        raise RuntimeError('On-modem LED policy selftest failed')
    output = (build / 'net-led-live.log').open('wb')
    process = subprocess.Popen(adb + ['shell', remote], stdin=subprocess.DEVNULL,
                               stdout=output, stderr=subprocess.STDOUT,
                               start_new_session=True)
    output.close()
    time.sleep(1)
    found = pids()
    if process.poll() is not None or len(found) != 1:
        raise RuntimeError('RAM LED startup failed; inspect net-led-live.log')
    status = json.loads(shell(remote + ' --status').strip())
    record = {'host_adb_pid': process.pid, 'native_pid': found[0],
              'flash_written': False, 'status': status}
    (build / 'net-led-launch.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
else:
    raise SystemExit('Usage: start-net-led.py [--stop]')

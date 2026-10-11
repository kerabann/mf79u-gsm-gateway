#!/usr/bin/env python3
"""Read-only native CP proof. Does not start IMS, dial, or change SIM/NV/flash."""
import json
import hashlib
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from ram_transfer import ram_push

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADB = [str(ROOT / 'outputs/adb'), '-s', '123456789ABCDEF']


def shell(command):
    output = subprocess.check_output(ADB + ['shell', command], timeout=25)
    return output.decode(errors='replace').replace('\r', '').strip()


def queues():
    # Compare queue identities, not traffic counters or message contents.
    return {(int(row[0]), int(row[1])) for line in shell('cat /proc/sysvipc/msg').splitlines()[1:]
            if len(row := line.split()) >= 2}


def main():
    before = queues()
    results = []
    for artifact in ('cp-ipc-probe', 'cp-ipc-selftest', 'mf79u-native-gateway'):
        remote = '/dev/.mf79u-native-gateway' if artifact == 'mf79u-native-gateway' else '/dev/.mf79u-' + artifact
        ram_push(ADB, HERE / 'build' / artifact, remote)
    for command in ('AT+CFUN?', 'AT+CEREG?', 'AT^SYSINFO', 'AT+CIREP?'):
        output = shell('/dev/.mf79u-cp-ipc-probe ' + "'" + command + "'")
        if not output.startswith('LOCAL_CP_OK command=' + command + ' '):
            raise RuntimeError('Native read-only CP probe failed: ' + command)
        results.append(output)
    for command in ('/dev/.mf79u-cp-ipc-selftest', '/dev/.mf79u-native-gateway --selftest'):
        output = shell(command)
        if not output.startswith('PASS '):
            raise RuntimeError('Native synthetic selftest failed')
        results.append(output)
    if queues() != before:
        raise RuntimeError('IPC queue identities changed; inspect ownership before restarting IMS')
    report = {
        'tested_at': datetime.now(timezone.utc).isoformat(),
        'target': 'physical MF79U B03, ARMv7 soft-float',
        'artifact_sha256': {name: hashlib.sha256((HERE / 'build' / name).read_bytes()).hexdigest()
                            for name in ('cp-ipc-probe', 'cp-ipc-selftest', 'mf79u-native-gateway')},
        'native_cp_queries': results[:4],
        'synthetic_tests': results[4:],
        'queue_inventory_preserved': True,
        'usb_at_relay_used_by_native_queries': False,
        'ims_registration_or_calls_performed': False,
        'sim_aka_transaction_tested': False,
        'flash_written': False,
    }
    (HERE / 'build/native-cp-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    for line in results:
        print(line)
    print('PASS IPC inventory unchanged; no IMS activation, calls, SMS, or flash writes')


if __name__ == '__main__':
    main()

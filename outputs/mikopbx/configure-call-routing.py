#!/usr/bin/env python3
"""Update the existing MF79U outgoing route; never dial or edit historical CDRs."""
import argparse
import importlib.util
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pbx_safe_api', HERE / 'configure-sip-messages.py')
pbx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pbx)
BACKUP = pbx.PRIVATE / 'pbx-call-routing-pre.json'
ROUTE = '22'
FIELDS = ('rulename', 'numberbeginswith', 'restnumbers', 'trimfrombegin', 'prepend', 'note')


def main(restore):
    pbx.require_no_calls()
    current = pbx.api('outbound-routes/' + ROUTE)
    if current['providerid'] != pbx.PROVIDER:
        raise RuntimeError('MF79U route ownership changed')
    pbx.PRIVATE.mkdir(mode=0o700, exist_ok=True)
    if not BACKUP.exists():
        with os.fdopen(os.open(BACKUP, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as file:
            json.dump(current, file)
    if restore:
        previous = json.loads(BACKUP.read_text())
        update = {k: previous[k] for k in FIELDS}
    else:
        update = dict(rulename='MF79U SIM calls', numberbeginswith='[0-9]{3}', restnumbers=-1,
                      trimfrombegin=0, prepend='',
                      note='External numeric calls through the MF79U SIM; internal extensions stay local.')
    pbx.api('outbound-routes/' + ROUTE, update)
    expected = '${REGEX("^' + update['numberbeginswith']
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        config = __import__('subprocess').check_output(['docker', 'exec', 'mf79u-mikopbx',
                  'cat', '/etc/asterisk/extensions.conf'], timeout=8).decode()
        if expected in config:
            pbx.require_no_calls()
            pbx.cli('dialplan reload')
            if expected not in pbx.cli('dialplan show outgoing'):
                raise RuntimeError('Outgoing route not loaded')
            print(json.dumps({'persistentOutgoingRoute': True, 'restored': restore,
                              'callsMade': False, 'historyModified': False}))
            return
        time.sleep(.5)
    raise RuntimeError('PBX route generation timed out')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--restore', action='store_true')
    main(parser.parse_args().restore)

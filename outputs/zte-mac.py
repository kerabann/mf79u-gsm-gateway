#!/usr/bin/env python3
"""Native MF79U factory USB access; no Windows or serial driver required."""
import argparse
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

USB = Path(__file__).with_name('zte-native-usb')

def at(command, expected=None):
    args = [str(USB), command]
    if expected is not None:
        args.append(str(expected))
    result = subprocess.run(args, capture_output=True, timeout=40)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip())
    data = result.stdout
    if not data.endswith(b'\r\nOK\r\n'):
        raise RuntimeError(data.decode(errors='replace').strip() or 'No AT response')
    return data[:-6]

def shell(command, expected=None):
    # Wrap the command so redirection covers every command and shell errors.
    return at('AT+SHELL=(' + command + ') >/dev/ttyGS0 2>/dev/ttyGS0', expected)

def pull(remote, destination):
    quoted = shlex.quote(remote)
    size = int(shell('/bin/busybox wc -c < ' + quoted).strip())
    digest = shell('/bin/busybox md5sum ' + quoted).split()[0].decode()
    destination = Path(destination)
    partial = destination.with_name(destination.name + '.partial')
    if destination.exists() or partial.exists():
        raise RuntimeError('Destination or partial file already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with partial.open('xb') as output:
        for offset in range(0, size, 4096):
            expected = min(4096, size - offset)
            for attempt in range(3):
                data = shell(f'/bin/busybox dd if={quoted} bs=4096 skip={offset//4096} count=1 2>/dev/null', expected)
                if len(data) == expected:
                    break
            else:
                raise RuntimeError(f'Short USB read at {offset}; retained {partial}')
            output.write(data)
            print(f'\r{offset + len(data)}/{size}', end='', file=sys.stderr, flush=True)
    local = hashlib.md5(partial.read_bytes()).hexdigest()
    after = shell('/bin/busybox md5sum ' + quoted).split()[0].decode()
    if local != digest or after != digest:
        raise RuntimeError(f'Checksum mismatch; retained {partial}')
    partial.rename(destination)
    print(f'\nVerified MD5 {local}', file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    command = commands.add_parser('at'); command.add_argument('command')
    command = commands.add_parser('shell'); command.add_argument('command')
    command = commands.add_parser('pull'); command.add_argument('remote'); command.add_argument('local')
    commands.add_parser('sms-status')
    commands.add_parser('sms-prepare')
    commands.add_parser('sms-list')
    args = parser.parse_args()
    if args.action == 'pull':
        pull(args.remote, args.local)
    elif args.action == 'at':
        sys.stdout.buffer.write(at(args.command))
    elif args.action == 'shell':
        sys.stdout.buffer.write(shell(args.command))
    elif args.action == 'sms-status':
        for command in ('AT+CPMS?', 'AT+CNMI?'):
            sys.stdout.buffer.write(at(command))
    elif args.action == 'sms-prepare':
        # Save incoming messages on SIM; notify with CMTI rather than direct CMT.
        for command in ('AT+CMGF=0', 'AT+CPMS="SM","SM","SM"', 'AT+CNMI=2,1,0,0,0'):
            sys.stdout.buffer.write(at(command))
    elif args.action == 'sms-list':
        at('AT+CMGF=0')
        # PDU mode avoids modem character-set ambiguity. CMGL may mark read.
        sys.stdout.buffer.write(at('AT+CMGL=4'))

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        sys.exit(str(error))

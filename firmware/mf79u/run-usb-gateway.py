#!/usr/bin/env python3
"""Restore the existing Mac IMS relay after a modem power/USB reconnect."""
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'firmware/mf79u/build'
LAUNCHER = ROOT / 'firmware/mf79u/run-pbx-gateway.py'
ADB = [str(ROOT / 'outputs/adb'), '-s', '123456789ABCDEF']
running = True
child = None


def report(event):
    print(json.dumps({'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                      'event': event}), flush=True)


def command(args, timeout=5):
    return subprocess.run(args, capture_output=True, timeout=timeout,
                          text=True)


def existing_gateway():
    """Adopt only the recorded launcher from this project; never signal it."""
    try:
        pid = int((BUILD / 'pbx-gateway-host-pid.txt').read_text().strip())
        result = command(['ps', '-p', str(pid), '-o', 'command='])
        tokens = shlex.split(result.stdout.strip())
        script = next(Path(s) for s in tokens if s.endswith('run-pbx-gateway.py'))
        if script.is_absolute():
            return script.resolve() == LAUNCHER
        cwd = command(['/usr/sbin/lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'])
        return any(line.startswith('n') and (Path(line[1:]) / script).resolve() == LAUNCHER
                   for line in cwd.stdout.splitlines())
    except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired):
        return False


def stop(signum, frame):
    global running
    running = False


def supervise():
    global child
    last = None
    while running:
        if child is not None and child.poll() is not None:
            report('relay_exited')
            child = None
            for _ in range(30):
                if not running:
                    return
                time.sleep(1)
        if child is not None or existing_gateway():
            state = 'relay_running'
        else:
            try:
                device = command(ADB + ['get-state'])
                connected = device.returncode == 0 and device.stdout.strip() == 'device'
            except (OSError, subprocess.TimeoutExpired):
                connected = False
            state = 'waiting_for_usb'
            if connected:
                links = ('ln -sf /mnt/userdata/mf79u/.mf79u-volte-private /dev/.mf79u-volte-private; '
                         'ln -sf /mnt/userdata/mf79u/.mf79u-sip-gateway /dev/.mf79u-sip-gateway; '
                         'ln -sf /mnt/userdata/mf79u/.mf79u-ims-userspace-ipsec.so /dev/.mf79u-ims-userspace-ipsec.so')
                try:
                    ready = command(ADB + ['shell', 'test -x /mnt/userdata/mf79u/.mf79u-volte-private && ' + links])
                    if ready.returncode == 0:
                        child = subprocess.Popen([sys.executable, str(LAUNCHER), '--adaptive-audio'],
                                                 cwd=ROOT)
                        state = 'relay_starting'
                except (OSError, subprocess.TimeoutExpired):
                    state = 'waiting_for_modem'
        if state != last:
            report(state)
            last = state
        time.sleep(2)


if __name__ == '__main__':
    BUILD.mkdir(parents=True, exist_ok=True)
    lock = os.open(BUILD / 'usb-gateway-supervisor.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('MF79U USB supervisor is already running')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        supervise()
    finally:
        if child is not None and child.poll() is None:
            # Only the launcher created by this supervisor is stopped.
            child.terminate()
            try:
                child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                report('relay_shutdown_pending')
        os.close(lock)

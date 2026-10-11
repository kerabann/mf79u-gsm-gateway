#!/usr/bin/env python3
"""Connect USB devices appearing after startup to Windows. Ctrl+C stops."""
import argparse
import re
import subprocess
import sys
import time

CLI = "/Applications/UTM.app/Contents/MacOS/utmctl"
VM = "E1B09ECF-899C-47DD-9E10-CA348E9DB18C"
ROW = re.compile(r"^(.*?)\s+([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\s+(\d+)\s*$")


def call(*args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=3)
    # AppleEvent errors can appear on stderr even with exit code zero.
    if r.returncode or r.stderr.strip():
        raise RuntimeError((r.stderr or r.stdout).strip() or f"exit {r.returncode}")
    return r.stdout


def inventory():
    output = call("usb", "list")
    if output.strip() == "No devices found. Make sure a USB sharing enabled VM is running.":
        return {}
    if "Location" not in output:
        raise RuntimeError(f"Unexpected USB list output: {output.strip()!r}")
    devices = {}
    for line in output.splitlines()[1:]:
        m = ROW.match(line)
        if m:
            name, vid, pid, location = m.groups()
            devices[(location, vid.upper(), pid.upper())] = name.strip()
        elif line.strip():
            raise RuntimeError(f"Cannot parse USB device: {line}")
    return devices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if call("status", VM).strip() != "started":
        raise RuntimeError("Start the Windows VM first")
    ignored = set(inventory())
    connected = set()
    previous = None
    errors = {}
    next_status = 0
    def report(message):
        if time.monotonic() - errors.get(message, -10) >= 5:
            print(message, flush=True)
            errors[message] = time.monotonic()
    print(f"Watching new USB devices → Windows; ignoring {len(ignored)} existing device(s). Ctrl+C stops.", flush=True)
    while True:
        try:
            if time.monotonic() >= next_status:
                if call("status", VM).strip() != "started":
                    print("Windows VM stopped; watcher stopped.", flush=True)
                    return
                next_status = time.monotonic() + 2
            devices = inventory()  # Snapshot, not live AppleScript references.
            present = set(devices)
            ignored.intersection_update(present)
            connected.intersection_update(present)
            if devices != previous:
                for (location, vid, pid), name in devices.items():
                    print(f"USB: {name} {vid}:{pid} location={location}", flush=True)
                if not devices:
                    print("USB list empty", flush=True)
                previous = devices
            if args.dry_run:
                return
            for key, name in devices.items():
                if key in ignored or key in connected:
                    continue
                location, vid, pid = key
                try:
                    call("usb", "connect", VM, location)
                    connected.add(key)
                    print(f"Connected: {name} {vid}:{pid}", flush=True)
                except (RuntimeError, subprocess.TimeoutExpired) as exc:
                    report(f"Connect failed: {name} {vid}:{pid}: {exc}")
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            report(f"UTM temporarily unavailable: {exc}")
            if args.dry_run:
                raise
        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nWatcher stopped.")
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Cannot start watcher: {exc}", file=sys.stderr)
        sys.exit(1)

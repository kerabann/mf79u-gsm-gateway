#!/usr/bin/env python3
"""Explicit, guarded B03 identity write with a private original-value backup.

--write reads the authorized new value from stdin. --restore-original reads
the saved original. Values/responses never appear in logs or public reports.
--reboot verifies persistence plus autonomous IMS/SIP startup.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("imei_patch", HERE / "install-imei-patch.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)
PRIVATE = ROOT / "outputs/private"
ORIGINAL = PRIVATE / "imei-original-123456789ABCDEF.json"


def at(command):
    try:
        p = subprocess.run([str(ROOT / "outputs/zte-native-usb"), command],
                           capture_output=True, timeout=35)
    except subprocess.TimeoutExpired:
        raise RuntimeError("USB AT timed out; inspect readback before retrying any write") from None
    if p.returncode:
        raise RuntimeError("USB AT failed; response intentionally omitted")
    return p.stdout.decode(errors="replace")


def read_identity(command="AT+READIMEI?"):
    response = at(command)
    values = re.findall(r"(?<!\d)\d{15}(?!\d)", response)
    if len(values) != 1 or not re.search(r"\bOK\b", response):
        raise RuntimeError("Identity query did not return exactly one value")
    return values[0]


def valid(value):
    if not re.fullmatch(r"[0-9]{15}", value):
        return False
    digits = [int(c) for c in value]
    return sum((n * 2 // 10 + n * 2 % 10) if i % 2 else n
               for i, n in enumerate(digits)) % 10 == 0


def preserve(value):
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    if PRIVATE.is_symlink():
        raise RuntimeError("Private backup directory must not be a symlink")
    os.chmod(PRIVATE, 0o700)
    if ORIGINAL.exists():
        if ORIGINAL.is_symlink() or ORIGINAL.stat().st_mode & 0o077:
            raise RuntimeError("Original identity backup permissions are unsafe")
        saved = json.loads(ORIGINAL.read_text())
        if not valid(saved.get("imei", "")):
            raise RuntimeError("Invalid original identity backup")
        # Never overwrite an existing original when switching a second time.
        return
    fd = os.open(ORIGINAL, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"schema": 1, "firmwareBase": "BD_XCBZHKMF79UV1.0.0B03",
                   "imei": value, "savedAt": datetime.now(timezone.utc).isoformat()}, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    if json.loads(ORIGINAL.read_text())["imei"] != value:
        raise RuntimeError("Original identity backup verification failed")


def main(args):
    if args.restore_original:
        if ORIGINAL.is_symlink() or not ORIGINAL.exists() or ORIGINAL.stat().st_mode & 0o077:
            raise RuntimeError("Private original backup unavailable")
        target = json.loads(ORIGINAL.read_text())["imei"]
    else:
        target = sys.stdin.readline().strip()
    if not valid(target):
        raise RuntimeError("Require exactly 15 decimal digits with a valid check digit")
    stock, candidate, _ = patch.prepare()
    if patch.remote_digest(patch.TARGET) != patch.digest(candidate):
        raise RuntimeError("Exact B03 IMEI-only patch is required")
    status = json.loads(patch.shell("cat /dev/.mf79u-gateway-status.json"))
    if status.get("activeCall") is not False:
        raise RuntimeError("Require no active call")
    checks = json.loads((ROOT / "outputs/zte-backup/checksums.json").read_text())
    for name in ("rootfs.mtd5.bin", "nvrofs.mtd3.bin"):
        data = (ROOT / "outputs/zte-backup" / name).read_bytes()
        if len(data) != checks[name]["size"] or hashlib.sha256(data).hexdigest() != checks[name]["sha256"]:
            raise RuntimeError("Saved recovery artifact checksum mismatch")
    before = read_identity()
    preserve(before)
    print("Private original-value backup verified; no active call.", flush=True)
    wrote = before != target
    if wrote:
        # Single explicit write, never automatically repeated if reply is ambiguous.
        response = at("AT+MODIMEI=" + target)
        if "+CME ERROR:" in response or not re.search(r"\bOK\b", response):
            raise RuntimeError("Identity writer did not confirm success; do not retry blindly")
    if read_identity() != target:
        raise RuntimeError("Immediate NV identity readback does not match requested value")
    print("Requested identity matches immediate NV readback.", flush=True)
    report = {"date": datetime.now().astimezone().date().isoformat(),
              "verifiedAtUTC": datetime.now(timezone.utc).isoformat(),
              "operation": "restore" if args.restore_original else "write",
              "validIdentityWritePerformed": wrote, "privateOriginalBackup": str(ORIGINAL),
              "immediateReadbackMatchesRequested": True, "rawFlashPerformed": False,
              "softwareRebootVerified": False, "persistedReadbackMatchesRequested": False}
    if args.reboot:
        # Recheck call state immediately before reboot, after readback.
        status = json.loads(patch.shell("cat /dev/.mf79u-gateway-status.json"))
        if status.get("activeCall") is not False:
            raise RuntimeError("Call became active; identity written, postpone reboot")
        previous_boot = patch.shell("cat /proc/sys/kernel/random/boot_id")
        print("Rebooting to check persistence and cellular identity.", flush=True)
        start = last_update = time.monotonic()
        try:
            subprocess.run(patch.ADB + ["shell", "sync; reboot"], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        ready = None
        while time.monotonic() - start < 240:
            try:
                boot = patch.shell("cat /proc/sys/kernel/random/boot_id")
                if boot and boot != previous_boot:
                    ready = json.loads(patch.shell("cat /dev/.mf79u-gateway-status.json"))
                    if ready.get("running") is True and ready.get("imsReady") is True:
                        break
            except (subprocess.SubprocessError, json.JSONDecodeError):
                pass
            if time.monotonic() - last_update > 25:
                print("Waiting for autonomous modem services.", flush=True)
                last_update = time.monotonic()
            time.sleep(3)
        if not ready or ready.get("imsReady") is not True:
            raise RuntimeError("Identity written; autonomous IMS verification timed out")
        if ready.get("activeCall") is not False:
            raise RuntimeError("Post-reboot call active; postpone AT queries")
        report.update({"softwareRebootVerified": True,
                       "persistedReadbackMatchesRequested": read_identity() == target,
                       "cellularCGSNMatchesRequested": read_identity("AT+CGSN") == target,
                       "imsReady": ready["imsReady"], "sipRunning": ready["running"],
                       "sipRole": ready.get("role"),
                       "observedRebootVerificationSeconds": round(time.monotonic() - start, 1)})
        if not report["persistedReadbackMatchesRequested"] or not report["cellularCGSNMatchesRequested"]:
            raise RuntimeError("Post-reboot identity mismatch; use private original for recovery")
    out = HERE / "build/imei-write-live.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--restore-original", action="store_true")
    parser.add_argument("--reboot", action="store_true")
    args = parser.parse_args()
    try:
        main(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)  # These messages contain no identities/responses.
        sys.exit(1)
    except (OSError, ValueError, subprocess.SubprocessError):
        print("Verification stopped. Details/identity responses intentionally omitted; inspect state before another write.", file=sys.stderr)
        sys.exit(1)

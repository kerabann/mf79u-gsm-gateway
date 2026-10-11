#!/usr/bin/env python3
"""Reversible, exact-B03 IMEI authorization branch patch; never sends NV writes.

Default: prepare a one-byte candidate. --install / --restore replace only
/lib/libatext.so atomically, then return the root filesystem to read-only.
Keep a hard link to the old mapped inode so JFFS2 can remount read-only.
The loaded vendor process is untouched; a separate reboot is required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from ram_transfer import ram_push

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADB = [str(ROOT / "outputs/adb"), "-s", "123456789ABCDEF"]
STOCK_SHA256 = "1c34f29d61f98a39c6241a70972b1989b6932c3a5e7844fb550ca443779b9678"
TARGET = "/lib/libatext.so"
BACKUP = "/mnt/userdata/mf79u/libatext.vendor.b03.so"
RAM = "/dev/.mf79u-libatext-imei.so"


def digest(data):
    return hashlib.md5(data).hexdigest()


def shell(command):
    return subprocess.check_output(ADB + ["shell", command], stderr=subprocess.PIPE,
                                   timeout=25).decode().replace("\r", "").strip()


def remote_digest(path):
    output = shell("md5sum " + shlex.quote(path)).split()
    return output[0] if output else ""


def prepare():
    stock = (HERE / "build/stock-rootfs/lib/libatext.so").read_bytes()
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256 or len(stock) != 101072:
        raise RuntimeError("Unexpected stock library; exact B03 is required")
    if stock[0x5A32:0x5A34] != bytes.fromhex("0bd0"):
        raise RuntimeError("Unexpected Thumb authorization instruction")
    patched = bytearray(stock)
    patched[0x5A33] = 0xD1  # BEQ -> BNE, matching the forum IMEI-only change.
    patched = bytes(patched)
    if [i for i, (a, b) in enumerate(zip(stock, patched)) if a != b] != [0x5A33]:
        raise RuntimeError("Candidate is not an exact one-byte patch")
    candidate = HERE / "build/libatext.imei-only.b03.so"
    candidate.write_bytes(patched)
    return stock, patched, candidate


def replace(restore):
    stock, patched, candidate = prepare()
    expected = digest(patched if restore else stock)
    desired = digest(stock if restore else patched)
    try:
        status = json.loads(shell("cat /dev/.mf79u-gateway-status.json"))
    except (json.JSONDecodeError, subprocess.SubprocessError):
        if not restore:
            raise RuntimeError("Gateway status unavailable") from None
        status = {}  # Permit recovery when the gateway cannot start.
    if status.get("activeCall") is True or (not restore and
            (status.get("activeCall") is not False or status.get("imsReady") is not True)):
        raise RuntimeError("Require a ready gateway and no active call")
    if remote_digest(TARGET) not in {expected, desired}:
        raise RuntimeError("Device library does not match stock or our exact candidate")
    if not restore and shell("test -f " + BACKUP + " && echo PRESENT") != "PRESENT":
        if remote_digest(TARGET) != digest(stock):
            raise RuntimeError("Original library missing; refuse to invent a device backup")
        result = shell("set -e; cp " + TARGET + " " + BACKUP + ".next; chmod 600 " +
                       BACKUP + ".next; mv " + BACKUP + ".next " + BACKUP + "; sync; echo BACKUP_OK")
        if "BACKUP_OK" not in result:
            raise RuntimeError("Device backup failed")
    if remote_digest(BACKUP) != digest(stock):
        raise RuntimeError("Verified original device backup is required")
    if remote_digest(TARGET) == desired:
        print("Requested library already installed; reboot required if loaded copy differs.")
        return
    mounts = shell("cat /proc/mounts").splitlines()
    if not any(line.startswith("/dev/root / jffs2 ro,") for line in mounts):
        raise RuntimeError("Expected read-only B03 JFFS2 root filesystem")
    keep = TARGET + ".mf79u-previous"
    if shell("test -e " + keep + " && echo PRESENT") == "PRESENT":
        # Deleting a prior mapped inode could again prevent a read-only remount.
        raise RuntimeError("Previous mapped library link exists; inspect ownership before replacing")
    if restore:
        source = BACKUP
    else:
        ram_push(ADB, candidate, RAM)
        source = RAM
    # Recheck immediately before remount. Never alter a mapped inode in place.
    command = ("set -e; test \"$(md5sum " + TARGET + " | cut -d ' ' -f 1)\" = " + expected +
               "; trap 'mount -o remount,ro /' EXIT; mount -o remount,rw /; ln " + TARGET + " " + keep + "; cp " + source +
               " " + TARGET + ".mf79u-next; chmod 755 " + TARGET + ".mf79u-next; " +
               "test \"$(md5sum " + TARGET + ".mf79u-next | cut -d ' ' -f 1)\" = " + desired +
               "; mv " + TARGET + ".mf79u-next " + TARGET + "; sync; echo REPLACED_OK")
    result = shell(command)
    if "REPLACED_OK" not in result or remote_digest(TARGET) != desired:
        raise RuntimeError("Library installation did not pass verification")
    if not any(line.startswith("/dev/root / jffs2 ro,") for line in shell("cat /proc/mounts").splitlines()):
        raise RuntimeError("Root filesystem was not returned to read-only")
    shell("rm -f " + RAM)
    print("Original B03 library restored." if restore else "One-byte B03 IMEI branch patch installed.")
    print("Root filesystem read-only; loaded vendor process untouched. Reboot to activate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.install or args.restore:
        replace(args.restore)
    else:
        stock, patched, candidate = prepare()
        print(json.dumps({"candidate": str(candidate), "changedOffset": "0x5a33", "changedBytes": 1,
                          "stockMD5": digest(stock), "patchedMD5": digest(patched),
                          "patchedSHA256": hashlib.sha256(patched).hexdigest(), "deviceChanged": False}, indent=2))

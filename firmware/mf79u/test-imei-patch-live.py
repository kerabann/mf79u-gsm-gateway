#!/usr/bin/env python3
"""Install/reboot verification using only a rejected one-digit IMEI argument.

IMEI values exist only transiently in this process, never in output or reports.
No valid IMEI write command, call or SMS mutation is sent.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("imei_patch", HERE / "install-imei-patch.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def at(command):
    result = subprocess.run([str(ROOT / "outputs/zte-native-usb"), command],
                            capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("USB AT request failed (response intentionally omitted)")
    return result.stdout.decode(errors="replace")


def identity():
    response = at("AT+READIMEI?")
    values = re.findall(r"(?<!\d)\d{15}(?!\d)", response)
    if len(values) != 1 or not re.search(r"\bOK\b", response):
        raise RuntimeError("Read-only identity query did not return exactly one identity")
    return values[0]


def verify():
    stock, patched, _ = patch.prepare()
    if patch.remote_digest(patch.TARGET) not in {patch.digest(stock), patch.digest(patched)}:
        raise RuntimeError("Library is neither stock nor our exact one-byte candidate")
    # Revalidate saved compatibility/recovery artifacts, without printing their contents.
    checks = json.loads((ROOT / "outputs/zte-backup/checksums.json").read_text())
    for name in ("rootfs.mtd5.bin", "nvrofs.mtd3.bin"):
        data = (ROOT / "outputs/zte-backup" / name).read_bytes()
        if len(data) != checks[name]["size"] or hashlib.sha256(data).hexdigest() != checks[name]["sha256"]:
            raise RuntimeError("Saved recovery artifact checksum mismatch")
    before_boot = patch.shell("cat /proc/sys/kernel/random/boot_id")
    previous_identity = identity()
    if "unauthorized" not in at("AT+MODIMEI=0").lower():
        raise RuntimeError("Unexpected stock authorization response; no installation")
    print("Stock baseline confirmed; original identity retained only in RAM.", flush=True)
    patch.replace(False)
    start = time.monotonic()
    print("Requesting software reboot to load the new library.", flush=True)
    try:
        subprocess.run(patch.ADB + ["shell", "sync; reboot"], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        pass  # adbd may disappear before returning its reply.
    ready = None
    boot_changed = False
    last_update = start
    while time.monotonic() - start < 240:
        try:
            current_boot = patch.shell("cat /proc/sys/kernel/random/boot_id")
            boot_changed = bool(current_boot) and current_boot != before_boot
            if boot_changed:
                ready = json.loads(patch.shell("cat /dev/.mf79u-gateway-status.json"))
                if ready.get("imsReady") is True and ready.get("running") is True:
                    break
        except (subprocess.SubprocessError, json.JSONDecodeError):
            pass
        if time.monotonic() - last_update > 25:
            print("Waiting for modem reboot and autonomous IMS/SIP startup.", flush=True)
            last_update = time.monotonic()
        time.sleep(3)
    if not boot_changed or not ready or ready.get("imsReady") is not True:
        raise RuntimeError("Reboot/IMS verification timed out; use guarded --restore if necessary")
    if ready.get("activeCall") is not False:
        raise RuntimeError("Active call present; postpone USB AT verification")
    if patch.remote_digest(patch.TARGET) != patch.digest(patched):
        raise RuntimeError("Library patch did not survive reboot")
    response = at("AT+MODIMEI=0")
    if "unauthorized" in response.lower() or not re.search(r"\+CME ERROR:\s*8001\b", response):
        raise RuntimeError("Patched handler did not return the expected pre-NV length error")
    same_identity = identity() == previous_identity
    del previous_identity
    if not same_identity:
        raise RuntimeError("Unexpected identity change; stop further tests")
    mounts = patch.shell("cat /proc/mounts").splitlines()
    root_ro = any(line.startswith("/dev/root / jffs2 ro,") for line in mounts)
    if not root_ro:
        raise RuntimeError("Root filesystem is not read-only after reboot")
    report = {
        "date": "2026-10-08", "firmwareBase": "BD_XCBZHKMF79UV1.0.0B03",
        "library": patch.TARGET, "stockMD5": patch.digest(stock),
        "patchedMD5": patch.digest(patched), "patchedSHA256": hashlib.sha256(patched).hexdigest(),
        "changedBytes": 1, "offset": "0x5a33", "instruction": "BEQ -> BNE",
        "installed": True, "deviceBackup": patch.BACKUP, "deviceBackupVerified": True,
        "rootfsBackupVerified": True, "nvBackupVerified": True,
        "softwareRebootVerified": True, "rootReadOnlyAfterReboot": root_ro,
        "stockInvalidArgumentResponse": "+CME ERROR: unauthorized",
        "patchedInvalidArgumentResponse": "+CME ERROR: 8001", "testArgument": "0",
        "imeiUnchanged": same_identity, "validIMEIWriteAttempted": False,
        "nvIdentityWriteAttempted": False, "rawFlashPerformed": False,
        "macAuthADBBypassesApplied": False,
        "imsReadyAfterReboot": ready["imsReady"], "sipRunningAfterReboot": ready["running"],
        "sipRole": ready.get("role"), "activeCall": ready["activeCall"],
        "rebootToReadyObservedSeconds": round(time.monotonic() - start, 1),
        "conclusion": "IMEI authorization branch bypass verified through invalid length rejection. Actual NV identity writing remains untested."
    }
    (HERE / "build/imei-patch-live.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-reboot", action="store_true")
    args = parser.parse_args()
    if not args.install_reboot:
        parser.error("Pass --install-reboot to perform this device-changing verification")
    verify()

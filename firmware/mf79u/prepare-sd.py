#!/usr/bin/env python3
"""Prepare a versioned MF79U runtime on an already formatted USB microSD.

Does not format a disk, install a boot hook, flash NAND, or copy credentials.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
WORK = HERE.parent.parent


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", required=True, help="The verified ZTE SD partition, e.g. disk5s1")
    args = parser.parse_args()
    d = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", args.disk]))
    parent = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", d["ParentWholeDisk"]]))
    if (parent.get("Internal") or parent.get("IORegistryEntryName") != "ZTE MMC Storage 2.31 Media"
            or parent.get("TotalSize") != 31268536320 or d.get("VolumeName") != "ZTE_SD"
            or d.get("FilesystemType") != "msdos" or not d.get("MountPoint")):
        raise SystemExit("Refusing: this is not the formatted, verified MF79U microSD")
    manifest = json.loads((BUILD / "manifest.json").read_text())
    version = manifest["version"]
    if version != "mf79u-custom-0.8-experimental" or manifest["autonomy"]["ready"]:
        raise SystemExit("Unexpected firmware stage")
    files = {
        "bin/mf79u-control": BUILD / "mf79u-control",
        "bin/mf79u-sip-gateway": BUILD / "modem-sip-gateway",
        "bin/mf79u-ims-private": BUILD / "volte-private-ipc",
        "bin/mf79u-ims-probe": BUILD / "volte-ipc-probe",
        "bin/mf79u-net-led": BUILD / "mf79u-net-led",
        "bin/mf79u-amr-tool": BUILD / "amr-tool",
        "bin/mf79u-cp-probe": BUILD / "cp-ipc-probe",
        "bin/mf79u-cp-selftest": BUILD / "cp-ipc-selftest",
        "bin/mf79u-native-gateway": BUILD / "mf79u-native-gateway",
        "bin/mf79u-sip-codec-selftest": BUILD / "sip-codec-selftest",
        "lib/mf79u-ims-userspace-ipsec.so": BUILD / "ims-userspace-ipsec.so",
        "certs/ca-bundle.pem": WORK / "work/zte/voice/sip-deps/ca-bundle.pem",
        "manifest.json": BUILD / "manifest.json",
        "native-cp-verification.json": BUILD / "native-cp-verification.json",
        "AUTONOMOUS.md": HERE / "AUTONOMOUS.md",
    }
    for name, source in {
        "opus": "work/zte/voice/sip-deps/opus-1.6.1/COPYING",
        "bcg729": "work/zte/voice/sip-deps/bcg729-1.1.2/LICENSE.txt",
        "openssl": "work/zte/voice/sip-deps/openssl-3.5.9/LICENSE.txt",
        "pjproject": "work/zte/voice/pjproject/pjproject-2.17/COPYING",
        "opencore-amr": "work/zte/voice/opencore-amr-0.1.6/LICENSE",
        "vo-amrwbenc": "work/zte/voice/vo-amrwbenc-0.1.3/COPYING",
    }.items():
        files[f"licenses/{name}.txt"] = WORK / source
    # Bind every runtime artifact to the reviewed rootfs manifest, before copying.
    changes = {c["path"]: c["sha256"] for c in manifest["changes"]}
    for name, source in files.items():
        if name.startswith("bin/") or name.startswith("lib/"):
            if name == "bin/mf79u-sip-codec-selftest":
                continue  # Diagnostic fixture, not a rootfs runtime overlay.
            path = "/usr/" + name if name.startswith("bin/") else "/" + name
            if digest(source) != changes[path]:
                raise SystemExit(f"Artifact changed after rootfs verification: {name}")
    root = Path(d["MountPoint"]) / "mf79u"
    target = root / "versions" / version
    target.mkdir(parents=True, exist_ok=False)
    entries = []
    for name, source in files.items():
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        sha = digest(source)
        if digest(dest) != sha:
            raise SystemExit(f"Copy verification failed: {name}")
        entries.append({"path": name, "bytes": dest.stat().st_size,
                        "sha256": sha, "md5": digest(dest, "md5")})
    for algorithm in ("sha256", "md5"):
        (target / ("SHA256SUMS" if algorithm == "sha256" else "MD5SUMS")).write_text(
            "".join(f"{e[algorithm]}  {e['path']}\n" for e in entries))
    (root / "README.txt").write_text(
        "MF79U SD runtime, stage 0.8 (experimental)\n"
        "This card stores versioned ARMv7 soft-float components.\n"
        "The modem still boots the B03 kernel/rootfs from internal flash.\n"
        "Native IMS/PDP/AKA autonomy is incomplete; voice needs the Mac relay.\n"
        "Settings and SIP credentials remain in /mnt/userdata/mf79u.\n"
        "Never mount the card writable on Mac and modem at the same time.\n"
        "No automatic IMS startup or raw flash is enabled by this bundle.\n")
    (root / "current.txt").write_text(version + "\n")
    report = {"prepared_at": datetime.now(timezone.utc).isoformat(),
              "card_bytes": parent["TotalSize"], "filesystem": "FAT32", "version": version,
              "files": entries, "total_bytes": sum(e["bytes"] for e in entries),
              "source_and_card_sha256_verified": True, "credentials_copied": False,
              "autonomous_voice_ready": False, "boot_hook_installed": False}
    (BUILD / "sd-prepare-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (target / "READY").write_text("sha256-verified\n")
    subprocess.run(["sync"], check=True)
    print(f"Prepared {len(entries)} files, {report['total_bytes']} bytes; all SHA256 verified")


if __name__ == "__main__":
    main()

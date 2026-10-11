> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# MF79U microSD runtime

Сверено 2026-10-08. Карта — исторический runtime0.8 архив; текущий
Control0.10/native/SIP/LED запускаются из внутренней userdata благодаря
control-internal-preferred. Сводка: [STATUS.md](STATUS.md).

The user copied the Flipper files to their own backup and explicitly authorized
formatting on 2026-10-07. No completed project backup of those files exists.
The unfinished raw image was cancelled; it is not a usable backup.

The physical card is 31,268,536,320 bytes. It was formatted on Mac as one MBR
FAT32 partition, volume `ZTE_SD`, starting at sector 2048. Disk numbers change;
identify `ZTE MMC Storage 2.31 Media` before using diskutil. Never select the
small virtual `ZTEMODEM` CD or an internal disk.

## Layout and verification

- `mf79u/versions/mf79u-custom-0.8-experimental/`: versioned ARM runtime,
  certificate bundle, licenses, manifest and diagnostic executables.
- `mf79u/current.txt`: staged version name; it is informational at this stage.
- `SHA256SUMS` and `MD5SUMS`: 21 files, 20,812,865 bytes, verified from Mac.
- `build/sd-prepare-report.json`: local copy/checksum and physical test evidence.

`prepare-sd.py --disk diskXs1` only copies to an already formatted, identified
ZTE card; it never formats a disk. It verifies runtime artifacts against the
reviewed rootfs manifest, copies licenses, checks every SHA256, and writes READY
last. It deliberately excludes settings, SIP credentials, SMS and NV backups.

## Ownership of the card

The card device is `/dev/mmcblk0`, partition `/dev/mmcblk0p1`. In USB mode it is
exported through `/sys/devices/platform/zx29_hsotg.0/gadget/lun1/file`.
`lun0` is the virtual CD and must remain unchanged. Simply clearing `lun1/file`
is insufficient: stock ZTE can populate it again when SD mode remains 0.

On this B03 the stock goform handlers HTTPSHARE_MODE_SET and
HTTPSHARE_AUTH_SET returned failure. The existing NV setting
`sdcard_mode_option` was changed from 0 to 1 with `nv set`. After the Mac volume
was unmounted, the card LUN was detached and its `ro` flag set to 1. HTTP share
status remained Disabled; no open file-sharing server was enabled.

Formatting from Mac does not refresh the modem kernel's cached partition map.
`sd-reread` opens the card read-only and calls BLKRRPART only after checking the
exact block device/capacity, no local mount, and an empty card LUN. This changed
the cached start from sector 32 to the actual sector 2048. It writes no sectors.
Build it with `sh build-sd-tools.sh`. Reboot naturally refreshes that map too.

Read-only mount recorded at the SD verification stage:

```text
/dev/mmcblk0p1 /mnt/userdata/mf79u/sd vfat ro,nosuid,nodev,noatime,fmask=0077,dmask=0077
```

Execution is enabled. Keep the runtime mount read-only. Never export/mount it
writable over USB while local processes use it. Before updating the card, stop
the SD executables, unmount it locally, then transfer ownership to Mac. This
reverse transition is not automated yet.

## Management service

The existing userdata wrapper can use the SD `bin/mf79u-control`. It checks a
checksum pinned in `/mnt/userdata/mf79u/sd-control.md5` (0600), requires the
read-only card mount and detached USB LUN, and retains the userdata executable
as fallback. It can mount the card read-only on boot when NV mode is 1 and the
USB card LUN is already detached. It never forcibly detaches a card from a
boot/background process. If these conditions fail, the UI uses its internal
copy. `start-control.pre-sd.sh` holds the pre-SD wrapper.

Settings and SIP secrets stay in `/mnt/userdata/mf79u` and were not changed.
The existing /etc/rc hook remains unchanged; no NAND image was flashed.
Direct SD execution of CP synthetic tests, native-controller synthetic tests
and all five SIP codec pipelines passed on the physical modem.

The SD bundle remains the version 0.8 storage/runtime snapshot. The later 0.9
native voice controller, media binaries, SIP and owned LED service start from
internal userdata. Local PDP, SIM AKA, IMS and SIP boot were verified with the
Mac relay/watcher stopped. The B03 kernel/rootfs still boots from internal NAND;
no direct bootloader/kernel boot from microSD or SD swap has been enabled.

Physical reboot verified: NV mode 1 persisted, USB card LUN stayed empty,
the LUN ro flag reset to 0 (no media is attached/exported), the card mounted
read-only, WebUI started from SD, HTTP 200 and settings MD5
were preserved. That original SD-only stage used the Mac watcher to restore
voice. Later 0.9 boot tests use only the on-device supervisor, with its explicit
PBX return route configuration. See AUTONOMOUS.md and
build/standalone-verification.json for the current evidence.

## Current runtime cleanup (2026-10-08)

The experimental VPN backend, API, seventh tab, stored node identity, SD binary,
Mac test proxy, build scripts, patches, upstream clones and runtime reports have
been removed at the user's request. WebUI has six tabs: Status / SIP / Messages /
Wi-Fi / Network / System. The network compatibility fallback, USB bridge recovery,
precompressed assets, ETag revalidation and parallel settings loads are retained.
API/credentials remain no-store. SD is remounted read-only; ordinary cellular
data remains blocked. Native/SIP PIDs and saved settings are preserved.

Permanent native-ring-only remains enabled: do not dial or answer SIM calls.
GSM voice backend remains unfinished; user reported50EUR for an incoming call.
Do not remove the guard or use automatic-answer helpers. See GSM-VOICE.md.
Read-only CS probe source and audit-cs-voice.py are retained.

Current install: build/control-update-install.json. Removal verification and
memory snapshot: build/runtime-cleanup-verification.json. Older full NAND0.9 and
SD0.8 archives were not rebuilt or flashed.

> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Preserve device defaults and reset settings without replacing firmware

Documentation audit 2026-10-08: [STATUS.md](STATUS.md) is the shared state/index.

Status (2026-10-08): design and read-only B03 audit. This feature is NOT installed
or implemented. No reset, identity/password write or raw flash was performed.

## Required behavior

Installation/upgrades preserve each device's original administrator credential,
Wi-Fi SSID/security/password, LAN/DHCP profile and original IMEI. Subsequent UI
changes affect working settings. Reset restores the original device profile,
clears user SIP/SSH configuration, and leaves the custom firmware installed.
Defaults are per device; no project password, lab PBX IP or another modem's
identity may be embedded in a shared distributable image.

Treat "factory" as the verified original device profile, not arbitrary current
settings. This modem's IMEI has already been changed; its protected original
backup exists on the Mac. A current READIMEI snapshot must not silently replace
that original. The existence of generic vendor default files does not prove
they contain all unit-specific factory credentials or their generation rules.

## Observed B03 behavior and current limitations

- mtd5/rootfs is 48 MiB and mounted read-only; mtd7/userdata is 24 MiB and writable.
  Other manufacturer identity/calibration storage includes nvrofs and yaffs.
  Do not repartition or write complete NV/calibration images for settings reset.
- Live Control0.10, native IMS/SIP, extended BusyBox and Dropbear currently live
  under /mnt/userdata/mf79u, along with configuration. /etc/rc invokes their
  userdata wrapper. This layout does not establish survival of a stock reset.
- The offline replacement-rootfs overlay places voice/control binaries in rootfs,
  and its rootfs wrapper creates missing userdata/native-enabled. The previously
  packaged 0.9 image has not been flashed, predates newer components, and is not
  a tested reset-capable release.
- readSettings currently uses compiled defaults when settings.json is missing.
  These still include laboratory TRUNK parameters. factoryHotspot reads current
  NV SSID1/WPAPSK1_encode, not an independently preserved original profile.
  Deleting settings.json alone is therefore not a factory-reset implementation.
- Stock WebUI invokes RESTORE_FACTORY_SETTINGS. zte_topsw_mc contains distinct
  normal/factory reset events and restore markers. zte_debug.sh processes
  factory_restore/userdata_restore_flag and deletes stock SMS/phonebook DBs.
  The complete vendor reset path and physical long-press behavior have not been
  live-tested. Do not claim it preserves our files or restores a modified IMEI.

Audit: build/factory-reset-audit.json contains presence/behavior booleans only.

## Storage and installation contract

Separate three logical areas:

1. Immutable firmware code: rootfs boot wrapper, controller, SIP/media libraries,
   control UI, tools, reset implementation and vendor-service policy. All required
   executables must be available without userdata or microSD.
2. Protected device factory profile: original admin verifier, AP/LAN profile,
   original IMEI and provenance, bound to the correct device. Capture before any
   customization. Keep outside the reset-cleared settings tree, root-only, with
   a verified backup and atomic creation that refuses overwrite. An update must
   preserve it; a generic image must never contain its secrets. The exact storage
   location must be chosen only after auditing the vendor erase/restore paths.
3. Writable working settings/state: settings.json, gateway.ini, PBX routes/CA,
   SSH password/enable state and SIP SMS queue state. Reset has an explicit
   allowlist; do not rm -rf the current mixed code/config directory.

For an already customized unit, import only verified original backups or device
manufacturer defaults. Refuse to label uncertain current credentials as factory.
Admin verification may be stored as the B03 SHA256 verifier rather than plaintext;
Wi-Fi needs its usable AP credential protected locally. Never return the factory
snapshot wholesale via HTTP, or include it in common logs/manifests/reports.

## Reset contract

A UI action and a verified physical long-press event must invoke the same local
reset controller. Physical Reset must remain usable after a forgotten admin
password, without relying on an authenticated vendor WebUI session.

Preflight: validate the device-bound complete factory profile and all restore
adapters before mutating anything. Refuse during an active call for the UI flow.
Use a durable phase journal outside the reset-cleared tree for interrupted-power
recovery. Do not blindly retry an uncertain IMEI write.

Restore administrator credential through a verified native B03 adapter; restore
original IMEI through the guarded write/readback helper; rebuild Wi-Fi/LAN/DHCP
settings from the original profile. Clear SIP credentials/registrations and SSH
configuration, invalidate all management sessions and cancel pending unsent SMS
jobs without transmitting them. Default custom SIP role is DISABLED, LTE data
blocked and SSH disabled; normal cellular registration/SMS remains available.
A secure factory hotspot and USB management provide setup access after reboot.

Reset-settings behavior and deletion of stored SMS/phonebook data must be explicit
and separately documented before wiring in the vendor destructive reset flow.
Never replay previously uncertain SMS after reset. Preserve the stable SSH host
key with device identity unless a separately requested erase changes that policy.

Verify all restored values before normal boot resumes. Applying a new identity
requires reboot; preserve factory profile and firmware across it. On an incomplete
reset, show recovery status and retain USB access rather than booting with a mix
of partially restored settings and assumed success.

## Implementation and validation order

1. Audit vendor physical reset events, erase lists and default credential/profile
   generation; prove a storage location survives both reset and firmware upgrade.
2. Implement installer capture/import with per-device provenance and no overwrite,
   then protected first-boot settings generation. Remove lab defaults on a fresh
   device. Package all Control0.10/SIP SMS/System dependencies in rootfs; check
   final image size and recovery before any flashing.
3. Add guarded reset controller, power-loss journal, UI and physical-button path;
   preserve vendor radio/calibration dependencies.
4. Test a disposable filesystem with synthetic secrets: empty userdata boot,
   repeated reset, update preservation, mismatched device, incomplete profile,
   current-versus-original IMEI, interrupted phases and SMS non-replay.
5. Only after backup/recovery checks, test a deliberate real device reset with
   disposable user settings. Confirm original password/AP/LAN/IMEI, custom UI and
   autonomous IMS boot without Mac or microSD. No such live reset is claimed now.

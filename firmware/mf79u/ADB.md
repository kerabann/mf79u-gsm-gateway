> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Automatic ADB at normal boot

Updated: 2026-10-11. Target: physical MF79U B03.

## Policy and startup order

Stock `/etc/rc` already starts `/bin/adbd` unconditionally. A running daemon
alone does not make ADB available: the enumerated USB profile must include the
`adb` function. B03 reads `usb_modetype` from NV_RO, whereas `nv set` changes
the ordinary writable configuration. The local SDK's `usb_NvGetUsbModeType`
and `zusbmodeSet_req`, plus the stock `/bin/nv` and `libnvram.so` disassembly,
identify the required vendor API and NV_RO string `ro`.

The shared `adb_boot.py` transformation inserts a synchronous call to
`/usr/zte/mf79u/adb-boot --ensure` before the first stock `adbd` launch and
before `modetype` is read or `zte_usb_cfg` starts. It runs after the existing
`nv set bootreason` request, when the vendor NV service is available.
The 4,940-byte ARMv7 soft-float helper uses the original uClibc/libnvram ABI.

If the profile is already `debug`, the helper performs no write or commit.
`user` or an empty default is changed only to `debug`, committed and read back.
It never accepts another key or target value. Explicit `factory`/`amt` profiles,
AMT boot mode and factory boot reason10 are preserved. Unknown modes and NV
errors fail without requesting a reset or USB re-enumeration. A five-second
alarm bounds the NV operation so it cannot hold startup indefinitely. The
existing daemon launch still follows. This policy covers normal firmware boot;
it does not replace vendor recovery behavior.

There is no resident helper, timer or watcher. Boot leaves one small RAM result
line in `/dev/.mf79u-adb-boot.log`; the normal `adbd` remains. The policy and
helper reside in rootfs, independently of the userdata WebUI/native runtime.

## Building, installation and packaging

Run from `<checkout>`:

```sh
sh firmware/mf79u/build-adb-boot.sh
python3 firmware/mf79u/test-adb-boot.py
python3 firmware/mf79u/install-adb-boot.py --install
```

The installer accepts only the exact stock B03 rc or its known management/ADB
variants, checks stock adbd/nv/libnvram hashes and refuses an active call.
It first runs a read-only check of the staged helper against the working device.
Small verified RAM stages are removed. The public original rc is backed up to
`/mnt/userdata/mf79u/rc.pre-adb-boot` (0600), with no settings or secrets copied.
The helper and rc are atomically renamed while rootfs is briefly writable;
an exit trap restores the read-only mount. It does not flash a partition image.
`--restore` requires that exact original rc backup and removes only this policy.
It does not switch the current USB profile or remove userdata services.

`prepare.py` packages the same helper and shared rc policy into a future rootfs
overlay. `verify.py` now rejects an image lacking the exact executable helper
or boot block. `install-control.py` also includes the policy and preserves it
when restoring just the management hook. The historical complete NAND/SD
archives remain unchanged; they do not contain this addition. Full replacement
rootfs flashing/recovery remains unverified.

## Verification

`test-adb-boot.py` checks insertion location, exact preservation of unrelated
rc bytes, idempotence and rejection of modified blocks. Thirteen isolated NV
cases cover unchanged debug, read-only check, user/empty-to-debug, reserved and
unknown modes, read/write/commit/readback failures and invalid arguments.
They perform no physical NV writes.

Repeat a read-only check, or explicitly request a normal software reboot:

```sh
python3 firmware/mf79u/verify-adb-boot.py --output firmware/mf79u/build/adb-boot-check.json
python3 firmware/mf79u/verify-adb-boot.py --reboot --output firmware/mf79u/build/adb-boot-reboot.json
```

The observer requires an actual changed kernel boot ID after `--reboot`, USB
ADB and ECM functions, configured gadget, debug NV, successful boot helper
result, one adbd parented by init, exact installed hashes and read-only rootfs.
It also checks the custom HTTP panel and restoration of native/SIP/voice mode;
VoWiFi-ready idle must have actual purple hardware mask5. Receipts omit
credentials and do not initiate calls/SMS. A software reboot does not establish
a physical cold-power-cycle result. Actual user-to-debug conversion is covered
by isolated tests; do not infer a physical NV conversion from an already-debug
reboot.

Installation receipt: `build/adb-boot-install-20261011.json`.
Expected rc MD5: `383f796a590fda5d2256b517a2acd6f7`.
Expected helper MD5: `25e00e0814c791769395564860508471`.
Software reboot receipt: `build/adb-boot-reboot-20261011.json`.

Physical software reboot changed kernel boot ID from f5a748bd… to
`7c8a7e60-5e2d-40d1-9830-955d187f747b`. ADB returned automatically at28.5s;
the helper logged `ADB_PROFILE_DEBUG_UNCHANGED`. Gadget PID0581 was CONFIGURED
with `ecm,diag,adb,serial,mass_storage`. One daemon741, PPid1, five threads;
rootfs was read-only and both installed hashes matched. USB VoWiFi native1700,
SIP1794 and actual purple5 recovered; the custom HTTP panel answered.

The first reboot observer falsely failed its daemon checks because it invoked
`pidof`, which stock B03 lacks. That failed receipt remains intact. The corrected
observer uses the command column of stock `ps`; the read-only same-boot check
passes in `build/adb-boot-postboot-20261011.json`. No second reboot was needed.
The initial30-second follow-up
`build/adb-boot-vowifi-stability-20261011.json` passes every USB/IMS/route/HTTP/LED
sample but fails its optional Wi-Fi lease check: the saved client was still
disconnected. ADB availability and USB VoWiFi do not establish Wi-Fi association.
The AP was still visible at-48dBm. Reassociate and a repeat of the saved network
selection (`sta_autoconnect0`, `ap_scan1`, `select_network0`, `ap_scan0`) did not
recover association. No SSID/password or persistent Wi-Fi configuration was
changed, and no DHCP client was started without an association. This remains an
existing Wi-Fi boot limitation; its cause is not established by the ADB change.
The final USB-only30-second check passes all three samples in
`build/adb-boot-usb-stability-20261011.json`: same boot, USB-selected IMS/voice,
ePDG route through bridge0, HTTP panel and actual purple LED. Wi-Fi is explicitly
DISCONNECTED in that receipt; it is not counted as a Wi-Fi success.

## Subsequent user reboot

The user subsequently reported that everything reconnected automatically.
Read-only verification found a new kernel boot
`8704dd24-6e4d-41c3-8ef2-c12c1a98b52f`, one adbd740/PPid1 and the successful
unchanged-debug helper result. USB0581 includes ECM+ADB; rootfs is read-only
and rc/helper hashes match. Wi-Fi TP-Link_8C63 is COMPLETED with DHCP
192.168.1.44/24. USB VoWiFi only/native1573/SIP1702 are ready, the actual LED
is purple5 and the custom HTTP panel responds. All three samples of the
30-second USB + Wi-Fi lease check pass. No settings were applied or services
restarted during this check; the prior failed Wi-Fi boot remains in the record.
The reboot mechanism and time from power-on were not observed.

Receipts: `build/adb-boot-user-reboot-20261011.json` and
`build/adb-boot-user-reboot-wifi-usb-20261011.json`.

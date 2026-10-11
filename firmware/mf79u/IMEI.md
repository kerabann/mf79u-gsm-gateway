> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# IMEI capability inspection — B03

**Current state, 2026-10-08:** an IMEI-only one-byte authorization branch patch
is installed. A subsequent explicitly authorized identity/NV write succeeded,
and both READIMEI and CGSN matched the requested value after reboot. Original
identity is saved privately for recovery. Control0.10 now exposes a guarded
System IMEI editor with a narrow local helper; see [SYSTEM.md](SYSTEM.md).
Full firmware/factory-reset status: [STATUS.md](STATUS.md), [FACTORY-RESET.md](FACTORY-RESET.md).
See the live write verification below.

## Historical read-only inspection (2026-10-07)

2026-10-07 historical baseline: read-only disassembly and checksum comparison.
At that time installed `/lib/libatext.so` MD5 matched the stock B03 library:
`d1ba655c5bc0ae566ea2a7b38fa0fbcd`. Our overlay has not replaced this library.

The AT extension library contains `MODIMEI`, `MODIMEI=`, `READIMEI`,
`READIMEI?`, and `imeiWrite_act_func` (Thumb function at 0x5a00).
Before validating digits, the write handler checks its factory authorization
flag; if it is not 1, it returns `+CME ERROR: unauthorized` (0x5a2a–0x5a4a).
It accepts 15 decimal digits, packs them into eight bytes and calls
`amt_nvro_write(0,8,...)` at 0x5b62. The matching read handler at 0x5954
reads NV item 0 through `cpnv_NvItemRead` and unpacks digits.
This is a persistent identity writer, rather than the cached WebUI value.

`ZteAuthList` at 0x7654 checks a generated challenge response before setting
this authorization flag. Runtime authorization on this unit was not queried;
no write command, unlock, patch, process-memory inspection, NV mutation,
service restart or raw flash was performed. Therefore capability is confirmed,
but a successful change on this unit is untested. Do not claim it is currently
unlocked, that our custom firmware exposes an IMEI editor, or that changing
only `cfg imei` changes the cellular identity.

A first-person forum report describes successful MF79U B03 durA IMEI changes
after installing a modified rootfs; it is supporting evidence for a different
unit, not a validation of ours:
https://4pda.to/forum/index.php?showtopic=1013289&st=8180 (post #8189).
No forum files were installed. Another developer advertises IMEI modification
in ZTE WebAdmin, but its model list does not explicitly establish MF79U B03:
https://github.com/gxpeng/zte_webadmin .

Machine-readable evidence: `build/imei-capability-verification.json`.
IMS remained ready and SIP PID 3074 unchanged after inspection.
Before any future persistent change, preserve original identity privately and
verify current NV backup/checksums/recovery; an existing rootfs backup alone is
not a restore plan for NV. Such a change is separate from this inspection.

## Downloaded modification analysis (2026-10-08)

The actual attachment was downloaded from the signed-in forum session:
[B03_MOD_adb_modimei, author post](https://4pda.to/forum/index.php?showtopic=1013289&view=findpost&p=143358579), attachment 35470196.
ZIP is 14,902,353 bytes, CRC valid, and contains only a 48 MiB rootfs.bin.
Archive SHA256: `75df51c92b78f878029726fb197d3f3864d9bc139280b9302404b0b4a3c92fbf`.
Rootfs SHA256: `7395d80fded04e5f2e29bc70347fd27dc039e556bc5ff66453ce53853be45ed0`.
It matches the rootfs already present in work/zte/b03mod; the earlier extracted
files were misleading, not a different firmware revision.

### JFFS2 history trap

The image contains old and replacement inodes for two binaries. Jefferson's
`dump_fs` writes the first regular filename and skips later replacements if
that file already exists. Consequently, fresh ordinary extraction also shows
stock libatext.so. Latest dirents by `(parent inode, name)` select libatext
inode 1815, version 415, after deletion version 414; production server inode
1816, version 181, after deletion version 180. Replaying their inode fragments
in ascending inode version restores the modified binaries. All their inode
and data CRCs passed. Recovered copies are in work/zte/b03-adb-modimei/replay.
Do not use work/zte/b03mod-extracted or fresh/ as authoritative for these files.
This does not invalidate stock B03 extraction used by our custom overlay; its
inspect-rootfs.py explicitly rejects deleted-dirent history.

### Actual changes

| Binary / location | Stock → modified | Effect |
| --- | --- | --- |
| libatext.so, imeiWrite_act_func 0x5a32 | BEQ → BNE, one changed byte at file 0x5a33 | Inverts factory auth condition before IMEI writer |
| libatext.so, macWrite_act_func 0x6adc | BEQ → BNE, one changed byte at file 0x6add | Same inversion for MAC write |
| libatext.so, ZteAuthGen 0x7578 | CBZ r1,0x7590 → B 0x757a | Always takes response block; no RSA challenge generated on this path |
| libatext.so, string at 0x144de | Previous error → OK plus author marker | Replaces ZAUTH response text |
| zte_production_server_at, file 0x4954 / VA 0xc954 | CBZ r5,0xc95e → B 0xc95e | Ignores ZADBPSWD verifier result; always takes success branch after existing format/verifier code |

libatext.so differs in 32 bytes total: four code bytes plus 28 string bytes.
Production server differs in two code bytes. Sizes remain unchanged. Added
adbd is byte-identical to the stock binary. The restored libatext SHA256 is
`1b608ab2d1464be62e98cafdb1268dc813bf184ffcbf828d10945c86b3b0d10d`;
production server SHA256 is
`676e8855857df47471865b3c5e66ef0a736b891c1565bcf585dbe3cd5e7bc656`.

The IMEI writer keeps 15-digit validation, BCD-style eight-byte packing, and
`amt_nvro_write(0,8,...)`. Its code after the changed branch is byte-identical
to stock. It does not inject a fixed IMEI, redirect writes, or implement a new
radio protocol. The patched condition admits the normal unauthorized state;
if factory authorization flag actually becomes 1, that condition instead
rejects the command. ZteAuthList's real response verifier remains unchanged.
Thus this is a binary bypass/inversion, not acquisition of a factory key.

Other image changes (SMS config, TTL script and alternate vendor WebUI) are
separate from the IMEI writer. No kernel/bootloader/baseband image is included
in the archive. The persistent IMEI belongs to device NV and is not changed
merely by downloading or unpacking rootfs. A factory settings reset would not
restore the stock rootfs instructions; real behavior was not tested here.

At the end of that analysis the modem still had stock library/server checksums;
IMS remained ready, SIP PID 3074 unchanged. No downloaded binary was executed,
no device file installed, no unlock command or NV/flash/IMEI write performed.
Evidence and complete byte differences: build/imei-modification-analysis.json.
Any future integration can be evaluated separately at the individual binary
level; this analysis does not validate applying either patch to a running device.

## IMEI-only live patch (2026-10-08)

User authorized reproducing the behavior on this modem. `install-imei-patch.py`
derives its candidate exclusively from the exact SHA256-checked stock library.
Only file byte `0x5a33` changes from `d0` to `d1` (BEQ → BNE at 0x5a32).
This matches the forum IMEI instruction. The 15-digit/decimal validation and
NV packing/writer are byte-identical to stock. MAC, ZAUTH and ADB-password
bypasses are not applied; production server and adbd retain their stock MD5.

Patched library MD5: `27a21baf57d9ec55e21f62a44e9d8468`.
SHA256: `6a5b233b701bcd65d84ec4b0f99126b921fa98ea9f52903c5cba3412ca64f636`.
The original device library is preserved at
`/mnt/userdata/mf79u/libatext.vendor.b03.so`, mode 0600, stock MD5 verified.
Saved rootfs and NV backup files also passed their recorded SHA256/size checks.

Live validation used only `AT+MODIMEI=0`. Before patch activation it returned
`+CME ERROR: unauthorized`; after software reboot it returned `+CME ERROR: 8001`.
Disassembly establishes that this one-digit argument branches out at the length
check, before `amt_nvro_write`. Read-only `AT+READIMEI?` values before and after
were equal; values were held only in RAM and never printed or recorded.
No valid IMEI write, call or SMS mutation was performed.

The first atomic rename unlinked the old mapped library inode, so JFFS2 refused
the attempted read-only remount with EBUSY. The installer stopped at that check.
The completed controlled reboot loaded the patched inode and restored rootfs
read-only. The installer now retains a hard link to the previous mapped inode
when replacing a file, avoiding that unlink condition on future replacements.
Do not blindly remove `.mf79u-previous` while its inode is mapped; the installer
refuses another replacement if that retention link exists.

After reboot: native controller `ready`, hostRelayRequired=false, IMS ready,
SIP server process running with no active call, WebUI HTTP 200. The verification
observed readiness in about 62 seconds including AT checks. This is service
startup evidence, not a new voice-call test or a registered SIP client test.

Evidence: `build/imei-patch-live.json`. Reproducible baseline/install/reboot test:
`test-imei-patch-live.py --install-reboot` (requires stock authorization behavior
still loaded). It never sends a valid 15-digit write argument.

Guarded rollback, when no call is active:

```sh
python3 <checkout>/firmware/mf79u/install-imei-patch.py --restore
<checkout>/outputs/adb shell 'sync; reboot'
```

Rollback verifies the device backup before atomic replacement. It does not need
IMS to be ready, allowing recovery when the gateway cannot start. A reboot is
required to change the library already mapped in `zte_mifi`. Rollback itself has
not been live-tested in this run. No full forum image or raw NAND flash was used.
Existing offline 0.9 images/packages do not contain this new device patch.
The factory flag inversion also retains the forum limitation: flag=1 would
reject the command. At the end of this invalid-argument test, actual identity
writing had not yet been attempted; the subsequent test below supersedes that.

## Authorized persistent identity write (2026-10-08)

The user subsequently supplied a specific new identity and authorized writing
it. Its 15-digit decimal format and check digit passed validation. No active
call was present; the exact patched library and saved rootfs/NV backups were
verified. `set-imei.py --write --reboot` issued one valid MODIMEI command, received
OK, and confirmed immediate READIMEI equality with the requested value.

After a verified software reboot, READIMEI and CGSN both matched the requested
value. Native IMS registered and SIP SERVER started autonomously. End-to-end
observed reboot verification took about 93 seconds. No test call or SMS was
sent. Evidence: `build/imei-write-live.json`; it contains only equality flags,
not either identity or their hashes.

The original identity was read before writing and is stored ONLY in protected
`outputs/private/imei-original-123456789ABCDEF.json` (file 0600, directory 0700).
Do not print, attach, commit, or copy it into common reports. This file is in the
current project outputs directory. This workspace now contains real directories,
not the former canonical-directory symlinks; check Path.resolve before recovery.
Subsequent writes must preserve this original backup rather than overwrite it.

To restore the original identity when no call is active:

```sh
python3 <checkout>/firmware/mf79u/set-imei.py --restore-original --reboot
```

This identity recovery command needs the IMEI-only library patch still active.
Restoring the stock library with install-imei-patch.py restores authorization
behavior only; it DOES NOT restore the original NV identity. If both need to be
restored, restore identity first, then the stock library. Identity restoration
has not itself been live-tested. Do not run it without user authorization.

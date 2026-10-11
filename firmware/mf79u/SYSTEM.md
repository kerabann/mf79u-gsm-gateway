> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Native System administration (control 0.10)

Audited 2026-10-11; cross-reference [STATUS.md](STATUS.md).

Normal boot now enables the ADB/debug USB profile before the original adbd and
USB configuration. The rootfs helper exits after the check; it does not add a
resident watcher. Installation, packaging and physical reboot evidence are in
[ADB.md](ADB.md). Stock recovery profiles remain available.

System runs inside the existing on-device Go control service. It needs no Mac
relay. Factory kernel/rootfs and the original BusyBox remain in place; installation
is an atomic userdata update, not raw flashing.

## Management API

### Current IMEI display repair (2026-10-11)

The physical modem was missing `tools/system-imei`, so the information API
silently omitted `imei` and Device IMEI stayed empty. The guarded Control
updater now restores this missing dependency from the verified ARM helper;
it does not replace a different executable helper. The restored helper has
MD5 `6cea9fd9432d810b99777396b6025db4` and mode0700.

`GET info` returns a generic `imeiError` if the reader fails. System displays
the error beside Device IMEI and disables Save IMEI until the current value
has been read. Refresh clears the error after a successful read. Missing,
invalid and failed helper output, successful read and authentication are
covered by Go tests; UI fixtures cover read/error/recovery and desktop/mobile
layout. Two local read-only operations on the modem returned the same valid
current identity; its value and hash were not retained. No identity write,
call, SMS or modem reboot was issued for this repair.

The deployed System HTML and JS match the source. Authenticated live `GET info`
was not independently exercised: API/UI checks use isolated fixtures, while
the helper was checked on hardware. Control replacement invalidates RAM
management sessions; sign in again and use System → Refresh if necessary.
The installer preserved settings and native/SIP PIDs. A later concurrent
runtime replacement was observed during verification; the final receipt
records that separate current state rather than claiming unchanged PIDs.
Receipts: hardware/installation (historical local artifact: `build/system-imei-display-live-20261011.json`),
UI fixtures (historical local artifact: `build/system-imei-display-ui-fixture-20261011.json`).

All `/api/system/*` routes require the existing management cookie. Mutations
also require matching Origin and X-CSRF-Token. SMS Basic authentication does
not grant system access. Responses use `Cache-Control: no-store`.

- `GET info`: model, running component versions, vendor firmware, processor,
  memory, flash partitions, storage, microSD, network interfaces, kernel modules,
  Wi-Fi driver hardware and installed SSH/BusyBox. IMEI is returned only to the
  signed-in administrator and is never included in public verification reports.
- `GET logs?source=native|ssh|kernel`: allowlisted sources, last 16 KiB.
  Credentials/private protocol lines and phone numbers are omitted; no arbitrary
  file access. Native/SSH logs are RAM files; SSH log is bounded at 64 KiB.
- `POST password`: currentPassword/newPassword/confirmPassword. B03 uses
  CHANGE_PASSWORD with SHA256 hashes, plus the normal AD token. The current
  password is re-authenticated; accepted changes invalidate all management
  sessions, even if verification of the new password is inconclusive. No plaintext
  password or new admin key is persisted in our configuration.
- `POST imei`: imei/confirm. Validate 15 digits and Luhn; reject during a call.
  Require exact B03 patched libatext MD5 and original recovery library checksum.
  Save the prior current identity in `imei-before-system.json` (0600) once.
  The helper sends one MODIMEI and reads back; never retries an uncertain write.
  Reboot is a separate explicit action. This backup is the identity immediately
  before the first System change, not necessarily the factory original. The
  separately protected original Mac backup remains authoritative for rollback.
- `POST reboot`: confirm=true. Reject during an active call and return 202 before
  invoking the normal system reboot.
- `GET/PUT ssh`: enabled/password/confirmPassword. Independent SSH password,
  12–128 printable ASCII characters; hash only, SHA512-crypt with random salt,
  written atomically to `ssh.password` (0600). Password is passed on stdin, never
  in argv, returned JSON or logs. Empty fields preserve the saved password.

`system-imei` uses the verified AT_CTL IPC ABI and its own exclusive reply queue;
READIMEI replies may contain an unlabelled number, so the parser requires exactly
one 15-digit value and terminal OK. It consumes no native controller queues.
IMEI/password mutation contracts are fixture-tested; new valid identity/admin
password changes are not performed simply to validate the UI.

## SSH / extended tools

Forum references:
- [SSH instructions](https://4pda.to/forum/index.php?showtopic=1013289&view=findpost&p=117162545)
- [Extended BusyBox](https://4pda.to/forum/index.php?showtopic=1013289&view=findpost&p=124888578)

Official source archives (SHA256 checked against published checksums):
- [Dropbear 2026.94](https://matt.ucc.asn.au/dropbear/releases/dropbear-2026.94.tar.bz2)
- [BusyBox 1.37.0](https://busybox.net/downloads/busybox-1.37.0.tar.bz2)

`prepare-system-tools.py`, `build-system-tools.sh` reproduce ARMv7 soft-float
static binaries. `work/zte/system-tools` holds complete upstream source archives,
checksums, extracted sources and the build Dockerfile. BusyBox SHA hardware
acceleration and Dropbear getrandom are disabled for the B03 CPU/kernel.
`src/dropbear-mf79u.patch` is the narrow source diff for the existing admin UID-0
account: read its SSH hash from our private file and execute our shell wrapper.
It does not modify vendor `/etc/passwd` or `/etc/shadow`. Public-key login and
port forwarding are disabled. Empty passwords remain rejected.

Install paths:
- `tools/dropbearmulti`; `tools/dropbear` and `tools/dropbearkey` symlinks.
- `tools/busybox`, 403 applets. Symlinks under `tools/bin`, including `busybox`.
- `tools/ssh-shell`: uses extended ash and the tools PATH, HOME=`ssh-home`.
- `tools/system-imei`: narrow read/write identity helper, no arbitrary AT command.
- `ssh-host-ed25519`: stable private host key (0600), generated on first enable.

SSH listens only on the configured LAN IPv4 and loopback, TCP 22, username
`admin` (the existing privileged device account). MF79U_WEB accepts it only on
bridge0/wlan0/wlan0-vxd/lo; all other IPv4 traffic to 22 is rejected and IPv6
traffic to 22 is dropped. Existing three-second firewall reconciliation now
checks those rules too. SSH configuration is restored by the control process
started from the existing `/etc/rc` chain. Disabling closes server descendants,
including shells which create their own process group. No killall is used.

No permanent SSH password is invented by the installer. SSH stays disabled
until the administrator sets one and enables it in System.

## Installation / evidence

`install-system.py` checks no active call, backs up the original control binary
on the Mac, transfers whitelisted files over the verified USB LAN, checks MD5,
and atomically renames them. The old management process is stopped after its
replacement is staged to release its mapped userdata inode before installing
additional tools. Native IMS/SIP remains running. A foreground ADB shell is
needed for manual UI startup: old adbd discards background shell launches.
Normal boot uses init and has no ADB dependency.

`test-system-live.py` reads the existing admin password through getpass, keeps
it in RAM and generates a temporary SSH password in RAM. It checks API
validation without real identity/password/SMS/call changes, authenticated SSH,
wrong password rejection, extended applets/shell arithmetic and session closure.
`--reboot` additionally checks the actual reboot API, autonomous IMS/SSH startup
and stable host key. Finally it disables SSH and removes the temporary hash/config.
Do not run this test over an existing enabled/configured SSH account.

Evidence: `build/system-install-verification.json`,
`build/system-live-verification.json`, `build/system-ui-verification.json`.
The earlier packaged NAND image 0.9 predates System; do not claim that archive
contains these later userdata components.

## SSH Save and management sessions

SSH validation/operation feedback is displayed next to its Save button; the
button shows progress while the request is running. Matching passwords require
12–128 printable ASCII characters. `node test-system-ui.js` checks rejection
before a request, local feedback, successful submit and secret-field clearing.

Own management sessions have a rolling 30-minute idle limit. Authenticated GET
responses now renew the browser cookie as well as the RAM expiration; without
this the cookie expired 30 minutes after initial login despite active polling.
Vendor reauthentication remains separate. Hot control-process replacement and
normal modem reboot still invalidate RAM sessions and require a fresh login.
`test-management-session-live.py` is a read-only 180-second session/status check;
it reads the existing password with getpass and retains cookies only in RAM.

## Root shell and blocked internet

Connect as `ssh admin@192.168.0.1`, using the configured separate SSH password.
The existing account has UID0: `id` returns uid=0(admin), gid=0(root). A separate
su/sudo step is not required. User-enabled SSH/password were preserved after
the temporary verification account was removed; do not run that test over them.

With LTE data disabled, ordinary cellular OUTPUT/FORWARD is blocked even for
root. A default route through wan1 and MF79U_DATA REJECT explain ping sendto
Operation not permitted. Only local IMS wan5 is exempt. Enabling LTE data in
Mobile allows ordinary internet; no setting is changed by viewing System.
The switch does not establish operator billing guarantees. See [NETWORK.md](NETWORK.md).

Session evidence: build/management-session-live.json records 187.6 seconds,
24 successful polling cycles, renewed cookie and stable control PID. This is
bounded stability evidence, not an indefinite-uptime claim. Later fallback
Control updates retain the same session/SSH implementation.
Factory-profile reset is designed only; there is no installed Reset action.
See [FACTORY-RESET.md](FACTORY-RESET.md).

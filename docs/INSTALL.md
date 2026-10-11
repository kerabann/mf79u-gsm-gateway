# Full overlay installation and recovery

For an authorized idle update that needs a new shared-INI voice mode, the
checked controller updater supports `--with-sip`. It verifies native/SIP
executables and ownership, backs up both binaries, stages compressed SIP for
small userdata, and preserves settings, boot, IMS media and CS artifacts:
`make task TASK=install-native-update.py ARGS="--install --with-sip" SERIAL=...`.
Control/UI uses the existing Control-only updater. Receive-policy changes can
require clear Telegram/SIP forwarding queues immediately before replacement:
`make task TASK=install-control-update.py ARGS="--require-sms-idle" SERIAL=...`.
This optional guard also refuses unfinished outgoing SMS jobs. It preserves the
existing durable inbox/state and native/SIP runtime. Neither update sends calls
or SMS or changes the selected mode by itself.

Use only the supported MF79U B03 kernel/CP ABI. Installation uses ADB plus an
explicit USB-reachable host IP for a temporary, allowlisted HTTP artifact server.
`adb` must be in PATH or passed as `ADB=/path/to/adb`; `SERIAL` maps to
`ANDROID_SERIAL`. Do not use a historical hard-coded serial for the main installer.

```sh
make build package package-check
make device-status SERIAL=...
make install-plan SERIAL=... HOST_IP=192.168.0.169
make install SERIAL=... HOST_IP=192.168.0.169
make verify-device SERIAL=...
```

`install-plan` is read-only. It checks idle voice/SMS, real runtime libraries,
exact kernel image/export profile, CP/module layout, original IMS binary and startup
policy, package completeness, hashes and userdata/rootfs free space. Unknown files/ABI
fail before mutation. Changing a loaded pinned CS driver, or applying a new stock startup policy, requires an explicitly
selected `REBOOT=1`; the installer never unloads it live.

The package installs Control, native, SIP, IMS media, CS driver/adapter/PCM,
VoWiFi runtime, LED, System/SSH/SD helpers and supervisors together. Embedded UI
and REST are part of Control. Private IMS is derived from the device original
using the checked recipe. Startup patches install ADB autoboot, management
autostart, vendor-service policy, the boot-wait page and IMEI authorization.
This modifies selected checked rootfs files, returning it read-only; no partition
image/raw flash or identity write is performed.

Existing settings, gateway configuration, Wi-Fi/SSH credentials, messages, SIM
data and voice guard are preserved. A first install retains a ring-only guard
until the user deliberately configures voice. Verification accepts an owned
Control process while first-time setup is pending; a configured installation
also requires owned native/SIP processes. The source has an English setup
UI; this migration does not inject personal configuration into the package.

Public binary/startup backups go only to `private/backups/<UTC timestamp>` with
checksums and restrictive permissions. Transfers stage one compressed artifact
at a time (largest first), verify before rename and stop only owned daemons. The installer checks
host-to-device HTTP reachability before service shutdown. It checks
the resulting hashes, process ownership, selected runtime readiness and unchanged
settings. It does not send a test SMS or place/answer a test call.

If a write/recovery check fails, the checked local backup remains available:

```sh
make restore BACKUP=/absolute/checkout/private/backups/<timestamp> SERIAL=... HOST_IP=192.168.0.169
# Different loaded CS revision requires REBOOT=1 within authorized scope.
make device-status SERIAL=...
```

Restore validates allowed targets and every backup hash before touching files.
It restores the artifact set and restarts the owned wrapper; inspect current
runtime readiness afterward. Keep ADB and a verified B03 recovery route available
during first-time provisioning. Rootfs/raw flashing and factory-reset preservation
are not the maintained deployment workflow. Individual historical installers
remain accessible through `make task` with their original narrower guards.

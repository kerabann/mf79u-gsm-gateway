# MF79U agent instructions

This repository is the source of truth for all further firmware work. Run from
the checkout root. Never depend on a sibling workspace, a personal home path or
untracked historical build files for a production build.

## Required workflow

- Use the root `Makefile` for builds, tests, packaging, diagnostics and installs.
  `make help` describes supported operations. Preserved tools are available with
  `make tasks` and `make task TASK=firmware/mf79u/<name> ARGS="..."`.
- Document every change in Markdown. Keep [docs/STATUS.md](docs/STATUS.md), the
  applicable topic document and validation evidence current. Read them before
  implementation; old dated experiments are historical evidence.
- Trace configuration, ownership and the actual data path before changing it.
  Use narrow changes and preserve existing settings, IDs and user data.
- Run `make test`, the relevant component build, `make package package-check`
  and `make audit`. `make ci` is the complete GitHub Actions workflow.
- Add meaningful isolated fixtures for changed behavior. UI changes need all
  eight tabs at desktop/mobile widths and embedded-asset rebuilds.
- A build, fixture or old receipt is not proof of current physical behavior.
  Report source/fixture/device evidence separately and label remaining gaps.

## Physical device rules

- Recheck `make device-status SERIAL=...` before any device change; addresses,
  boot, PIDs, radio state and IMS access can change independently of the source.
- Never print or commit passwords, AKA challenges/replies, SIM identifiers,
  cookies, phone numbers, SMS contents, recordings, device dumps or live configs.
  Keep private inputs/backups under ignored directories with restrictive modes.
- No real call, SMS submission, answer, IMEI NV write, modem reboot or raw flash
  is part of a build/UI test. Such operations require explicit user scope.
  A previous one-shot test receipt does not authorize a repeat.
- Preserve `/mnt/userdata/mf79u/native-ring-only` if present. Never remove it or
  auto-answer a roaming SIM without renewed instruction. A roaming incoming call
  previously caused a reported charge. Use an explicitly approved inexpensive
  SIM for full call/audio tests.
- Preserve the confirmed IMS sound. CS emphasis belongs only in the CS path;
  do not change IMS gains, AMR CMR, the shared FIR or global codec order casually.
- **External PCM is fixed: mono PCM16LE, 16000 Hz, 320 samples per 20 ms.**
  Internal CS hardware runs 8 kHz/160 and the bridge resamples it.
- Only kill/restart processes after verifying pidfile, executable and ownership.
  CS modules remain pinned: never `rmmod` a production driver live. A changed
  driver requires a checked software reboot (`REBOOT=1`) within authorized scope.
- Ordinary LTE data blocking must retain operator IMS `wan5`. VoWiFi-only
  forbids LTE/CS voice fallback and cellular SMS submission fallback/retries.
  The explicitly selected `VOWIFI_SMS` compatibility option uses GSM as its
  primary SMS path, with CS voice flags disabled and the adapter suspended;
  it still forbids LTE/CS voice fallback and automatic SMS transport failover.
- Never deploy link-only SDK shims. They exist solely for linking against the
  documented B03 ABI; the installer checks the real device libraries and CP ABI.
- The old browser command console is removed. Do not restore `outputs/zte-shell`
  or its menu/iframe integration. System/SSH is the maintained access path.
- Userdata overlay installation is the maintained delivery path. Historical
  rootfs/SD images are stale. Factory-profile-preserving Reset is not implemented.
  Raw flashing needs exact compatibility, complete backups and recovery evidence.

## Architecture and entry points

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/FEATURES.md](docs/FEATURES.md), [docs/BUILD.md](docs/BUILD.md),
[docs/INSTALL.md](docs/INSTALL.md), [docs/TESTING.md](docs/TESTING.md) and
[docs/INDEX.md](docs/INDEX.md). The full prior Markdown context is retained in
[docs/WORKSPACE-HISTORY.md](docs/WORKSPACE-HISTORY.md). Current instructions above
take precedence over dated paths and superseded limitations in that history.

## B03 constraints

Go must remain pinned to 1.25.12: later FIPS `.bss` growth exhausted this device.
Runtime limits: GOMAXPROCS=1, GOGC=20, GOMEMLIMIT=6MiB. Stock getrandom is
incompatible; retain `/dev/urandom`. Stock ash cannot be assumed to support shell
arithmetic. `ip addr replace` is unsupported. Vendor firewall rules are rebuilt;
keep our owned chains/idempotent reconciliation. ADB session background jobs may
die; use the checked detach helper and wait for old wrapper cleanup. Userdata is
small: stream compressed individual artifacts and verify each checksum.

Keep the admin UI in English, with simple framed tabs and scoped Save actions.
UMTS and GSM wideband are not supported claims. Hardware 8 kHz CS audio is not HD.

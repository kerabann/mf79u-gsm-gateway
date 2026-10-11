# Current project status

Updated 2026-10-11. This Git repository is the new source of truth. The complete
original topic documentation and test sources have been imported. The migration
is packaging/build work; it does not itself constitute a new physical call test.

The maintained delivery is the device-local userdata overlay. Full NAND/rootfs
0.9 and SD 0.8 archives are historical and were not flashed or refreshed. Reset
that preserves/restores a factory profile is designed, not implemented.

## Implemented and previously physically confirmed

- Outgoing/incoming CS↔SIP/PBX tone, echo and timely release; persistent driver,
  adapter/PCM bridge, AUTO fallback and startup recovery. GSM codec/rate is still
  unmeasured; hardware PCM is 8 kHz and does not establish GSM wideband.
- Local CP/AKA/IMS, private userspace IPsec/media, AMR-WB/NB and SIP voice without
  a Mac relay. Preserve the confirmed IMS sound when changing CS behavior.
- Wi-Fi client/hotspot, USB internet source for ePDG, VoWiFi-only runtime and
  autonomous reconnection. Read current topic receipts for voice/audio boundaries.
- IMS-only VoWiFi SMS: one authorized real send/receive was confirmed. No cellular
  fallback or retry in VOWIFI mode. Durable IMS receive inbox and SIP delivery ACK.
- English seven-tab WebUI; Mobile settings, scoped Save, framed blocks; LEDs,
  SMS management, USB/LAN/DHCP/LTE firewall and system/SSH/IMEI controls.

See [FEATURES.md](FEATURES.md) for code, tests and evidence topic links.
Latest original history: [firmware STATUS](../firmware/mf79u/STATUS.md).

## Repository delivery and validation

The root Makefile builds every runtime component and creates an allowlisted,
checksummed overlay. GitHub Actions builds/tests the same checkout without private
vendor inputs. A link-only SDK describes the B03 ABI; runtime vendor libraries
remain on the device and are checked before install. Private IMS and the one-byte
IMEI authorization patch are checksum-bound recipes, not committed vendor blobs.

Follow [MIGRATION.md](MIGRATION.md) for the actual completed verification report.
The initial publication commit `cbb0ae7` was pushed to `main` on 2026-10-11.
The first [GitHub-hosted workflow](https://github.com/kerabann/mf79u-gsm-gateway/actions/runs/38158311596)
completed successfully on Ubuntu 24.04 x86_64 in 7m 16s for `cbb0ae7`.
This hosted receipt validates the initial publication; the later UI changes
below have local checks and are not attributed to that older workflow run.

## Remaining boundaries

Only the exact supported MF79U B03 kernel/CP ABI is accepted. Other variants,
UMTS and GSM wideband are unverified. The registrar is one-account/one-binding
UDP; trunk transport supports UDP/TCP/TLS. Full rootfs flashing and factory reset
preservation are not production workflows. Previously observed remote clearing,
clock and DSP faults are documented historically; use the accepted production
driver/profile rather than resurrecting older experiments.

## Current UI audit and CS compatibility correction, 2026-10-11

A fresh UI/runtime audit corrected network readiness/rollback notices, delayed
apply after cancellation, scoped drafts, unnecessary SIP reloads and misleading
voice/PBX status. Missing SSH runtime files were recovered. A legacy GSM driver
compatibility correction restored CS readiness without changing its driver or
PCM/IMS media. Updated Control/native are installed without a modem reboot.

Fresh physical checks include real 90-second expiry, gateway-address restoration,
UDP PBX registration, admin/SSH password rotations, hotspot settings, GSM CS/AUTO
readiness, LTE data-off guards and a user-confirmed incoming VoLTE conversation.
All seven fixture views passed 1280/390/320px. See [the audit matrix](UI-E2E-20261011.md)
for exact source/browser/API/device boundaries, preserved artifact hashes and
remaining call/Wi-Fi/transport checks. The user deferred another outgoing call;
the complete combination matrix is not claimed as passed.

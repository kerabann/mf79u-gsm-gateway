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
Do not infer a GitHub-hosted run merely from a local `make ci` success.

## Remaining boundaries

Only the exact supported MF79U B03 kernel/CP ABI is accepted. Other variants,
UMTS and GSM wideband are unverified. The registrar is one-account/one-binding
UDP; trunk transport supports UDP/TCP/TLS. Full rootfs flashing and factory reset
preservation are not production workflows. Previously observed remote clearing,
clock and DSP faults are documented historically; use the accepted production
driver/profile rather than resurrecting older experiments.

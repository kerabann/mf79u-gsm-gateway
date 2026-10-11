# MF79U GSM / VoLTE / VoWiFi SIP gateway

Device-local firmware overlay for the **ZTE MF79U with the exact B03 ABI**.
It bridges SIM voice and SMS to SIP, with an embedded English administration UI.
The maintained installation uses userdata and checked startup patches; it is
not a generic modem image or a signed factory flasher.

Features include GSM CS and IMS voice, AUTO/VoLTE/CS/VoWiFi-only policies,
PBX trunk and single-client SIP registrar, SIP SMS and private IMS SMS, configurable
SIP codecs/transports, Caller ID/privacy, hotspot/client Wi-Fi, USB management,
LTE data firewall policy, status LEDs, SSH and system management. See the complete
[feature/evidence matrix](docs/FEATURES.md) for exact scope and limitations.

```sh
make help
make ci                         # All builds, isolated tests, package and audits
make package                    # dist/mf79u-gateway.tar.gz + manifest + SHA256SUMS
make device-status SERIAL=...    # Read-only; requires adb in PATH
make install-plan SERIAL=... HOST_IP=192.168.0.169
make install SERIAL=... HOST_IP=192.168.0.169
make verify-device SERIAL=...
```

Build prerequisites: Docker, GNU-compatible Make, Python 3.12+, Node 24 and Go.
The build selects Go **1.25.12**. On Linux, Docker requires a running daemon;
Docker Desktop supports local macOS builds. Internet access is needed for the
pinned upstream source archives and container packages. No modem, private dump,
SIM identity or credentials are required for `make ci`.

[GitHub Actions](.github/workflows/firmware.yml) runs the same `make ci` on Ubuntu,
then uploads the complete overlay and checksums. CI never accesses a device or
places calls/SMS. Link-only B03 ABI libraries are generated from public metadata;
the package excludes them. The installer checks real B03 libraries/kernel/CP and
derives the private IMS binary from the original on the device.

All future work belongs in this checkout. Agents should start with
[AGENTS.md](AGENTS.md), [current status](docs/STATUS.md) and the
[full documentation index](docs/INDEX.md). Build/install instructions and recovery
are in [BUILD.md](docs/BUILD.md) and [INSTALL.md](docs/INSTALL.md).
The migration inventory and verification are in [MIGRATION.md](docs/MIGRATION.md).

Keep secrets, device settings, SMS, recordings and vendor firmware dumps outside
Git. `make audit` checks the publication file set and documentation. Topic docs
retain the complete dated project history; uncommitted private live receipts
remain local and are not evidence from a fresh CI/device run.

Project licensing has not yet been selected by the owner. No new license grant
is implied by this migration. Third-party components retain their own licenses;
see [THIRD-PARTY.md](docs/THIRD-PARTY.md) before distributing binaries.

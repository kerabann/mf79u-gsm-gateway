# Build and GitHub Actions

Run everything from the repository root through one Makefile.

```sh
make bootstrap
make build
make test
make package package-check audit
# Complete clean-checkout workflow, also used by GitHub Actions:
make ci
```

Required host tools: Docker daemon, Make, Python 3.12+, Node 24 and Go. The build
pins Go 1.25.12 for the B03 memory limit. `sources.lock.json` pins all nine upstream
archives by URL and SHA256. `make deps` verifies existing archives or downloads
and safely extracts missing ones. Downloaded/extracted trees remain ignored.
`make fetch-check` independently downloads and verifies every locked archive.
`make clean-checkout` exports the Git index into a separate checkout and runs the
complete `make ci`. Stage intended source, test and documentation changes first:
untracked files and unstaged contents are excluded, so local files cannot hide
an incomplete commit. Its optional local cache contains only checksum-verified
upstream archives.

The Dockerfile pins Debian by digest and installs ARM soft-float compiler tools,
native sanitizers, autotools/CMake, ARM GMP and qemu-user.

`make build-control`, `build-native`, `build-sip`, `build-ims`, `build-cs`,
`build-vowifi`, `build-system`, `build-adb` and `build-helpers` support focused
iteration with their own prerequisites. Production source remains under
`firmware/mf79u`; every historical first-party build/diagnostic is available
through `make task`, with explicit arguments.

## Building without proprietary dumps

`make sdk` creates **link-only** ELF libraries from the symbol ABI in
`profiles/b03/link-abi.json`. They supply the vendor SONAMEs/exports for linking
our uClibc loadable components. These libraries cannot implement vendor runtime
behavior and are deliberately excluded from the package. On-device runtime uses
the genuine B03 libraries; `make install-plan` checks their SHA256 fingerprints.
Kernel module call relocation checks use the pinned export/mode metadata and
accepted module layout. If a private kernel image is supplied, its complete hash
and exports are additionally checked by the original audit implementation.

The private IMS executable is an installer recipe applied to the verified
original device executable. The result must have the historically accepted
SHA256. It is not downloaded, embedded in Git or included as a vendor binary in
the CI overlay. The same principle applies to the IMEI authorization branch;
installation does not perform an IMEI NV write.

Optional historical emulation inputs:

```sh
make vendor-import VENDOR_ROOT=/path/to/your/extracted-b03-rootfs KERNEL=/path/to/ap_cpuap.bin
make vendor-check
make tasks
make task TASK=test-cs-nsd-b03 ARGS=""
```

These input files, rootfs images and private receipts are ignored. Historical
rootfs tooling is retained for research and requires its documented private
inputs; `make build`/`make package` use the maintained overlay workflow.

The retained host USB AT utility builds with `make build-host-tools` (host
`pkg-config` and `libusb-1.0` development files required). Execute an explicitly
authorized command through `make usb-at ARGS="AT+..."`. This is separate from
the device-local firmware build and is not needed by GitHub Actions.

## GitHub Actions

[firmware.yml](../.github/workflows/firmware.yml) runs on push, pull request and
manual dispatch. Ubuntu runs `make ci`, then uploads the overlay, manifest and
SHA256SUMS, plus sanitized JSON check reports. No repository secrets, modem or
host-specific directories are required. CI executes the real ARM SIP gateway
under qemu and native C policy fixtures with ASan/UBSan. Physical modem behavior
still requires an authorized live check; CI cannot prove RF/audio/ePDG service.

`make clean` removes generated artifacts and `dist`, preserving private vendor
inputs. Never cache `private/`, live settings, SMS, credentials or recordings in
Actions. No automatic installation, device calls or public release publication
is part of the workflow.

## Optional documentation assets

`make docs-deps docs-assets` installs locked Playwright/Chromium tooling and
regenerates the public desktop/mobile gallery from a disposable loopback fixture.
It does not require ADB or read any live settings. These npm dependencies are
optional and are not part of firmware builds or `make ci`; see [UI](UI.md).

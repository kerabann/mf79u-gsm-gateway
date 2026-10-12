# Third-party components and distribution

Upstream sources are pinned in [sources.lock.json](../sources.lock.json).
`make deps` downloads/checks them into ignored build directories. Build changes
to strongSwan/Dropbear are preserved in the first-party build/preparation scripts
and source files, including `src/dropbear-mf79u.patch`.

| Component | Version | Upstream license/source |
| --- | --- | --- |
| PJSIP | 2.17 | GPL/commercial; upstream `COPYING` |
| bcg729 | 1.1.2 | GPL; upstream `LICENSE.txt` |
| strongSwan | 6.1.0 | GPL; upstream `COPYING` and per-file notices |
| BusyBox | 1.37.0 | GPL; upstream `LICENSE` |
| Dropbear | 2026.94 | MIT-style/per-file; upstream `LICENSE` |
| Opus | 1.6.1 | BSD-style/per-file; upstream `COPYING` |
| OpenSSL | 3.5.9 | Apache 2.0; upstream `LICENSE.txt` |
| opencore-amr | 0.1.6 | Apache 2.0/per-file; upstream license files |
| vo-amrwbenc | 0.1.3 | Apache 2.0/per-file; upstream license files |
| ARM libgcc/libc and GMP | Debian Bookworm packages | Package copyright files/licenses |
| Go Daddy G2 public root certificate | SHA256 `45140b3247eb9cc8c5b4f0d7b53091f73292089e6e5a63e2749dd3aca9198eda` | [Official public CA repository](https://certs.godaddy.com/repository); embedded for Telegram TLS |

Optional documentation tooling is locked in [package-lock.json](../package-lock.json).
Playwright/Playwright Core 1.62.1 use Apache 2.0; the optional macOS fsevents
dependency uses MIT. Browser binaries installed by `make docs-deps` retain their
upstream notices and stay outside Git and the firmware package.

This is an inventory of the source/build dependency licensing, not a new license
grant for the project's original code. The owner has not selected the project's
publication license. Preserve all upstream notices and supply the required
corresponding source/build changes when distributing GPL-linked firmware binaries.
Review the actual pinned upstream licenses rather than inferring licensing from
this short table. The CI artifacts are build/test outputs, not an automated public
binary release with a resolved project license.

Proprietary ZTE dumps, vendor libraries and device-specific configuration are not
committed or distributed in the overlay. Link-only ABI shims contain symbol names
and metadata, not the vendor implementation. The installer creates private IMS
and the IMEI authorization change from an owned device's exact checked original.

# Repository migration — 2026-10-11

The firmware's first-party sources, WebUI/REST, tests, build/installation/recovery
tools, emulation scripts, PBX example tools and Markdown topic documentation
are now maintained in this Git checkout. The source layout is preserved to keep
existing imports and relative paths readable. There are no links to a sibling
workspace. All public workflows enter through the root Makefile.

[migration-manifest.json](migration-manifest.json) records every original source
and destination hash, size, path and transformation. Generated output, downloaded
upstream trees, device dumps/configuration/credentials/messages/recordings and
historical private receipts are intentionally excluded from publication. Accepted
CS parameters and previously generated first-party detach helper sources were
promoted into `firmware/mf79u/profiles/b03` so no feature relies on ignored output.

The publication article and its illustration sources/images are excluded at the
user's request. The previously removed browser console is also excluded. System/SSH remains
the maintained access path. All firmware technical documentation remains included.

## Changes required for a portable repository

- Preserve production C/Go/WebUI behavior; rewrite build plumbing for a clean
  checkout and generate the B03 link-only SDK from ABI metadata.
- Separate the accepted production CS build from historical call/probe receipt
  dependencies. Preserve the old builder alongside the documented accepted profile.
- Build every runtime component through Make, then package an explicit complete
  allowlist. Private IMS and IMEI authorization use checked on-device recipes.
- Add the full overlay installer with compatibility/idle/ownership/space checks,
  backup, restore and per-artifact transfer verification.
- Replace personal home paths and former test phone literals in public material.
  Former dial destinations are nondialable placeholders in historical tools;
  configure an explicitly authorized destination before using those tools.
- Keep complete dated Markdown history and add current README/AGENTS/architecture,
  feature, build, CI, installation/recovery and testing documentation.
- Add GitHub Actions using `make ci` without vendor dumps or account secrets.

## Verification receipt

Completed locally on 2026-10-11:

- **447 imported files:** every destination exists and matches its recorded
  migration hash (`make verify-migration`). Independent original-tree inventory
  found no missing firmware source or technical Markdown topic. Exceptions are
  the owner's excluded publication article/illustrations, retired browser console
  and proprietary stock-panel backups. A generated vendor startup copy is
  reconstructed from its checked device original rather than published.
- **154 native source/header files and 32 Control/WebUI files:** production
  behavior is preserved. The only fingerprint differences inside these source
  directories are privacy normalization in two test fixtures and the historical
  opt-in IPC call probe, plus whitespace-only normalization in the portless
  adapter. Build plumbing is separately recorded in the manifest.
- **42 Markdown documents / 319 local links:** current entry points, agent rules,
  architecture, complete feature matrix, build/CI, install/recovery and dated
  technical history; no missing local target (`make audit`).
- **Nine upstream archives:** each public URL was independently downloaded again
  and matched its locked SHA256 (`make fetch-check`).
- **Clean-checkout `make ci`: PASS.** A separate publication-only Git checkout
  built all components, ran the isolated suite, produced and checked the package,
  validated Actions syntax and scanned publication sources. No vendor dump,
  private receipt, settings, previous source tree or compiled artifact was reused.
  Only checksum-verified upstream archive cache was reused. Final installer/docs
  refinements also received isolated regression and publication checks.
- **Tests:** 26 native C fixtures (23 ASan/UBSan, three ARM32 qemu), four Python
  safety/media regressions, 47 top-level Go tests executed in Linux, four JS UI
  suites, all five real ARM SIP codec pipelines, WB/NB PCM network transport,
  registrar IMS/CS modes, SIP SMS and four bidirectional RTP/PCM media cases.
  Packaging/installer regressions reject corrupt/incomplete/unsafe/duplicate
  payloads, changed PCM, insufficient space, unavailable transfer setup, pending
  or unverifiable SMS and an unknown pinned CS driver before service shutdown.
- **Package:** 28 checked runtime/recipe files, approximately 11.1 MiB compressed.
  Complete runtime allowlist, hashes, member/path safety and the unchanged external
  PCM16LE mono 16000/320 contract pass. SDK shims, vendor binaries, credentials and
  personal configuration are absent. `make build-host-tools` also compiled the
  retained USB AT utility without USB I/O.
- **CS candidate parity:** rebuilt module MD5
  `c58ea61d11ac531dabc057114a8f399e` is byte-identical to the original workspace's
  current build candidate. It differs from the driver pinned on the modem;
  source/candidate parity does not establish that this candidate was installed.
- **Physical read-only plan:** exact B03 library/kernel/CP compatibility, idle
  voice/SMS, startup recipes and package completeness pass. About 9.9 MB userdata
  and 25.7 MB rootfs free were observed; the ordered staging bound was 7.35 MB
  userdata and 70.5 kB rootfs. The selected driver requires `REBOOT=1` for a later
  explicitly authorized installation. These measurements can change independently.
- **Publication:** candidate allowlist, Python/shell/JS syntax and Gitleaks pass.
  The pinned Go scanner fallback used by Actions was exercised locally.

Reports are written to ignored `reports/`. The package/manifest/checksum file are
in ignored `dist/`. Historical private receipts remain outside Git. Normal CI
checks migration coverage while allowing intentional future source edits;
`make verify-migration` is the stricter original migration-fingerprint check.

No physical install, reboot, real call/SMS, IMEI write or fresh visual browser
run was performed. Existing hardware receipts remain dated historical evidence.
The initial publication commit `cbb0ae7` is now available on GitHub `main`.
The first [hosted workflow](https://github.com/kerabann/mf79u-gsm-gateway/actions/runs/38158311596)
completed successfully on Ubuntu 24.04 x86_64 in 7m 16s for that publication
commit. Later [UI audit changes](UI-E2E-20261011.md) are validated separately and
are not included in that hosted result. Factory-profile-preserving Reset remains unimplemented;
UMTS and GSM wideband are not supported claims.

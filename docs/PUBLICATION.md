# Repository presentation

Updated 2026-10-12. Runtime source baseline: `ef2ce63`. This change presents the
existing firmware for public readers; it does not change the installed runtime.

## Public entry points

- [README](../README.md): overview, capabilities, voice/SMS policies, current
  verification boundaries, build/install commands and repository map.
- [UI gallery](UI.md): sign-in, all eight tabs, SIP trunk/server and Wi-Fi
  Hotspot/Client; 22 full-page desktop/mobile screenshots plus an overview.
- [Architecture](ARCHITECTURE.md): two editable SVG diagrams and the retained
  detailed Mermaid/source ownership view.
- [Documentation index](INDEX.md): guides by the reader's goal, retaining topic history.
- [Contributing](../CONTRIBUTING.md): development, evidence and publication rules.

Presentation assets live under `docs/assets/`. Source directories and historical
IDs/receipts retain their paths. Optional locked Playwright tooling is exposed
through `make docs-deps docs-assets`, separate from normal firmware CI.

## Screenshot provenance

The renderer uses the existing disposable frontend server and the actual source
assets. Its public response overrides contain synthetic operator/SSID/signal
values and an invented SMS. Password fields are blank; IMEI is omitted.
There is no ADB invocation, modem access or external browser request. The only
POST is an intercepted synthetic Wi-Fi scan. Sign-in is rendered locally without
submitting credentials. The overview combines cropped browser renders and
explicitly labels their demo origin.

Ten authenticated views were checked at 1280, 390 and 320 px: all eight tabs,
plus SIP trunk and Wi-Fi Client. All 30 checks passed with no horizontal overflow,
JavaScript errors or unexpected writes. Twenty authenticated screenshots and two
sign-in screenshots were captured at 1280/390 px. Visual review covers the
overview, diagrams and desktop/mobile gallery. The local sanitized report is
`reports/docs-assets.json`.

The diagrams describe the implementation at a high level. They group media and
control links and do not claim observed carrier topology or successful calls.
Physical verification remains in [STATUS](STATUS.md) and the linked topic docs.

## Validation

`make docs-deps` and `make docs-assets` passed using the locked Playwright 1.62.1
and its matching Chromium. The gallery's [provenance record](assets/provenance.json)
records browser versions, source-asset hashes and screenshot hashes.

`make test package package-check audit` passed: Go/JS fixtures, 28 native tests
and five Python regressions, ARM SIP/codec/RTP fixtures, workflow guards, the
complete build, the 28-file overlay and its checksums/PCM contract. Publication
allowlist/Gitleaks and all Markdown local links passed. The full local output is
`reports/publication-validation.log`; generated checks remain outside Git.

README and gallery were additionally rendered with GitHub-flavored Markdown;
all 22 gallery images loaded. SVG canvas/text bounds and accessible metadata
passed, and screenshots/diagrams were visually reviewed. These are local
validation results, not a claim about a new GitHub-hosted run.

No modem configuration, install, reboot, call, SMS or identity write is part of
this update. Project licensing remains an owner decision; no license is added.

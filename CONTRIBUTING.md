# Contributing

Start with [current status](docs/STATUS.md), [architecture](docs/ARCHITECTURE.md)
and [AGENTS.md](AGENTS.md). Current guides and accepted production revisions
take precedence over dated experiments. The project license has not yet been
selected; see the [licensing note](README.md#licensing).

## Development workflow

Keep normal operations behind the root Makefile. Trace the affected configuration,
ownership and data path; make a focused change and update its topic document and
status. Preserve public API/configuration contracts and the fixed external PCM
format. Add isolated fixtures when behavior changes.

```sh
make help
make test
make package package-check audit
# The complete GitHub Actions workflow:
make ci
```

For a focused change, use the relevant `build-*` and `test-*` targets described in
[BUILD](docs/BUILD.md). UI assets are embedded in Control; rebuild them with
`make build-control`. Check all eight tabs at 1280/390/320px and include the
affected SIP roles/Wi-Fi modes. The [gallery workflow](docs/UI.md#regenerate-the-gallery)
provides source-rendered public screenshots without device access.

Before a clean-checkout check, stage the intended files: `make clean-checkout`
exports the Git index, so unstaged edits and untracked helpers are excluded.
Review `git diff --cached --check` and the staged file list before committing.

## Report evidence clearly

Use the repository's bug/feature forms to describe the problem, resulting behavior
and validation. Distinguish source,
isolated fixtures, browser rendering and physical device results. Include the
source revision and sanitized failure metadata where useful. A build or an old
receipt cannot establish current hardware behavior.

Never attach credentials, SIM/device identities, phone numbers, SMS content,
recordings, private packet traces, vendor dumps or live settings. Private receipts
belong under ignored `reports/` or `private/`; `make audit` scans publication
candidates with redaction. Report credential exposure privately to the owner
instead of copying the value into a public issue.

## Device work

Build/UI tests never authorize a call, SMS, answer, identity write, reboot or raw
flash. Physical work needs explicit owner scope and a fresh read-only device
check; follow the ownership, guard and recovery rules in [AGENTS.md](AGENTS.md)
and [INSTALL](docs/INSTALL.md). Preserve the established IMS audio path and
keep CS changes scoped to CS. Do not revive quarantined experiments or the
removed browser command console.

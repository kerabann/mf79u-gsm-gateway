# Verification

`make test` is fully isolated from a modem, SIM, PBX account and real SMS/calls.
The C fixtures run in disposable Linux with AddressSanitizer and UBSan; ARM SIP
fixtures run under qemu. Go tests exercise configuration, permissions/sessions,
SMS formats/dispatcher/spool, Wi-Fi and System. JavaScript fixtures cover System,
roaming state, Wi-Fi and VoWiFi UI behavior. The SIP fixtures exercise registrar
Digest/replay/recovery/Disabled behavior, both cellular backends, SIP MESSAGE
success/timeout/duplicates/CPIM and PCMU/PCMA bidirectional RTP↔PCM.

`make lint` checks Python syntax, shell syntax and JavaScript. `make audit`
checks documentation links, publication files, source migration coverage and
migration coverage. `make verify-migration` additionally checks the original
migration fingerprints; normal CI allows deliberate later source edits without
rewriting the preserved migration receipt. `make package-check` rejects duplicates,
unsafe members, unexpected payloads, checksum mismatches, missing runtime files
or a changed external PCM contract.

Native tests run 26 C fixtures (23 with ASan/UBSan, three under ARM32 qemu)
and five Python regressions. The new actual ARM VoWiFi controller fixture gates
private IMS on an authenticated simulated tunnel with no cellular service
and requires B03 private mode17 (SYSINFO service5 is not that enum);
it covers private CEREG/CGREG queries, tunnel loss/recovery, CP query failure,
preserved SIP and roaming ring-only rejection. The kernel relocation test generates synthetic ELF
modules and export tables rather than requiring quarantined historical binaries.
Hardware-only PCM/LED/portless-adapter programs and dynamic vendor selftests
require real B03 services and are outside isolated CI. SIP codec/network tests
run separately under qemu; they are not omitted from the complete suite. Compiling those programs does not prove a physical device test.
Preserved tools under `firmware/mf79u/test-*` document additional historical
fixtures and authorized physical test procedures. Run them only through
`make task` after reading their topic document and distinguishing device mutations.

`make test-workflow` verifies a real temporary Git index exports only staged
contents, excluding untracked helpers and unstaged edits. `make clean-checkout`
runs the full CI from that index; stage intended changes before running it.
This prevents a local untracked test from masking an incomplete pushed commit.

`make test-workflow` also exercises corrupt/missing/extra/duplicate/traversal packages,
the PCM contract, staging-space bounds and rejection before service shutdown
when space or transfer setup is unavailable, and fail-closed SMS/driver ownership
checks. `make workflow-check` runs pinned
actionlint; `make audit` always runs Gitleaks, using pinned Go sources if its CLI
is absent.

`make device-status`, `make install-plan` and `make verify-device` are read-only.
After an authorized install, verify aggregate runtime recovery, owned children,
settings/guard preservation and every installed checksum. For a SIP SERVER,
client binding after a service restart requires a fresh REGISTER; a presence
toggle does not refresh registration. Never infer a preserved binding from a PID.

UI behavior changes require all eight tabs and relevant roles/Client settings at
1280/390/320px, with no horizontal overflow or JS errors. Use non-secret fixtures.
Rebuild Control because HTML/CSS/JS are embedded. Serving source assets is not
proof that the modem is running the new executable.

Telegram fixtures check strict TLS, the bundled public CA fingerprint, bound
DNS/HTTPS, private error redaction and GET-only diagnostic response allowlisting.
`make task TASK=diagnose-telegram.py` reads only sanitized queue/interface facts;
`ARGS=--installed-network` additionally invokes the installed Control's read-only
DNS/TLS/getMe/getChat checks, without submitting a Telegram message. See
[WEBHOOKS.md](WEBHOOKS.md) for the current delivery receipt and commands.

The full frontend fixture (`test-ui-actions.js`) runs from `make test-js` and
Control builds. `make task TASK=test-ui-e2e-server.py ARGS='--timeout 12'` serves
the disposable browser fixture on loopback. `ui-e2e-device.py --assets` compares
all five live embedded assets against source; `--call-stats` returns strictly
allowlisted call metadata. `ui-e2e-api.py` reads credentials through a hidden
terminal prompt and emits only sanitized results. Its explicit
`--pbx-registration`, `--administrator-password`, `--ssh-password` and
`--hotspot-settings` modes change real settings
temporarily and restore them; they require separately authorized physical test
scope. They do not submit SMS/calls. The initial PBX test is specific to the
dedicated local password-free MF79U provider and refuses other profiles.
Password tests are real API/authentication checks; valid new credential entry
through the browser requires user handoff. Read-only device helper flags
`--cs-diagnostics` and `--network-policy` report owned process/driver/firewall
facts, without live rules or configuration values. `install-native-update.py
--install` is an authorized native-only update with executable/supervisor
ownership, idle, backup and staging-space checks. It leaves the persistent CS
driver/media untouched. Run through `make task` after `make test-native
build-native`, then obtain a fresh client REGISTER.
`make test-workflow` checks this updater's refusal before any transfer/shutdown
for active calls, an unknown executable/supervisor and insufficient staging space.
It also checks a call or ring-only marker change arriving during transfer is
refused before shutdown. Its explicit `--ring-only` option enables persistent
dial/answer protection for an authorized roaming registration-only check; this
does not prevent private VoWiFi IMS registration and is never removed by update.

Physical evidence is separate: do not repeat one-shot SMS/call tests, change IMEI
or reboot merely to validate the repository migration. See [AGENTS.md](../AGENTS.md)
for the current permission/roaming/PCM constraints and [MIGRATION.md](MIGRATION.md)
for completed checks in this migration.

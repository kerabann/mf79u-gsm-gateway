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
and four Python regressions. The kernel relocation test generates synthetic ELF
modules and export tables rather than requiring quarantined historical binaries.
Hardware-only PCM/LED/portless-adapter programs and dynamic vendor selftests
require real B03 services and are outside isolated CI. SIP codec/network tests
run separately under qemu; they are not omitted from the complete suite. Compiling those programs does not prove a physical device test.
Preserved tools under `firmware/mf79u/test-*` document additional historical
fixtures and authorized physical test procedures. Run them only through
`make task` after reading their topic document and distinguishing device mutations.

`make test-workflow` exercises corrupt/missing/extra/duplicate/traversal packages,
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

UI behavior changes require all seven tabs and relevant roles/Client settings at
1280/390/320px, with no horizontal overflow or JS errors. Use non-secret fixtures.
Rebuild Control because HTML/CSS/JS are embedded. Serving source assets is not
proof that the modem is running the new executable.

Physical evidence is separate: do not repeat one-shot SMS/call tests, change IMEI
or reboot merely to validate the repository migration. See [AGENTS.md](../AGENTS.md)
for the current permission/roaming/PCM constraints and [MIGRATION.md](MIGRATION.md)
for completed checks in this migration.

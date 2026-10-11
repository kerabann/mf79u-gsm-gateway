> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Boot UI and runtime memory

Updated: 2026-10-11. Physical MF79U B03, userdata runtime; packaged NAND/SD
archives remain older and no raw image was flashed.

## Startup frontend

The vendor goahead starts before our Control network redirects. The live
stock index initially served the old UI. It is now backed up and replaced by
boot-wait.html: a small English starting page which retries index.html every
2 seconds, preserving the selected hash. It contains no old ZTE JS/CSS/runtime.
start-control-userdata.sh installs LAN port80→18080 redirects before waiting
for interfaces; Control later maintains them. Loopback goform stays on80.
The rootfs packer already maps our actual UI into the final stock web path;
the waiting stub is only needed for the currently installed userdata overlay.

## Optional vendor services

B03 run/sync entries for zte_topsw_data_stat, zte_topsw_pbm and zte_topsw_ussd
were removed from the persistent daemon policy. These are vendor traffic
statistics, phonebook and USSD workers; our UI does not use their endpoints.
Their underlying adapters remain for compatibility. TERM was ignored, so
verified exact executables were stopped with KILL while no call was active.

The targeted workers' measured pre-stop resident PSS was228KiB, with620KiB
swap. RSS is shared and cannot be summed as freed RAM. Before/after process
reports are build/memory-before-trim-20261011.json and memory-after-trim-20261011.json.
The latter confirms these exact three workers are absent. Different VoWiFi
states make aggregate before/after memory totals unsuitable as a causal saving.
Largest required consumers before trimming: Control PSS5672KiB, charon1792KiB,
private IMS1709KiB, goahead976KiB. Goahead remains required by current login and
vendor API. Radio, CP, SIM/SMS, Wi-Fi, DHCP/DNS, router, NTP, watchdog, USB,
ADB, native, SIP and CS runtime remain installed. FOTA, remote DM and vendor
LED/self-registration were already disabled by prior policy.

## Reversible deployment and validation

Checksummed backups in userdata: daemon.pre-trim-20261011.conf,
index.pre-boot-wait-20261011.html, start-control.pre-early-20261011.sh.
Root changes use remount/read-only trap plus staged atomic rename.
Installer source generates the same daemon policy and accepts the prior native
policy during upgrade. Receipt build/boot-ui-memory-trim-install-20261011.json.
No active call and unchanged native/SIP PIDs were verified during installation.
VoWiFi had already lost readiness after its initial successful boot registration
before any service was stopped; do not attribute this to the trimming.
The further boot observation passed: all observed HTTP responses were the custom
frontend (first response at46.7s); no vendor UI was observed. All three disabled
workers were absent after reboot. Hardware masks were only red1 then purple5;
actual VoWiFi ready at about167s stayed ready for at least120 consecutive seconds.
Management login and saved SERVER/VOWIFI/CLIENT configuration were verified.
Receipt: boot-ui-memory-trim-verify-20261011.json (historical local artifact: `build/boot-ui-memory-trim-verify-20261011.json`).
Steady post-boot memory: build/memory-after-trim-boot-20261011.json.
A bounded read-only native integer probe during recovery confirmed normal
retry state; no keys, SIP payloads or identities were copied. Diagnostic symbol
artifacts are offline only and are not installed runtime candidates.

The preceding requested reboot proved hardware LED red1→purple5 only, actual
VoWiFi ready after about167s including provider P-CSCF failover:
build/led-vowifi-only-boot-20261011.json. This short proof does not establish
long-term tunnel stability, voice/audio or reauthentication.

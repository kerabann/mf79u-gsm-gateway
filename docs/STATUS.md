# Current project status

Updated 2026-10-12. This Git repository is the new source of truth. The complete
original topic documentation and test sources have been imported. The migration
is packaging/build work; it does not itself constitute a new physical call test.

The maintained delivery is the device-local userdata overlay. Full NAND/rootfs
0.9 and SD 0.8 archives are historical and were not flashed or refreshed. Reset
that preserves/restores a factory profile is designed, not implemented.

## Incoming multipart SMS forwarding fix, 2026-10-12

The user reported that long incoming GSM SMS were forwarded as fragments. B03
exposes a growing inbox row with `received_all_concat_sms` and concat counters;
the shared Telegram/SIP reader had ignored them. It now waits for completion,
keeps unfinished rows in modem memory, and selects one longest complete snapshot
per storage/ID. Incomplete rows do not enter either forwarding queue or its seen
baseline and cannot trigger automatic deletion. Incoming text uses the existing
2680-byte SIP body bound; outgoing submission stays at 670 characters. Go tests
cover staggered/out-of-order snapshots, restart, no premature forwarding/delete,
whole-message delivery/ACK/deduplication and conflicting metadata.

Control MD5 `2322c6d06d8233607ab5f9859be0ff7b` is installed using the optional
`--require-sms-idle` guard; legacy forwarding queues were clear before replacement.
The update preserved settings, boot and native2147/SIP2148. A read-only installed
metadata check found seven complete GSM inbox rows: three ordinary rows with
`all=1,total=0,received=0` and four multipart rows with `all=1,total=2,received=2`.
Two subsequent worker-poll snapshots retained VOWIFI_SMS, ready Wi-Fi IMS,
GSM SMS registration, disabled CS signaling/audio and the registered Linphone
client; SIP queued/pending/buffered counts stayed0. The complete test suite,
28-file package/check and publication/documentation audit passed. No new SMS,
call, answer or reboot was initiated. Reception of a new delayed multipart SMS
after installation remains untested on hardware (`liveMultipartReceptionTested=false`);
the staged completion/forwarding behavior is fixture evidence. Safe receipt:
`reports/sms-multipart-live-20261012.json`. Details:
[incoming SMS assembly](../firmware/mf79u/SMS-API.md#incoming-multipart-sms-2026-10-12).

## Roaming SIM VoWiFi registration fixed, 2026-10-12

The owner subsequently authorized GSM registration for SMS with VoWiFi-only
voice. The separate `VOWIFI_SMS` / **VoWiFi only + GSM SMS** option is installed
and selected. Fresh CP checks confirmed GSM profile13, CFUN1, CREG5 (roaming)
and both CS voice flags0. VoWiFi over USB remained ready, CS signaling/audio
disabled; native2147/SIP2148 and the same boot stayed stable for60s after apply.
The user confirmed incoming SMS: two new Telegram deliveries and two new SIP
acknowledgements, with IMS received0 and the three earlier IMS incoming messages
unchanged. Those forwarded inbox snapshots arrived through GSM; counters alone
do not establish two distinct logical SMS, because the multipart bug above could
forward a growing prefix more than once. Calendar date advanced
from2000 to2026 after registration; Telegram GET-only bot/chat diagnostics now
return200/OK with strict TLS. No manual clock setting, call/SMS submission or
reboot was performed. The original VOWIFI IMS-SMS path is retained. Evidence:
`reports/vowifi-gsm-sms-{live,stability,incoming-route}-20261012.json`. Details:
[compatibility mode](../firmware/mf79u/SMS-IMS.md#vowifi-only-voice-with-gsm-sms-2026-10-12).

Installed native MD5 `5baa88e88525c47f0c44cdba3a5a2327`: the owned B03 IMS
engine now admits an authenticated SWu tunnel without cellular registration.
Its private compatibility mode uses B03's `^MODE` enum17, not SYSINFO enum5.
Physical registration completed at native elapsed15s (401 → SIM AKA → 200),
VoWiFi/SIP voice-ready at19s. A further60s read-only check passed readiness,
USB ePDG route, management and purple idle LED. Real EPS/CS telemetry stays4;
no cellular attachment is claimed. Native2130/SIP2131, bootfc55eaf9… retained
through final verification. The existing Linphone account was reopened and
`localRegistered=true` was restored after the SIP process replacement.

The roaming `native-ring-only` guard was enabled during registration diagnostics.
The owner subsequently explicitly requested its removal while remaining in
VoWiFi-only. The marker is now absent and runtime reports `ringOnly=false`;
requested/effective mode remains VOWIFI, IMS and the registered Linphone client
remain ready. Four post-removal snapshots confirmed unchanged boot, native/SIP
PIDs, settings and runtime checksums, with CS signaling disabled. VoWiFi-only
still forbids LTE/CS voice and cellular SMS fallback. Receipt:
`reports/vowifi-ring-only-disabled-20261012.json`. No call or SMS was initiated.
The native-only updater verified unchanged settings, private IMS/media, SIP,
CS driver/adapter/PCM and boot. No call, SMS, reboot or radio setting change.
`make test`, native build, package/package-check and audit passed. Receipts:
`reports/native-update-install.json`,
`reports/vowifi-roaming-verified-20261012.json`,
`reports/vowifi-roaming-sip-client-20261012.json`. Details:
[VoWiFi correction](../firmware/mf79u/VOWIFI.md#roamingno-cellular-ims-compatibility-correction-2026-10-12).

Read-only inspection after the owner changed SIM found VOWIFI-only with USB
internet selected. The SIM-derived ePDG is for public PLMN 250/02. An initial
snapshot confirmed the SWu tunnel and two assigned P-CSCF addresses, but IMS
and voice never became ready. Two complete native attempts exhausted both
P-CSCF waits with `tunnel=1 registered=0 ims=1`; each IMS start recorded
`waiting_for_radio_service`, with no REGISTER or SIP response metadata observed.
Later ePDG attempts exited with code 1 and `vowifi_start_failed`. Last observed
hardware LED was red; native2336/SIP2469, boot and registered local SIP client
were preserved. Details, limitations and next diagnostic hypothesis:
[VoWiFi new-SIM check](../firmware/mf79u/VOWIFI.md#new-sim-registration-check-2026-10-12).
No settings, runtime installation, reboot, call or SMS submission was performed.
The owner subsequently authorized repair and confirmed the SIM is roaming.
The completed repair above supersedes this initial read-only diagnosis.

## Incoming SMS diagnosis on the roaming SIM, 2026-10-12

The owner sent an SMS to the new modem SIM and expected Telegram/Linphone;
the sender showed sent, without a delivery report. Read-only inspection found
the same boot/native2130/SIP2131, ready VoWiFi-only over USB, SMS IPC
ready/configured/formatVerified=true and fenced=false, but received0 since this
native start. No IMS MESSAGE/CMT/durable-receive event appeared in the retained
small native log; no PDU, unsupported PDU or incomplete multipart remained.
The three retained IMS incoming SMS are older, all acknowledged by SIP. Current
SIP diagnostics reported vendorReady=true, no pending incoming or queued work;
Telegram also had no pending job. Fresh CP reads returned CFUN4 and
CREG/CGREG/CEREG state4, with SIM PIN ready. No current cellular attachment was
observed. This locates the missing IMS delivery before the forwarding stages;
the precise SMSC/IP-SM-GW routing/service cause is not established.

A separate bound-interface Telegram GET-only check resolved DNS but returned
`tls_invalid_certificate`: the modem's UTC date was 2000-01-01, while the public
Telegram leaf observed from the host is valid2025-11-11 through2026-12-13.
At that diagnostic point the clock was an additional Telegram blocker; the
later GSM registration above supersedes this failure with working strict TLS.
During the earlier diagnostic no clock/settings/runtime changes, SMS submission, manual
Telegram message, call or reboot were performed. Reports:
`reports/sms-delivery-path-20261012.json`,
`reports/sms-delivery-network-20261012.json`. Further evidence and limitations:
[SMS diagnosis](../firmware/mf79u/SMS-IMS.md#roaming-sim-incoming-sms-diagnosis-2026-10-12).

MegaFon-specific research on2026-10-12 found an official VoWiFi condition:
airplane-mode users should register in the cellular network every1.5 hours.
The current FAQ does not promise incoming SMS through VoWiFi. Firsthand user
reports include both working and failing SMS setups, so a universal carrier
SMS prohibition is not established. Our fresh device-status check still showed
ready VOWIFI with native2130/SIP2131; the published90-minute condition was not
reproduced as a failure. SMS-over-IP subscriber provisioning/routing and accepted
Contact capabilities require further evidence. No radio/clock/runtime changes
or new SMS/call were initiated. Sources and compatibility limits:
[MegaFon service check](../firmware/mf79u/SMS-IMS.md#megafon-specific-service-check-2026-10-12).

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
- English eight-tab WebUI; Mobile settings, scoped Save, framed blocks; LEDs,
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
The initial publication commit `cbb0ae7` was pushed to `main` on 2026-10-11.
The first [GitHub-hosted workflow](https://github.com/kerabann/mf79u-gsm-gateway/actions/runs/38158311596)
completed successfully on Ubuntu 24.04 x86_64 in 7m 16s for `cbb0ae7`.
This hosted receipt validates the initial publication; the later UI changes
below have local checks and are not attributed to that older workflow run.

## Remaining boundaries

Only the exact supported MF79U B03 kernel/CP ABI is accepted. Other variants,
UMTS and GSM wideband are unverified. The registrar is one-account/one-binding
UDP; trunk transport supports UDP/TCP/TLS. Full rootfs flashing and factory reset
preservation are not production workflows. Previously observed remote clearing,
clock and DSP faults are documented historically; use the accepted production
driver/profile rather than resurrecting older experiments.

## Current UI audit and CS compatibility correction, 2026-10-11

A fresh UI/runtime audit corrected network readiness/rollback notices, delayed
apply after cancellation, scoped drafts, unnecessary SIP reloads and misleading
voice/PBX status. Missing SSH runtime files were recovered. A legacy GSM driver
compatibility correction restored CS readiness without changing its driver or
PCM/IMS media. Updated Control/native are installed without a modem reboot.

Fresh physical checks include real 90-second expiry, gateway-address restoration,
UDP PBX registration, admin/SSH password rotations, hotspot settings, GSM CS/AUTO
readiness, LTE data-off guards and a user-confirmed incoming VoLTE conversation.
All seven fixture views passed 1280/390/320px. See [the audit matrix](UI-E2E-20261011.md)
for exact source/browser/API/device boundaries, preserved artifact hashes and
remaining call/Wi-Fi/transport checks. The user deferred another outgoing call;
the complete combination matrix is not claimed as passed.

## Incomplete UI commit and checkout verification, 2026-10-11

The [workflow for `6fa01c6`](https://github.com/kerabann/mf79u-gsm-gateway/actions/runs/38166521915)
failed in the Control build because `test-ui-actions.js` was referenced but absent
from the pushed commit. Nine UI audit source/test/helper/document files remained
untracked locally; this also omitted the native updater regression and the audit
document linked from this status. The repair includes those publication files.

The old clean-checkout helper copied untracked files and working-tree contents,
so it could conceal an incomplete commit. It now exports only the Git index.
A real temporary Git regression checks exclusion of untracked files and unstaged
edits and inclusion after staging. Run `make clean-checkout` after staging the
intended change.

Validation passed: `make test-workflow` and a complete `make clean-checkout`
(`make ci` from the prepared Git index). This includes Linux Go tests, all UI
fixtures, 26 native selftests plus four Python regressions, ARM SIP/RTP tests,
the complete 28-file overlay and checksum/PCM checks, publication secret scan
(499 files) and documentation audit (43 documents, 324 local links). Local logs
and the Git-index checkout receipt are under ignored `reports/`. This is local
CI evidence, not a successful replacement GitHub-hosted run. No modem operation
is part of the CI repair.

## Telegram SMS webhooks, 2026-10-11

The eighth tab, **Webhooks**, contains one **Telegram SMS** block: Enabled,
BOT-token, Chat-id, Send through interface and **Delete after send to chat**.
A scoped authenticated/CSRF-protected Save does not reload voice/SIP or apply
network settings. Incoming cellular modem/SIM and private IMS SMS use the shared
normalized inbox path, including with SIP Disabled. A private bounded queue,
restart deduplication, retry and confirmed-delivery deletion run on the modem.
DNS and HTTPS bind to the selected interface without automatic uplink fallback;
operator IMS `wan5` is excluded. Existing mobile data firewall policy applies.

Current validation and physical-install boundaries: [WEBHOOKS](WEBHOOKS.md).

Control-only installation and fresh embedded-asset verification passed. Boot,
native3483/SIP3484, settings/gateway hashes, guards and IMS/voice readiness were
preserved. All eight browser fixture tabs passed 1280/390/320px (24 views).
`make test`, final Linux Go tests, package checks and repository audit passed.
The full package is checked but was not installed: its different pinned CS
driver would require a checked reboot. No modem reboot, call, SMS or real
Telegram send/delete occurred during that initial install. The later owner
configuration and actual delivery are recorded below.

## Telegram TLS repair and real delivery, 2026-10-11

After owner configuration, a real incoming SMS remained queued because B03's
old CA store did not trust Telegram's Go Daddy G2 chain. A bound-interface
read-only probe confirmed DNS success and `tls_untrusted_root`. Control now
embeds the official public CA root in the Telegram client, retains strict
certificate/hostname validation and provides sanitized DNS/TLS/getMe/getChat
diagnostics. Source/provenance and exact receipts: [WEBHOOKS](WEBHOOKS.md).

After Control-only installation, the existing queued SMS was accepted by
Telegram: delivered 0→1, queue 1→0, no pending deletion. The enabled deletion
option reduced the private IMS inbox from four incoming SMS to three. Bot/chat
checks both returned HTTP 200 / `ok:true` through USB `bridge0`. No new SIM SMS,
manual Telegram test message, call or reboot was issued. Settings/gateway hashes,
boot, native3483/SIP3484 and guards were preserved; installed Control and public
assets matched source. IMS/voice was already not ready in the fresh preflight
and remained not ready at that snapshot. Readiness subsequently recovered on the
same boot/PIDs without a recovery action, before the update below.

## Telegram and connected SIP delivery together, 2026-10-11

Telegram auto-delete could race SIP's independent inbox polling. Before deleting
the original, Control now persists a private copy for an available SIP peer.
SIP receives the same sender/body even after original deletion, and removes its
copy only on persisted SIP 2xx ACK. A restart/disconnection retains the copy;
full queues/write failures defer original deletion without Telegram resubmission.
Disconnected/Disabled peers introduce no new deletion dependency.

The combined fix is installed with fresh source/binary/asset/preservation checks
passing. Same boot/native3483/SIP3484, settings and guards; IMS/voice ready and
SERVER client still registered. Only Control restarted. Race/restart/privacy/
ACK/bounds/disconnected fixtures pass. After installation, the user confirmed a
fresh incoming SMS reached both Telegram and the SIP client. No SIM SMS was
submitted by the agent. See [WEBHOOKS](WEBHOOKS.md) and
[SMS-SIP](../firmware/mf79u/SMS-SIP.md) for behavior and receipts.

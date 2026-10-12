> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Linphone / SIP Server / VoWiFi Only

Updated: 2026-10-12. Physical MF79U, USB management192.168.0.1/24.
No reboot, rootfs/NAND flash or external PCM change is required.

## SWu local voice-resource correction, 2026-10-12

The earlier registration adapter exposed the authenticated SWu packet service
to B03 but did not announce local voice-resource availability. The new narrow
controller change sends `+CGEV: ME ACT 5,6` only to its owned IMS child after
tunnel, IMS registration, frontend and codec readiness. The existing private
IMS context is CID5; CID6 is a compatibility marker, not an observed cellular
dedicated bearer. No CP command, LTE/CS admission, PCM, AMR policy, media library
or private binary patch changes. [GSMA IR.51 v9 section2.4.1](https://www.gsma.com/newsroom/wp-content/uploads/IR.51-v9.0.pdf)
requires use of preconditions with local availability reflected in SDP even
when local resources already exist. The adapter uses B03's original signaling
state machine; it does not remove preconditions or disable the timeout globally.

The indication is idempotent for one owned IMS process and reset on teardown.
Failure to send it or loss of registration/tunnel during dispatch keeps voice
unready. Normal LTE IMS never enters this path. Existing tunnel-generation
replacement stops the old private engine; a new authenticated generation must
register and receive its own resource indication.

`make task TASK=firmware/mf79u/test-vowifi-qos-b03.py` executes the exact private
B03 ELF after applying and verifying the existing checksum-bound patch recipe.
It requires the ignored stock B03 input and has no device or network access.
The real CGEV parser/handler validates the chosen normal account and secondary
resource ID, while another primary CID or mismatched deactivation does not
change it. The real timer setter cancels an already active timer; the real183
branch schedules6000ms for missing resources and skips it when ready. The real
completed-transaction branch calls the existing precondition completion for an
already-ready bearer. Finally, the real completion function updates local
direction to sendrecv and reaches UPDATE while preserving synthetic remote
mandatory/unmet conditions. Libc, external getters/locks and final SIP transport
are fixture boundaries; this is not a full network call. Receipt:
`reports/vowifi-qos-b03-offline.json`.

The actual ARM controller fixture in `make test-native` verifies no resource
event before tunnel/registration, exactly one per private engine, a fresh
event after tunnel recovery, preserved real cellular telemetry/guards and no
resource event after switching to ordinary VoLTE. Safe diagnostic tools:
`make task TASK=firmware/mf79u/inspect-vowifi-qos.py ARGS='--refs 0x169d0'`
performs checksum-bound static inspection; `make task
TASK=firmware/mf79u/verify-vowifi-qos.py` reads sanitized runtime status and only
five fixed QoS scalars from a verified owned child. It emits no identifiers,
SIP bodies or memory dumps. `ARGS='--wait 120 --require-ready'` also requires
ready SWu/IMS and the normal-account resource flag1; it never places a call.

Physical baseline before installing this correction: native1328/SIP1329,
same boot, USB IMS ready again, resource flag0. During this continuation the
old runtime lost SWu at elapsed1797 and recovered at2026 after a manager restart
and P-CSCF failover. Its separate tunnel/registration renewal delay is not
repaired by the call-resource change. Baseline receipt:
`reports/vowifi-qos-before-20261012.json`.

Full `make test build-native package package-check audit` passed, including28
native fixtures and5 Python fixtures; the exact B03 emulator also passed its5
case groups. Logs: `reports/vowifi-qos-native-tests-20261012.log` and
`reports/vowifi-qos-validation-20261012.log`.
The native-only updater installed MD5`62a9352296662a098986228670a2486b` and
restarted its owned supervisor. It then exceeded the120-second readiness
deadline, so no successful installer receipt was emitted. Native1508/SIP1509/
CS1520 remained idle on the same boot; private IMS/media/SIP hashes match the
baseline. The first two P-CSCF attempts ended without registration at elapsed75
and146. Safe snapshot: `reports/vowifi-qos-after-20261012.json`. The backup was
retained under ignored private backups. The updater's final aggregate settings/
CS preservation check was not reached and must not be reported as completed.
The subsequent bounded observer lost ADB access before completion; it produced
no successful readiness receipt. At12:05UTC the owner reported IMS recovery.
A new read-only check on boot4e4d111b… found native1531/SIP1532/CS1610 and its
owned private IMS1534, ready USB SWu/IMS, registered Linphone and both call legs
idle. The installed native matches the candidate; private IMS/media/SIP match
the earlier baseline. Exact checksum-bound B03 reads show normal-account
resource flag1, emergency0, preconditions1 and the QoS timer inactive. The
native resource event and ready state both occurred at elapsed353 after six
ePDG manager failures; IMS registered at349. This proves the resource
indication reaches the physical B03 process, not a corrected real call.
Receipt: `reports/vowifi-qos-ready-20261012.json`. The later boot change was
observed, not requested or performed by this continuation; its cause was not
investigated. Registration delay remains unresolved. No further call allowance
had been consumed at that point; a new bounded test was requested from the owner.

### Physical call verification after the correction

The owner authorized one call of up to20seconds. At native elapsed523 the call
sent INVITE, received100/183, completed PRACK/200 and then B03's own UPDATE/200.
Further183 and180 followed, then403 and ACK; no premature B03 CANCEL occurred.
The call closed itself before the attempted UI hangup. The owner heard one
Linphone ringback and reported that the destination handset was not yet on.
The exact403 reason was not retained: the controller does not forward the
media library's reason phrase. Do not infer a balance, roaming or carrier ban,
or claim that the powered-off handset definitively explains403.
Receipts: `reports/vowifi-qos-call-after-20261012.json` and
`reports/vowifi-qos-call-once-20261012.json` (allowance consumed).

The owner explicitly requested one repeat. At elapsed634 another INVITE
completed PRACK/UPDATE/200 and reached180. The owner confirmed the destination
handset rang and was not answered. UI hangup produced call_ended at656 and
CANCEL/200/487/ACK. No403 occurred in this attempt. The observed native interval
was22seconds, not the promised20; UI confirmation was at22240ms. This overrun
was disclosed to the owner. Do not repeat this manual timing approach for a
future hard duration bound: prepare a checked independent cutoff first.

Both legs were idle afterward, with the same boot/native1531/SIP1532/private
IMS1534, ready USB SWu/IMS, registered Linphone, normal resource flag1 and
unchanged installed hashes. Receipts:
`reports/vowifi-qos-call-repeat-after-20261012.json` and
`reports/vowifi-qos-call-repeat-once-20261012.json` (allowance consumed).
Outgoing ringing is physically confirmed after the correction. Answered
audio/duplex is not verified by these tests; no PCM/media changes were made.
Registration delay remains a separate unresolved issue. No further call is
authorized, and no test remains armed.

## Registered outgoing-call failure, 2026-10-12

The owner reported that VoWiFi had registered but outgoing calls failed, and
explicitly supplied a test destination. On the newly observed boot, native1535/
SIP1537 were ready in `VOWIFI_SMS`, USB SWu/IMS ready, roleSERVER and Linphone
locally registered. Ring-only was absent and CS signaling/audio disabled.
Installed hashes matched the previous runtime: native49aebaf…,
SIPbf43f737…, Control2322c6d…, private IMS2e722047… and media8da9d5e….
The destination and credentials were not saved in receipts or documentation.

One call was made from the existing Linphone account through its ordinary
dialer. The passive observer saw SIP active at elapsed32.75, the IMS backend
admitted at34.99, SIP cleared by41.76 and the native backend idle by43.98.
The native call event was at its own elapsed990. Operator metadata then showed
100 →183 →200 →200 →487, with no native CONNECT or SIP media-ready event.
The200 responses cannot be claimed as an answered INVITE because the method
was not retained. Linphone's latest call metadata showed INVITE401 challenge,
authenticated INVITE100, final487, ACK and OutgoingProgress→Error→Released.
It showed no sent CANCEL. The owner confirmed neither handset ringing nor
Linphone ringback. Both runtime legs cleared; the same boot/native/SIP/CS PIDs
and ready IMS/local registration were preserved. No second call was issued
at this diagnostic stage.

CP CSTA and ZCSVOICESPT queries returned unsupported/error replies. Historical
[IMS media diagnostics](VOICE-BACKEND.md#предыдущий-этап-с-новой-sim-достижение-183-и-отказ-кодека)
already describe those B03 limitations, so they are not by themselves the
current cause. The failure is between IMS early progress and connection,
with an IMS-side487 also relayed to Linphone. The responsible component and
exact cancellation reason are not established by these metadata alone.

The current private child maps the installed media library and has software
media, network PCM, wideband and operator codec flags enabled. Memory/process
metadata was read without dumping memory or identities. A separate short,
isolated ARM test loaded that exact installed media library and passed NB,
all9 WB modes and G.722 ABI tests (all result0). It generated synthetic PCM
only in its own process and did not initialize IMS, place a call or change
radio/configuration. Its temporary RAM helper was removed. This checks the
codec adapter, not media admission/negotiation in the failed real call.

The controller's `read_lines` had dropped the existing library's numeric
media errors and most SIP method metadata. The diagnostic correction admits
only exact known scalar names and bounded numeric values, and known direction/
method/byte-count lines. It does not relay arbitrary vendor trace, SDP, SIP
headers/bodies, identities, AKA material or PCM. Sanitized errors and request
methods are required before declaring a media bug or operator rejection.
Successful codec-frame ioctls/results are excluded from the added logs to avoid
per-frame stdout overhead. Sanitizer vectors cover exact-name admission,
private suffixes, overflow, unchanged errno and hot-path suppression. The actual
ARM controller fixture verifies safe scalar/protected-method retention and
rejection of arbitrary trace suffixes without changing readiness or guards.
Implementation and installation validation are tracked separately from a new
real-call result; the current failure has not been repaired on hardware.

The complete `make test build-native package package-check audit` passed.
After final hot-path/fixture changes, `make test-native build-native package
package-check audit` passed again:27 native selftests plus5 Python regressions,
ARM-controller lifecycle/metadata checks and the complete28-file overlay.
The native-only updater installed MD5`59f85129c2f3fa27ba6bc03820ba9f67`, preserving
boot, settings, private IMS/media, SIP and CS binaries. New native1328/SIP1329
completed REGISTER401/AKA/200 at elapsed16 and voice readiness at20. The
existing Linphone account was reopened without credential changes and
`localRegistered=true` verified again. The constructor/socket scalar metadata
is physically visible; that is observability proof, not a successful new call.
The owner separately authorized **one** further bounded call. That allowance
was consumed; no automatic repeat is armed or further real call authorized.

The second passive observer saw SIP active at elapsed17.44, native IMS call
admission at19.71, SIP clear at27.61 and native idle at28.86. The actual retained
sequence was TX INVITE →RX100 →RX183 →TX PRACK →RX200 →TX CANCEL →RX200 →
RX487 →TX ACK. Duplicate TX rows are observer paths for the same message,
not proof of two calls. The B03 engine originated CANCEL;487 is the subsequent
INVITE termination. AMR encoder/decoder initialization, PCM resource/preopen,
PCM format and read/write start all completed with no retained failure/errno.
Both PCM workers received262144-byte stacks and normal scheduling. PCM stop
and preclose followed clearing. This supersedes an unconfirmed codec-startup
hypothesis; a synthetic codec PASS alone was never call/audio proof.

### QoS/dedicated-bearer cancellation hypothesis

Static inspection was bound to stock B03 SHA256
`3516bf3adfcfe97bbb029b1a89a1ada45b9b1bb578a08170d0141e15a96ab738`
and the installed private patch SHA256
`e0a712e079afa2c97a8c16092e1ff7a96d63525b24f49ac07fa1d1511d89eed0`.
These are code addresses in that exact executable, not a generic vendor ABI:

- `on_call_tsx_state` at0x1b802 checks183, global preconditions enabled,
  account dedicated-bearer readiness via0x1433c and a call-info state.
  At0x1b84e it schedules the0xc6e08 QoS timer for0x1770 =6000ms.
- `tqos_timer_cb` at0x17b10 queries CS/redial capability through0x140dc,
  then calls pending-call hangup at0x74a64 regardless of that capability.
  This gives the observed unsupported ZCSVOICESPT query →CANCEL sequence.
  The separate8000ms local-ringback timer is not this QoS timer.
- `zIms_cc_set_dedicated_eps_bearer` at0x169d0 sets the account bearer flag,
  cancels an active QoS timer and enters local-precondition completion.

A temporary read-only ARM helper verified the exact executable and owned-child
parent before reading a fixed numeric allowlist. It found preconditions1,
both account bearer flags0, timer callback0x17b11 (Thumb), inactive heap index-1
and a nonzero retained timer deadline after the call. The timer field layout
was checked against B03's own initialization/read/schedule code. Last-call
precondition fields were already reset to0 after clearing, so they cannot
prove the operator's requested conditions. No arbitrary memory, SIP packet,
identity or voice samples were dumped. The helper and host build files were
removed; the safe scalar receipt remains ignored.

The6-second QoS wait, failed-bearer flags and observed local CANCEL strongly
support a missing voice-resource completion in the current SWu compatibility
path. Callback execution itself was not instrumented, and the183 SDP was not
retained; this remains a causal hypothesis rather than a directly traced
callback. SIP preconditions can delay handset alerting until required resource
conditions are met; see [RFC3312 sections5/6](https://www.rfc-editor.org/rfc/rfc3312.html).
Registration readiness alone does not satisfy those call conditions.

The owner explicitly clarified that a **local SIM had successful VoWiFi calls
over Wi-Fi or USB**. That is an owner-confirmed working baseline of the same
access path, not a VoLTE/CS baseline. The earlier radio profile, bearer flags
and negotiated SDP were not recorded. Current `VOWIFI_SMS` uses GSM profile13
with CS voice flags disabled, so both operator negotiation and the changed
radio/access compatibility state remain possible differences. Do not claim
the current operator prohibits VoWiFi calling, or blindly assert that the
local SIM omitted mandatory preconditions. A repair must adapt SWu call-resource
completion without enabling LTE/CS fallback or altering the preserved IMS sound;
no such behavioral repair has yet been installed.

Final read-only verification retained the same boot/native1328/SIP1329/CS1339,
ready USB IMS, localRegistered=true, both call legs idle and CS signaling/audio
disabled. Two real outgoing attempts in this investigation were individually
authorized; no further call, SMS, answer or reboot was initiated.

Safe ignored evidence: `reports/vowifi-call-20261012.json`,
`reports/vowifi-call-after-20261012.json`,
`reports/vowifi-call-linphone-meta-20261012.json`,
`reports/vowifi-call-runtime-meta-20261012.json` and
`reports/vowifi-call-media-selftest-20261012.json`,
`reports/vowifi-call-diagnostics-install-20261012.json` and
`reports/vowifi-call-diagnostics-ready-20261012.json`,
`reports/vowifi-call-diagnostics-20261012.json`,
`reports/vowifi-call-diagnostics-after-20261012.json`,
`reports/vowifi-call-qos-{static,scalars}-20261012.json` and
`reports/vowifi-call-final-20261012.json`. Validation logs:
`reports/vowifi-call-diagnostics-{validation,final-validation}-20261012.log`.

## Test case

1. Verify no active call. Keep confirmed Wi-Fi Client epic-wifi connected with
   COMPLETED and a DHCP address; USB management remains unchanged.
2. Select SIP Server, account100, existing SIP password, bind192.168.0.1,
   UDP port5080. Preserve enabled codec order.
3. Select VoWiFi Only and Save. Expect effectiveVoiceMode=VOWIFI,
   imsAccess=WIFI, imsReady=true and voiceReady=true. Network LED idle purple5.
4. Add third-party SIP account in Linphone: username100, domain192.168.0.1,
   registrar sip:192.168.0.1:5080;transport=udp, UDP, existing SIP password.
   Expect localRegistered=true on modem and registered account in Linphone.
5. Dial the user-supplied test number. Expect native callBackend=ims,
   imsAccess=WIFI, activeCall=true and green network LED2. Answer the remote
   phone, verify speech in both directions, then hang up and verify both legs
   clear promptly. Do not count RTP counters as audible speech proof.
6. After clearing, retain SIP Server / VoWiFi Only and the Linphone account.
   Expect no active call and purple idle LED5. A Wi-Fi outage must block voice
   rather than start LTE/CS fallback; physical outage/recovery is a separate case.

## Historical initial result, 2026-10-11

SIP Server and account100 already existed. VoWiFi Only saved; SWu established.
Provider-list automatic P-CSCF failover observed after SIP500. Linphone form
prepared, awaiting the actual existing SIP password; the protected browser
DOM exposes a redacted placeholder, so it cannot be used for authentication.
Actual Linphone registration and call/audio are not yet confirmed.

Implementation details and prior registration proof: [VOWIFI.md](VOWIFI.md).

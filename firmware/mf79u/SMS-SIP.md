> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Device-local SMS over SIP MESSAGE

Audited 2026-10-11. [STATUS.md](STATUS.md) distinguishes installed runtime,
historical successful PBX tests and the latest GSM fallback check.

Implemented 2026-10-08 in the existing SIP gateway and native Go management
service. Neither direction uses a Mac relay. PCM and voice codecs are unchanged.
The fallback update separates SIP MESSAGE startup from IMS registration.
This is a reversible userdata installation, not raw
flash. Older SD runtime copies and existing 0.9 firmware archives do not include
this change.

## Operator SMS over IP

Current implementation: [SMS-IMS.md](SMS-IMS.md). VOWIFI now forces outgoing
UI/REST/SIP SMS through private IMS, with durable incoming PDU storage and no
cellular submission fallback. The one authorized USB IMS test got RP-ACK and
the user confirmed receipt. Their reply arrived through private IMS and was
saved in the durable IMS inbox; final native readiness and retained messages
were checked after the service update. Other voice modes keep B03 SEND_SMS.
The audit below describes the preceding revision.

## Historical read-only verification boundary (2026-10-11)

Read-only audit of boot77358efe-ab8b-4ca5-bcfc-7805ba743549 found ready IMS
over logical WIFI access with USB uplink, VOWIFI voice mode and cellular
registration still active. The retained native log contains two
`SMS_IMS_CAPABILITY advertised=1` records: the IMS metadata parser observed
`+g.3gpp.smsip` in REGISTER. This advertises an SMS-over-IMS reception capability;
it does not prove submission or delivery of a specific SMS. See
[3GPP TS24.341 section5.3.2.2](https://www.etsi.org/deliver/etsi_ts/124300_124399/124341/11.02.00_60/ts_124341v110200p.pdf).

Our WebUI/REST and LAN SIP MESSAGE worker submit through the existing B03
`SEND_SMS` backend and read vendor modem/SIM storage. That API provides command
status but no measured bearer for an individual message. The audited worker
did not force SMS through the private IMS engine. At that audit, VoWiFi only applied to voice
admission/fallback; cellular SMS remained enabled. Do not equate LAN SIP MESSAGE
with the operator's SMS-over-IMS MESSAGE using application/vnd.3gpp.sms.

No IMS MESSAGE/delivery/report indications were present in the retained bounded
native metadata during this audit. This is not proof that earlier SMS used
cellular transport or that SMSoIP is unsupported. Per-message operator transport
in either direction remains unverified; proving it requires observing an actual
SMS transaction in the IMS path. No SMS was sent, marked read or deleted,
no radio/settings changed, and no message contents or phone numbers captured.
Receipt: `build/smsip-readonly-audit-20261011.json`.

## Using Linphone

In SERVER mode, register the existing single account on the modem's SIP server. Open a basic,
unencrypted chat addressed to `sip:<phone-number>@192.168.0.1:5080`, using the
actual configured modem address and SIP port. Send plain text; Unicode is
preserved. A national number is passed to the SIM unchanged; the gateway does
not guess a country code. Limits are 670 Unicode characters / 2680 UTF-8 bytes.
Long messages may consist of multiple charged cellular SMS segments.

Incoming messages from modem memory and SIM are polled every five seconds and
sent to the single registered client. Existing inbox messages are also delivered
once. Their SIP From identifies the SMS sender, including alphabetic sender IDs;
the SIP account name is not substituted. Messages stay in their original storage
and are not marked read or deleted by SIP delivery. Linphone displays its own
arrival time; the original SMS date remains available in the WebUI/REST API.

In TRUNK mode an incoming SMS goes to the configured incoming SIP user at the
configured PBX server. Outgoing MESSAGE is accepted only from existing trusted
PBX peers. The PBX must support MESSAGE routing. Our MikoPBX has persistent incoming routing
to 201 and authenticated outgoing routing through the trunk; the user confirmed
the ordinary PBX message test. Setup/Caller ID are documented in
[PBX README](../../outputs/mikopbx/README.md). Separately, on 2026-10-08 the configured
MikoPBX acknowledged incoming MESSAGE with IMS absent; its endpoint contacts
were unavailable, so final client display was not confirmed. The saved role
at that verification was TRUNK. A PBX SIP 2xx confirms acceptance by that peer,
not display or reading by the ultimate client.

DISABLED prevents SIP SMS processing; cellular receipt/storage and WebUI/REST
remain available. The SIP process starts before IMS and remains running in
cellular SMS fallback mode. In GSM/3G roaming, B03 receives SMS through its existing cellular/WMS
service; WebUI/REST and SIP delivery use the same modem/SIM storage. LTE or an
IMS bearer is not required for SIP registration or MESSAGE. Numeric SIP INVITE requires a ready voice backend: VoLTE or the installed GSM CS
adapter. Without either backend it gets 503 and never creates a SIM call.
SMS readiness remains independent of voice readiness.

The native controller queries actual EPS and circuit-switched registration. It
starts private IMS only after EPS registration (home or roaming). IMS timeout,
crash or LTE loss stops only the owned IMS engine and its queues, preserving
the SIP PID/client binding and SMS worker. The current voice registration policy attempts VoLTE for 60 seconds in AUTO,
then selects GSM CS; VoLTE retry is due after 15 minutes and starts only when idle.
Manual VOLTE/CS preferences are also available. See [REGISTRATION.md](REGISTRATION.md).
PCM remains 16000 Hz, 320 mono PCM16LE samples per 20 ms. Status reports the actual
voice backend; SMS-only is shown only when neither voice backend is ready.

Supported bodies: text/plain and CPIM containing text/plain. Typing indications
and read receipts are ignored with SIP 200 and never become SMS. Attachments,
group chat and encrypted LIME bodies are unsupported (415). Linphone's basic
chat uses SIP SIMPLE; see its [official API documentation](https://download.linphone.org/snapshots/docs/liblinphone/5.6/python/).

## Submission and delivery are separate

The current revision keeps the SIP MESSAGE transaction pending with `100 Trying`
while the asynchronous worker submits the SMS once through the mode-selected
backend: private IMS in VOWIFI, B03 SEND_SMS otherwise.
Only command completion (IMS +CMGS/OK after RP-ACK, or B03
`sms_cmd_status_result=3` in other modes) produces local `sent` and
final SIP **200 OK**, allowing Linphone to finish its sending status. The final
200 confirms modem submission, **not delivery to the recipient or reading**.
A timeout/error becomes `uncertain`, produces SIP **504**, and is never
resubmitted automatically. A restart while `sending` also becomes `uncertain`.
The old implementation returned 202 immediately on durable enqueue and did not
return successful cellular submission to the SIP sender.

Successful submissions generate no separate chat message. Their confirmation is
only the final SIP200 response to the original MESSAGE. Old completed SIP
transactions cannot change an existing Linphone history entry.

An uncertain result generates a service notice from `sip:MF79U@<modem>:<port>`
in a separate conversation. It explicitly refers to lack of confirmation by the
modem API and says that the recipient may still receive the SMS. It must never
impersonate the SMS recipient. This is a local diagnostic, not a remote reply or
an operator delivery receipt. The original implementation sent this notice from
the recipient's number; the installed revision fixes that attribution.

The authorized live Linphone test submitted exactly one SMS to the open contact;
the user confirmed receipt on the phone. B03 nevertheless reported command
status 2 and stored the outgoing item with tag 3. Stock B03 service.js treats
status 2 as failure and 3 as completion. The discrepancy remains unexplained;
do not reinterpret all status 2 results as success, silently retry, or treat the
local warning as proof of non-delivery. No second test SMS was sent.

## Implementation and bounds

- `src/sip-sms.h`: authenticated MESSAGE handler, private IPC and incoming SIP
  delivery with acknowledgement only after a SIP 2xx response.
- `control/sms_sip.go`: worker inside the existing native Go process. B03's
  existing administrator SHA256 verifier is read locally into RAM; no new saved
  plaintext password or external HTTP endpoint is introduced.
- `/mnt/userdata/mf79u/sms-sip.sock`: Unix socket 0600 in protected userdata.
- `/mnt/userdata/mf79u/sms-sip-state.json`: atomic durable queue, 0600. Up to 64
  logical outgoing jobs, 64 retained incoming copies and 300 acknowledged
  incoming/status IDs. Pending outgoing job text is
  cleared at terminal state; numbers and deduplication metadata remain private.
- Logical outgoing deduplication uses SIP Call-ID/CSeq plus payload validation.
  Retrying the same logical transaction is idempotent within retained history;
  an explicit new chat send is a new SMS and may be charged again.
- Incoming delivery retries after failure; the bounded acknowledgement history
  prevents routine duplicate delivery after reboot, but is not an unbounded
  exactly-once guarantee. SIM and modem IDs are namespaced separately.
- IPC framing: `MSM1`, one opcode/status byte, four-byte big-endian length; max
  payload 8192. Opcodes 1 enqueue, 2 next, 3 acknowledgement, 4 aggregate
  diagnostics. Diagnostics contain flags/counts only, no subscriber data.
- SIP logging is disabled. Passwords, phone numbers and SMS contents must not
  appear in general test reports or logs.

## Validation and recovery

`build-control.sh` runs Go fixtures and cross-compiles using Go 1.25.12 ARM
soft-float. `test-sip-sms.py` exercises the actual ARM SIP binary against an
isolated fake SMS socket: Unicode, CPIM, sender identity, Digest, registration,
logical duplicate/conflict, unsupported bodies, length limits and no DIAL.
Existing registrar fixtures and Go race tests also pass.

The original SMS-over-SIP installer `install-sms-sip.py --install` verifies backed-up/recorded installed binary
checksums and no active call, stops only the owned native supervisor, transfers
two whitelisted artifacts to userdata, atomically installs them and verifies
autonomous startup after software reboot. Settings/gateway.ini checksums are
unchanged. The older SD binary is excluded by control-internal-preferred.

Original binaries and checksums are in `build/pre-sms-sip-20261008/` on the Mac.
Its `--restore` targets that original installation and has not been live-tested.
Its checksum guards may reject newer fallback binaries; it is not a verified
rollback procedure for the current revision. Original installation evidence:
`build/sms-sip-verification.json`. Current fallback backups are listed below.

## Outgoing CS SMS verified on 2026-10-10

One authorized SIP MESSAGE was sent through the installed local B03 SMS worker
with GSM registered (CREG=1), EPS unregistered (CEREG=2) and IMS disabled.
SIP returned 202, the same durable queue job reached `sent`, and the user
confirmed receipt. No repeat submission was made. Destination and body were
matched only in RAM; the report contains neither. The completed body was erased
by the worker as intended. The test monitor was corrected to match retained
payload hash instead of the erased body.

Evidence: cs-sms-submit-live.json (historical local artifact: `build/cs-sms-submit-live.json`).
`test-cs-sms-submit.py` is an explicit one-message hardware test, not a fixture.
Do not run it again to reproduce a status display; a new run sends another SMS.

## Historical GSM fallback validation (2026-10-08)

`test-native-fallback.py` and `src/native-fallback-fixture.c` run only inside an
isolated container with fake CP/IMS/SIP, never on the modem. They test searching,
GSM roaming, IMS timeout/crash/recovery and LTE-to-GSM transitions while retaining
the SIP PID. Compile-time accelerated timers are fixture-only; that historical production revision used
15-second radio polling, a 300-second IMS attempt and 60-second retry.
Current registration timing and persistent voice runtime are documented in REGISTRATION.md.
`test-sip-sms.py` now runs the real ARM SIP binary without READY, verifies incoming
Unicode/SIP acknowledgement and rejects numeric voice INVITE without DIAL.

Read-only physical check (aggregate flags/counts only, no subscriber data):

```sh
python3 firmware/mf79u/verify-sms-fallback.py --observe-seconds 30
```

The intended roaming SIM registered with epic on GSM/EDGE: vendor
`simcard_roam=International`, CREG stat=5, CEREG stat=2, IMS absent. A real
reboot verified SIP/SMS startup from init before cellular registration. The
final active-call cleanup revision passed physical native selftest and a
30.3-second stable-PID observation; timeout/crash/LTE transitions are covered
by isolated fixtures, not a live multi-operator recovery test.

Aggregate inbox count rose from 5 to 6 and SIP acknowledgements from 5 to 7,
with pending incoming 1 to 0. Final diagnostics were incoming=7, delivered=8,
pendingIncoming=0, queued=0, vendorReady=true. Acknowledgements include retained
messages, so their count is not the count of new cellular arrivals. Cellular
storage receipt and PBX acceptance were verified; the user did not identify a
specific test SMS and final client display remains unconfirmed. No outgoing
SMS or calls were issued during fallback verification.

Report: gsm-sms-fallback-live.json (historical local artifact: `build/gsm-sms-fallback-live.json`).
Previous native/control binaries: `build/pre-gsm-sms-fallback-20261008/`.
Only userdata components are updated; full NAND0.9 and SD0.8 archives are
unchanged. Registered without IMS is now yellow; see [NETWORK-LED.md](NETWORK-LED.md).

## Submission-status fix (2026-10-11)

Private IPC opcode5 reads a job result without mutation: 0=sent, 5=queued/sending,
6=failed/uncertain, 2=unknown. SIP holds at most8 pending transactions and polls
once per second. The transaction layer owns retransmissions; durable Call-ID/CSeq
identity prevents resubmitting the same job even after a new transport transaction.
Pending responses finish with504 after20s if completion cannot be confirmed.
Reload/shutdown closes pending transactions with503 and releases owned references.
A later uncertain result still generates the separate warning; successful completion
generates no unsolicited message.

Validation: Go queue/status tests and the real ARM SIP binary under the isolated
Unix-socket fixture pass confirmed200, unconfirmed504, CPIM/plain Unicode,
authentication, duplicate suppression, conflict rejection and service notices.
The fixture makes no cellular SMS or calls. Build/fixture receipts:
`build/sms-submission-{control,sip}-build.log` and
`build/sms-submission-sip-fixture.json`.

Guarded userdata installer: `python3 firmware/mf79u/install-sms-submission-status.py`.
It checks idle calls/SMS, backs up only public binaries, installs Control/SIP with
checksummed compressed transfer and restarts the existing local services.
It checks unchanged settings and the pinned CS driver, plus IMS/SIP recovery.
The binary replacement itself does not reboot; no raw flash, codec or PCM change. Firmware sources and current
build artifacts include the fix; historical rootfs/SD archives remain outdated.
Live receipt: `build/sms-submission-status-install-20261011.json`.
A fresh Linphone outgoing SMS and its visible UI status need user verification;
the installer does not initiate a charged SMS.

Installer correction: the first attempt exhausted userdata while retaining the old
executable plus the expanded candidate and both compressed candidates. Checksums
prevented replacing the original; services restarted with the original hashes,
and the partial temporary files were removed. The final installer backs up both
public executables on the host, stops their mapped processes, and removes one
old executable before expansion. On failure it restores from the checked backup.
Compressed candidates are removed after each replacement. This is documented
as an installation failure, not a spontaneous modem reset.

Read-only live proof: `python3 firmware/mf79u/verify-sms-submission-status.py`.
It uses an ephemeral ADB Unix-socket forward, queries vendor readiness and retained
submission results, and saves only counters/status/PIDs. It never sends SMS or
prints message contents, phone numbers or transaction IDs. Receipt:
`build/sms-submission-status-live-20261011.json`.

The final binaries were installed on the same boot, and a read-only probe verified
one retained confirmed submission, zero queued/uncertain jobs, SMS vendor ready,
and one MF79U service notice acknowledged by the registered SIP client. This is
peer acceptance, not visual proof of the Linphone chat UI. VoWiFi REGISTER returned
operator500 after the service restart and remained unavailable during the180s
recovery gate. IMS had recovered by the immediate pre-reboot snapshot (`preRebootIMSReady=true`);
the deliberate normal software reboot verified autonomous startup. Do not claim
the reboot was necessary to recover IMS. It is not a spontaneous reset. The installation receipt
records pre/postboot state; the final live probe records SMS/SIP counters.

Final deliberate postboot validation passed: autonomous native/SIP readiness,
VoWiFi over USB, original settings hashes, installed Control/SIP hashes and CS
driver checksum. IMS registered at native elapsed41s and SIP ready46s; the full
host postboot gate took84.3s including USB reconnect. The final read-only SMS probe
checks the retained successful job and persisted notice acknowledgement again.
No fresh cellular SMS, call or Linphone UI capture was performed.

## Success notices removed (2026-10-11)

At the user request, `sent` jobs no longer enter the incoming SIP notice queue.
This also suppresses unacknowledged notices for retained successful jobs. Final
SIP200 after SEND_SMS completion remains unchanged. Failed/uncertain submission
warnings remain. Existing chat history is not deleted. Control-only update keeps
the native/SIP processes, binding, IMS and settings intact; no reboot or test SMS.
Go submission-result test checks that successful completion produces no notice.

Removal installed and verified on the physical modem. Native1697/SIP1749, IMS
readiness, local SIP binding and settings were preserved; Control alone restarted.
Receipt: `build/sms-success-notice-removal-install-20261011.json`. No reboot,
new SMS or calls. Successful retained submission still reads confirmed via IPC5.

## Telegram auto-delete coexistence (2026-10-11)

Current repository behavior: [Webhooks](../../docs/WEBHOOKS.md). Telegram and SIP
poll independently, so deleting the original after Telegram acceptance could
remove it before the SIP worker saw it. Before automatic deletion, Control now
saves a private incoming copy for a connected SERVER client/available TRUNK.
The existing IPC `next` serves that copy even after the original is gone; SIP
2xx ACK atomically records dedupe and removes the body. Copies survive a Control
restart or a subsequent peer disconnect. Disabled/disconnected peers create no
new copy. Full queues/persistence failures defer original deletion without
repeating confirmed Telegram delivery. Incoming sender/Unicode fields and the
SIP binary, registrar, IMS/CS media and outgoing SMS dispatcher are unchanged.

The persistent state read limit is now 600000 bytes, with separate 64-entry
outgoing and incoming bounds. IPC diagnostics expose `bufferedIncoming` and a
deduplicated `pendingIncoming` count, without private fields. Existing states
without an `Inbox` field remain compatible.

Delayed-poll/original-deletion, restart, ACK persistence rollback, body erasure,
queue bounds and peer availability fixtures pass. Control-only update is
installed with the same native/SIP PIDs and registered SERVER client; fresh
IMS/voice readiness and installed public artifacts match the receipt. No new
SIM SMS/call or reboot was issued by the agent. The user subsequently confirmed
a fresh incoming SMS reached both Telegram and the SIP client after the update.

> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# SMS over VoWiFi / USB IMS

Installed in userdata, 2026-10-11. One authorized REST SMS was accepted by the
operator over the actual USB VoWiFi tunnel in1.54s (SIP MESSAGE202 then RP-ACK
and +CMGS/OK). The user confirmed phone receipt and sent a reply. Native received
that reply through private IMS and Control saved it in the IMS inbox. This
replaces the former voice-only scope of VOWIFI mode. The physical SMS test used
USB internet; Wi-Fi uses the same dispatcher and IMS engine but was not the
uplink for this test.

In `voice_mode=VOWIFI`, WebUI, SMS REST and authenticated LAN SIP MESSAGE submit
through the owned private IMS engine. It uses the current ePDG/IMS tunnel over
Wi-Fi or USB internet. No B03 SEND_SMS, CMGS/ZMGS to cellular CP, automatic retry
or cellular SMS fallback is permitted in this mode. AUTO/VOLTE/CS preserve the
existing B03 submission path. IMS registration, transport and receipt on the
recipient phone are separate facts; REGISTER smsip alone is not a delivery test.

- `src/ims-sms-native.h`: private SOCK_SEQPACKET socket0600, exclusive AT port4,
  CMGF0 PDU mode, prompt/CMGS response correlation, timeout fence, counters.
- `control/sms_ims.go`: one SMS dispatcher shared by UI, REST and SIP. An outgoing
  durable journal precedes submission; a restart marks sending uncertain and
  does not replay it. Only all IMS +CMGS/OK results produce accepted/success.
- `control/sms_pdu.go`: GSM7 default/extension and Unicode encoding, concatenation
  without splitting an escape or UTF16 surrogate; text decoding/reassembly.
- Native incoming CMT/CDS PDUs are fsynced to a private bounded128-file spool
  before CNMA1 / RP-ACK. Failed persistence produces CNMA2 instead. IMS-local
  CSMS1 acknowledgement policy does not change cellular WMS configuration.
- Control imports incoming text into private `sms-ims-state.json`0600:128 messages,
  256 incomplete parts and512 dedupe hashes. IDs `ims-<hash>` do not collide with
  B03 numeric IDs. Read/delete operate on the original store; SIP receipt does
  not mark read/delete. The UI's Modem memory includes IMS messages.
- The incoming reassembled text bound is2680 UTF-8 bytes, matching the existing
  SIP body buffer; outgoing submission remains670 characters. The cellular
  compatibility path now also waits for B03 multipart completion before the
  shared Telegram/SIP forwarding stage: [incoming assembly](SMS-API.md#incoming-multipart-sms-2026-10-12).
- Unsupported binary/compressed/national-language PDUs stay in private
  `.unsupported` spool files; no misleading decoded text is delivered. These
  retained files count against the128-file bound. They are not silently erased.
- RP-ACK confirms SMSC acceptance, not delivery/read by the recipient. A partial
  multipart failure is uncertain; the accepted parts are never resubmitted.
- No IMS body, key, phone number, SMS text or administrator secret enters metadata
  logs or general verification receipts. PCM/codecs/CS driver are unchanged.

Private IPC: packet `MSI1` plus one opcode/status byte and optional payload.
Opcode1 reads aggregate readiness/counters; opcode2 submits one validated hex PDU.
Replies0 success,2 unavailable,3 busy,6 rejection,7 uncertain,8 invalid.
Readiness requires VOWIFI requested/effective, IMS registered, ePDG tunnel ready,
the owned B03 G_IMS_CMGF enum verified as PDU0 and no timeout fence. B03 does
not return an AP terminal response for its CMGF configuration command. Native
reads only the four-byte enum at0xcea14 in its own verified B03 child; no process
memory writes or subscriber data reads are used. The socket is root-only.

`test-sms-ims.sh` exercises native state/storage under ASan/UBSan and Linux Go
fixtures, including production Unix packet IPC. Existing UI/REST/SIP fixtures
also run. `install-sms-ims.py` backs up public Control/native binaries, stages
compressed userdata candidates, checks idle voice/SMS and preserves settings,
SIP/IMS media artifacts and the CS driver. No reboot or raw flash is needed.
Existing archive images remain historical; the userdata/source runtime is the
current delivery until the eventual consolidated package is rebuilt.

Protocol references:
[3GPP TS24.341](https://www.etsi.org/deliver/etsi_ts/124300_124399/124341/18.00.00_60/ts_124341v180000p.pdf),
[TS27.005 PDU commands/CNMA](https://www.etsi.org/deliver/etsi_ts/127000_127099/127005/18.00.00_60/ts_127005v180000p.pdf),
[TS23.040 TPDU/concatenation](https://www.etsi.org/deliver/etsi_ts/123000_123099/123040/18.00.00_60/ts_123040v180000p.pdf).

## VoWiFi-only voice with GSM SMS, 2026-10-12

The owner authorized cellular registration while keeping all calls on VoWiFi,
and a separate compatibility option. `voiceMode=VOWIFI_SMS`, shown as
**VoWiFi only + GSM SMS**, selects GSM2G profile13 and CFUN1, with both
VOICE_SUPPORT and OPEN_VOICE_FLAG0. The CS adapter remains suspended. Only
authenticated SWu IMS is admitted for calls; missing internet, tunnel loss,
IMS failure, or a legacy CS-only marker cannot enable CS/VoLTE fallback.
Cellular registration status is refreshed independently even while VoWiFi is
ready. `cellularSmsRadioReady` reports checked profile plus actual CREG1/5;
it does not promise receipt of an SMS. Ordinary mobile internet blocking remains.

This explicit option sends UI/REST/LAN SIP SMS through the existing B03 cellular
dispatcher once. It does not first try IMS or resend a failed/uncertain message.
Both existing cellular inboxes and the durable private IMS inbox remain readable;
incoming IMS messages are still retained if the operator delivers one. The
original `VOWIFI` option continues to submit through IMS only, without cellular
fallback. The new UI option is disabled until native advertises support.

Isolated ARM lifecycle checks cover CFUN4 to GSM registration with voice flags0,
simultaneous VoWiFi readiness, fresh cellular status, tunnel loss with cellular
registration retained, blocked outgoing/answer actions without ring-only, and
rejection of an unexpected CS incoming event. Go fixtures verify one cellular
SMS submission and no IMS submission in compatibility mode. These fixtures do
not issue real calls/SMS. All eight WebUI tabs passed1280/390/320px browser
checks, including selecting/saving this option and the GSM SMS description.

Installed native MD5 `49aebaf92185e49d8bbdc716e0c06939`, SIP
`bf43f7374bdc926c6fd7c23d6703e9b6`, Control
`92a9c4299b6f6d6489a14ca2e3ef7501`. The focused update preserved settings,
boot, the installed IMS media/private engine and all CS artifacts. SIP changes
only accept the new shared-INI mode; codecs/clock/PCM processing are unchanged.
The subsequent mode apply changed only VoiceMode and preserved native2147/
SIP2148. Fresh read-only CP queries returned CFUN1, CREG2,5, profile13 and
VOICE_SUPPORT/OPEN_VOICE_FLAG0. Five snapshots across60s confirmed simultaneous
GSM SMS registration and ready USB VoWiFi voice, with CS signaling/audio disabled
and the Linphone client registered. Ring-only remained disabled as requested.

The user confirmed new incoming SMS. SIP acknowledgement count14→16 and
Telegram delivery count3→5 confirm two new forwarding deliveries. These counts
do not prove two distinct logical SMS: the subsequently fixed cellular multipart
reader could forward evolving prefixes of one message. Private IMS
received0, no durable IMS receive event, and the three retained IMS incoming
messages/dates were unchanged: the forwarded snapshots arrived through GSM. No SMS
body, sender, message identifier or credential was emitted or added to receipts.
The modem's calendar date advanced from2000 to2026 after GSM registration,
without a manual time-setting command; GET-only Telegram bot/chat checks now
return HTTP200/OK with certificate validation enabled. Pending forwarding work0.
No real call, outgoing SMS or manual Telegram message was initiated. Hardware
voice/audio and outgoing GSM SMS were not re-tested. Receipts:
`reports/vowifi-gsm-sms-live-20261012.json`,
`reports/vowifi-gsm-sms-stability-20261012.json`,
`reports/vowifi-gsm-sms-incoming-route-20261012.json`. Temporary diagnostic tasks
and RAM executables were removed; `set-vowifi-sms-mode.py --apply` retains checked
private configuration backups and refuses a repeat against the selected mode.

## Roaming SIM incoming SMS diagnosis, 2026-10-12

The owner sent to the currently installed roaming SIM and expected delivery to
Telegram/Linphone. The sender reported sent without a delivery report. On the
same boot/native2130/SIP2131 after the VoWiFi repair, IMS/tunnel/voice and the
SERVER client remained ready, with ringOnly=false. Read-only native SMS opcode1
reported ready/configured/formatVerified=true, fenced=false, submitted0,
confirmed0, received0 and rejected0. The retained native log was only1699 bytes
and contained no IMS MESSAGE, CMT, durable receive, invalid PDU or storage error
event. No .pdu/.unsupported spool file or incomplete multipart was present.

The three private IMS incoming messages retained from earlier on2026-10-11 all
matched SIP delivery acknowledgements and Telegram's seen baseline; their
identifiers/sender/body were compared only in RAM. The read-only SIP diagnostics
reported vendorReady=true, incoming10, pendingIncoming0, bufferedIncoming0,
queued0 and delivered14. Telegram was configured/enabled, destination unchanged,
queue0 and delivered3. These aggregate historical counts do not prove arrival
of this newly sent SMS. An independent vendor-inbox read could not authenticate;
no raw reply/credential was printed or saved, and no inbox mutation was made.

Fresh exclusive-queue CP queries confirmed SIM PIN ready, CFUN4,
CREG/CGREG/CEREG state4 and short no-service SYSINFO. This is a fresh cellular
measurement, unlike the native status's cached values in the ready Wi-Fi branch.
The observed failure is absence of inbound private IMS delivery, with no queued
forwarding item. No operator SIP rejection was observed, and the exact upstream
SMSC/IP-SM-GW service/routing reason remains unconfirmed. Do not attribute it to
Linphone, ring-only, PDU decoding or Telegram deletion, or claim carrier SMS
support from successful voice/IMS registration alone.

Separately, the installed Telegram GET-only diagnostic resolved DNS but failed
certificate verification with `tls_invalid_certificate`. The device clock was
2000-01-01; a host-side public TLS leaf check observed validity2025-11-11 to
2026-12-13. Incorrect time is therefore a further Telegram delivery blocker,
independent of the missing inbound SMS. Time synchronization was not changed
during this diagnostic. No real SMS/call/manual Telegram message, reboot, radio
or settings change was initiated. Temporary metadata probes were removed from
RAM and the host task was removed. Safe receipts:
`reports/sms-delivery-path-20261012.json`,
`reports/sms-delivery-diagnosis-20261012.json`,
`reports/sms-delivery-network-20261012.json`.

## MegaFon-specific service check, 2026-10-12

The owner identified the current Russian roaming SIM as MegaFon. Its public
ePDG PLMN250/02 matches the already observed tunnel. A fresh root-Makefile
device-status check still reported VOWIFI, IMS/voice ready, native2130/SIP2131,
no active call and ring-only disabled. This verifies current registration,
not arrival of the missing SMS or operator SMS service provisioning.

The [official MegaFon VoWiFi FAQ](https://moscow.megafon.ru/help/faq/chto_takoe_vowi_fi.html)
was read in the browser on2026-10-12 after the text-fetch tool could not fetch
it. It says airplane-mode users must reconnect to the cellular network every
1.5 hours. It also limits its availability statement to supporting devices and
notes possible internet-provider blocking. The current FAQ describes voice;
it neither guarantees SMS over VoWiFi nor states a universal SMS prohibition.
The published cellular-refresh condition matters to a long-running CFUN4
gateway, but we have not reproduced a90-minute expiry or established that it
caused this missing message. Successful current ePDG/IMS registration does not
support blaming a blanket internet/geographic block for the present failure.

[Firsthand reports dated2025-12-29](https://4pda.to/forum/index.php?showtopic=954354&st=95660)
describe both SMS directions working on Xiaomi14/12, and failures on other
MegaFon setups; one poster also checked the SMS counter in the personal account.
These are individual user observations, not a carrier guarantee or a controlled
test of this SIM abroad without cellular registration. They prevent treating
older claims that MegaFon never supports SMS over VoWiFi as established fact.
Device, subscriber/region provisioning and roaming policy remain hypotheses.

[TS24.341 clauses5.3.2.2 and5.3.3.2](https://www.etsi.org/deliver/etsi_ts/124300_124399/124341/18.00.00_60/ts_124341v180000p.pdf)
distinguish the device's `+g.3gpp.smsip` advertisement from the operator's
IP-SM-GW/HSS availability and routing updates. A200 REGISTER alone does not
prove that the operator routes this subscriber's incoming SMS to that contact.
Our source's capability log only finds the tag in an outgoing REGISTER; it does
not confirm operator provisioning or precisely parse the accepted Contact.

Next useful checks are the current subscriber's incoming SMS-over-IP support
through VoWiFi while abroad with no cellular registration, and sanitized
REGISTER/accepted-Contact metadata. The access header is another compatibility
variable: source uses IEEE-802.3 for USB and IEEE-802.11 for client Wi-Fi.
Its effect on MegaFon SMS policy is unmeasured; the installed preserved IMS shim
also differs from the locally rebuilt candidate, so source alone is not proof
of its current on-wire headers. Do not fabricate a WLAN/cellular identity or
enable cellular fallback based on these hypotheses. The earlier incorrect-clock
Telegram TLS failure remains a separate local issue. No device changes, SMS,
calls, clock correction or cellular attachment were initiated by this research.

## Live evidence

Same boot77358efe-ab8b-4ca5-bcfc-7805ba743549 and original settings. Current
installation receipts `build/sms-ims-install-20261011.json` and
`build/sms-ims-native-update-20261011.json` preserve rollback binary snapshots.
The latter is a native-only update; Control remains available. Installer does
not send SMS/calls. Shared Mobile/framed-tab UI changes from the other task are
retained in the source and modem-served assets.

Single real SMS: `build/sms-ims-live-send-once-20261011.json` records only
HTTP/result/counter/PID metadata, no recipient or body. Native observed SMS
submission, IMS MESSAGE, SIP202/200 and IMS RP acknowledgement. Submitted1,
confirmed1, rejected0; native/SIP PID unchanged during send and IMS still ready.
The pre-update incoming snapshot also reported received1. No recipient or body
was copied into verification reports. The final journal contained2 accepted and2
received messages, no incomplete parts, sending or uncertain messages; these
aggregate totals include additional device activity, not extra sends by the
one-send test script.
A diagnostic-only JSON formatting bug displayed fenced=true even while the
actual guard was false (ready=true and submission was allowed). Corrected source
and fixture assert both flags. The fix is installed: native MD5
`dde984d74696e64c77069de1f27e6cf9`, ready/configured/formatVerified=true,
fenced=false after native-only restart. The original send receipt preserves the
old diagnostic value rather than rewriting historical evidence. Counters reset
on native restart; the durable inbox and outgoing journal remain intact.
`build/sms-ims-final-verification-20261011.json` records current readiness,
preserved settings/boot, served HTML/JS matching source and unchanged SIP,
IMS media shim and final CS driver. Control MD5
`2b2947fe8e7418d1c901d84137671ea7`. No additional SMS was initiated by the final
verification or installer. The latest native update briefly cleared the SIP
registrar's in-memory client binding. Linphone was reopened with its existing
account, and the modem confirmed localRegistered=true again without a new SMS
or call. The two retained incoming IMS message keys also match SIP delivery
acknowledgements; no outgoing SIP job remains queued/sending. Merely toggling
Linphone's Connected presence did not refresh REGISTER. Temporary read-only
probe executables were removed from RAM after verification.
Do not run the one-send script again: its existing receipt is an at-most-once
guard, including ambiguous results. No automatic duplicate SMS was initiated.

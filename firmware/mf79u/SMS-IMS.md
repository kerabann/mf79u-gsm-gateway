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

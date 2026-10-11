# Webhooks: Telegram SMS

Updated 2026-10-12. Source of truth: this Git repository. The Webhooks tab has
one framed **Telegram SMS** block and uses the existing common Save controls.

The2026-10-12 incoming-SMS diagnostic found an additional TLS blocker after the
CA repair: the device clock was2000-01-01, and the bound-interface GET-only probe
returned `tls_invalid_certificate` despite working DNS. The host-observed public
Telegram leaf validity starts2025-11-11. Correct time synchronization is required;
certificate validation must stay enabled. The new roaming-SIM SMS had not arrived
through private IMS and no Telegram job was queued, so this TLS fault alone does
not explain the absence of that incoming SMS. See the
[current SMS diagnosis](../firmware/mf79u/SMS-IMS.md#roaming-sim-incoming-sms-diagnosis-2026-10-12).

Later the same day, the authorized VOWIFI_SMS GSM-registration apply was followed
by a calendar date in2026. No manual clock command was issued. The bound-interface
GET-only diagnostic now returned HTTP200/OK for both bot and chat with strict
certificate validation. Telegram's delivered count increased3→5 and SIP
acknowledgements increased14→16 for new GSM inbox deliveries; no forwarding job
remained queued. These are forwarding counts, not proof of two distinct logical
SMS: the subsequently fixed multipart reader could export a growing prefix.
This supersedes the earlier clock blocker for this live state.
See [compatibility verification](../firmware/mf79u/SMS-IMS.md#vowifi-only-voice-with-gsm-sms-2026-10-12).

## Configuration and behavior

Incoming cellular multipart SMS is eligible for forwarding only after B03 marks
assembly complete. Partial content never enters Telegram's queue/seen baseline
or triggers Delete after send. SIP uses the same gate, and the full durable SIP
copy is still retained before Telegram's independent deletion. Missing parts
stay in modem memory; no timer exports a fragment. See
[incoming assembly](../firmware/mf79u/SMS-API.md#incoming-multipart-sms-2026-10-12).

- **Enabled** starts forwarding new incoming SMS independently of the SIP role.
- **BOT-token** is the BotFather token. A blank field retains the saved token;
  normal settings/status responses never contain it. Save clears the input.
- **Chat-id** accepts a numeric private/group/channel ID (including negative
  IDs) or an `@channel` username. The bot must have permission to send there.
- **Send through interface** selects USB/LAN `bridge0`, Wi-Fi Client
  `wlan0-vxd`, or an available ordinary mobile `wan*` interface. IMS `wan5` is
  excluded. The interface must have a working internet route and DNS. USB uses
  the existing USB internet settings; Wi-Fi requires Client mode. Mobile data
  must already be enabled for a mobile interface. Saving this block never
  changes routes, Wi-Fi mode, LTE policy, voice registration or SIP binding.
- **Delete after send to chat** defaults to off. When checked at delivery, the
  original SMS is deleted only after Telegram returns HTTP 200 with `ok:true`
  and any needed copy for a connected SIP peer is safely saved.
  A failed deletion retries deletion alone, including across a Control restart.
  Pending queue data is removed when processing finishes; delivery fingerprints
  do not contain the sender/text.

Every forwarded message is plain Unicode text with exactly this arrangement:

```text
sender number
message text
```

The implementation uses HTTPS JSON `sendMessage`, without `parse_mode`, and
disables link previews. Telegram's [official Bot API](https://core.telegram.org/bots/api#sendmessage)
defines the request fields and success response. HTTPS validates certificates
and the hostname using device system roots plus the embedded public Go Daddy G2
root from the [official CA repository](https://certs.godaddy.com/repository).
The stock B03 CA store lacks this root. The bundled certificate's DER SHA256 is
`45140b3247eb9cc8c5b4f0d7b53091f73292089e6e5a63e2749dd3aca9198eda`;
it is a self-signed CA, not the expiring Telegram server certificate. Only the
Telegram client uses this additional root; system and SIP/IMS trust stores are
unchanged. TLS 1.2 or newer is required; certificate/hostname checks remain on.
There is no proxy or redirect, and
both DNS sockets and HTTPS sockets use Linux `SO_BINDTODEVICE`. An unavailable
interface fails closed; the worker does not try another uplink or bypass the
ordinary LTE data firewall.

## Receive, queue and deletion

Control polls every five seconds and uses the shared `incomingSMS` normalization
for modem memory, SIM and the assembled private IMS inbox. B03 incoming read and
unread tags are 0/1; outgoing, drafts and invalid bodies are ignored. Sender
Unicode decoding and multipart IMS assembly retain their existing behavior.
Neither a browser login nor an enabled SIP gateway is needed for the worker.
No SMS submission/voice/PCM/IMS bearer path is changed.

On first setup, and when the chat ID changes, the current inbox becomes a
baseline; existing messages are not exported. While disabled, observed new
messages are skipped; previously queued jobs pause and resume with Enabled.
Changing chat discards the old destination's pending queue and establishes a new
baseline. Token/interface changes retain pending jobs. An already started HTTPS
request can complete using its captured settings.

`settings.json` and `sms-telegram-state.json` are private userdata files, mode
0600. The queue holds up to 128 messages. Each fingerprint includes storage,
original ID, sender, date and body, independent of read/unread tag. A full queue
does not mark additional SMS as processed, so later polls can pick them up while
they remain in the inbox. Unchanged polling does not rewrite flash state.
Queued bodies survive deletion from the inbox by a user. Receive/API failures
preserve the queue and never pretend the inbox is empty.

Delivery errors retain jobs; retry waits at least 15 seconds and respects
Telegram `retry_after` (capped at 24 hours). Telegram responses, HTTP error URLs,
token, SMS bodies and senders never enter service logs or webhook status. UI
status reports only availability, delivery counts, queue size and fixed errors.
Telegram has no idempotency key for `sendMessage`: a timeout after acceptance,
or power loss before saving the acknowledgement, can still cause a duplicate
on retry. Successful persisted acknowledgements are not resent.

For deletion, the persisted job first records Telegram acceptance, then checks
the complete incoming fingerprint is still present. A reused vendor SMS ID
cannot authorize deletion of a different body. IMS IDs go to the existing
private inbox deletion path; cellular IDs go to the existing B03 DELETE_SMS
path. SMS deleted independently is treated as already removed. Existing SIP
inbox delivery can observe the same SMS independently; Telegram deletion also
removes it from subsequent UI/REST/SIP inbox listings.

Before automatic deletion, Control saves a separate private SIP copy if an
active SERVER client is registered, or the configured TRUNK is available
(registered when registration is enabled; a running static trunk otherwise).
Already SIP-acknowledged SMS needs no copy. The copy uses the same fingerprint,
sender and Unicode body, and is served through the existing SIP MESSAGE IPC
even after the original disappears. It survives Control restart/disconnection
and is removed only with the persisted SIP 2xx acknowledgement. No voice/IMS
readiness is required for SIP SMS. Original SMS deletion can finish while this
independent delivery is pending; Telegram is not resent to wait for SIP.

The private SIP copy queue is limited to 64 messages. Failure to save/full queue
defers deletion of the original and retries without resending Telegram. A
disconnected/Disabled peer creates no new copy or deletion dependency. With the
checkbox off, normal SIP polling continues to use the retained original inbox.

## Validation and delivery evidence

Initial implementation/install checks on 2026-10-11 (before owner configuration):

| Layer | Result |
| --- | --- |
| Isolated `make test` | PASS native/SIP/Go/JS/workflow fixtures; no device access |
| Final `make test-go` | PASS Linux Go fixtures, including real loopback interface binding/TLS and full-queue deletion drain |
| Browser fixture | PASS all eight tabs at 1280/390/320px (24 views), no overflow or JS errors; Webhooks scoped Save, token clearing and deletion flag passed |
| ARM Control and full overlay | PASS `make build-control`, `make package package-check`; all 28 payload files/checksums and PCM contract verified |
| Repository audit | PASS syntax, migration coverage, publication/secret checks and Markdown links |
| Installed physical Control | PASS guarded Control-only update; installed executable and all five embedded assets match source |
| Physical runtime preservation | PASS same boot, native3483/SIP3484, settings/gateway hashes, ring-only guard and IMS/voice readiness; no modem reboot/calls/SMS |
| Real Telegram forwarding/deletion | Not tested: BOT-token/chat-id are unconfigured; forwarding remains disabled |

The initial installed Control MD5 was `c84d03dfac22088a48187ea6717b035d`, SHA256 `a2c857d9d1def0841ae1163b1ef49db3f2c1f9a6df0d4759aa54d1d7bfa81dcf`.
The full-overlay read-only install plan refused a different pinned CS driver;
it would require an explicitly scoped checked reboot. Only Control was updated,
with a separate read-only Control staging-space preflight. The installed CS
runtime and IMS/SIP media were preserved. The full package was built/checked,
but **was not installed** over the pinned driver.

Sanitized local receipts (generated/ignored):
`reports/telegram-test.log`, `reports/telegram-test-go-final.log`,
`reports/webhooks-ui/result.json`, `reports/webhooks-ui/webhooks-{1280,390,320}.png`,
`reports/telegram-package.log`, `reports/telegram-audit-final.log`,
`reports/telegram-device-before.json`, `reports/telegram-device-after.json`,
`reports/telegram-control-install.log`, and
`firmware/mf79u/build/control-update-install.json`.
No bot credentials or real Telegram/SIM messages were used by fixtures.
The owner subsequently configured the real bot/chat in the UI; the live delivery
check and repair below supersede the initial unconfigured boundary.

## Physical Telegram TLS repair, 2026-10-11

The owner's incoming SMS was queued but not forwarded: enabled/configured,
USB `bridge0` up with internet route and DNS, queue one unsent job. The installed
read-only probe resolved Telegram successfully but returned `tls_untrusted_root`
for `getMe`. The old device system-root file existed but did not trust Telegram's
Go Daddy G2 chain. An official public root is now embedded as described above.
TLS errors also have a fixed, specific status message without private URLs.

After a guarded Control-only install, the normal worker automatically retried
the existing job. Persistent delivery count changed 0→1, queue 1→0 with no
pending deletion, and private IMS incoming count changed 4→3 with
**Delete after send to chat** enabled. No new SIM SMS or manual Telegram
`sendMessage` probe was submitted. Bound-interface read-only `getMe` and
`getChat` both returned HTTP 200 / `ok:true`; this verifies API acceptance,
not that a recipient has read the message.

The TLS-only Control revision MD5 was `5c1cebe02c20e33711d4ff8f8b137af6`, SHA256
`5214debca8abab711c1c4fe5ae0aa06757aebd3f6d2c9316ba50b1c556821d1a`.
Same boot/native3483/SIP3484, settings/gateway hashes and ring-only guard were
preserved, and the executable/all embedded assets matched the checked source.
No modem reboot or call occurred. IMS/voice readiness was already false in the
fresh preflight and remained false afterward; consequently the strict aggregate
post-install verifier reports this readiness boundary despite all preservation
and artifact checks passing. This webhook repair does not claim current voice
readiness or modify/restart native/SIP to restore it.
Readiness subsequently recovered on the same boot/PIDs before the SIP-copy
update below; no recovery action/reboot was issued.

The additional Go fixtures verify the exact public root fingerprint, strict TLS
configuration, error privacy and GET-only diagnostic response allowlisting.
Sanitized local receipts: `reports/telegram-tls-failure.json`,
`reports/telegram-ca-delivery.json`, `reports/telegram-ca-device-{before,after}.json`,
`reports/telegram-ca-control-install.log`, `reports/telegram-ca-test-go.log`.
Credentials, sender and message bodies were kept only in process memory/device
private storage; they are not included in reports or Git.

## Telegram plus connected SIP delivery, 2026-10-11

The user confirmed Telegram receipt but reported missing SIP receipt. Independent
pollers allowed the successful Telegram worker to delete a new SMS before SIP's
five-second inbox refresh. The durable handoff above removes that race without
restarting SIP or changing its MESSAGE protocol/media.

Fixtures pass delayed SIP polling after original deletion, Unicode/sender
preservation, Control restart, duplicate retention/ACK suppression, failure to
save the copy, bounded queue backpressure, disconnected/Disabled peers and body
removal from disk after ACK. Confirmed Telegram jobs are never resent during a
SIP-copy/deletion retry. The existing ARM SIP MESSAGE fixture still checks the
real gateway's Unicode delivery/2xx ACK behavior.

The combined TLS/SIP-copy Control is installed: MD5
`a60db0a1511c4e3673ce90218366efb6`, SHA256
`214b10d4a6c15e999504fc7f0303e64a8791df0bdfd853c575d1e607d6c435b0`.
Fresh post-install checks passed: unchanged boot/native3483/SIP3484,
settings/gateway hashes/guards, IMS/voice ready, SERVER client registered, and
installed binary/all embedded assets matching source. Control alone restarted;
there was no modem reboot, SIP reload or new SIM SMS/call submitted by this work.
The user subsequently confirmed that a fresh incoming SMS arrived in both
Telegram and the SIP client after this update. This adds physical recipient
confirmation to the fixture/install evidence; the agent submitted no SIM SMS.

Sanitized receipts: `reports/telegram-sip-baseline.json`,
`reports/telegram-sip-after.json`, `reports/telegram-sip-device-{before,after}.json`,
`reports/telegram-sip-control-install.log` and `reports/telegram-sip-test-go.log`.
The follow-up metadata-only receipt is `reports/telegram-sip-confirmed.json`.
It records Telegram delivered 2→3 and SIP acknowledgements 13→14, with both
private delivery queues empty, the client registered and deletion still enabled.
The Telegram delivery count had reached two through independent user/device
activity before this update; this is not a second agent-originated test message.
Final `make test`, `make package package-check` and `make audit` passed for the
combined revision: ARM/Go/JS/native/workflow fixtures, complete 28-file overlay,
unchanged PCM contract, publication/secret scan and Markdown links. Logs:
`reports/telegram-sip-test.log`, `reports/telegram-sip-package.log` and
`reports/telegram-sip-audit.log`. No frontend behavior changed in this repair;
the installed assets still match the eight-tab browser-checked source.

Commands run from the repository root through Make:

```sh
make test
make build-control
make package package-check
make audit
```

The Go fixtures cover scoped auth/CSRF/token masking, private persistence,
incoming filtering, Unicode payload formatting, baseline/disable/new-chat
behavior, queue capacity, failed writes, restart dedupe, TLS rejection, rate
limits and confirmed-delivery deletion/retry/reused-ID protection. Linux fixtures
exercise actual bound-loopback TLS and missing-interface refusal. Frontend
fixtures cover the eighth tab, token clearing, interface choices, the deletion
checkbox and scoped Save with other drafts retained.

Browser QA is reproducible with an installed Playwright package and Chromium:
`make task TASK=test-webhooks-browser.py` (`NODE_PATH` selects the package;
`MF79U_BROWSER_EXECUTABLE` can select an existing Chromium executable).
The fixture never connects to a modem, PBX, Telegram or SIM.
`make task TASK=verify-webhooks-device.py` saves a read-only pre-install receipt
and checks Control staging space. After the guarded Control-only updater,
`make task TASK=verify-webhooks-device.py ARGS=--after` compares the same boot,
voice owners, protected settings and installed public assets. Pass `ADB` and
`SERIAL` explicitly for the connected device. This verifier creates no login,
call, SMS, Telegram request, deletion or configuration change.

For troubleshooting, use `make task TASK=diagnose-telegram.py` to read only
allowlisted settings/queue/interface metadata. Add
`ARGS='--installed-network --report-prefix telegram-check'` to invoke the
installed Control's `-native -telegram-diagnose` mode: bound DNS, TLS, `getMe`
and `getChat`, without `sendMessage`, settings changes, service startup or queue
mutations. It does not require temporary binary staging. Private API responses
and token-bearing error URLs are omitted; only fixed error categories and
numeric status/error codes appear. The report prefix preserves earlier receipts.

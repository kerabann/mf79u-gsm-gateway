# Webhooks: Telegram SMS

Updated 2026-10-11. Source of truth: this Git repository. The Webhooks tab has
one framed **Telegram SMS** block and uses the existing common Save controls.

## Configuration and behavior

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
  original SMS is deleted only after Telegram returns HTTP 200 with `ok:true`.
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
and the hostname using device system roots. There is no proxy or redirect, and
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

## Validation and delivery evidence

Completed on 2026-10-11:

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

The installed Control MD5 is `c84d03dfac22088a48187ea6717b035d`, SHA256 `a2c857d9d1def0841ae1163b1ef49db3f2c1f9a6df0d4759aa54d1d7bfa81dcf`.
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
Authenticated live webhook configuration and end-to-end Telegram delivery are
separate remaining checks after the owner supplies credentials through the UI.

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

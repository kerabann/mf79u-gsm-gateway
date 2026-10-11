> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# SMS REST API

Audited 2026-10-08; [STATUS.md](STATUS.md) links all related work. GSM/3G receipt
and SIP delivery without IMS are described in [SMS-SIP.md](SMS-SIP.md).

The API runs on the modem alongside the WebUI. Base URL normally
`http://192.168.0.1`. No Mac relay, PBX or external SMS service is required.

## Authentication

For automation, send `Authorization: Basic <base64(admin:password)>` on each
SMS REST request. The username is `admin`, password is the modem administrator
password. No cookie, Origin or CSRF header is needed with explicit header
authentication. The modem validates the password through the B03 SHA256
challenge on every request. This header only authenticates `/api/v1/sms/messages`
and its DELETE resource paths, not other management endpoints.

`curl -u admin` prompts for the password without putting it in command arguments.
Do not send a `WWW-Authenticate` challenge; the API does not prompt browsers or
establish an implicit Basic browser session. Basic encodes rather than encrypts
credentials; use it over the trusted management LAN.

Alternatively, browser/session clients can use:

1. `POST /api/login`, JSON `{"password":"<modem administrator password>"}`.
   Send `Content-Type: application/json` and `Origin: http://192.168.0.1`.
2. Keep the returned `mf79u_session` cookie and JSON `csrf` value in memory.
3. Send the cookie on every request. For POST/DELETE send the same Origin,
   `X-CSRF-Token: <csrf>` and JSON Content-Type when there is a body.
4. Sessions expire after 30 minutes without activity. Authenticated management
   GETs renew both RAM expiry and the HttpOnly cookie Max-Age. `GET /api/session`
   returns the CSRF value of an existing session. `POST /api/logout` closes it.

The short ZTE backend session is renewed automatically in memory. It is separate
from the management session. The API does not write administrator passwords or
cookies to flash. Normal settings/status endpoints omit SIP/Wi-Fi passwords.
The admin UI has a separate CSRF-protected credential endpoint for editing them.

## Resources

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/v1/sms/messages?storage=modem` | No body; default storage is modem | `{ "storage": "modem", "messages": [...], "capacity": {...} }` |
| GET | `/api/v1/sms/messages?storage=sim` | No body | Same shape, SIM memory |
| POST | `/api/v1/sms/messages` | `{ "number": "+123456789", "text": "Hello" }` | `{ "ok": true }` after vendor completion |
| DELETE | `/api/v1/sms/messages/17` | No body | `{ "ok": true }` |
| DELETE | `/api/v1/sms/messages` | `{ "ids": ["17", "18"] }` | `{ "ok": true }` |

Reads list messages without marking them read. `messages` retains B03 metadata
(`id`, `tag`, etc.), with UTF-16 content decoded into `text`.
`number` is decoded from UTF-16BE when necessary; ordinary/local numbers and short
codes are preserved without guessing a country code. `date` is ISO 8601/RFC3339
with the SMS timezone (quarter-hour ZTE offsets converted to hours/minutes).
Unknown/invalid dates are `null`. Original values remain in `rawNumber`/`rawDate`.
`direction` is `incoming` for tags 0/1, `outgoing` for tags 2/3, `draft` for tag 4,
and `unknown` otherwise. These meanings are verified against the B03 conversation
renderer (`smsOtherTmpl` / `smsMeTmpl` / draft branch). Tag 1 denotes a new incoming
message; tag 0 is incoming too. An outgoing direction does not prove delivery.
Legacy `/api/sms` keeps its raw number/date contract for the existing WebUI.

Example message (fictional):

```json
{
  "id": "17",
  "number": "+123456789",
  "date": "2026-10-07T18:04:05+03:00",
  "direction": "incoming",
  "tag": "0",
  "text": "Hello",
  "rawNumber": "002B003100320033003400350036003700380039",
  "rawDate": "26,10,07,18,04,05,+12"
}
```

Empty storage returns `messages: []`. Invalid/missing vendor lists are errors,
never silently presented as an empty inbox. Both memories are paginated internally.
Use the IDs from the chosen list for deletion. Up to 100 IDs per delete.

Sending supports Unicode, 1–670 characters. Multipart SMS can incur several SMS
charges. The vendor send confirmation means local submission completed; it does
not guarantee delivery to the recipient. Sending/deletion poll vendor completion
for up to 10 seconds; no automatic mutation retry is performed. If completion is
uncertain, inspect the list/status before retrying. The backend does not expose a
new message ID in this response.

Errors are JSON `{ "error": "..." }`: 400 invalid request, 401 management login
required, 403 Origin/CSRF rejected, 405 unsupported method, 428 vendor re-login
failed, 502 modem operation/response failure. Legacy `/api/sms` and
`/api/sms/action` remain compatible with existing clients and WebUI.

## Incoming multipart SMS, 2026-10-12

B03 assembles cellular SMS segments in its own inbox. While receiving, the same
row may expose only a prefix and later grow to the full text. Its stock frontend
filters `received_all_concat_sms=0` and prefers the longest snapshot of a repeated
inbox ID. The shared Telegram/SIP reader now applies that completion policy:
an explicit incomplete flag, outstanding parts, malformed or contradictory
concat metadata holds the row. Missing optional metadata retains legacy ordinary
SMS behavior. `received_all_concat_sms=1` with consistent available counters, or
complete counters when the flag is omitted, permits forwarding. The field names
also appear in the [MF79U client reference](https://github.com/sebenik/zte-sms).

No arbitrary delay is added to single SMS. Polling discovers the full message
after B03 completes assembly; incomplete rows remain in modem memory without
being marked seen, queued for Telegram/SIP, or automatically deleted. Missing
segments do not cause a timed partial export. Repeated same-ID rows select the
longest complete text; contradictory same-ID bodies/senders are held instead of
guessing. Separate IDs are not combined by sender/time. The existing durable
forwarding queues and receipt deduplication apply only after completion. Raw
WebUI/REST inbox reads retain the original concat metadata and incomplete rows
for administration; manual read/delete behavior is unchanged.

Incoming text is bounded by the existing SIP receiver limit of 2680 UTF-8 bytes
(up to 2680 ASCII or 1340 Cyrillic characters). This replaces the inappropriate
outgoing 670-character check on incoming delivery, without increasing the SIP
wire buffer. Outgoing UI/REST/SIP submission remains 1–670 characters. Larger
incoming bodies remain in the modem inbox and are not truncated or exported.

`mf79u-control -native -sms-receive-diagnose` performs read-only local vendor
queries and reports only storage counts and concat flag/counter patterns. It
does not expose IDs, senders, text, dates or credentials, nor submit/delete SMS.
Isolated fixtures cover delayed snapshots, restart while incomplete, one full
Telegram/SIP delivery, deletion after confirmation, duplicate/conflicting rows,
legacy fields, Unicode and the existing wire bound. Live installation/metadata
evidence is in `reports/sms-multipart-live-20261012.json`: installed Control MD5
`2322c6d06d8233607ab5f9859be0ff7b`, seven complete B03 incoming rows, including
four with two of two segments received, and unchanged native2147/SIP2148 with
ready VOWIFI_SMS/IMS/local SIP registration. This confirms the device fields and
installed runtime, not reception of a new delayed multipart SMS after the update.
No real SMS/call or manual deletion was issued during verification.

Use the maintained read-only check through the root Makefile:

```sh
make task TASK=verify-sms-multipart.py SERIAL=... ADB=/path/to/adb
```

The focused Control updater's `--require-sms-idle` option refuses replacement
while Telegram or SIP has unfinished forwarding/submission work. It was used
for this receive-policy installation; see [installation](../../docs/INSTALL.md).

## CLI client

`sms-api.py` uses Python's standard library, prompts for the administrator
password, and keeps credentials/cookies only in process memory:

```sh
python3 firmware/mf79u/sms-api.py list --storage modem
python3 firmware/mf79u/sms-api.py list --storage sim
python3 firmware/mf79u/sms-api.py send +123456789 --text 'Hello'
python3 firmware/mf79u/sms-api.py delete 17 18
```

Omit `--text` to read the SMS body from stdin. Automation can use
`--password-stdin`: the first input line is the password, remaining input is the
message body when sending. Never put passwords in command-line arguments.
`--url` selects another modem address. List output contains private message data;
route it to the intended consumer rather than general diagnostic logs.

Validation: fixture tests cover Basic password validation, wrong-password rejection,
credential endpoint isolation, Unicode sending, storage reads, single/bulk
removal, authentication, CSRF, malformed requests and vendor completion. Live
verification performs read-only lists/negative validation, without sending,
deleting or marking any real SMS read.

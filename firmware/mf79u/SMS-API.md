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

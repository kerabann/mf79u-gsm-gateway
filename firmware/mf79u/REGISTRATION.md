> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

## WCDMA removed (2026-10-11)

WCDMA development was cancelled at the user's request. The current WebUI,
settings/INI validation and native controller accept AUTO, VOLTE, VOWIFI and CS.
AUTO prefers the selected available VoWiFi source, then LTE/IMS and GSM CS;
no WCDMA registration attempt is made.
The separate cyan WCDMA LED policy was removed. Every active call remains green.
The improved CS driver, adapter and PCM bridge are retained byte-for-byte;
external PCM stays mono PCM16LE16000/320. IMS audio processing is unchanged.
Historical WCDMA tests below are retained as evidence, not current support or a roadmap.

Verified on the physical modem after the removal: AUTO/VOLTE, IMS ready,
no active call, WebUI offers AUTO/VOLTE/CS only, idle LED blue (mask4).
Runtime installation preserved the boot and did not replace any CS binary.
Controller fallback fixture, SIP incoming/reload fixture, CS policy selftest,
Control tests and LED policy selftest passed. No real call or SMS was issued.
Receipts: `build/wcdma-removal-verification.json`,
`build/registration-runtime-install-without-wcdma.json`,
`build/registration-fallback-fixture.json`, `build/led-gsm-lte-install.json`.
Full NAND/rootfs and SD archives were not rebuilt or flashed.

# Voice registration and automatic CS fallback

Updated: 2026-10-10. The persistent driver, adapter, native registration controller
and WebUI are installed in userdata. An outgoing production SIP→GSM call had
tone/echo and automatic remote clearing at20s, confirmed by the user; MM/audio
returned to reusable idle without reboot. Incoming CS→SIP/PBX tone, speech echo
and prompt clearing are also user-confirmed. Physical AUTO failed-IMS→CS passed
twice, including after a fresh software boot. This is distinct from the preceding
MO40 diagnostic. The CS-only emphasis comparison produced clearer echo; no IMS
audio processing was changed. CS heartbeat underflow during DSP startup and
deferred incoming media startup are fixed in the final pinned driver. Incoming
tone/echo/clearing passed and AUTO/IMS standalone startup was verified again
after its final software reboot.
See [CS-AUDIO.md](CS-AUDIO.md) for revision-specific sound/clearing evidence.
Current receipts and remaining limits are listed below.

Saved `voiceMode` / `voice_mode` selects:

- `AUTO`: prefer the selected available VoWiFi internet source, then attempt
  LTE/VoLTE; after a 60-second LTE/IMS registration deadline select GSM
  CS. The deadline starts after the synchronous IMS/PDP setup attempt returns;
  setup, cleanup and radio registration add time. The two physical failure tests
  reached CS ready after122.8s and111.2s from selecting AUTO. Retry VoLTE when
  the 15-minute retry deadline is due and the gateway is idle.
- `VOLTE`: LTE/VoLTE only; registration failure leaves SMS and LAN SIP available.
- `VOWIFI`: IMS through the selected Wi-Fi Client or USB internet source only;
  never fall back to cellular voice. See [VOWIFI.md](VOWIFI.md).
- `CS`: GSM/2G CS only. UMTS/3G CS has not been implemented or validated.

The Mobile tab contains Registration preference and current voice mode/phase,
followed by LTE data / mobile internet and VoWiFi internet source. The status API
reports the requested preference, effective preference, radio registration
mode, registration phase, fallback reason and remaining retry time. A conversation
retains its backend until actual MM and audio cleanup. Applying settings is blocked
while either SIP or the native controller owns a call.

The B03 radio transition checks CFUN, profile and both voice flags. GSM uses
profile 13 and flags 1/1; VoLTE uses profile 27 and flags 0/0. Switching temporarily
re-registers the radio. Existing USB/Wi-Fi management and SIP service stay running.

`mf79u_cs_voice.ko` starts suspended. The adapter creates a fresh session epoch,
heartbeats its lease and sends commands with monotonically increasing call IDs.
Incoming SETUP produces CALL CONFIRMED and ALERTING; CONNECT requires SIP ANSWER.
The streaming PCM process has no diagnostic conversation deadline and preserves
the external mono PCM16LE, 16000 Hz, 320 samples / 20 ms contract. The driver waits
for real MM release and checked DSP/register restoration before reusing the call
state. Stale commands cannot act on a subsequent conversation.

Sources: `src/cs-call-state.h`, `src/cs-caller.h`, `src/cs-voice-driver.c`,
`src/cs-driver-runtime.inc`, `src/cs-voice-adapter.c`,
`src/voice-registration-policy.h`, `src/native-gateway.c`, `control/`.
Build: `build-cs-voice.py`, `build-native-cp.sh` and the production runtime build.
No raw flash or rootfs installation is involved.

## Verification on 2026-10-10

- `build/registration-fallback-fixture.json`: actual ARM native controller with
  isolated CP/IMS/CS fixtures; timeout/crash fallback, active-call preference
  pinning, idle promotion, stale call events and no DIAL replay. Failing network
  status queries retain the registration deadline. This is not RF evidence.
- `build/sip-registration-config-fixture.json`, updated registrar and SMS tests:
  shared `voice_mode` accepted on startup/reload; invalid modes rejected.
  The first incoming trial was rejected with SIP603 while its intended test
  route failed to reload because that field was previously unknown to SIP.
- `build/sip-cellular-persistent-cs-1.json`: production outgoing tone/echo,
  user-confirmed automatic hangup at20s; boot and runtime PIDs stayed unchanged.
- `build/persistent-cs-incoming-live.json`: incoming SETUP→SIP INVITE→PBX ANSWER→
  CS CONNECT, Opus tone/echo and prompt handset clearing, confirmed by the user.
  The temporary PBX route and echo extension were restored/removed. The oversized
  offer included PJPROJECT2.17 default RTT; voice calls now explicitly offer only
  one audio stream. A synthetic32-digit caller and all five enabled codecs fit
  within1345bytes instead of1553bytes, avoiding dependence on UDP fragmentation.
  `build/sip-incoming-transport-fixture.jsonl` is isolated transport evidence.
- `build/registration-fallback-live.json` and
  `registration-fallback-postboot-live.json`: physical LTE registration with
  failed IMS registration caused GSM CS readiness without changing boot or
  native/SIP/adapter PIDs. The owned temporary IMS rejection rule was removed.
- `build/registration-autoboot-live.json`: fresh boot251bf0c0…, AUTO/IMS ready,
  Control/native ancestry rooted in init, checked module loaded suspended and
  fresh CS adapter session. IMS registered29s and SIP ready32s after controller
  startup; Mac relay absent. Installed artifacts matched local build digests.
- `build/cs-clarity-call-lease-fixed-1.json`:25-second outgoing call on the
  first lease-fixed revision,1253PCM frames without clipping; the user confirmed
  echo until the end and normal automatic clearing.
- `build/persistent-cs-incoming-mt-audio-pending.json`: final-driver incoming
  tone/echo/normal automatic clearing confirmed by the user, unchanged boot and
  restored idle. PBX timeout configured45s; observed kernel CONNECT ACK→idle
  interval23.607s. This is not a45-second media endurance result.
- `build/registration-autoboot-final-20261010.json`: final fresh bootd034ef41…,
  AUTO/IMS ready, Control/native rooted in init, final checked module suspended,
  no Mac relay. IMS registered26s and SIP ready29s after native startup.
  `build/cs-audio-final-verification.json` additionally checks the unchanged IMS
  binary/library and shared resampler baseline, idle state and absent test markers.
- `build/cs-sms-submit-live.json`: exactly one CS SMS, IMS off, CREG1/CEREG2,
  queue `sent` and recipient-confirmed receipt. No automatic resend.
- `build/registration-ui-desktop.jpg` and `registration-ui-mobile.jpg`: browser
  fixture at837px and390px, selector/save/status tested with no horizontal
  overflow. This is layout evidence, not an authenticated physical UI save.

`install-registration-runtime.py` backs up checked userdata binaries on the Mac,
stops only owned idle services and installs the runtime with a driver digest
manifest. A pinned, already-loaded driver must match its recorded boot digest;
a new driver revision requires reboot. Older rootfs/SD archives remain historical.

## Audio boundary and unchanged IMS path

The working CS hardware route is narrowband PCM8000Hz/160samples; its separate
bridge converts to the unchanged PCM16000Hz/320samples contract. The SIP codec
may still be Opus/G.722/G.711/G.729 according to the configured offer and peer.
A wideband SIP codec cannot recreate frequencies missing from CS PCM. The actual
GSM speech codec/rate and contribution of DSP filters have not yet been measured.

The user reported muffled incoming CS echo. The shared FIR preserves300–3000Hz
within0.03dB and passes the existing C resampler test; it was not edited. The IMS
private executable and audio library match their checked pre-investigation hashes.
IMS gain, AMR-NB/WB conversion, high-rate CMR and global SIP codec order remain
unchanged. Any CS quality correction must be isolated to CS. Evidence and current
comparison: [audio-quality.md](../../outputs/mikopbx/audio-quality.md). The Status
voice profile now distinguishes GSM8k PCM from the IMS AMR-WB capability.

No UMTS CS or GSM wideband audio is claimed. End-to-end testing so far uses the
ordinary lab SIM and MikoPBX/USB path; other operators and long-duration endurance
have not been validated. The older rootfs/SD bundles do not contain this update.


### WCDMA validation limit, 2026-10-10

WCDMA registration/SMS are confirmed, but `voiceReady` currently denotes the
local adapter being available, not proof of a completed network WCDMA call.
Explicit narrowband codec negotiation still receives network rejection before
CONNECT ACK. A same-SIM GSM control call works with tone/echo/clearing.
See [UMTS.md](UMTS.md#explicit-codec-offer-physical-failure-and-gsm-control)
for current driver checksums and sanitized receipts.

> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

## UI audit compatibility correction, 2026-10-11

Fresh CS selection registered in GSM but stayed at `starting_cs`. The preserved
production driver remained suspended without a fault; an owned adapter restart
did not restore readiness. The native controller had begun sending an explicit
RAT suffix in RESUME, which the legacy installed driver rejects. Returning to
the original three-field RESUME restores GSM readiness and is also accepted by
the current source driver, whose default is GSM.

Native-only update MD5 `fa5969f94697c7ec141b58b25898a69e` produced
`cs_media_ready` after two seconds. Adapter, PCM bridge, driver MD5
`b3440aadf8e7be2e2321d13e539ba078`, SIP and IMS media binaries were preserved;
no reboot, unload, audio gain/CMR/FIR or external PCM change. Native lifecycle
fixtures reject a fourth field on the simulated legacy driver; the actual
adapter loop checks both legacy and extended parsing. This is fresh idle
readiness evidence, not a new CS conversation/audio test. See
[the audit matrix](../../docs/UI-E2E-20261011.md) for remaining coordinated calls.

# CS sound and call-startup fixes

Updated: 2026-10-10. This document covers the userdata CS runtime; old rootfs
and SD images have not been repackaged or flashed.

## Sound profile

The hardware stream remains PCM8000Hz/160samples. Its separate userspace bridge
converts to the unchanged external mono PCM16LE16000Hz/320samples per20ms.
CS now uses `--stream-clarity`, applying `y[n]=x[n]+0.2(x[n]-x[n-1])` at8kHz
in each direction, with int16 saturation and state erased after the call.
DC gain is unity; gain at3kHz is2.60dB, bounded below2.93dB. The profile cannot
restore GSM wideband frequencies or prove the selected cellular codec/rate.

The user reported clearer echo in the25-second comparison
`build/cs-clarity-call-trace1.json`:1249PCM frames, no RX/TX clipped samples,
normal SIP-controlled clearing. Synthetic frequency/DC/saturation tests pass
under UBSan. Production does not save audio or clipping files; the RAM-only
test marker enables aggregate metadata and bounded adapter diagnostics.

IMS executable/audio library, gain/CMR policy, shared8↔16k FIR and global SIP
codec order are unchanged. The earlier Opus/PCMU comparison remained muffled;
changing SIP codecs alone did not solve the user's report.

## Immediate clearing during DSP startup

The CS worker captures `now`, then performs DSP bootstrap, which can sleep.
During that work the adapter refreshes `lease_at`. The old expression
`now-lease_at > 10000000000ULL` wraps if the heartbeat is newer than `now`.
The driver then disables CS and clears its call despite a live owner.

`build/cs-clarity-call-trace2.json` captured CONNECT→clearing about1.5seconds
later, no adapter HANGUP/SUSPEND command, zero PCM frames, then a suspended
driver. This matches the worker's only autonomous `desired_enabled=0` path.
The modem boot and native/SIP processes stayed unchanged; this failure was
not an IMS sound change or confirmed power failure.

The fix snapshots the heartbeat once and checks `now>=heartbeat` before
subtracting. A heartbeat updated during bootstrap remains live. A genuinely
missing owner still expires after10seconds. The regression test covers the
future heartbeat, exact boundary, real expiry and uint64 boundary;
`build/cs-owner-lease-regression.json` records the old false-expiry example.
Kernel relocation audit passed for the new pinned B03 driver.

The call test previously accepted an early remote BYE after a brief CONNECT.
It now requires the planned talk duration and substantial RTP reception.
The trace2 call's old `call_tool_exit=0` therefore is not a successful audio
comparison. Incoming tests also require the echo duration and preserve old
receipts via explicit labels.

## Installation and verification

`install-registration-runtime.py --reboot-new-driver` verifies the existing
loaded-module digest against its installed file, backs up binaries on the Mac,
stops only owned idle services, requires actual driver/audio quiescence and
installs checked userdata files. It never unloads the pinned module live.
The software reboot must produce a new boot ID, checked new module digest and
voice readiness; `build/registration-driver-upgrade.json` records the result.

The first lease-corrected driver (MD5bf1ffbac6aa7602852a131a5b8e8d79c) was
checked after boot19c54aa8…. Its25-second postboot outgoing call passed
the stricter duration/RTP check, delivered1253PCM frames without clipping and
returned to reusable idle. The user confirmed echo until the end and normal
automatic clearing: `build/cs-clarity-call-lease-fixed-1.json`.
The first incoming repetition failed before CONNECT ACK: stage9→10→6 after
about10seconds, with no PCM startup. Its receipt is
`build/persistent-cs-incoming-lease-fixed.json`; the temporary PBX route was
restored. This is distinct from the fixed heartbeat regression.

The MT path used to wait for CONNECT ACK before attaching its speech frontend.
It now starts the separate PCM owner and audio route after SIP ANSWER, during
ANSWER_PENDING; a CS_CONNECTED notification still requires network ACK and
PCM readiness. Ringing alone never starts media or answers. The adapter bootstrap
guard remains15seconds for an offline PCM endpoint, independently of the
30-second network-ACK wait. The real adapter fixture checks that MT media starts
in ANSWER_PENDING before network ACK and is not spawned a second time.

The previous10-second ACK guard was a prototype limit. T313 is30seconds in the
MS call-control timer table; the speech connection is attached by CONNECT rather
than deferred until its ACK. References: [3GPP TS24.008, sections5.2.2.5–9](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/08.03.00_60/ts_124008v080300p.pdf),
[3GPP timer table](https://www.3gpp.org/ftp/tsg_ct/tsg_ct/tsgc_28/docs/pdf/CP-050071.pdf).
This change does not claim full protocol conformance. A decoded CC-message type
and expected-transaction boolean are logged without payloads or identities.
The final driver is installed after another checked software reboot:
MD5 `b3440aadf8e7be2e2321d13e539ba078`, SHA256
`e2893fde7fd62a42ab4becb3cab1907693eb38d19cf7ad6430e4a08b946d2b34`.
`build/registration-driver-upgrade.json` records this revision;
`build/registration-driver-upgrade-lease-fixed.json` preserves the earlier one.

The final incoming repetition passed with network CONNECT ACK, tone, speech echo
and normal automatic handset clearing, confirmed by the user. Boot and native/SIP
processes remained unchanged; driver/MM/audio returned to reusable idle. Receipt:
`build/persistent-cs-incoming-mt-audio-pending.json`. Its PBX absolute timeout was
configured as45seconds, but the observer recorded23.607seconds from kernel
CONNECT ACK until driver idle. The observer does not measure PBX Answer time;
this receipt is not proof of45seconds of media. The temporary PBX echo extension
was removed and the original incoming route restored.

AUTO was then saved and verified after a final fresh software reboot:
`build/registration-autoboot-final-20261010.json`, bootd034ef41…. IMS registered
26seconds and SIP was ready29seconds after native controller startup. Control
and native startup are rooted in init; the checked CS module is suspended and
the adapter is supervised by native. No Mac relay or temporary IMS rejection
rule remains. `build/cs-audio-final-verification.json` verifies unchanged IMS
binary/library and shared FIR hashes, AUTO/IMS idle and absent test markers.
The physical WebUI login page was reloaded after boot; authenticated UI Save
was not repeated. The earlier UI layout/selector evidence remains fixture-based.

The outgoing25-second confirmation applies to the prior lease-fixed revision;
the final revision additionally changes MT media startup/ACK timing and adds
numeric CC metadata. Long-duration endurance and other operators remain untested.


## User feedback after shared-driver update (2026-10-11)

After the WCDMA signaling/metadata revision, the user reported that GSM sound
became noticeably better. The same current driver passed GSM tone/echo/clearing.
WCDMA was cancelled on2026-10-11. Keep the existing CS processing and binaries;
this subjective improvement does not establish an AMR-WB radio codec.
See [UMTS.md](UMTS.md) for the installed driver and physical receipts.

## Preserved during WCDMA removal (2026-10-11)

No CS runtime rebuild or replacement was performed. Retained MD5 values:

- Driver: `c58ea61d11ac531dabc057114a8f399e`.
- Adapter: `bb20d794f2f92b32a54c2893c51bc430`.
- PCM bridge: `b158b536943c52dc4c7bac33bb670db9`.

No new real call was made for this removal. The user's prior GSM sound confirmation
remains the audio evidence. See `build/wcdma-removal-verification.json`.

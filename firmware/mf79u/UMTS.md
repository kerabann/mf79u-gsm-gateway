> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

## WCDMA removed (2026-10-11)

WCDMA development was cancelled at the user's request. The current WebUI,
settings/INI validation and native controller accept only AUTO, VOLTE and CS.
AUTO goes directly from LTE/IMS to GSM CS; no WCDMA registration attempt is made.
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

# WCDMA / UMTS CS voice and SMS

Updated: 2026-10-10. SMS delivery confirmed; voice implementation remains under validation.

User requests calls and SMS through 3G, in addition to the existing GSM and
LTE/IMS paths. This is WCDMA/UMTS, not CDMA/CDMA2000. A prior physical test
registered the Primetel SIM in Cyta 28001 in WCDMA-only mode; see
[OPERATOR-UMTS.md](OPERATOR-UMTS.md).

The WebUI labels this mode **WCDMA**. Settings/shared INI/native registration
retain the internal value `UMTS`.
The existing `CS` setting retains its GSM-only meaning. UMTS uses checked B03
profile14 and voice flags1/1, GSM profile13/flags1/1, LTE profile27/flags0/0.
AUTO tries LTE/IMS, then UMTS CS, then GSM if the bounded UMTS attempt fails;
idle promotion to LTE remains at15 minutes. Calls retain their admitting
backend until real clearing; no DIAL is replayed during fallback.

The persistent CS signaling/PCM adapter is shared. Radio registration alone
does not prove that its CC/MM or audio route works for UMTS. The external
PCM16LE16000Hz/320samples contract and the existing IMS processing are preserved.
The current CS PCM bridge is8kHz, so no UMTS wideband/AMR-WB claim is made.
SMS keeps the existing vendor CS worker and SIP MESSAGE/API queue; no duplicate
submission or automatic resend is introduced.

Physical call/SMS testing uses one user-supplied RAM-only destination. Report
files must omit the destination, message content, SIP identities, and voice data.
The original AUTO/LTE service is restored after testing. The user is asked to
confirm audible speech/echo and actual SMS receipt; modem submission and RTP
counters alone do not establish those outcomes.

## Physical verification and LED

Registered idle WCDMA uses cyan (green + blue, mask6). Every active call, including incoming ringing, uses green mask2.
Idle without registration remains red.
The device reported `umts_registered=true`, `color_mask=6`, `hardware_mask=6`.
This confirms the applied hardware mask; visual color has not been confirmed
by the user.

One outgoing SMS was submitted once through the existing CS worker while
registered on WCDMA/Cyta. The user confirmed receipt. Evidence:
`build/umts-sms-submit-live.json`. One outgoing call received CALL PROCEEDING
then cleared before answer; SIP returned487 and RTP count was0. The user
confirmed that the destination did not ring. Evidence:
`build/sip-cellular-umts-cyta-1.json`. WCDMA calls/audio are not yet validated.

UI labels were changed from UMTS to WCDMA without changing the stored mode
value or the registration protocol.

A diagnostic driver candidate adds bounded AA3F release-reason metadata
(offset2 u16, verified against the B03 constructor). It logs only reason/read
status/call stage/direction. This is an internal MM reason, not automatically
a standardized network cause. This describes the first diagnostic revision; the current installed revision
is recorded below.

## Release-reason diagnostic revision

The diagnostic driver MD5 ddf4affa61d18bb5470dffebc9047edc was installed with
a deliberate software reboot. Fresh boot1104b2df-826a-4227-b84e-294ee4b64835
registered WCDMA and restored the CS/SIP services. One diagnostic call again
received CALL PROCEEDING, then AA3F internal MM release reason10 (read success),
without a network CC clearing message seen by the current decoded handler.
RTP0; no answer. The runtime returned idle without another reboot.
Evidence: build/sip-cellular-wcdma-cyta-release-reason-2.json and
build/registration-driver-upgrade-wcdma-reason.json.

A further candidate observes bounded scalar ASC event metadata within the
existing owned callback, including incoming NAS message type and first Cause
IE only for CC clearing. No additional callback is stacked, no number,
message content or PCM is emitted. This will distinguish decoded CC filtering
from a lower-layer release.

The expanded trace found WCDMA uses E1F2 incoming data and E1F3 release rather
than GSM ABDF/ABD9. B03 message destructor BF2BBEF2 verifies the E1F2 owned
wire pointer at offset8, matching the12-byte NAS envelope. The candidate
adds E1F2 to incoming caller parsing and bounded NAS metadata; outgoing AAD4
metadata is included to distinguish normal MM responses from unexpected
CC STATUS. This was installed and captured network CC causes in the following tests;
it has not established a working WCDMA call.

The registration installer now stages/replaces only binaries whose checksum
actually differs, while preserving checked backups and the pinned-driver
fresh-boot requirement. Unchanged runtime files are still verified and listed
in the installation receipt. This avoids repeatedly transferring the large
unchanged SIP executable during driver diagnostics.

## WCDMA codec negotiation candidate

The latest outgoing attempt was cleared by the network with CC cause34;
incoming reached SIP/PBX but received network DISCONNECT cause21 before
answer. The user heard unavailable. Temporary PBX route/extension were restored.
The previous empty CALL CONFIRMED and GSM-only SETUP did not carry an explicit
UTRAN Supported Codec List. The candidate adds IE40 to SETUP/CALL CONFIRMED
only in WCDMA: GERAN NB bitmap1f, UTRAN NB bitmap60 (UMTS AMR/AMR2), no
wideband bit. Native sends the idle-only RAT2/3 when resuming the owned adapter.
GSM packet construction is unchanged. This is a standards-based improvement,
not proof that codec negotiation caused the observed network rejection.
Sources: [TS24.008 sections5.2.1.11/10.5.4.32](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/07.14.00_60/ts_124008v071400p.pdf),
[TS26.103 section6](https://www.etsi.org/deliver/etsi_ts/126100_126199/126103/05.02.00_60/ts_126103v050200p.pdf).


## Explicit codec offer: physical failure and GSM control

The codec candidate was installed through a deliberate fresh boot. Current
pinned driver MD5 `e4343516116ae99774207ced59d2b7b4`, boot
`d6f00334-50d4-43b5-a229-82feac29f0ed`, native3198/SIP3414/adapter3508.
The resume readback/log confirmed RAT3 and the WCDMA NB codec offer.
Checked receipts: `build/registration-runtime-install-wcdma-codecs.json` and
`build/registration-driver-upgrade-wcdma-codecs.json`.

Outgoing `build/sip-cellular-wcdma-cyta-codecs-5.json` reached CALL PROCEEDING
with the25-byte SETUP, but did not receive CONNECT before the bounded setup
deadline. Clearing included network RELEASE cause34; RTP0. This test does not
prove that the network initiated clearing before the local setup deadline.
Incoming `build/persistent-cs-incoming-wcdma-codecs-2.json` reached SIP200/ACK;
CALL CONFIRMED was10bytes, then ALERTING and CONNECT were sent. Network
DISCONNECT cause21 arrived about110ms after CONNECT, before CONNECT ACK.
The user again reported unavailable. No connected stage or audible audio was
established. Temporary PBX extension was removed and the incoming route restored.

The same current driver/SIM/destination passed a GSM control call:
`build/sip-cellular-gsm-wcdma-control-6.json`. The user confirmed call, tone,
echo and normal clearing. This separates the failure from a general SIP/CS
bridge or destination failure, but does not by itself identify the WCDMA cause.
Owned scalar traces are preserved in
`build/wcdma-codecs-and-gsm-control-metadata.json`; numbers, speech and SIP
identities are excluded. Read-only AT checks returned ZAMRSUP0,0,
ZUECAPASET3,3,0,0,0,1 and CVMOD0; their fields are not interpreted as proof
of voice support. No speculative NV/configuration write was made.

The incoming tester now recognizes a short completed call from the native
incoming event as well as the current owner, and records failure/after-state
and incoming-route restoration. Previously a call shorter than polling could
leave it waiting for180s and omit those failure fields. Python compilation passed.

Working SIP-WCDMA remains unfinished. The next investigation concerns UTRAN
voice channel/RAB assignment and B03 capability handling, rather than another
unchanged call or PCM processing change. AUTO/LTE restoration is checked after
testing; full NAND/SD delivery images remain unchanged.


A subsequent reversible ZAMRSUP1,0 hypothesis probe registered WCDMA, but the
call tester exited before creating a call receipt or sending INVITE. It is
**not a network rejection test** and does not validate the parameter's meaning.
The user reported no call. ZAMRSUP0,0 was read back after restoration;
AUTO/LTE/IMS ready and the same native/SIP/adapter PIDs were confirmed.
Receipt: `build/wcdma-amr-flag-control-7.json`. No further GSM call is needed.

WCDMA standards include AMR-WB (nine modes through23.85kbit/s); this project
has not confirmed its selection on B03/current network. A true HD path also
requires cellular audio above8kHz. The current CS hardware bridge operates
8kHz and resamples to the existing external16kHz/320sample contract, so it
cannot preserve wideband content merely by advertising AMR-WB. Wideband
advertisement remains disabled pending capability/audio-path proof; IMS audio
processing is unchanged. Source: TS26.103 section5.7 linked above.


## Continued investigation and GSM audio feedback

The user reported noticeably improved GSM sound after the shared CS driver
update. Preserve the current GSM PCM processing after WCDMA removal;
this audible result is not evidence of AMR-WB.

`test-wcdma-amr-flag-live.py` now reads/validates the RAM-only destination
before any ADB/USB subprocess, preventing inherited stdin from consuming it.
It also requires both native and SIP backend readiness before the one DIAL,
and restores ZAMRSUP0,0 and AUTO/IMS in finally. The previous flag-control7
exited2 before a receipt/INVITE, consistent with invalid/empty stdin; it is
not a measured network failure. Candidate flag-control8 is a separate receipt
and does not alter GSM/IMS binaries or audio parameters.


Flag-control8 was stopped before INVITE because its waiter checked a nonexistent
SIP status field `ready`. The actual field is `voiceReady`. ZAMRSUP0,0 and
AUTO/IMS were restored and checked before the corrected control9. Both failed
preparations had zero DIAL attempts; do not count them as network call failures.
The reusable probe now accepts an explicit unique label and single-dial flag.


## AMR flag control9 and sequence diagnosis (2026-10-11)

With corrected RAM-only destination handling and actual SIP voiceReady gate,
control9 sent exactly one INVITE/DIAL. SETUP25bytes received CALL PROCEEDING;
E1F3 release followed about0.7s later, AA3F internal reason10, with no network
CC clearing message observed. SIP487, RTP0, no CONNECT. Temporary ZAMRSUP1,0
therefore did not establish a working call; ZAMRSUP0,0 and AUTO/IMS were restored.
Receipts: `build/wcdma-amr-flag-control-9.json` and
`build/sip-cellular-wcdma-amr-flag-control-9.json`.

The observed UTRAN establishment also delivered MM IDENTITY REQUEST next to
our MM confirmation/SETUP; both our SETUP and vendor IDENTITY RESPONSE were
queued. A diagnostic revision records only N(SD) in existing bounded NAS
metadata to check their actual sequence/order. It does not change the shared
vendor sequence allocator, message construction, PCM or IMS processing.
TS24.007 section11.2.3.2.3 requires sequence numbering in Iu mode as well;
zeroing the UTRAN N(SD) is not justified. Source:
[TS24.007](https://www.etsi.org/deliver/etsi_ts/124000_124099/124007/10.00.00_60/ts_124007v100000p.pdf).


Sequence diagnostic driver MD5 `c58ea61d11ac531dabc057114a8f399e`
was installed through a deliberate fresh boot. Actual control10 with original
ZAMRSUP0,0 sent one DIAL. ASC observed SETUP N(SD)1 followed by the vendor
MM IDENTITY RESPONSE N(SD)2. These are consecutive modulo4: no duplicate or
reordered sequence was observed. CALL PROCEEDING followed, then E1F3/AA3F
reason10 without CONNECT. Do not change/zero the shared sequence allocator on
this evidence. Receipts: `build/registration-driver-upgrade-wcdma-sequence.json`,
`build/wcdma-amr-flag-sequence-10.json`,
`build/sip-cellular-wcdma-amr-flag-sequence-10.json`,
`build/wcdma-sequence-final-restore.json`.

Current native3008/SIP3257/adapter3271 are idle with AUTO/LTE/IMS ready.
The new revision only adds N(SD) scalar diagnostics; GSM PCM/IMS audio are
unchanged. UTRAN RAB/UE-capability static entry points are recorded in
`build/cpko-wcdma-rab-validity-audit.txt` and
`build/cpko-wcdma-sync-release-audit.txt`; these partial disassemblies do not
prove a failing branch or authorize a capability bypass. A same-SIM 3G-only
ordinary-phone call was requested as an independent network control.
Working SIP-WCDMA remains unfinished; do not count adapter-ready as a
successful network call or claim AMR-WB.

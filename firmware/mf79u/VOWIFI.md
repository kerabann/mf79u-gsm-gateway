> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

## USB internet for VoWiFi (2026-10-11)

Final near-AP reboot restored USB IMS/SIP (native29s/34s) and Wi-Fi via the
boot retry; the full LED/lease gate completed112s after reboot. A subsequent
60-second USB + Wi-Fi steady-state check passed. Wi-Fi initial boot is still
slow. Final source is USB / gateway192.168.0.169, VoWiFi only, actual purple5.
Details and repeatable test: [connection audit](CONNECTIVITY-20261011.md).

Mobile now has **VoWiFi internet source: Wi-Fi client / USB Ethernet** and USB
IPv4 gateway/DNS fields. USB works with AUTO and VoWiFi only; it does not require
a Wi-Fi association. Old configurations default to Wi-Fi. A gateway must be
another usable IPv4 host in the management subnet, with 1–3 IPv4 DNS servers.
Save uses the existing 90-second network confirmation/rollback workflow.

Control owns two /1 internet routes through bridge0, metric5, and an explicit
DNS override. Existing Wi-Fi metric10 routes and LAN management remain intact.
These routes also affect other ordinary modem internet traffic. Switching back
removes only the owned route tuples and restores the saved resolver file;
foreign metric5 route conflicts are rejected. Wi-Fi DHCP maintenance does not
replace the USB DNS override. Native requires usblan0 carrier and the Control
ready marker, pins the selected source during a call, and reports vowifiUplink
separately from logical IMS non-3GPP access. Charon binds bridge0 for USB.
The IMS P-Access-Network-Info header uses IEEE-802.3 for USB, without a fabricated
WLAN node. Token definition: [RFC7315 section5.4](https://www.rfc-editor.org/rfc/rfc7315.html#section-5.4).
SIM EAP authentication, encryption, PCM, codec order and gains are unchanged.
Purple LED still requires actual ready VoWiFi IMS, including over USB.

A computer must provide internet forwarding/NAT. On this Mac the requested
USB gateway is192.168.0.169, modem192.168.0.1/24. The temporary helper is
`share-usb-internet-macos.py`: run with sudo and `start`, undo with `stop`.
It detects the host internet interface, installs NAT only for the modem /32
in its own com.apple/mf79u-usb anchor, holds a PF enable reference, and does
not reload/flush the global rules. It refuses a missing Apple NAT anchor.
The helper is a host convenience, not a firmware service or IMS relay.
Host address/sharing must be re-established when that network changes.

Validation: Go/API/UI fixtures, ARM builds, shared SIP settings selftest,
authenticated real ARM registrar fixture, codec pipelines and native fallback
fixture passed. USB IMS with Wi-Fi disabled, TP-Link Wi-Fi IMS, hardware purple
LED and software reboot startup are physically verified. See
[connection regression audit](CONNECTIVITY-20261011.md) for exact timings,
boot Wi-Fi retry validation and limits. The SIP shared-config omission and
unreclaimed staging from the initial USB change are documented there.

## Restored runtime; Wi-Fi path blocks VoWiFi validation (2026-10-11)

ADB/debug USB0581 and the custom Control0.10 UI are physically restored.
Checked local public binaries/scripts were reinstalled into userdata, including
the fast REGISTER/retry changes and fresh-VIP SWu candidate. The pinned final
CS driver MD5 remains b3440aadf8e7be2e2321d13e539ba078. No rootfs/partition
image was flashed. Former admin login succeeds. Native/SIP processes run;
startup after a subsequent reboot has not yet been checked.

SERVER extension100 and VOWIFI-only settings were recreated. The prior SIP
extension secret was unavailable, so a new private secret was generated only
in modem settings; Linphone registration with it is unverified. epic-wifi is
visible at-38dBm but two connection attempts failed during WPA handshake.
Previously authorized Lipetsk-2G connected with WPA2/CCMP and DHCP
192.168.50.96/24; network apply was confirmed. USB remains192.168.0.1/24.
Internet ping through wlan0 passed2/2, and ePDG routes use wlan0. RAM-only
IKE diagnostics observed12 sends/9 retransmissions and0 received packets;
this does not prove an authentication or operator rejection. IMS is not ready,
imsAccessNONE, actual idle hardware LED red1. Purple/renewal speed remain
unverified. The observer was stopped because initial registration never passed;
private RAM diagnostics and temporary CLI were removed, logging returned quiet.
No call or SMS was sent. Requested confirmation of the current epic-wifi password.

Receipts: build/usb-userdata-runtime-restoration-20261011.json,
build/usb-userdata-settings-restored-20261011.json,
build/usb-userdata-restoration-status-20261011.json. The userdata clearing
cause remains unresolved; lack of Control/ADB preceded the privileged helper,
so do not assign causality to that helper solely from this observation.

## USB restored; userdata runtime absent (2026-10-11)

The user executed the privileged recovery helper. Factory AT1602 was verified;
a factory-mode reboot registered SHELL/ZUSBMODE. Correct SHELL commands must
be unquoted (the B03 implementation passes the raw parameter to soft_system).
Debug USB0581 and ADB are now physically verified, with a changed USB serial.

The current boot mounts mtd7 userdata, but /mnt/userdata/mf79u is absent.
A read-only raw scan in host RAM found no old runtime/settings names;99.53%
of bytes were erased. No raw partition image was saved. The stock fs_check
contains erase/reinitialization paths; the exact trigger remains unresolved.
Rootfs still contains our hook, boot-wait page and service policy. The former
admin password works. Do not claim this recovery preserved userdata.
The helper is disabled pending reset-path audit. Public runtime restoration is
in progress; settings and physical renewed VoWiFi are not yet verified.
Receipt: build/usb-normal-mode-recovery-20261011.json.

# VoWiFi userdata runtime and validation

## Recurring red LED / IKE renewal (2026-10-11)

The previous 120-second boot observation did not prove sustained VoWiFi.
Wi-Fi remained COMPLETED with DHCP while voice registration was lost. A
controlled IKE reauthentication reproduced the loss: the operator deleted
its old IKE SA and returned EAP_FAILURE to the overlapping replacement,
despite a successful local USIM AKA response. The default four-hour IKE
rekey interval implied a 1440-second overtime margin: operator AUTH_LIFETIME
1800 seconds therefore scheduled reauthentication after only 360 seconds.
No OOM kill was present in the inspected kernel log.

The candidate explicitly uses sequential IKE reauthentication and a
120-second overtime margin (operator-triggered renewal at 1680 seconds).
Authentication, mutual ePDG verification and DPD remain enabled. The manager
allows a bounded 120-second CHILD/VIP gap; the native controller revokes
voice readiness immediately, preserves the SIP process, and recreates IMS
when the new IKE generation becomes available, including a changed VIP.
The LED stays red during a real registration gap and becomes purple only
on actual IMS readiness. Seamless calls during renewal are not claimed.
Safe native lifecycle events expose manager exit and tunnel replacement;
raw identity-bearing diagnostic logs stay protected in device RAM only.

Incident and installation receipts: build/vowifi-recurring-red-incident-20261011.json,
build/vowifi-recurring-red-observation-20261011.json,
build/vowifi-reauth-fix-install-20261011.json. The first sequential-only attempt also received EAP_FAILURE. A fresh initiation
in the same charon succeeded. The next SWu-specific candidate requests a fresh
VIP during reauthentication instead of inheriting the previous VIP; generic
IKE configurations retain their original behavior. Fresh-VIP reauthentication passed actual EAP-AKA, IKE SA2 and CHILD SA2
in the same charon. Full IMS voice recovery remains unproven; USB/ADB and
HTTP management disappeared during validation. This is not a passed stability
or call test.

Updated: 2026-10-11. Requested: AUTO prefers Wi-Fi IMS, VoWiFi only forbids
cellular voice fallback, and idle registered VoWiFi uses a purple network LED.

Source candidates add a SIM-authenticated ePDG IKEv2/EAP-AKA transport,
source-specific IPv4 routing through an owned `vowifi0` interface, native
registration orchestration, IMS interface selection and Wi-Fi access headers.
Control/UI accept VOWIFI. The LED policy uses red + blue for ready VoWiFi
while preserving green for connected/outgoing calls. PCM format and codec
processing remain unchanged.

The userdata runtime has been installed for physical validation; no NAND/rootfs
flash or reboot was performed. SIM authentication and the SWu child SA have
passed. Actual IMS over Wi-Fi registration (401 → SIM AKA → 200), voiceReady
and purple hardware LED mask5 passed; VoWiFi call/audio remains unverified. VoWiFi-only
without Wi-Fi blocks LTE/CS in the actual controller fixture. Persistent CS
module, external PCM format, operator codec/gain policy remain unchanged.

The first integrated attempts exposed B03 shell behavior in route setup,
a VICI notification/updown timing race, and excessive RAM pressure from
unneeded extracted tools/certificates. Route setup now uses bundled BusyBox;
startup waits for both assigned VIP and P-CSCF metadata. Tools are removed
after use and on cleanup. Process-group cleanup covers extraction children;
source-specific route leases preserve overlapping IKE reauthentication.
`test-vowifi-updown.py` proves that teardown keeps foreign routes and overlapping
owned leases. `test-registration-fallback.py` proves VoWiFi-only cannot dial
via CS or start LTE without Wi-Fi. A bounded supplicant query tolerates up to
thirty seconds of missing replies after a confirmed association; an explicit
non-COMPLETED reply clears that cache immediately. STATUS waits are bounded to
one second while idle and 250 ms during calls. Tunnel startup has a bounded
120-second allowance for extraction and local SIM/CP authentication. Cleanup
after an unexpected manager exit retains the owned address until its exact
source rule is removed, even if charon already removed the bridge. The route
fixture covers this regression and preserves unrelated rules/routes.

The reduced static client uses builtin AES/SHA1/SHA2, FIPS-PRF and GMP;
OpenSSL and unused tools/certificates are absent from the steady RAM runtime.
The current 987764-byte bundle contains all provider-assigned P-CSCF addresses;
mutual EAP-AKA and SWu establishment passed.
Only IPv4 SWu and the current operator's mutual EAP-only authentication have
been exercised. Native/API configuration currently selects VOWIFI for testing.
No VoWiFi call, media test, reauthentication or boot test has passed yet.

Read-only packet metadata localized the next IMS blocker: B03 selects TCP
for the initial REGISTER. Its TCP handshake passes, but AF_PACKET captures
REGISTER data with an incomplete TX-offload checksum before bridge transmission.
A 1400-byte segment to port 5060 was measured with checksum_valid=0; repeated
segments received no SIP registration reply. The packet adapter now completes
IPv4 TCP/UDP checksums before userspace ESP encapsulation. The independent
known-value selftest covers odd payloads, repeated normalization, fragments and
malformed lengths. Physical validation of that revision received the first SIP response (500)
from P-CSCF over TCP. Wi-Fi access type was independently observed as IEEE-802.11.
The next candidate adds the actual associated AP BSSID as i-wlan-node-id and
preserves available cellular access information in Cellular-Network-Info,
as required by [GSMA IR.51 section 2.2.1](https://www.gsma.com/newsroom/wp-content/uploads/IR.51-v6.0.pdf).
The corrected access headers passed actual IMS registration; see
build/vowifi-ims-live-20261011.json (historical local artifact: `build/vowifi-ims-live-20261011.json`). No packet
payload, SIM identity or authentication key was written to a receipt.

StrongSwan 6.1.0 source archive SHA256:
`fe6c97481298767213cfc2e9a1da29fdd8018d481ff4cb9cf0283099654f20d4`.
The userspace packet adapter passed a physical IPv4 UDP duplex test
(`build/vowifi-packet-adapter-live-20261011.json`). AF_PACKET must use
ETH_P_ALL for outgoing capture and bind after raising the owned bridge.
The source uses strict hex decoding for AKA fields. Runtime lifecycle,
full authentication parsing and VoWiFi-only require further validation. No rootfs/NAND image was
flashed and no modem reboot was performed for these changes.

## Operator probe via epic-wifi

DNS resolved the SIM-derived ePDG. IKE_SA_INIT received a valid response and
selected AES-CBC-256 / HMAC-SHA2-256 / MODP2048. IDr using the ePDG hostname
was rejected before EAP; using the IMS APN (`ims`) obtained EAP-AKA. The first
EAP attempt sent NAK because the standard AKA dependency FIPS-SHA1 required
the built-in keyed-SHA1 provider; the build now enables that provider.

The daemon needs enough workers for its blocking network/netlink/VICI jobs;
16 workers successfully served VICI, while 8 deadlocked configuration loading.
Identity configurations and diagnostic logs remain protected modem RAM only.
This initial probe retained the old native/IMS/SIP processes. Later userdata
runtime installation is documented above and in the installation receipt.

Protocol references: [Cisco ePDG IKE_AUTH IDr/APN description](https://www.cisco.com/c/en/us/td/docs/wireless/asr_5000/21-23/EPDG-Admin/21-23-epdg-admin/m_suppressing-handover-request-for-vowifi-ir-subscribers-.pdf),
[strongSwan source](https://github.com/strongswan/strongswan),
[WGT observed VoWiFi identity exchange](https://github.com/working-group-two/engineering-blog/blob/master/pages/blog/_posts/2020-03-30-catch-imsi-from-vowifi-session.md).

B03's real successful USIM reply contained five fields after the response
prefix: status, CK, IK, padded RES and decimal RES hex-character length. Each of the
three binary fields is 16 bytes. The adapter preserves empty fields, trims
external whitespace, restricts parsing to the response line and decodes hex
strictly. It now handles the five-field shape and retains the four-field
fixture shape. The network EAP MAC is checked by strongSwan; no integrity
check is bypassed. Values of CK/IK/RES/identity are not stored in receipts.

The operator completed EAP-AKA and mutual EAP authentication. SWu IDr now
requests `ims` through a narrowly gated `ike_auth` patch, while remote identity
remains the exact SIM-derived ePDG hostname. The current operator uses EAP-only
authentication; its mutual EAP proof and identity are required, instead of a
public-key authentication constraint. No EAP MAC or authentication check is
bypassed. The successful response allocated IPv4 `10.64.216.74/32` and a
P-CSCF `10.144.5.162`; the child SA and source-specific table79 route were
established in the RAM-only probe. This is SWu transport proof, not yet IMS
registration or call/audio proof.

B03 reports RES length in hex characters: a reported16 selects8 binary bytes.
Both network EAP success and its final mutual authentication passed after this
conversion. Successful tunnel receipt: `build/vowifi-tunnel-live-20261011.json`.

## P-CSCF recovery and Linphone case (2026-10-11)

The operator assigns 10.144.13.162 and 10.144.5.162 in variable order.
A failed first endpoint returned SIP500. Native now retries only provider-listed
addresses after the bounded IMS deadline, retaining the authenticated SWu
transport, native and SIP processes. The working endpoint is remembered only
in protected RAM, and only reused if the next provider list contains it.
Physical event vowifi_pcscf_failover at elapsed596 was observed on native2602
with SIP2628 unchanged. Final registration/call results are tracked separately.

User requested a persistent SIP Server account100, UDP192.168.0.1:5080,
VoWiFi Only and registration in the open Linphone application, followed by
an outgoing test to the supplied number. Credentials are excluded from records.
See [LINPHONE-VOWIFI-TEST.md](LINPHONE-VOWIFI-TEST.md).

## Fast re-registration candidate (2026-10-11)

Built, not yet installed after USB management became unavailable. Only received
REGISTER 5xx responses trigger immediate provider P-CSCF failover; MESSAGE
responses and body text do not. A bounded CSeq/header parser emits the status
code only. The existing LTE setup wait remains8s; Wi-Fi setup uses1s for the
last command instead of an LTE radio delay. Actual registration/voice readiness
still requires the existing IMS and frontend/AMR-WB acknowledgements. Failed
SWu attempts retry after5/10/20/40/60s, capped, resetting after actual readiness.
This avoids a fixed60s delay on the first recoverable error without an unbounded
retry storm. Parser negative controls and actual native-controller registration
fixtures pass; hardware timing and complete renewed IMS readiness are pending.
Receipt build/vowifi-reauth-diagnosis-and-speed-20261011.json.

USB reconnect follow-up: macOS enumerates19d2:1602 with two vendor interfaces;
AT/CGMR/CFUN queries respond, ADB and USB management Ethernet are absent.
No USB composition, NV, factory reset or flash command was issued. A cold
15-second disconnect and direct alternate port were requested. Receipt:
build/usb-reconnect-observation-20261011.json. Fast candidate remains uninstalled.

Second direct-port cold reconnect still enumerated19d2:1602; read-only AT+ZMODE?
returned2 (factory). The selected MF79U SDK maps2 to factory and0 to user USB.
AT+ZMODE=0 returnedOK and readback0. AT+CFUN=1,1 (reset parameter1 is listed
in the B03 command audit) returnedOK; USB detached. Awaiting enumeration.
No factory reset or flash command was issued. Receipt:
build/usb-normal-mode-recovery-20261011.json.

### USB recovery blocker after second reconnect (2026-10-11)

After the AT normal-mode change/reset, the modem enumerated PID1405 (CDC ECM
and mass storage). USB LAN192.168.0.1 and stock goform login work; HTTP80 serves
our boot-wait HTML, custom Control18080 is unavailable and ADB is absent.
The boot-wait page alone does not prove that start-control was invoked or why
it stopped. Do not diagnose userdata loss or a spontaneous reboot from this.
Stock SET_DEVICE_MODE requests with the stock login/AD sequence returned
failure; no successful debug-mode mutation was established.

The checksum-pinned offline B03 kernel contains usb_mode_work atC020B906;
requestA8 selects factory USB notification. An EP0 request returnedPIPE and
no mode change was observed. The source also documents vendor SCSI OPENDL99
as a factory/boot-flag switch. A mass-storage recovery claim failed with
LIBUSB_ERROR_ACCESS(-3); no SCSI command was sent. Both modem volumes were
cleanly unmounted for the claim and remounted afterward. Noninteractive sudo
requires a Mac password. No SD file, partition image or firmware image was
written during this recovery.

[recover-usb-at.py](recover-usb-at.py) is a manual macOS recovery helper for
PID1405, interface2, vendor OPENDL on CD-ROM LUN0. It refuses non-root use,
flushes the two known USB volumes, remounts them on an unsent-command failure,
and does not issue storage WRITE/FORMAT. OPENDL itself changes the boot flag
and mode; debug mode must subsequently be restored and verified through AT.
Only Python syntax and the non-root refusal are validated; the privileged
hardware path is unverified. A user must run it in their terminal with sudo;
never request or store their Mac password. Installation and physical tests of
the speed candidate are still pending. Receipt:
build/usb-normal-mode-recovery-20261011.json (latest_observation).

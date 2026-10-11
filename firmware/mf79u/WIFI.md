> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Wi-Fi Hotspot / Client

Updated: 2026-10-11. This replaces the previous hotspot-only requirement.
Current boot/TP-Link association limits and USB independence:
[connection audit](CONNECTIVITY-20261011.md). Earlier physical results below
remain receipts of those individual tests.
Latest user-initiated reboot8704dd24… restored TP-Link_8C63 automatically:
COMPLETED/DHCP192.168.1.44/24. All3samples of a30-second read-only check passed
alongside USB VoWiFi, SIP, purple LED and HTTP. No network apply was needed.
Receipt: build/adb-boot-user-reboot-wifi-usb-20261011.json. The prior failed
Wi-Fi boot is retained; this result does not prove every future boot succeeds.

## UI and connection

Wi-Fi → Mode: Hotspot or Client → Enabled → Save. In Client mode:

- Scan networks and select a 2.4 GHz network, or enter the exact SSID manually.
- Select WPA2-Personal and enter its password (8–63 bytes), or Open.
- Hidden SSIDs are probed with `scan_ssid=1`; manual entry works without a scan.
- IP, gateway and DNS come from DHCP. The current connection state, SSID and
  address appear on Wi-Fi and Status.
- Confirm network settings within 90 seconds. Failed association/DHCP or an
  unconfirmed change restores the previous confirmed Wi-Fi/LAN profile.

Hotspot retains WPA2-Personal, SSID, password and Hidden network controls.
Only one confirmed profile is saved. Switching mode clears input credentials;
enter the desired profile before Save. Hotspot and Client are mutually exclusive.
WPA3-only, enterprise/EAP and WEP are unsupported; scan marks them unavailable.

A scan while Client is active uses the existing supplicant. A scan from Hotspot
or disabled temporarily borrows the radio and restores its confirmed state
before replying. An active hotspot therefore disconnects briefly during scans.
Calls, pending network confirmation and simultaneous network operations block
scanning. USB management remains enabled; after changing the LAN subnet, renew DHCP or
set a matching USB client address. A conflicting legacy 192.168.0.1 recovery
alias is removed only after a non-overlapping management address is installed.

## Runtime and ownership

`control/network.go` handles mode apply, cleanup and status; `control/wifi.go`
handles scan parsing, PSK derivation and uplink subnet checks. The B03 Realtek
WEXT driver uses `opmode=16` for AP and `opmode=8` for station. B03 also needs
`sta_autoconnect 0`, `ap_scan 1`, `select_network 0`, then `ap_scan 0` after
3 seconds. The stock script sets `ap_scan 1` before `sta_autoconnect 0`;
current client configuration also explicitly sets `auth_alg=OPEN` before WPA2.
A controlled exact-order/BSSID retry still failed on the current TP-Link signal;
see the current audit rather than treating the sequence alone as a stable boot proof. A generic WEXT-only
configuration scanned but did not finish association in the physical test.
Client detaches
`wlan0` from `bridge0`, while `usblan0`, management IP and vendor dnsmasq remain.
The saved Client mode is retained during boot instead of replaced by factory AP.

Owned `wpa_supplicant` and `udhcpc` have explicit PID/config paths under
`/dev/mf79u`. Process stop verifies the command belongs to that directory.
The SSID is hex-encoded and WPA2 PSK is derived with PBKDF2-HMAC-SHA1, avoiding
quoted configuration injection. `wpa.conf` is 0600. Public settings, receipts
and logs exclude credentials; settings and explicit authenticated credentials
API keep the established access policy.

DHCP/static client gateway uses `/1` routes with metric10 without deleting
cellular defaults; IMS sockets stay bound to `wan5`. DNS is kept during the
active Wi-Fi uplink and restored on return to Hotspot/disabled. DHCP deconfig
clears the expired address and owned gateway/DNS state; renew refreshes routes. Client lease
IPv4 subnets overlapping the configured LAN are rejected and rolled back. When the
user changes LAN to a different subnet, only known conflicting prior/recovery
aliases are removed; unrelated management addresses are left intact. The LTE
cellular output policy remains unchanged. This feature connects the modem
itself; no new USB-to-Wi-Fi NAT sharing behavior is claimed.

## Verification

Go fixtures cover WPA PSK known vector, secure configuration serialization,
WPA2/Open validation, malformed SSIDs, scan escaping/deduplication/unsupported
security, and overlapping subnets. `test-wifi-ui.js` tests safe selection,
mode visibility and Open controls. `build-control.sh` runs these fixtures
alongside existing Control/system/roaming checks and builds ARMv7 soft-float.

A Chromium UI fixture passed 1280px and 390px: mode switch, scan selection,
manual hidden SSID, Open security, no JavaScript errors or horizontal overflow.
Screenshots: `build/ui-wifi-client-1280.png`, `build/ui-wifi-client-390.png`.
These screenshots are fixtures, not proof of physical association.
The final installed UI also passed at 1280px/390px with actual saved Client
SSID/DHCP status, no JS errors or overflow: `build/ui-wifi-client-live-1280.png`
and `build/ui-wifi-client-live-390.png`.

Realtek adds runtime flags to `opmode` after association (`0x409` observed);
status tests the station bit rather than requiring the exact initial value8.
IPv6 link-local prefixes are not IPv4 subnet conflicts.

Physical installation and connection results are recorded in
`build/wifi-client-install-20261011.json` and
`build/wifi-client-live-20261011.json`. On 2026-10-11 the real API scan found
six networks including `Lipetsk-2G`; saved Client WPA2 reached COMPLETED and
received `192.168.50.96/24`, gateway `192.168.50.1`. The profile was confirmed.
USB management remains `192.168.0.1/24`; no subnet migration is needed.
DNS lookup and an HTTP fetch through the Wi-Fi routes passed. Native PID527,
SIP PID529, boot and IMS-ready state were preserved. Hotspot scan/restore and
failed-association rollback also passed (`build/wifi-hotspot-live-20261011.json`,
`build/wifi-client-rollback-20261011.json`). This initial test did not check client startup after reboot; later reboot
checks are in the connection audit and have not established stable Wi-Fi boot; no physical Open or hidden-network association was performed. The original binary has a
verified gzip backup locally at `build/control-pre-wifi-client-20261011.gz`;
installation also keeps the same named protected userdata gzip backup.
No rootfs/NAND or SD archive was rebuilt or flashed. Native/CS/SIP audio
binaries and external mono PCM16LE16000/320 were not changed.

## Scan recovery, 2026-10-11

A later live check found `wlan0` down with `INTERFACE_DISABLED`, despite the
saved Client profile. Raising the interface restored scan results. B03 also
returned `FAIL-BUSY` immediately after `ap_scan 1`, while returning nearby
networks normally. The scanner now raises the Client interface and accepts
`FAIL-BUSY` as an already running scan; other failures remain errors. The UI
shows the actual API error instead of replacing every failure with a generic
message. Fixtures cover active-scan and actual-failure responses.

The earlier successful DHCP/HTTP test is historical. Subsequent association
was intermittent (`COMPLETED` followed by disconnect); current connectivity
must be checked independently before claiming working VoWiFi.

## Scan recovery and current uplink

The scan recovery build was installed without reboot:
`build/wifi-scan-recovery-install-20261011.json`, control MD5
`053b567b7944ea934e36c39893d9aef6`. A missing owned supplicant is recreated
from the confirmed Client profile before scanning. Live UI scans at 1280px
and 390px displayed `epic-wifi`; no JS errors or horizontal overflow occurred.
Screenshots: `build/ui-wifi-scan-recovery-live-{1280,390}.png`.

The new user-selected `epic-wifi` completed WPA2 association and DHCP:
`192.168.1.44/24`, gateway `192.168.1.1`. DNS resolution of the SIM-derived
ePDG and an HTTP fetch passed through WLAN routes. Settings were confirmed
through the ordinary UI API. Receipt: `build/wifi-epic-client-live-20261011.json`.
The earlier `Lipetsk-2G` connectivity result is not the current selected uplink.
Native PID527, SIP PID529, LTE IMS and boot ID were preserved.
That scan receipt predates the new native VoWiFi runtime and later control
updates. Current VoWiFi validation is tracked in [VOWIFI.md](VOWIFI.md).
The current control also reaps only matching owned supplicant/DHCP processes
before rebuilding a profile; unrelated/vendor daemons are preserved. Classifier
tests cover foreign process names, paths and lookalike substrings. The UI uses
native IMS readiness as authoritative over older SIP status.

## Очистка ошибки после восстановления (2026-10-11)

Подтверждённый Client epic-wifi снова COMPLETED с IP192.168.1.44, но старая
ошибка Wi-Fi connection failed / rollback сохранялась в networkError.
Теперь maintenance очищает только эту ошибку при отсутствии pendingNetwork,
совпадении подтверждённой SSID, COMPLETED и действительном непустом IP.
Сохранённый DHCP lease при DISCONNECTED и другая SSID ошибку не скрывают.
Go regression tests и сборка Control прошли; исправление установлено в userdata.
UI уже удаляет networkNotice после очистки networkError сервером.

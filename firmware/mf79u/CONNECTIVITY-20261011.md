> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Connection regression audit and USB/Wi-Fi VoWiFi validation

Date: 2026-10-11. Physical B03 MF79U. Connection corrections below use the
userdata overlay; the subsequent ADB boot policy also updates two rootfs files
without flashing a partition image. See [ADB.md](ADB.md).

## Latest user reboot

The user reports automatic reconnection after their own reboot. Read-only
checks confirm boot8704dd24… with ADB740/PPid1, USB ECM+ADB, Wi-Fi
TP-Link_8C63 COMPLETED/DHCP192.168.1.44/24, USB-selected VoWiFi only,
native1573/SIP1702 ready, actual purple5 and custom HTTP. A30-second check
passed all3samples including Wi-Fi lease, without applying settings or restarting
services. This supersedes the disconnected Wi-Fi state observed after the first
ADB test reboot; both receipts remain. The user's reboot mechanism and startup
duration were not measured. Receipts: adb-boot-user-reboot-20261011.json and
adb-boot-user-reboot-wifi-usb-20261011.json.

## Confirmed regression and correction

The USB feature added `vowifi_uplink` to the shared gateway.ini. Native read it,
but the SIP parser rejected unknown fields. The old running SIP process could
keep its prior config after failed SIGHUP; fresh boot instead printed
GATEWAY_CONFIG_INVALID and native logged sip_start_failed, then stopped.
This omission was in our USB change. sip-settings.h now validates the shared
field (empty/WIFI/USB) and leaves its handling to native. Unknown fields and
unsupported values remain rejected. The real ARM SIP registrar fixture now
starts with VOWIFI/USB config. Host and ARM settings selftests, authenticated
registrar/disabled/recovery tests and all five codec pipelines passed.

Installed SIP MD5: e03d90dbbf2f5e0f8878bf414b6843b4. The production media clock
wrapper, codecs, PCM and IMS gains were retained. Native/SIP startup worked
on the first software reboot after the correction.

## Access stall and installation memory

The previous install left public uncompressed staging in /dev: Control6.9MiB,
native603KiB, IMS shim411KiB and runtime965KiB. A second Control transfer then
added another expanded6.9MiB plus compressed payload. That is approximately
18–19MiB of temporary RAM on a 56MiB device, alongside active services.
ADB/HTTP/AT stalled while kernel USB Ethernet/ping remained alive. The old
kernel log was lost at physical reconnect: OOM causality is not proven.

install-usb-vowifi-fix.py now installs one artifact at a time, expands directly
to userdata, checks both compressed/installed MD5, and removes its RAM payload.
The measured maximum compressed staging was2958216bytes; no uncompressed RAM
stage remains. Public rollback artifacts were copied/hash-verified on the host;
no settings or credentials were copied. Removing duplicate on-device public
backups returned userdata use from86% to59% (about10MiB free).
The Control-only option preserves native/SIP/IMS processes; their PIDs/readiness
were unchanged by the later Control update.

## Host NAT and Wi-Fi name

Mac status initially showed forwarding/PF enabled but no MF79U NAT rule.
After the user ran the helper again, USB DNS and HTTP passed. ICMP to1.1.1.1
still received no replies, so ping alone is not a valid internet gate here.
share-usb-internet-macos.py now supports read-only status and an idempotent
start for restoring the owned rule. It does not reload the global PF rules.
The reason the earlier anchor was absent is not established. No root helper
watcher or system-wide sharing service was installed.

The provided TP-LINK_8C63 spelling did not associate. A fresh scan returned
TP-Link_8C63 at-48dBm/WPA2. With that exact SSID and the supplied password,
association/DHCP/VoWiFi IMS all passed at192.168.1.44/24. Passwords are excluded
from this report and receipts.

## Boot client retry

The first reboot restored USB IMS, but the saved Wi-Fi client lost association
between association completion and DHCP; Control reported a DHCP timeout.
Bootstrap now retries that client profile once after5seconds, provided settings
are unchanged and there is no active call. USB may register while this runs.
The retry alone did not solve the second reboot's Wi-Fi failure. Password and
runtime PSK were checked in RAM and matched. The stock rtl_wlan_connect.sh also
sets auth_alg OPEN explicitly; our client config omitted it. A controlled live
set_network auth_alg OPEN plus the normal select sequence then held WPA2/CCMP
association and acquired192.168.1.44. That parameter is now explicit in the
client config. It means IEEE802.11 Open System authentication before WPA2;
it does not make the network unencrypted. It did not establish stable client
autostart on the next reboot. Do not attribute the loss solely to timing or
auth_alg.

Reapplying an unchanged owned USB gateway keeps its existing route tuples and
ready marker, updating DNS without a route teardown. The third reboot reached
IMS at native elapsed35s and VoWiFi/SIP at40s. Its receipt contains a transient
Wi-Fi COMPLETED without an IP address: that is not a DHCP or stable client pass.
Later association/lease recovery was intermittent. USB registration and purple
LED remained ready through these Wi-Fi failures.

A controlled retry of the stock command order, using a network-free supplicant,
all explicit WPA2 fields and the actual BSSID, received13 successful control
replies but association timed out. Kernel metadata reported association timeout
and retry, before DHCP. The scan later measured TP-Link at-72dBm compared with
the earlier-48dBm. After the user moved the modem closer, the scan returned
-48dBm again. Association without DHCP succeeded; starting the original DHCP
hook then retained COMPLETED/192.168.1.44 across16 samples. Wi-Fi VoWiFi
registered in29.7s and passed a60-second stability check.
This does not establish an incorrect password or prove an RF cause. A tentative
DHCP netlink-clear change was reverted because failure was reproduced without
DHCP; it is not included in the installed firmware. The later paired observation
also did not reproduce a deconfiguration-triggered Wi-Fi disconnect. Stronger
signal accompanied recovery, but it does not prove that all earlier failures
were RF-only.

## Physical results and bounds

USB VoWiFi only registered with Wi-Fi disabled: logical imsAccess=WIFI,
vowifiUplink=USB, tunnel/IMS/voice ready; ePDG used bridge0 via192.168.0.169.
Charon interfaces_use was bridge0,vowifi0. Hardware LED mask5 means red+blue,
with green off (purple); Wi-Fi LED was off in that test.
TP-Link Wi-Fi VoWiFi also registered; source changes preserved native/SIP PIDs.
The first software reboot reached IMS at native elapsed32s and VoWiFi/SIP at37s;
HTTP was observed intermittently from48s and consistently again from59s. No
stock UI was observed in these samples. Polling cannot exclude a shorter flash.

This verifies network/tunnel/IMS readiness, not voice audio or renewal under a
long-running call. No call/SMS was initiated by these tests, no factory/USB-composition command was
issued, and no NAND/rootfs image was flashed. The final pinned CS driver stays
b3440aadf8e7be2e2321d13e539ba078.

Receipts:

- build/vowifi-usb-sip-config-fix-install-20261011.json
- build/vowifi-usb-control-boot-fix-install-20261011.json
- build/vowifi-usb-without-wifi-live-20261011.json
- build/vowifi-tplink-live-20261011.json
- build/vowifi-usb-reboot-before-client-retry-20261011.json
- build/vowifi-usb-reboot-before-explicit-auth-20261011.json
- build/vowifi-usb-reboot-live-20261011.json

## Repeatable physical stability test

`verify-vowifi-uplink.py` is read-only. It samples native tunnel/IMS/voice,
selected source, ePDG route, actual LED and HTTP management every15seconds.
WIFI requires an associated client and usable IPv4 address. `--require-wifi`
adds that check during a USB test. Calls are not initiated; an existing call
uses its normal call indication instead of imposing purple.

Example from the project root:

```sh
python3 firmware/mf79u/verify-vowifi-uplink.py --source USB --duration 120 --output firmware/mf79u/build/usb-check.json
```

The120-second USB check passed all9 samples while Wi-Fi was disconnected.
Receipt: build/vowifi-usb-stability-live-20261011.json. This establishes USB
independence, not a long call/audio or full IKE reauthentication test.

## Source switches with the modem near TP-Link

Wi-Fi reached ready in29.7s; switching back to USB reached ready in22.5s.
Native1577/SIP1669 were preserved across both source changes. Wi-Fi stayed
COMPLETED at192.168.1.44, networkError was empty, and each ePDG route used the
selected interface. Wi-Fi passed all five60-second steady-state samples.

The first sample immediately after USB IMS readiness still saw the prior red
hardware LED; subsequent15-second samples were purple. This transition sample
is retained as a failed strict stability check, rather than counted as a pass.
The earlier120-second USB check was entirely purple/ready. Final boot/steady
validation follows below. These measurements do not prove call audio.

Additional receipts:

- build/wifi-dhcp-compare-live-20261011.json
- build/vowifi-wifi-stability-near-ap-live-20261011.json
- build/vowifi-source-compare-near-ap-live-20261011.json
- build/vowifi-usb-return-transition-live-20261011.json

## Final reboot near the access point

Software reboot changed boot tof5a748bd-24e6-42e1-8d43-fd5571b250b3. HTTP Control returned at
49.3s; sampled responses never showed the stock UI. USB IMS registered at native
elapsed29s and VoWiFi/SIP at34s. No second Mac NAT start was needed. The saved
Wi-Fi profile eventually recovered via the boot retry, with COMPLETED and
192.168.1.44 present when the full ready/LED/lease check ended at112s.
This is a successful recovery boot, not an immediate Wi-Fi startup claim.
Network error was empty. Hardware LED was actual purple5.

Receipt: build/vowifi-usb-reboot-near-ap-live-20261011.json.
The strict post-boot steady-state test is in
build/vowifi-usb-final-live-20261011.json.

The final strict60-second test passed all five samples, including actual
purple LED, USB IMS/route, management HTTP and simultaneous Wi-Fi lease.
Final UI sign-in passed and displayed VoWiFi via USB, Registered IMS and
Client registered SIP. No voice audio test was initiated.

Final installed Control MD5: f0d11ba461c3f31f9cc5e53d73c482a7.
Local build and physical installed hashes match for Control and SIP.
Go fixtures passed after the final source/test update.

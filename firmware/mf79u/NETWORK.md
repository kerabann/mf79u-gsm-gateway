> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Shared USB / Wi-Fi LAN and DHCP

Audited: 2026-10-08. Installed network implementation was verified on 2026-10-07.
[STATUS.md](STATUS.md) distinguishes the saved laboratory profile from live state.
In Hotspot mode USB Ethernet (`usblan0`) and Wi-Fi (`wlan0`) belong to `bridge0` and
use one LAN/DHCP profile. The modem address stays static; connected clients
can obtain their own addresses through DHCP.

| UI field | Meaning / current default |
| --- | --- |
| Subnet | IPv4 network address with CIDR prefix: `192.168.0.0/24` |
| IP gateway | Modem address and DHCP default gateway: `192.168.0.1` |
| IP pool | Inclusive client address range: `192.168.0.2-192.168.0.253` |
| DNS servers | DHCP option 6, comma separated: `1.1.1.1,8.8.8.8` |
| Routes via DHCP | Optional routes, one line each: `1.2.3.4 via 192.168.0.10` |

The route example is a placeholder, not a configured route. A bare destination
IP becomes `/32`; a network destination requires CIDR. The next-hop router
must have a stable, usable IP in this LAN. Ensure it cannot collide with a
DHCP assignment. Routes are advertised to clients, not installed as modem
uplink routes. They do not bypass the LTE data switch.

Settings validate subnet `/8`–`/30`, canonical network addresses, pool ordering,
usable gateway/pool addresses and exclusions of the modem/recovery address.
Up to three IPv4 DNS servers and 20 unique routes are supported. An explicit
`0.0.0.0/0` route is rejected; the IP gateway defines the default route.
DNS here changes DHCP advertisements only, not operator IMS resolution.

Custom routes use DHCP options 121 and 249. The encoded list includes the
default route because clients using option 121 ignore option 3 under
[RFC 3442](https://www.rfc-editor.org/rfc/rfc3442.html#section-3).
Client installation depends on DHCP client support. Without custom routes,
only ordinary subnet/router/DNS options are emitted.

## Apply / recovery

Save uses the existing network apply and confirmation flow. Confirm within
90 seconds or the prior Wi-Fi/LAN profile is restored. Open the new modem IP
to confirm reachability. USB recovery remains at `192.168.0.1/24`; changing
subnet does not configure a client's manual address automatically. Reconnect
or renew DHCP on USB/Wi-Fi clients to receive the new values. Manual clients
must be configured separately. The development Mac uses a manual USB address;
tests did not change it or its default route.

Persisted `settings.json` has a `lan` object with `subnet`, `gateway`,
`poolStart`, `poolEnd`, `dns`, `routes` (destination/gateway pairs), and derived
legacy `mode=STATIC`, `address=gateway/prefix`. Legacy address-only settings
migrate on load/PUT. Secrets remain excluded from public settings responses.

## Native ownership / boot

`control/lan.go` reuses vendor dnsmasq 2.88 and its existing lease file,
`/etc_rw_mbb/ztembb/configs/dnsmasq.leases`. It validates generated syntax,
atomically updates `/tmp/dnsmasq.conf`, and restarts only inventoried dnsmasq
processes whose executable and arguments point to that config. Upstream DNS
and unrelated vendor options are preserved. The first config is backed up to
`/mnt/userdata/mf79u/dnsmasq.vendor-before-network.conf` with mode 0600.
No second persistent DHCP daemon is added; lease duration is 24 hours.

Native WebUI reconciles confirmed LAN settings every 10 seconds, including
after vendor config regeneration. While a network apply is ready and awaiting
confirmation it maintains the candidate; rollback maintains the old profile.
The existing boot wrapper starts this binary. No new raw flash or full-image
build was done; the earlier experimental 0.9 image lacks these changes.

## Verification

`build/lan-dhcp-verification.json` links the installed control hash to evidence.
Go fixtures cover legacy migration, malformed pools/routes, exact RFC route
encoding, preservation of unrelated dnsmasq config and idempotence. A real
DHCP DISCOVER/OFFER probe over USB verified a temporary `192.168.7.0/24`
profile, gateway `.7.1`, DNS and the default + `1.2.3.4/32 via .7.10` route
in both 121/249. Explicit rollback restored `.0.0/24` and removed routes;
the original profile was subsequently applied and confirmed. No DHCP REQUEST
was sent and no lease accepted. IMS remained ready with unchanged SIP PID.

All five tabs passed desktop and 390 px overflow checks. Unchanged Save did
not open a network-confirmation prompt. Screenshot:
`build/ui-network-dhcp-desktop.png`. No calls or SMS mutations were performed.
Wi-Fi client lease acquisition and a full hardware reboot were not tested
in this change; the DHCP packet test used the shared bridge over USB.

## Cellular output policy and lab PBX return paths

LTE data off rejects ordinary IPv4/IPv6 forwarding through wan* and modem-local
output through wan*, with a local IMS wan5 exception. Root privileges do not
bypass this filter; ping over the wan1 default route can return Operation not
permitted. Cellular registration and GSM SMS storage remain possible. External
SIP then needs a reachable USB/LAN path; factory-reset design retains safe
mobile-data defaults, but factory reset itself is not implemented.

Docker Desktop can source PBX packets from the Mac primary uplink IPv4 rather
than the USB peer. Both the protected pbx-return-routes /32 entry through the
USB peer and SIP trustedPeers must match it; never replace the Mac default
route with the modem. Addresses 192.168.1.28 and 172.30.230.46 were observed at
different lab stages. Detect the current address before changing either setting;
a historical entry alone does not prove current PBX connectivity.

## B03 netlink compatibility update2026-10-08

Control falls back to sysfs and vendor ip address queries on Go netlink failure.
LAN reconciliation and UI clear the recovered LAN DHCP error. Existing addresses
and DHCP/settings are preserved; physical read/idempotence test passed. Details
and memory/latency evidence: [WEBUI.md](WEBUI.md).

## Wi-Fi Client update (2026-10-11)

The [Wi-Fi Client implementation](WIFI.md) detaches `wlan0` from `bridge0` and
uses its own DHCP lease, gateway routes and DNS. USB/LAN keeps the configured
static management address and vendor DHCP server. Client and management subnet
must not overlap; failure rolls back the previous network profile.
Wi-Fi DNS is maintained during the active uplink and restored on switching
back to Hotspot/disabled. The boot hook applies the saved Client profile;
`factoryHotspot` no longer replaces an explicitly saved Client configuration.

For an upstream Wi-Fi subnet matching the old `192.168.0.0/24`, choose a different
LAN subnet before saving Client settings. The Client implementation installs
the chosen management address before removing the conflicting known recovery
alias. Thus `192.168.0.1` is not a recovery endpoint during that connection.
The tested `Lipetsk-2G` upstream supplies `192.168.50.0/24`; it does not
conflict with management `192.168.0.0/24`. USB/LAN remains `192.168.0.1`.
An earlier overlap result was a bug comparing shared IPv6 link-local prefixes;
only IPv4 networks are compared now. The temporary `.79` trial was rolled back.

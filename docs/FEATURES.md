# Complete functional inventory

This matrix maps the existing functional requirements to the imported code,
package and verification. All paths below are relative to `firmware/mf79u`.
Historical physical results are preserved in the topic docs. They are distinct
from tests run during this migration and from a fresh live device test.

| Function | Imported source / packaged component | Evidence and boundaries |
| --- | --- | --- |
| Local CP IPC/PDP/SIM AKA | `src/cp-ipc.*`, `cp-pdp.*`, `native-gateway.c` → native | [AUTONOMOUS](../firmware/mf79u/AUTONOMOUS.md); local operation, no Mac relay |
| Operator IMS SIP/IPsec/media | `ims-userspace-ipsec.c`, `ims-software-media.c`, `vendor-codecs.c` → IMS media; private IMS recipe | [AUDIO-PATH](../firmware/mf79u/AUDIO-PATH.md), [CODECS](../firmware/mf79u/CODECS.md) |
| AMR-WB/NB modes, rate/CMR | `amr-rate-policy.*`, `ims-software-media.c` | WB 0–8, NB 0–7; operator negotiated/measured rate remains separate |
| Persistent GSM CS calls/clearing | `cs-voice-driver.c`, `cs-driver-runtime.inc`, `cs-voice-adapter.c`, state/wire/lease headers | [CS-AUDIO](../firmware/mf79u/CS-AUDIO.md), [GSM-VOICE](../firmware/mf79u/GSM-VOICE.md); MO/MT echo and timely hangup historically confirmed |
| CS audio and clarity | `cs-pcm-bridge.c`, `cs-pcm-clarity.h`, ring/SPSC/resample headers | Hardware 8k/160 → fixed external 16k/320; no GSM HD/UMTS claim |
| AUTO/VOLTE/CS/VOWIFI policy/fallback | native + `voice-registration-policy.h`, `voice-backend-policy.h` | [REGISTRATION](../firmware/mf79u/REGISTRATION.md); IMS failure fallback historically tested incl. reboot |
| ePDG/EAP-AKA/VoWiFi Wi-Fi/USB | `vowifi-*`, patched strongSwan + prepare/charon/swanctl + start/updown | [VOWIFI](../firmware/mf79u/VOWIFI.md), [CONNECTIVITY](../firmware/mf79u/CONNECTIVITY-20261011.md); live voice/audio boundaries remain dated |
| SIP Disabled/TRUNK/SERVER | `modem-sip-gateway.c`, `sip-settings.h`, `sip-registrar.h` | [WEBUI](../firmware/mf79u/WEBUI.md); SERVER has one account/binding, UDP; TRUNK UDP/TCP/TLS |
| SIP codec enable/order | Opus, G.722, PCMA, PCMU, G.729 via checked PJSIP/dependencies | [CODECS](../firmware/mf79u/CODECS.md); configurable independent of cellular codec |
| Caller ID / Privacy | `caller-id.*`, SIP gateway | From/PAI separate from auth username; Privacy retained |
| Cellular SMS read/send/manage | Control `sms*.go`, vendor API/native CP | [SMS-API](../firmware/mf79u/SMS-API.md); B03 SEND_SMS in supported non-VOWIFI modes |
| VoWiFi-only IMS SMS | `ims-sms-native.h`, Control `sms_ims*.go` + native/IMS | [SMS-IMS](../firmware/mf79u/SMS-IMS.md); no cellular fallback/retry; durable PDU before ACK, Unicode/concatenation inbox |
| VoWiFi-only voice + GSM SMS compatibility | `VOWIFI_SMS`, native registration/call admission + Control cellular SMS | [Compatibility mode](../firmware/mf79u/SMS-IMS.md#vowifi-only-voice-with-gsm-sms-2026-10-12); GSM2G/CFUN1 with CS voice flags0; no cellular voice or SMS transport failover |
| SIP MESSAGE/SMS confirmation/inbox delivery | `sip-sms.h`, Control SMS Unix IPC/job worker | [SMS-SIP](../firmware/mf79u/SMS-SIP.md); waits for confirmed submission, unconfirmed failure no auto resend; delivery ACK retained |
| Telegram incoming SMS webhook | Control `sms_telegram.go`, bound DNS/HTTPS + private queue | [WEBHOOKS](WEBHOOKS.md); optional delete after Telegram confirmation with durable handoff to connected SIP; source/fixture/device boundaries below |
| REST/login/CSRF/sessions/config | `control/*.go` embedded in Control | auth/error/recovery/config fixtures imported |
| Eight-tab English WebUI | `control/web/` + System JS | Status, Mobile, SIP, Messages, Webhooks, Wi-Fi, Network, System; framed blocks, scoped Save, no CDN |
| Hotspot / Client Wi-Fi scan/DHCP | `control/wifi*.go`, web app | [WIFI](../firmware/mf79u/WIFI.md); WPA2-Personal/Open, hidden/enabled/SSID/password |
| USB/LAN/static network/DHCP | `control/network.go`, network helpers | [NETWORK](../firmware/mf79u/NETWORK.md); shared USB/hotspot LAN, vendor DHCP retained |
| Ordinary LTE OUTPUT/FORWARD block | Control owned IPv4/IPv6 chains | IMS `wan5` remains allowed; external SIP needs viable USB/Wi-Fi route |
| Network/Wi-Fi LEDs | `net-led*.c` packaged LED daemon | [NETWORK-LED](../firmware/mf79u/NETWORK-LED.md); red/yellow/blue/purple/green/incoming combinations |
| System info/IMEI/error/NV tooling | `system-imei.c`, `control/system*.go`, IMEI branch recipe and tool | [SYSTEM](../firmware/mf79u/SYSTEM.md), [IMEI](../firmware/mf79u/IMEI.md); package installation reads/patches authorization, does not write IMEI |
| SSH/B03 BusyBox shell | patched Dropbear, BusyBox, `ssh-shell.sh` | [SYSTEM](../firmware/mf79u/SYSTEM.md); independent private credential store, no vendor passwd overwrite |
| Autonomous supervision/startup/ADB | start scripts + helpers and boot recipe | [ADB](../firmware/mf79u/ADB.md), [BOOT-MEMORY](../firmware/mf79u/BOOT-MEMORY.md); owned init ancestry and memory limits |
| SD read-only runtime/tools/backup | `sd-reread.c`, `sd-backup-server.c`, SD tools | [SD](../firmware/mf79u/SD.md); no simultaneous host/device RW mount |
| Diagnostics/recovery/emulation | All first-party source/tests/build/prepare/install tools | `make tasks`; checksum/ownership gates remain; private input recipes documented |
| Historical rootfs/image builders | original `build.sh`, `prepare.py`, `pack-image.py`, verifiers | Retained research workflow with private inputs; stale images not used by main install |
| Factory-profile-preserving Reset | design documentation only | [FACTORY-RESET](../firmware/mf79u/FACTORY-RESET.md); **not implemented**, no invented migrated implementation |
| Protocol research | original technical Markdown | [DSP-ABI](../firmware/mf79u/DSP-ABI.md), historical UMTS docs; dated research is not support |

`docs/migration-manifest.json` enumerates every imported file with source and
destination hashes and publication/build transformations. `make verify-migration`
checks all destinations; `make audit` checks source publication and documentation.
No secrets, device dump, SMS contents, recording or old compiled image is required
to preserve a feature's source code. Complete runtime packaging is independently
checked against the allowlist in `scripts/package.py`.

> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Linphone / SIP Server / VoWiFi Only

Updated: 2026-10-11. Physical MF79U, USB management192.168.0.1/24.
No reboot, rootfs/NAND flash or external PCM change is required.

## Test case

1. Verify no active call. Keep confirmed Wi-Fi Client epic-wifi connected with
   COMPLETED and a DHCP address; USB management remains unchanged.
2. Select SIP Server, account100, existing SIP password, bind192.168.0.1,
   UDP port5080. Preserve enabled codec order.
3. Select VoWiFi Only and Save. Expect effectiveVoiceMode=VOWIFI,
   imsAccess=WIFI, imsReady=true and voiceReady=true. Network LED idle purple5.
4. Add third-party SIP account in Linphone: username100, domain192.168.0.1,
   registrar sip:192.168.0.1:5080;transport=udp, UDP, existing SIP password.
   Expect localRegistered=true on modem and registered account in Linphone.
5. Dial the user-supplied test number. Expect native callBackend=ims,
   imsAccess=WIFI, activeCall=true and green network LED2. Answer the remote
   phone, verify speech in both directions, then hang up and verify both legs
   clear promptly. Do not count RTP counters as audible speech proof.
6. After clearing, retain SIP Server / VoWiFi Only and the Linphone account.
   Expect no active call and purple idle LED5. A Wi-Fi outage must block voice
   rather than start LTE/CS fallback; physical outage/recovery is a separate case.

## Current result

SIP Server and account100 already existed. VoWiFi Only saved; SWu established.
Provider-list automatic P-CSCF failover observed after SIP500. Linphone form
prepared, awaiting the actual existing SIP password; the protected browser
DOM exposes a redacted placeholder, so it cannot be used for authentication.
Actual Linphone registration and call/audio are not yet confirmed.

Implementation details and prior registration proof: [VOWIFI.md](VOWIFI.md).

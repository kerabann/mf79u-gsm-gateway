# WebUI gallery

Captured 2026-10-12 from the repository's HTML/CSS/JavaScript in Chromium.
These are real browser renders with **synthetic demo data**, not screenshots
of a connected modem or evidence of network/call readiness. Passwords are blank,
device identity is omitted, and the sample SMS contains invented text.

The overview is a labeled composition of two cropped screenshots. Every image
below is a full-page render. Open an image to inspect its original resolution.

![Desktop and mobile overview](assets/ui-overview.png)

| Tab | What you can manage |
| --- | --- |
| Status | Mobile/IMS/SIP state, signal metrics, interfaces, voice profile and access. |
| Mobile | Voice policy, LTE data blocking, VoWiFi source and USB gateway/DNS. |
| SIP | Disabled, PBX trunk or single-client server, codec order and connection settings. |
| Messages | Modem/SIM inbox, compose, read/delete and inline REST API documentation. |
| Webhooks | Telegram incoming SMS delivery, egress interface and delete-after-confirmation. |
| Wi-Fi | Hotspot or Client, SSID/password, scan/manual selection, security and status. |
| Network | Shared USB/hotspot subnet, gateway, DHCP pool, DNS and advertised routes. |
| System | Device information, administrator credentials, SSH, logs and guarded system actions. |

## All screens

<details>
<summary><strong>Sign in</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop sign-in](assets/screenshots/login-1280.png) | ![Mobile sign-in](assets/screenshots/login-390.png) |

</details>

<details open>
<summary><strong>Status</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Status](assets/screenshots/status-1280.png) | ![Mobile Status](assets/screenshots/status-390.png) |

</details>

<details>
<summary><strong>Mobile</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Mobile settings](assets/screenshots/mobile-1280.png) | ![Mobile voice settings](assets/screenshots/mobile-390.png) |

</details>

<details>
<summary><strong>SIP · built-in server</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop SIP server](assets/screenshots/sip-1280.png) | ![Mobile SIP server](assets/screenshots/sip-390.png) |

</details>

<details>
<summary><strong>SIP · PBX trunk</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop SIP trunk](assets/screenshots/sip-trunk-1280.png) | ![Mobile SIP trunk](assets/screenshots/sip-trunk-390.png) |

</details>

<details>
<summary><strong>Messages</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Messages](assets/screenshots/sms-1280.png) | ![Mobile Messages](assets/screenshots/sms-390.png) |

</details>

<details>
<summary><strong>Webhooks</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Webhooks](assets/screenshots/webhooks-1280.png) | ![Mobile Webhooks](assets/screenshots/webhooks-390.png) |

</details>

<details>
<summary><strong>Wi-Fi · Hotspot</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Hotspot](assets/screenshots/wifi-1280.png) | ![Mobile Hotspot](assets/screenshots/wifi-390.png) |

</details>

<details>
<summary><strong>Wi-Fi · Client and scan</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Wi-Fi Client](assets/screenshots/wifi-client-1280.png) | ![Mobile Wi-Fi Client](assets/screenshots/wifi-client-390.png) |

</details>

<details>
<summary><strong>Network</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop Network](assets/screenshots/network-1280.png) | ![Mobile Network](assets/screenshots/network-390.png) |

</details>

<details>
<summary><strong>System</strong></summary>

| Desktop · 1280 px | Mobile · 390 px |
| --- | --- |
| ![Desktop System](assets/screenshots/system-1280.png) | ![Mobile System](assets/screenshots/system-390.png) |

</details>

## Regenerate the gallery

Optional documentation tooling is pinned separately from firmware dependencies.
Node 24 and npm are required. From the repository root:

```sh
make docs-deps         # Locked Playwright and matching Chromium
make docs-assets       # Disposable loopback fixture; no modem access
make audit
```

To use an already installed browser, supply
`MF79U_BROWSER_EXECUTABLE=/absolute/path/to/chromium make docs-assets`.
`NODE_PATH` can select an existing Playwright installation. Otherwise the
repository's pinned local dependency is used.

The renderer serves the unmodified source UI and overrides fixture responses
with public demo values. It rejects external requests and unexpected writes;
the only POST is a simulated Wi-Fi scan. It checks ten authenticated views at
1280/390/320px for overflow, JavaScript errors and blank password fields. The
eight tabs plus trunk/Client variants produce twenty full-page screenshots;
two sign-in screenshots and the overview complete the gallery. A sanitized
validation report is written under ignored `reports/docs-assets.json`.
The public [provenance record](assets/provenance.json) contains browser versions,
source-asset hashes and screenshot hashes so readers can identify the capture.

SVG diagrams are editable repository assets, with accessible titles/descriptions.
They depict a simplified design and policy, not instrumented operator topology.
When the UI changes, rerun this target and review both desktop and mobile images
before committing. Device validation remains separate; see [TESTING](TESTING.md).

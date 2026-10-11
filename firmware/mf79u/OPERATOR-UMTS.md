> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Current operator UMTS check

Checked: 2026-10-10. Initial research was followed by an authorized bounded
physical WCDMA-only registration test. No voice calls or SMS were sent.

## Physical registration test (latest evidence)

**UMTS registration succeeded for the current Primetel SIM through Cyta PLMN
28001.** This does not establish an operational Primetel-owned UMTS RAN.

Stock B03 `zte_mifi` maps `Only_WCDMA` to 14 in its local preference table
(virtual address 0x551e8 string pointer / 0x551ec value 0x0e). The probe selected
`AT^SYSCONFIG=14,0,1,2` with checked readback, then re-enabled the radio.
Automatic operator selection remained enabled. Samples included:

```text
^SYSCONFIG: 14,0,1,2
+CREG: 2,1,"0087","00335234",2,1
+CGREG: 2,1,"0087","00335234",2,"01",1
+COPS: 0,2,"28001",2,1
^SYSINFO: 2,3,0,5,1,,4
```

CREG/CGREG status 1 confirms CS/packet registration; COPS access technology 2
confirms UTRAN/UMTS. Earlier samples used vendor access value 8; the conclusion
uses the later unambiguous value 2. This is network registration evidence only:
UMTS calls, CS audio, codec selection, and HD voice remain untested.

The existing supervisor was temporarily paused and the native controller allowed
to exit through its normal cleanup, releasing IMS/SIP/CS. No saved settings or
voice flags were changed. Original profile 27,0,1,2 and CFUN=1 were restored,
then the same supervisor resumed. Receipt:
`build/umts-registration-live-20261010-attempt2.json`.
Final checks confirm AUTO/VOLTE, LTE PLMN 28020, IMS ready, SIP gateway ready,
PBX contact available, unchanged boot ID, and the new native process parented by
the original supervisor. Native/SIP/CS processes were intentionally restarted;
their PIDs changed. The receipt's initial predicate only accepted PLMN 28020 and
therefore returned false; post-processing preserves that result separately and
records successful UMTS registration in PLMN 28001 from the captured samples.
The first preparation attempt stopped before selecting UMTS because its wait
misclassified the exited native process (zombie under the paused supervisor).
It restored LTE/IMS on the same boot; preserved receipt:
`build/umts-registration-live-20261010.json`. The probe now accepts a zombie as
an exited process and checks the published stopped state and suspended driver.

The sections below preserve the initial research context; the physical test
supersedes the statement that UMTS registration was not tested.

## Billing interpretation (2026-10-10)

The serving Cyta PLMN does not by itself change the subscriber's Primetel retail
plan. Domestic partner-network access is expected to retain domestic plan
charging; this is an interpretation, not a measured billing result or an
explicit Primetel national-roaming guarantee found in this check.
[Primetel plan terms](https://context.primetel.com.cy/giga-unlimited-and-international-traveller-mobile-plans-terms-conditions)
describe included national calls while in Cyprus. The exact active plan and
its domestic partner-network conditions have not been verified. Registration
status 1 is not proof of tariff classification. No billable call was made in
the registration test; no charge receipt exists.

## Live evidence

USB ADB device is present. `outputs/zte-native-usb 'AT+COPS?'` returned twice:

```text
+COPS: 0,2,"28020",7,1
OK
```

Serving PLMN is 28020 (Primetel), access technology 7 is LTE. Read-only native
status reports `state=ready`, `imsReady=true`, `voiceBackend=ims`,
`voiceMode=AUTO`, `registrationMode=VOLTE`, `callBackend=none`.
No UMTS registration was tested. A COPS display-format request (`AT+COPS=3,0`)
returned OK; the subsequent query still returned numeric format 2. This request
does not select a network or RAT. WebUI status could not be read anonymously
(HTTP 401); no credentials were printed or stored.

## Published evidence and conflict

- [Primetel infrastructure](https://business.primetel.com.cy/infrastructure-network)
  still advertises nationwide 3G and 4G/LTE coverage.
- [Primetel VoLTE FAQ](https://primetel.com.cy/volte-en) still describes fallback
  to 2G/3G outside 4G coverage. Neither page supplies a current verification date
  for those statements.
- [KORE network sunsets](https://www.korewireless.com/network-sunsets/) lists
  `CYPRUS | PRIMETEL | 3G | Shutdown finished`, without a completion date.
  This is KORE's published connectivity table, not a direct Primetel shutdown
  announcement. It conflicts with the operator's undated marketing/FAQ pages.
- [ITU PLMN allocation](https://www.itu.int/dms_pub/itu-t/opb/sp/T-SP-E.212B-2016-PDF-A.pdf)
  identifies 28020 as PrimeTel PLC; used for operator identity only.

## Initial research conclusion (superseded by physical test above)

Primetel historically supported UMTS/3G. Current availability on 2026-10-10 is
not confirmed; KORE reports shutdown completed. Do not treat UMTS as an available
production fallback based on the undated Primetel pages. The live observation
only proves current LTE/IMS readiness, not presence or absence of UMTS coverage.
Direct operator confirmation or a separate bounded on-device registration test
would resolve the conflict. Project UMTS CS/media support remains unimplemented
and unvalidated as documented in REGISTRATION.md; no AMR-WB over UMTS claim is made.

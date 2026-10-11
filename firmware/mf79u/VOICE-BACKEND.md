> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# История исследования голосового backend

## Current persistent runtime (2026-10-10)

The installed userdata runtime now includes `mf79u_cs_voice.ko`, a supervised
CS adapter and a streaming userspace PCM bridge; external PCM remains mono
PCM16LE 16000Hz, 320samples/20ms. The driver exposes `/sys/mf79u_cs_voice`,
starts suspended and stays pinned after detachment. Epoch/call IDs, lease,
real MM quiescence, DSP restoration and closed PCM ownership gate reuse.
SIP clock uses SCHED_OTHER rather than maximum realtime priority.

Production outgoing SIP→GSM tone/echo and prompt handset clearing20s were
confirmed; physical AUTO failed-IMS→GSM fallback also passed with unchanged
boot and native/SIP/adapter PIDs. Exactly one CS SMS was confirmed by the worker
and recipient. Incoming production tone/echo/clearing and fresh AUTO/IMS autoboot
are now confirmed, as is a40-second postboot fallback call. The user reports
muffled CS speech under both Opus and PCMU; the CS-only emphasis comparison
produced clearer echo. A false heartbeat expiry during DSP bootstrap was found
and corrected; a25-second outgoing call on the lease-fixed revision passed with
echo and normal clearing. The final revision starts MT media after SIP ANSWER
before CONNECT ACK; incoming tone/echo/normal clearing are user-confirmed without
reboot. AUTO/IMS standalone startup passed after the final fresh boot, with IMS
registered26s and SIP ready29s after native startup. Final receipts and revision
boundaries: [CS-AUDIO.md](CS-AUDIO.md).
The IMS audio path and shared resampler remain unchanged.
See [REGISTRATION.md](REGISTRATION.md) for current receipts and boundaries.
Sections below are historical diagnostic stages, including older “not installed”
claims. No older rootfs/SD image has been updated or raw-flashed.


### MO40: SIP echo и управляемый SIP отбой подтверждены (2026-10-10)

Пользователь: «Все рабоатет. Завершился на 28й секунде». Проверен новый
streaming тракт без диагностических DSP/ARM тонов: 2s tone создаёт PBX,
затем Echo; её absolute timeout25s даёт SIP HANGUP → stop только нашего
CS вызова. Оба события подтверждены отчётом; резервный CS timeout40s
не был причиной завершения. Kernel PCM не ограничен22s, userspace
`--stream` не ограничен30s; прекращение потока привязано к clearing.

Userspace frames1309/TX1311, UDP RX1251/TX1309, drop0/bad0, завершение
finished1/failed0, RAM buffers cleared. UDP empty58 включает запуск/отбой;
не заявлять отсутствие любых underruns. SIP received1261/sent1251,
queue underflows0/overflows0. Clock SCHED_OTHER0 подтверждён.
Boot e58dfbf0… и native1839/SIP1969 сохранились во время теста.
Callback/admission/MM/audio/profile27/flags0/0/guardsfalse/IMSready полностью
восстановлены. Временная PBX extension удалена, PBX idle, процессы теста закрыты.

USB появился после перестановки пользователем в другой порт; en10 вновь
192.168.0.169/24, IMS восстановился до теста. Перед этим пользователь сообщил
перезагрузку ноутбука. Не связывать старое отсутствие USB с отказом CS-кода:
MO40 тогда не был armed и не звонил. `build/cs-mo40-reconnected.json` — ранний
снимок до регистрации IMS; последующее IMSready есть в before/test и restore.

Evidence:
`build/cs-mo40-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-streaming-sip-control-{live,test,kernel,restore}.json`.
`build/cs-pcm-stream-build.json` связывает исходник и новые ARM binaries.
`test-cs-pcm-bridge-stream.py` запускает настоящий bridge с виртуальными
sysfs/clock/PCM2: поток45s, SIGTERM, preconnect timeout90s и сохранённый
старый30s diagnostic limit прошли UBSan. Буфер проверяется после erase.
Первый macOS ASan запуск превысил timeout и не засчитан; опубликован только
успешный UBSan результат `build/cs-pcm-stream-fixture.json`.

Это диагностический исходящий GSM вызов с PCM/SIP эхом и SIP управлением
отбоем. Постоянный CS adapter, входящий GSM→SIP с ответом по SIP ANSWER,
повторные вызовы одним модулем и автоматическое переключение IMS/CS ещё
не установлены. Production binaries, автозапуск и firmware package не обновлялись.
Следующий этап требует убрать one-call budget только вместе с полным
переинициализированием PCM/CC и проверкой epoch/call ID; нельзя просто
оставить существующий диагностический hook активным навсегда.

### MO40: подготовка до переподключения USB (история 2026-10-10)

После успешного MO39 модем перестал отображаться в USB/ADB. Пользователь
сообщил, что ноутбук перезагружался. Причина отсутствия USB не установлена;
это не подтверждённая перезагрузка модема. MikoPBX запущена. Попытка MO40
завершилась на первой проверке ADB, до guards, radio changes, arming и dial.
Последнее подтверждённое восстановление IMS — MO39, 17:39:05 UTC.
Снимок: `build/cs-mo40-usb-unavailable.json`. Перед продолжением нужна свежая
проверка модема, адресов, IMS, отсутствия звонка и временных обработчиков.

Streaming module собран offline, relocation audit passed:
`build/cs-mo-probe40-build.json`. В отчёте явно отключены DSP/ARM tones и
локальное kernel echo; отсутствует фиксированный media deadline. PCM ABI
сохранён: mono PCM16LE 16000 Hz, 320 samples/20 ms; аппаратный порт 8000 Hz.
На том этапе: CS backup timeout40s, userspace bridge limit30s (позднее снят),
PBX tone2s/echo/absolute25s. Эти тестовые ограничения ещё не production.

`test-cs-sip-hangup.py` проверил единственный owned CS stop при повторном
SIP HANGUP, отсутствие лишнего stop после remote CS clear и cleanup при
ошибке SIP setup. `test-cs-audio-lifecycle.py` с UBSan проверил оба режима:
старый diagnostic deadline и3600s виртуального streaming без media timeout;
clocks сохраняются до MM idle. Это проверки исходников без аппаратуры.
Результаты: `build/cs-sip-hangup-fixture.json`,
`build/cs-audio-lifecycle-test.json`. Persistent CS adapter, повторные вызовы
одним модулем и автоматический voice fallback всё ещё не установлены.

### MO39: исправлен отбой GSM, телефон завершил вызов на20s (2026-10-10)

Пользователь подтвердил автоматическое завершение на20-й секунде.
Единственное изменение сигнализации — coding Cause Q.931(0)→GSM PLMN(3).
DISCONNECT с cause16/coding3 отправлен2082.558s, RELEASE пришёл2082.732s
теперь также с cause16/coding3 (ранее126/coding3). CONNECT2063.772s;
полный локальный cleanup2083.699s. Задержка70s в этом сравнении устранена.
Ответ пользователя не содержит отдельного подтверждения эха в MO39;
предыдущие MO36–38 содержат подтверждённое эхо.

Без перезагрузки, прежние boot/native1681/SIP1779. Callback/admission/MM,
аудио, profile27, flags0/0, guardsfalse и IMSready восстановлены.
Kernel RX635/TX637, dropped0/busy0, TXempty32words: не заявлять нулевой jitter.
`build/cs-mo39-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-{live,test,kernel,restore}.json`.

Следующая проверка MO40: тот же duplex без диагностических DSP/ARM тонов
и22s media deadline. Звук живёт до clearing, затем silence до MM idle.
SIP HANGUP от PBX через25s направляется только своему одноразовому CS
обработчику; kernel40s остаётся страховочным лимитом теста. Production
adapter, многократные звонки одним модулем и автоматический fallback
ещё не установлены. UBSan fixture покрывает непрерывный поток за пределами
старого deadline и сохранение clocks до MM idle; аппаратный тест ожидается.

### Исправление Cause перед MO39 (2026-10-10)

В MO/MT/ring обработчиках исправлено поле Cause: октет `0x80` (Q.931)
заменён на `0xe0` (GSM PLMN, location=user). Причина16 и формат LV для
DISCONNECT / TLV для RELEASE сохранены. TS24.008 §10.5.4.11, table10.5.122
требует GSM-кодировку для представимых причин; поддержку Q.931 сеть
обеспечивать не обязана. Полученное ранее coding3 означает GSM PLMN,
не national (national=coding2); cause126 трактуется как127 по table10.5.123.
[ETSI](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/08.16.00_60/ts_124008v081600p.pdf).
Нарушение кодирования было подтверждено до MO39; последующий MO39
подтвердил устранение задержки в этом сравнении (см. выше). ASan/UBSan проверили MO/MT Cause, переходы, границы чтения;
ring fixture также прошёл. MO39 сохраняет звуковой тракт/таймер18s,
ASC18 наблюдает150s; задержка MM отключена (default0).

Статический B03 аудит проследил передачу без изменения байтов:
AAD4 → BF28E340 → ABA8 → BF043728/BF04294C → BF04337C → B29B.
Флаг1 выбирает SAPI0; длина в байтах, копируются ровно length байтов.
Это доказательство структуры кода, не регистрации передачи по эфиру.
`build/cpko-asc-raw-send-audit.txt` и `build/cpko-gsma-dispatch-audit.txt`.

Normal-clock SIP candidate также прошёл изолированный controller fixture
(синтетический CS child, ownership/fallback/crash recovery) и все пять
кодеков на ARM: `build/sip-normal-clock-controller-codecs.log`.
Постоянный аппаратный CS adapter/fallback по-прежнему не установлен.

### IMS baseline: immediate remote hangup confirmed (2026-10-10)

The same ordinary SIM/destination was called through the installed IMS/SIP
runtime, without radio or PBX configuration changes. Synthetic tone followed
by RAM-only echo; SIP BYE sent exactly18s after200/ACK and acknowledged1ms
later. User confirmed handset release immediately when echo stopped (no exact
handset second supplied). RTP900received/900sent; same boot/native1681/SIP1779,
IMSready, no active call. `build/sip-cellular-ims-baseline1.json`.
The70s clearing delay is specific to the tested CS scenario; do not attribute
it to the user's timer or claim that local RELEASE proves remote clearing.

The new normal-clock production candidate also passed all four isolated ARM
SIP/RTP<->PCM2 cases (PCMU/PCMA, both call directions, backend loss rejection).
`build/sip-normal-clock-media-fixture.log` and `build/sip-cs-media-fixture.json`.
The first host attempts were inapplicable (container guard, Python3.14 lacks
audioop); the successful rerun used the disposable build container. Neither
fixture touches the physical modem. Persistent CS adapter remains unfinished.

### MO38: MM-release delay excluded; third SIP/CS echo without reboot (2026-10-10)

User confirmed echo until20s and automatic handset clear70s. The new2s MM
release delay was armed at1134.978s after queued RELEASE COMPLETE, but RR
release arrived1135.378s and genuine MM release reason10 ended the local call
before our deferred MM request ran. Thus immediate AA3E is not required for
this early channel release or the remote delay. No delay promotion to default.
Full callback/audio/register/profile/flag/guard/IMS restoration passed on the
same boot/native/SIP. Third consecutive echo call without spontaneous reset.
Receipts `build/cs-mo38-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-*`.

The supported normal-clock wrapper is now shared as `src/sip-clock-policy.c`
and linked by `build-sip-gateway.sh`; the diagnostic includes the same source.
Both production candidate SIP and codec selftest built successfully (expected
static-glibc DNS warnings); `build/sip-normal-clock-build.json` binds hashes.
No candidate installed, no old package/rootfs receipt updated as current.

`test-sip-cellular-call.py` adds a direct, single authorized SIP/PCMU call through
the installed backend: RAM-only tone/echo, BYE at18s, unchanged radio/PBX/processes,
number stdin only, scalar reports. Offline G.711 vectors and bounded RTP header
parsing passed. The next comparison is IMS on the same SIM/destination; it is
not an implementation of the persistent CS adapter or automatic voice fallback.

### MO37: echo until20s, handset release70s, no reboot (2026-10-10)

The user corrected the initial report: echo stopped around20s, not2s. Remote
handset cleared itself at70s. ASC saw DISCONNECT775.575s, cause16/coding0/loc0,
network RELEASE775.716s, cause126/coding3/loc0, and RELEASE COMPLETE775.717s.
MM release was queued immediately after RC, AADA followed within1ms, RR release
arrived776.110s. No repeated CC RELEASE reached ASC during the remaining watch.
ASC restored at836.279s, about79s after CONNECT: the reported70s remote clearing
preceded radio restoration. The late independent MM/SS exchange was observed
only as scalar metadata; its content was not read or saved.

This is the second consecutive SIP/CS echo test with a measured SCHED_OTHER0
clock and no reboot. Kernel RX626/TX628, dropped0/busy0/TXempty0; SIP PCM queue
underflow0/overflow15. Same boot/native/SIP; ordinary profile/flags/guards/IMS
fully restored. Production binaries/fallback unchanged.

Evidence: `build/cs-mo37-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-{live,test,kernel,restore}.json`.
The RELEASE response alone does not acknowledge remote-user clearing:
[TS24.008 section5.4.3](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/04.09.00_60/ts_124008v040900p.pdf).

### MO38 preparation: isolate final-message delivery from MM release

Optional diagnostic `--mm-release-delay 2` queues RELEASE COMPLETE immediately,
then lets the original lower layers run for at least2s before requesting MM
release. CC/ASC never sleep; monotonic deadline is checked by the existing CC
command path. Network MM release still wins immediately. It is a delivery-race
hypothesis, not a confirmed fix. Default delay remains0; builder/armer require
matching receipt. ASC lifetime150s prevents radio restoration during the90s
remote observation window. No production change. Existing Cause/MO sanitizers
and PCM lifecycle tests passed; pending hardware test.

### MO36: SIP echo confirmed, no reboot; remote clearing still delayed (2026-10-10)

User confirmed tone and SIP echo; the handset ended automatically at77s.
Local CONNECT219.570s, DISCONNECT238.377s (~18.8s connected), network RELEASE
238.567s, RELEASE COMPLETE238.567s, MM idle239.365s; audio/callback/admission
restored239.555s. Local release does not prove timely remote clearing.
The shared B03 N(SD) allocator was used: SETUP2, CONNECT ACK3, DISCONNECT0,
RELEASE COMPLETE1. This did not fix the handset delay.

Diagnostic SIP clock was measured SCHED_OTHER0. Same boot a7acac28… and
production native1681/SIP1779 survived; profile27, flags0/0, guardsfalse and
IMSready were independently restored. User confirmed bidirectional media via
MikoPBX. Kernel RX666/TX668, dropped0/busy0/TXempty0; SIP PCM queue had8
underflows and9 overflows, so do not claim zero jitter throughout the path.
This supports the priority fix, but one successful call is not a repeated-call
stability proof. Production CS/SIP fallback is still not installed.

Evidence: `build/cs-mo36-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-{live,test,kernel,restore}.json`.
Kernel SHA256 `1b9fa54def12b5d213539916aeb39cc9842058008053a65e7edfa339809da2ec`.
Diagnostic SIP SHA256 `35f3da17dca4aaf9bc42749f3881d0afa40231dd1453707907d52a2027fabe2c`.
No production binary changed. Next: passive ASC clearing metadata under the
same measured clock policy; audit MM release ordering before changing it.

### Normal-priority SIP/DSP overlap passed; IMS recovery still incomplete (2026-10-10)

Diagnostic SIP SCHED_OTHER0 plus the unchanged idle DSP/I2S probe completed:
three tone on/off/on phases, registers/AP fields restored, module unloaded,
synthetic media400sent/388received, echo energy0.999846. No reboot, no captured
fault, same production PIDs and boot. Prior SCHED_RR99 overlap failed before
phase0 completed. This supports the scheduling hypothesis; it is not yet a
repeated-call stability proof or a production fix.

`build/cs-sip-dsp-load-{live,kernel}-normal-clock-cycle1.json`. Automatic restore
waited100s for IMS and expired. Radio profile27, flags0/0 and guardsfalse were
restored on the same boot; IMS was still unavailable after another100s. Two
IMS attempts logged `CP_FAILURE tag=AT+ZPDPDEACT=5 errno=110`; no AKA values or
SIP messages saved. Recovery cannot be called complete. See
`build/cs-sip-normal-clock-overlap-recovery.json`.

IMS recovered late: the pre-reboot snapshot already shows IMSready. The
deliberate ordinary software reboot then executed; it was unnecessary for IMS
recovery. `build/cs-sip-normal-clock-deliberate-reboot.json` preserves both
snapshots. Do not count this deliberate reset as a spontaneous reboot.

Offline `test-cs-nsd-b03.py` emulates the exact B03 allocator instructions:
all four initial counter values and both stubbed SIM contexts return/increment
modulo4 and write only the selected two-byte state. Device not accessed;
`build/cs-nsd-b03-offline.json`. The subsequent MO36 implementation uses this helper.
Sequence requirement: [3GPP TS24.007 section11.2.3.2.3](https://www.etsi.org/deliver/etsi_ts/124000_124099/124007/16.03.00_60/ts_124007v160300p.pdf).

### Reboot reproduced without a SIM call; normal-priority SIP diagnostic (2026-10-10)

MO35 used an18s connected timeout and unchanged20s PCM duration. USB disappeared
about6s after CONNECT, before any timeout/stop-enqueue/DISCONNECT receipt. User
heard only a tone; no echo; handset ended itself at32s. Delayed network cleanup
after loss of the modem is plausible, not established. MO35 exact artifact is
quarantined. Original failure receipts retain runtime_restored=false; separate
`build/cs-mo35-reboot-recovery.json` confirms restoration after that reboot.

`test-cs-sip-dsp-load.py` then overlapped the previously checked idle DSP/I2S
loop and synthetic SIP/PCMU/PBX media. **No SIM call and no CC hooks** were used.
SIP connected while I2S was active, then USB disappeared before the first1.6s
phase completed. Thus CC clearing and the call timeout are not necessary for
this reboot. No fatal kernel or userspace fault receipt was captured. The test
still had GSM registered; it is not an electrical power measurement.

Evidence preserved as `build/cs-sip-dsp-load-{live,kernel}-before-normal-clock.json`.
`build/cs-sip-dsp-load-reboot-recovery.json` confirms new boot b4066e72…,
native1575/SIP1631, profile27, flags0/0, guardsfalse, IMSready and PBX idle.

Source audit found PJMEDIA's null-device clock requests SCHED_RR99. Live
production SIP thread metadata confirms policy2/rt_priority99, above CP and
watchdog threads. Causation is unproven. A diagnostic-only link wrapper requests
PJMEDIA_CLOCK_NO_HIGHEST_PRIO using the supported master-port option, preserving
the library lifecycle; installed IMS/SIP binaries and libraries are unchanged.
`build/cs-sip-normal-clock-synthetic-live.json` confirms all diagnostic threads
SCHED_OTHER/priority0,400 sent/399 received, echo energy0.99991, zero PCM
underflow/overflow, same boot/production PIDs/IMS and PBX cleanup. SIP SHA256
35f3da17dca4aaf9bc42749f3881d0afa40231dd1453707907d52a2027fabe2c. The no-call
DSP/SIP overlap now requires measured normal clock policy before DSP startup.
Do not repeat the unchanged failing combination.

A separate previously documented gap remains: raw CC sends bypass B03's shared
N(SD) modulo4 sequence allocator at BF29BE71. It may explain remote clearing,
fixed in the subsequent MO36 diagnostic, without correcting remote clearing. Production CS/SIP fallback is unfinished.

### MO34: PCM stopped safely, then reboot; ordinary IMS restored (2026-10-10)

User: «После прекращения звука, вызов не сбросился, а модем перезагрузился».
Connected624.755s; PCM630.294s; stop650.294s. Live kernel capture confirms
PCM queues cleared once, RX999/TX1001 frames, dropped0/busy0/TXempty0,
and **clocks retained**, with no DSP close yet. SIP emitted STATS, ENDED487,
PCM_QUEUE(received999/played981/underflows0/overflows7). The bridge finished
normally after999frames. Last host sample651.18s still had state5 and
7420KiB free/10892KiB cache/5632KiB free swap, then USB disappeared.
Thus early DSP/clock close is not sufficient to explain this reboot.

There was no diagnostic user-fault receipt. This is not proof that every
process or the kernel was healthy. The first capture allowlist omitted
several vendor M0/ZSP/CAP ramdump prefixes; version2 now includes those exact
metadata prefixes and allocator/watchdog failures. Full unfiltered kernel
logs, audio and memory dumps are not saved. No panic/sysctl setting changed.
MO34 exact module is quarantined; do not infer stability from clean PCM stop.

Reports: `build/cs-mo34-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-{live,test,kernel}.json`.
Failure receipt remains runtime_restored=false. Separate
`build/cs-mo34-reboot-recovery.json` confirms boot2ba4a627…,
native1432/SIP1507, ordinary profile27/flags0/0/guardsfalse and LTE/IMSready.
No call or capture process remains armed. Production binaries unchanged.

User confirmed a passive USB-C/USB-A adapter and reports stable IMS calls.
Read-only Mac16,7 IORegistry audit: all three AppleT8132USBXHCI controllers
advertise the same sleep/wake port current limit, 3000mA; the modem allocation
is 500mA on controller location0x02000000. No higher-limit controller was
observed. These values are configuration/allocation metadata, not measured
current, voltage, or a guarantee of 3A through this legacy-device adapter.
No power fault is established; stable IMS prioritizes investigation of our
experimental CS/DSP path. Another port can compare the physical connection,
but increased available current has not been demonstrated. Mac was on battery.

`build/cs-usb-port-power-audit.json` records the read-only check. Same modem
boot2ba4a627…, native1432/SIP1507, IMSready and no active call/CS observer were
rechecked. No new SIM call, radio transition, power setting or binary change.
The source review of CS timeout/queue teardown found no proven reboot cause.
Production CS/SIP/fallback and repeated-call stability remain unfinished;
MO32 speech echo remains proven.

### Diagnostic SIP fault capture: three no-SIM regressions passed (2026-10-10)

`build/cs-sip-pcm-fault-handler-cycle{1,2,3}.json`: real on-device diagnostic
SIP/PCMU and MikoPBX, synthetic PCM only. Each run passed, IMS/boot/production
PIDs preserved, temporary PBX extension removed and PBX idle. No fault receipt.
The new handler does not reproduce or explain MO33. Kernel capture now starts
before GSM preparation and closes independently even after a failed call.

MO34 is an instrumented repeat, not a claim that the hardware failure is fixed:
it retains the unproven deferred-close candidate and adds the checked SIP/PCM
fault handlers plus live kernel metadata. Exact failed MO32/MO33 artifacts
remain quarantined. Production binaries and panic sysctls stay unchanged.

### MO33 recovery; user-process panic path and crash instrumentation (2026-10-10)

Ordinary LTE/IMS restored, flags0/0/profile27 and both guardsfalse, boot29c49b43…,
native1619/SIP1698. `build/cs-mo33-reboot-recovery.json`. PBX has0 active calls.
MO33 failure receipt remains runtime_restored=false; recovery is separate.

Live B03 has vm.ramdump_on_user=1, vm.ramdump_on_panic=1, vm.panic_on_oom=2,
kernel.panic_on_oops=1 and panic_on_abnormal_exit_pid=0. The matching SDK
fs/exec.c do_coredump calls ramdump_entry when sysctl_ramdump_on_user is set;
B03 image strings also contain "User ramdump enabled, user panic". Thus a
userspace fault is a concrete alternate reboot mechanism, not proof that
SIP actually faulted. No panic policy was changed and no crash was induced
on the modem. /proc/last_kmsg, pstore and /proc/kallsyms are unavailable.

Diagnostic-only SIGSEGV/BUS/ILL/ABRT/FPE handlers now emit signal/code and
PC/LR/SP/fault addresses, then _exit without a core dump. No memory content,
SIP credentials or speech is logged. Production builds omit the handler.
Host handler fixture passed; cross-compiled soft-float binaries built with
strict warnings. The SIP debug ELF is retained only on the host for symbol
lookup. `build/diagnostic-fault-host-test.json`.

`cs_kernel_failure_capture.py` streams a metadata allowlist from /proc/kmsg;
unrelated kernel text is discarded. Idle start/owned stop and filter tests
passed: `build/cs-kernel-capture-idle-test.json`. No firmware/panic setting
was modified. Synthetic SIP/PBX regression is underway before another SIM call.

### MO33: reboot before shutdown test; collect kernel failure evidence next (2026-10-10)

User: «перезагрузился сразу как прозвучал первый тон». PCM began at596.613s;
last host sample597.07s, SIP_MEDIA_CONNECTED arrived, but no1s bridge window
or PCM stop event. Therefore the deferred shutdown change was **not exercised**,
and early hardware close cannot explain every reboot. Last memory sample:
MemFree3148KiB/Cached14916KiB/SwapFree7516KiB. Neither OOM nor driver panic
is confirmed. MO32 remains the successful physical SIP speech result.

`build/cs-mo33-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-{live,test}.json`.
Exact module c20295a9… quarantined. The temporary PBX extension was removed;
PBX idle must be rechecked after its absolute timeout. USB disappeared and
restoration did not run: persistent test guards/profile may remain. Do not
claim the earlier MO32 recovery receipt is current after this failure.
Before any new call, recover ordinary profile/IMS and arrange live kernel
failure capture. Current panic_on_oom=2 may turn memory exhaustion into a
reboot, but that setting alone is not evidence of OOM. No further call is armed.

### MO32: real GSM/SIP/PBX speech echo; reboot at media shutdown (2026-10-10)

User confirmed **«эхо есть»**. MO32 second attempt passed actual GSM speech
through ARM1, the userspace PCM bridge, diagnostic SIP/PCMU and MikoPBX Echo.
The bridge received999/sent1001 PCM frames, UDP RX984/TX999, bad0/full0;
per-second SIP and bridge speech levels agree in both directions. This is a
physical speech result, distinct from the earlier synthetic SIP fixtures.
`build/cs-mo32-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-{live,test}.json`.

The modem unexpectedly rebooted around the20s PCM deadline. Last host sample
was uptime446.46/state5; PCM began426.732, expected stop446.73. The bridge saw
PCM offline and finished, then USB disappeared. No final kernel restore log
survived. Memory pressure is not established: the last sample had3216KiB free,
15564KiB cached and6448KiB swap free; SIP was started after GSM registration,
with its executable in userdata. Premature DSP/I2S shutdown while GSM remains
connected is the current hypothesis, **not a confirmed root cause**. The exact
MO32 module SHA a77aee22… is quarantined; the interrupted report retains
runtime_restored=false. PBX extension was removed; after recovery PBX has0 calls.

`build/cs-mo32-sip-echo-reboot-recovery.json` independently confirms ordinary
profile27/flags0/0, guardsfalse and LTE/IMSready on new boot2eed8c87…,
native1362/SIP1382. Production binaries were not replaced. Diagnostic SIP
checksum-owned executable remains in userdata for the next test; it is not a
boot service. No speech or destination was saved.

The new MO userspace variant closes/clears PCM once at the deadline, then
feeds silence and retains both clock paths through DISCONNECT/RELEASE/MM
clearing. Full DSP/register restoration waits for MM idle. The same applies
to remote clearing before the deadline. Signaling timeout remains bounded;
remote hangup correctness is still separate. Instance range extended to64 to
preserve unique historical receipts. MO33 will test this shutdown change.
Offline lifecycle fixture passed (actual step/hold code, UBSan): timed stop,
remote clearing, silence, single PCM close, hardware close only at MM idle.
ARM build c20295a9… passed kernel relocation audit. Receipt:
`build/cs-audio-lifecycle-test.json`. Host ASan stalled before main in the
macOS runtime; it was stopped, so no ASan pass is claimed.
Production CS/SIP fallback and repeated-call stability remain unvalidated.

### MO32 pre-call reboot; memory-pressure mitigation (2026-10-10)

A second unexpected reboot occurred during radio_on in GSM preparation,
before loading MO32, starting PCM or issuing DIAL. Diagnostic SIP was already
listening. This rules out the new MO32 audio handler as the immediate trigger;
it does not establish the cause of MO29. Failure receipts were archived as
`cs-mo32-precall-reboot-{test,preparation}.json`. Independent cleanup removed
the PBX extension despite USB loss. `cs-mo32-precall-reboot-recovery.json`
confirms current IMSready, profile27/flags0/0/guards false, native1595/SIP1693,
boot1d95f647-2ca6-415e-a368-6124118e1749, no diagnostic modules after reboot.

Live B03 has panic_on_oom=2 and /dev mounted tmpfs (not ramfs). OOM is a
hypothesis; no panic log survives. Avoidable memory pressure: an additional
4.2MiB SIP executable in tmpfs plus a second SIP process during radio changes.
The test now starts private SIP only AFTER GSM registration and uses a
checksum-named mode0700 userdata code file, allowing clean code pages to be
discarded. Upload staging is removed before execution; minimum userdata free
space is checked. This is a temporary diagnostic file, not an installed boot
service or raw-flash operation. Config/identity/PCM remain in RAM.
Cache receipt records storage/path/checksum; remove the owned file after use.
Radio preparation now records incremental scalar memory snapshots.
MO32 instance remains unused and can be armed after the corrected preparation.

### Instrumented SIP path validated; MO32 plain media test prepared (2026-10-10)

New diagnostic SIP SHA256 a6876f4b1a3a5b30ebe8b6d13a15cb42f7ae48adde37861c76cab740a30e1687
passed no-SIM PCM/PBX echo: 400 sent/399 returned, tone fraction0.999958,
SIP queue underflow/overflow0. Diagnostic PCM_LEVEL saw peak8000 on input
and7938 on returned echo, confirming both measurement points. Original
pre-instrumentation receipt is `cs-sip-pcm-synthetic-pre-levels-live.json`;
current `cs-sip-pcm-synthetic-live.json` identifies the new binary.
Old cache removed after checksum/boot verification; one new cache remains.

MO32 uses plain `--sip-media` (no comparison routing), the MO31-confirmed
userspace PCM path, and this instrumented SIP binary. It collects levels
at GSM RX, SIP conference input/output and PCM return, plus incremental
kernel/memory metadata. No production installation; MO29 cause still unknown.

### MO31 userspace echo passed; diagnostic SIP levels added (2026-10-10)

User confirmed speech echo through the current SPSC/userspace resampler.
The remote party ended after about15s connected, so the PCM stage lasted
10.1s (not a completed20s stability run). RX506/TX508 frames, kernel TXempty0,
RXdrop0/busy0, userspace tx_full0, failed0. Per-second GSM RX peaks reached4385;
levels later fell as speech stopped. Exact raw speech was not saved.
MemFree minimum observed approximately2.3MiB with17MiB Cached and5.3MiB free
swap; no reset occurred. `cs-mo31-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-*`.
IMS/profile/flags/guards/callbacks/MM restored, same boot/native1710/SIP1798.

The diagnostic-only SIP build now emits one-second PCM_LEVEL aggregates at
the conference input/output. Production builds omit this code. New build
passed strict ARM soft-float compilation; synthetic SIP/PBX validation is
running before another physical test. A checksum/boot-verified old RAM cache
is removed before a new SIP build upload to avoid retaining duplicate4.2MiB
binaries. Planned MO32 is the plain SIP media test (no MO29 comparison mode),
with three measurement points and incremental kernel/resource metadata.
The MO29 reboot cause remains unknown; no stability claim is made.

### MO30 baseline echo passed; IMS restored (2026-10-10)

User confirmed speech echo. The short ARM1 kernel path matched MO26 in
.text/relocations/data/rodata byte for byte. RX speech peak4017,
TX22797/RX22794 words, echo TXnonzero14832, underrun324/overrun0, failed0.
Channel1/mode9 matched MO26/27/28. Callback/MM/clock/register restoration
passed on the same boot/PIDs. After GSM→LTE reattach IMS registered again:
native1710/SIP1798, ringOnly=false/csOnly=false, profile27/flags0/0.
`cs-mo30-full-voice-arm-echo-arm1-rx-only-tx-switch-{live,test,restore}.json`.
Earlier IMS500/reboot recovery receipts remain historical failure evidence.

Prepared MO31: current userspace PCM/SPSC echo without SIP, bounded20s.
Per-second speech level metadata is flushed immediately, and DIAL snapshots
also preserve bounded MemFree/Cached/Swap/Slab/uptime counters. This isolates
the userspace audio leg while avoiding the MO29 combined SIP comparison.
No cause for the MO29 reboot is claimed, and that exact module stays blocked.
Production CS↔SIP and automatic fallback remain uninstalled.

### Recovery status and short baseline isolation prepared (2026-10-10)

User confirms no physical power/USB intervention during MO29. Kernel text,
relocations, data and rodata match MO28 byte for byte (`cs-mo29-offline-audit.json`);
this excludes a new kernel-code change, not an existing race or hardware fault.
The new userspace comparison passed no-SIM on-device SIP/PBX test:
`cs-sip-pcm-compare-synthetic-live.json`, 401 source frames, 400 UDP return,
no drop/bad, 500 Hz energy fraction0.999244, stable per-second level metadata.
Runtime policy/processes unchanged; IMS was already unavailable before it.

Controlled reboot restored ordinary LTE policy/flags/guards, but IMS still
returns500. Do not call this fully restored IMS. Temporary PBX resources are
removed. Cleanup now attempts PBX and RAM resources independently on USB loss;
failure-injection fixture passed and metadata survives cleanup errors.
DIAL snapshots now save the existing sanitized kernel metadata every2s.

Prepared MO30 short baseline: known MO26 ARM1 kernel echo, no userspace PCM,
no SPSC transport and no isolated SIP. This is a regression/isolation test,
not a repeat of the quarantined MO29 combination. Explicit --allow-unregistered
accepts only pre-existing IMS unavailability; it still requires ordinary
profile27/flags0/0, no call, and restores/checks LTE registration, callbacks,
MM, guards and the same boot/PIDs. Reports retain actual ims_ready=false;
default tests still require IMS readiness. No production firmware installed.

### MO29 interrupted by reboot; recovery in progress (2026-10-10)

User heard a beep, no echo. The one authorized DIAL write succeeded;
status reached CONNECTED (state5), and the userspace bridge became online.
Then USB disappeared. Boot changed from `1c2740a7-7cbf-49e2-b08e-bc6c1e476282`
to `7d74c305-5d77-435c-b8ef-35b8aafa5f72`; all RAM modules/endpoints vanished.
No previous-kernel log is available. Cause is UNKNOWN; no new call is armed.
MO29 module SHA256 `e2ec138969a20ae4dfc13660c01d4869e89fe83c277b64c7a3f49d986520d7fe`
is blocked in the armer. Its call/audio/PCM source hashes equal MO28; changed
userspace comparison and the runtime state still require isolation.
Per-second bridge metadata was buffered and lost at reboot. It now flushes
line by line; this change improves evidence and is not a crash fix.

PBX temporary extension removed and zero active channels confirmed. Radio
profile27/voice flags0/0 restored. IMS initially returned500; a controlled
reboot under the restored ordinary policy is underway. Recovery receipt:
`build/cs-mo29-reboot-recovery.json`. The original interrupted test report
must retain `runtime_restored=false`; recovery is a separate operation.
Production voice/fallback was not installed. RAM SIP cache disappeared
with reboot, so its old receipt is historical.

### SIP software path verified; prepared MO29 local/PBX echo comparison (2026-10-10)

Two no-SIM tests passed on the modem with the real isolated SIP binary and
MikoPBX Echo: `build/cs-sip-pcm-synthetic-live.json` returned a 500 Hz tone
(energy fraction 0.999958), and `build/cs-sip-pcm-bridge-synthetic-live.json`
verified the actual 8→16→8 kHz bridge code (0.999882, RMS5686.83).
The latter sent404/received403 UDP frames, with drop/bad0; SIP played404,
queue underflow/overflow0. Synthetic sysfs was used; this does not prove
physical GSM speech through SIP. No SIM/CP access or audio persistence;
PBX extension/process removed, IMS/PIDs/boot unchanged.

MO28 physical speech echo remains unconfirmed. Prepared `--sip-compare` for
MO29: same verified hardware profile and SPSC transport, then three seconds
of local userspace speech echo, a half-second 2 kHz marker, and PBX echo.
The UDP path runs throughout. One-second peak/energy/active-sample metadata
compares GSM RX with PBX return without saving speech. This comparison has
not yet run. Production CS call control and IMS fallback remain uninstalled.

### MO28 SIP/PBX: тон есть, эха нет; проверяется обратный RTP (2026-10-10)

Пользователь: «писк был — эхо нет». GSM→userspace999 frames/20s,
RX157845 nonzero samples; PCM2 UDP TX999/RX997, drop/bad0, empty5.
SIP queue received999/played999/underflows0/overflows0/high_water5;
PCMU negotiated, SIP_MEDIA_CONNECTED. Из PBX только137 nonzero frames,
соответствующих преимущественно tone; speech echo НЕ подтверждён.
Kernel SPSC busy/drop0, tx_empty260 (включает старт), buffers cleared.
Отключение verbose printk восстановило практически50frames/s вместо48;
восстановлены IMS/profile/flags/callbacks/MM/guards и прежние PID/boot.
Temporary PBX extension removed, PBX idle, isolated SIP exited.

Далее `test-cs-sip-pcm.py` проверяет synthetic500Hz PCM2→SIP/PCMU→PBX Echo
и обратно без SIM/GSM/CP IO. Сэмплы не сохраняются, только energy/counts.
Для повторов временный SIP binary сохраняется как checksum-named private
RAM cache `/dev/.mf79u-cs-sip-cache-*`; active hard link/config/process
удаляются после теста. Cache metadata — `build/cs-sip-cache.json`, очистить
этот owned cache по checksum/boot после завершения диагностики.
MO28 два pre-call отказа (unused variable и CLI response parsing) произошли
до radio/dial; исправлены, временная extension после первого CLI сбоя удалена.
SPSC ARM stress compiled, но не запускался: qemu-arm отсутствует; host stress
и live B03 binary-transport подтверждены отдельно.

### MO27: подтверждён duplex через userspace; готовится SIP/PBX (2026-10-10)

Пользователь: «тон и эхо были». `cs-mo27-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-*`:
bridge RX480/TX482 frames, RX72923/TX68441 nonzero samples, tx_full0,
finished1/failed0. Kernel RX/TX contention38/39 words, empty108; buffers cleared.
Полностью восстановлены IMS/profile27/flags0/0/callbacks/MM/guards, прежние
boot/native1620/SIP1680. Теперь подтверждён8→16→8k userspace speech duplex.

После этого общая блокировка заменена SPSC очередями: worker никогда не
ждёт userspace; frame publication release/acquire, overflow drops new data.
Host stress проверил3.2M ordered words при двух потоках и cursor wrap.
Повторный1000-frame binary sysfs test на B03 PASS, busy/drop0, runtime unchanged.
Receipt `cs-pcm-transport-live.json`; первая версия сохранена как
`cs-pcm-transport-lock-live.json`. Подробные per-second printk исключены из
userspace audio loop: их влияние на measured48frames/s пока гипотеза.

MO28 --sip-media готовит отдельный RAM SIP endpoint5082 / RTP12004 / PCM46010–46011,
отдельные status/caller paths и PCMU. Production SIP5080 и его конфигурация
не меняются. Единственная временная runtime PBX extension `cs-audio-probe`
делает700Hz tone2s→Echo(), absolute25s; исходный incoming route не меняется,
запись не включается. После20s PCM SIP завершается, extension удаляется.
SIP sender использует ephemeral UDP port; adapter проверяет loopback/PCM2/длину,
а не ошибочно требует source46000. Это отдельный physical media test;
production call-control/fallback и стабильность ещё не установлены.

### PCM transport проверен; подготовлен MO27 через userspace (2026-10-10)

`cs-pcm-transport-live.json`: 1000 кадров / 320000 synthetic bytes без
искажений, включая NUL/high-bit; repeated seek, EAGAIN и EINVAL проверены.
RX/TX1000, dropped/busy/empty0; module unloaded, RAM cleared, sysfs removed,
IMS/native1620/SIP1680/boot сохранились. CP/radio/DSP не изменялись.

`cs-pcm-bridge.c` получает ARM1 PCM через root-only sysfs, поднимает частоту
до16k/320, формирует два тона и затем возвращает речь с80ms задержкой через
16→8k FIR. Отдельный UDP mode реализует PCM2 на46001↔46000, но ещё не
проверен с SIP. MO27 --userspace-pcm сохраняет hardware profile MO26;
после DSP/ARM controls работает10s userspace вместо4s kernel echo.
Сборка и B03 relocation audit прошли; builder/armer привязываются к MO26
и binary transport receipts. Номер/samples не сохраняются. Live call pending;
production SIP/native binaries не менялись, fallback не установлен.

### PCM transport: подготовлен обмен kernel↔userspace (2026-10-10)

После подтверждённого MO26 echo добавлены ограниченные RX/TX очереди
`cs-pcm-ring.h` и root-only sysfs `pcm_rx`/`pcm_tx`/`pcm_info`.
Внутренний кадр 160 PCM16LE samples/8 kHz/20 ms; внешний SIP контракт
16 kHz/320 samples сохраняется через существующий FIR resampler.
Очереди очищаются при завершении; samples не пишутся в отчёты.
`cs-pcm-loop-probe.c` и `test-cs-pcm-transport.py` отдельно проверяют
двоичный обмен синтетическими кадрами без CP/DSP/radio/call IO.
Host ring selftest и exact B03 module relocation audit прошли.
Live transport и новый userspace audio ещё проверяются; это диагностический
код, не установленный production CS↔SIP/fallback.

### MO26: впервые подтверждено слышимое GSM эхо через ARM1 (2026-10-10)

Пользователь: «Эхо было». Вызов переключил TX с ARM0 на ARM1 через1s:
ARM0 process6, ARM1 process7; затем4s ARM1 RX→80ms RAM delay→ARM1 TX.
TX/RX23080слов, RXnonzero22992, echo TXnonzero15065, peak5150,
underrun323/overrun0/failed0. Echo buffer cleared, обе стороны hardware
restore прошли. Рабочий duplex находится на ARM1/F8A06000 при full voice API,
timing01ef2001, divider00200019/00010032 и loopa9. ARM0 оставался RX-only;
его полное отключение этим тестом не проверено. Исходный MO21 ARM0 uplink
остаётся историческим успешным тестом при другом наборе активных портов.

`cs-mo26-full-voice-arm-echo-arm1-rx-only-tx-switch-{live,test,restore}.json`,
модуль SHA2567797cb6b221052a528573ebb0155d990cafa03dcb4048a97d61d3ffa5d93f545.
Все проверки LTE/IMS/profile27/flags0/0/guards/callbacks/MM завершились,
boot/native1620/SIP1680 сохранены; mo26 inactive pinned. Это короткий физический
echo тест; SIP PCM transport, длительный duplex и production voice fallback
ещё не установлены. Следующий этап — ограниченный kernel↔userspace PCM bridge
с внешним неизменённым mono PCM16LE16000/320 и тем же hardware profile.

### MO25: RX-only не дал слышимого эха; подготовлен TX comparison MO26 (2026-10-10)

Пользователь услышал тон, но не эхо. `cs-mo25-full-voice-arm-echo-arm1-rx-only-*`:
TX/RX22903, RXnonzero22836, echo TXnonzero15070, peak2981, underrun321,
overrun0/failed0. ARM1 process6 удерживался; windows во время echo содержали
2203..4376 samples above64/sec, peak1650..2981. Это не только постоянный
offset, но происхождение как GSM speech ещё не подтверждено на слух.
Полностью восстановлены IMS/profile/flags/guards/callbacks/MM/AP/tone/registers,
boot/native1620/SIP1680 прежние; mo25 inactive pinned.

MO26 `--arm1-tx-switch` отдельно проверяет передатчик: DSP1kHz2s, ARM0
500Hz1s, затем ARM0 process6/ARM1 process7 и ARM1 1500Hz1s; оставшиеся4s
эхо ARM1 RX→RAM→ARM1 TX. Выбор TX port меняется только между этапами,
не DSP profile/mux/gain. Метаданные содержат переключение и RX windows;
восстановление обоих портов прежнее. Offline compile/kernel relocations PASS.
До результата это диагностический код, production CS↔SIP/fallback не включён.

### ARM1 RX-only idle прошёл; подготовлен MO25 (2026-10-10)

`cs-full-voice-both-ports-signal-rx-only-live.json`: process6/TX0 во всех трёх
фазах, tone on RX6371/changes6370/crossings3184/peak7594; off6421/32/15;
повторный on6428/6396/3197/peak7599. ARM0 RX остаётсяzero. Анализатор признал
1kHz signal/negative control; all ACK/failed0, restore/unload/IMS/PID прошли.

MO25 `--full-voice-arm-echo --arm1-echo --arm1-rx-only` использует process6 и
не пишет ARM1 FIFO. Вначале DSP1kHz2s, затем ARM0 500Hz1s/1500Hz1s, затем
ARM1→RAM→ARM0 echo4s. Отдельные метаданные каждую секунду считают peak и
samples above64, чтобы отличать речь от малого постоянного уровня. Сэмплы
не сохраняются. Компиляция/точный kernel relocation audit прошли. Это новый
диагностический вызов; слышимость эха и production duplex ещё не подтверждены.

### MO24: ARM1 получает данные, но пользователь не слышит эхо (2026-10-10)

`cs-mo24-full-voice-arm-echo-arm1-rx-{live,test,restore}.json`: connected,
TX23200/RX23203/nonzero23146, echo TX15110nonzero, peak5230,
underrun324/overrun0/failed0; RAM cleared, registers/AP/tone restored.
Пользователь сообщил тишину. Эти ненулевые данные не доказывают приём речи;
duplex не подтверждён. Пользователь уточнил: начальный писк был, затем тишина.
Возвращены callbacks/MM/profile27/flags0/0/IMS/guards, boot/PID сохранены.
Следующий bounded idle test проверяет ARM1 только на приём (process6,
подтверждённый реальным zDrvI2S_Read_Start_Do), исключая лишний TX silence.
Это проверка направления, а не изменение DSP gains или непроверенного mux.

### DSP→ARM1 подтверждён; подготовлен GSM echo ARM1→ARM0 (2026-10-10)

`cs-full-voice-both-ports-signal-live.json`: тон1000Hz/on: ARM1 RX6393,
changes6392, peak7594, sign crossings3196; off: RX6428/changes32/crossings16;
повторный on после восстановления tone block: RX6428/changes6396/peak7597/
crossings3198. Это ожидаемая частота1kHz при8k mono16, ARM0 остаётсяzero.
`cs_i2s_signal.py` проверяет все шесть строк и отрицательный контроль;
недостающие строки/нулевой tone peak отклоняются. All ACK/failed0/unload,
peripheral/AP/tone/radio/IMS/flags/profile/guards/callbacks/MM restored.
Речь GSM через ARM1 ещё не проверена: это локальный DSP tone.

Подготовлен MO24 `--full-voice-arm-echo --arm1-echo`: DSP control2s,
ARM0 tone2s, затем ARM1 RX→80ms RAM delay→ARM0 TX4s. ARM1 TX передаёт
silence; ARM0 RX дренируется без передачи. Оба порта восстанавливаются,
echo RAM очищается. Builder/armer требуют explicit flag и checksum принятого
idle signal receipt; проверены compilation/relocations старого echo и нового.
Production бинарники/SIP/fallback ещё не менялись; PCM16k/320 сохранён.


### Подготовлен bounded idle тест обоих ARM I2S портов (2026-10-10)

`test-cs-audio-mailbox-ack.py --full-voice-open --both-ports` сравнивает
первоначальный и поздний ARM0 profile при одновременно запущенном ARM1
01ef2001/00200019/00010032. Все значения и source hashes проверяются по
`mf283u-full-voice-start-config-audit.json`. Два этапа по1.6s, DSP tone,
ARM TX silence, отдельные RX/nonzero counters. Before-write проверяется
idle ARM1; сохраняются оба divider/controls и clock flags29/31/30/32.
DMA выключен, IRQ handler/GPIO/CC hooks/вызовы отсутствуют; restore включает
оба порта.

Двухпортовый idle тест выполнен: `build/cs-full-voice-both-ports-live.json`.
ARM0 RX6406/6297, nonzero0; ARM1 RX6374/6296, все ненулевые. ARM1 timing,
process7 и divider подтверждены. Это ещё не звук: следующий `--both-ports-signal`
сравнит тон on/off/on и changes/all-ones/peak без сохранения отсчётов.
All ACK, failed0, registers/AP/tone/header/config restored; модуль выгружен,
IMS/profile27/flags0/0/guards/callbacks/MM восстановлены, boot/PID прежние.


Signal test обнаружил меняющийся ARM1 поток при DSP tone:6395слов/6394changes,
peak7734; после STOP6430слов/32changes (остаток FIFO). ARM0 всегдаzero.
Вторая попытка START дала peak2: STOP обнуляет duration, поэтому новый тест
восстанавливает весь проверенный tone block перед START и считает sign crossings.
Первый receipt сохранён как `cs-full-voice-both-ports-signal-before-tone-reload-*`.
Это свидетельство DSP→ARM1, ещё не подтверждение принятой GSM речи.

### MO23: late profile не дал приёма во время вызова (2026-10-10)

Пользователь не услышал голос эхом. TX/RX23133 слов, RX nonzero0/peak0,
echo TX nonzero0, underrun321, overrun0. На фазе echo подтверждены
01ff2005 и divider00400019/00010019; failed0, buffer_cleared1.
`build/cs-mo23-full-voice-arm-echo-late-start-{live,test,restore}.json`:
исходные callbacks/MM/radio/profile27/flags0/0/IMS/guards/header/config и
AP/tone/registers восстановлены, boot/native1620/SIP1680 сохранены.
Inactive mo23 pinned до reboot. Следующий audit касается второго ARM I2S
порта: штатный data start использует оба, прежние тесты читали только ARM0.
Новый вызов без отдельного диагностического изменения не нужен.

### Поздний профиль штатного запуска: отдельная idle проверка (2026-10-10)

Дополнительный audit реального vp_VoiceI2sStart24783410 обнаружил, что после
Open в модели ARM0 получает config24acc9ec: timing01ff2005, divider00400019/
00010019, slot width32 и обратную фазу. ARM1 получает прежний config24acca68.
`mf283u-full-voice-start-config-audit.json` записывает фактические аргументы
zDrvI2S Configure, а не только первоначальный profile. Baseline эмуляторы и
receipts сохранены; DMA/IRQ и availability остаются синтетическими.

Новый idle-only `--rx-start` сравнивает прежний и поздний ARM0 profile по1.6s
с теми же DSP параметрами и ARM TX silence. GPIO, ARM1, DMA/IRQ ownership и
DSP code не меняются. Builder проверяет хеши offline audit и точные значения.
`build/cs-full-voice-rx-start-live.json`: baseline RX6431, late RX6404,
оба nonzero0. All ACK/failed0/restoration/unload/IMS/flags/profile/guards
прошли, boot/native/SIP сохранены. Это idle результат без независимо
проверенного сигнала на выходе DSP; он не исключает работу late profile
во время разговора.


### Проверка выбора RX слота без SIM-вызова (2026-10-10)

`emulate-mf283u-rx-slots.py` исполняет исходный reference I2S API с selector0/1/2,
не меняя baseline emulator/receipt. Получены timing01ef2001/01ef4001/01ef6101
при одинаковых divider00200019/00010032 и loopa9. Это два mono slot и stereo
варианта; точная полярность слотов на B03 ещё не установлена.
`--i2s-rx-slots` ограничен idle DSP-loop, проверяет хеши и ожидаемые регистры.
Полный DSP profile MO21 сохраняется; три фазы по1.6s передают ARM silence,
DSP tone перезапускается перед каждой фазой. Сохраняются только счётчики.
No CC hook/dial/answer/GPIO/DMA/IRQ ownership or DSP program upload.

Компиляция default idle и нового варианта, точный B03 relocation audit прошли.
Live wrapper `test-cs-audio-mailbox-ack.py --full-voice-open --rx-slots` возвращает
исходные radio/header/config/guards. `build/cs-full-voice-rx-slots-live.json` завершён: mono selector0 RX6431,
selector1 RX6428, stereo RX12768; все nonzero0. TX25582/RX25627,
failed0, все negative ACK. Peripheral/AP/tone/header/config/radio/IMS/guards
и callbacks/MM восстановлены, модуль выгружен; boot/native/SIP прежние.
Оба mono slots дали нули в idle; перенос этого вывода на подключённый
вызов не доказан, поскольку выход DSP-тона независимо не наблюдался.


### MO22: приём речи пока нулевой (2026-10-10)

Выполнен `--full-voice-arm-echo` на том же полном profile, что и MO21.
После DSP control2s и ARM tone2s четыре секунды работал ограниченный RAM echo.
Пользователь эха не услышал. RX23365 слов, nonzero0/peak0; TX23363 слов,
echo TX nonzero0, underrun320 (ровно начальная задержка80ms), overrun0.
Это не подтверждённый duplex: причина отсутствия DSP→ARM ещё исследуется.
Буфер512 слов очищен при stop; речь и номер не сохранялись.

Все команды получили ожидаемый ACK; registers/AP/tone возвращены, failed0.
Отчёты `build/cs-mo22-full-voice-arm-echo-{live,test,restore}.json` подтверждают
LTE/IMS, profile27/flags0/0, исходные callbacks/MM/guards и прежние boot/PID.
Модуль mo22 inactive pinned до reboot. Default/tone/echo compilation и точный
kernel relocation audit прошли; недопустимые opt-in отклонены до device IO.
Production CS/SIP/fallback не установлены. Следующий шаг — аудит RX mux/выхода
DSP; неизменённый звонок повторять не следует.

### MO21: звук ARM → GSM подтверждён (2026-10-10)

Пользователь услышал три меняющихся тона после начального DSP-писка.
Перед PCM-этапом DSP-генератор остановлен командой13 (ACK ffed);
500/1000/1500Hz создавал ARM через FIFO. Это первое подтверждение цифрового
uplink, необходимого для SIP. Full voice Open/Enable profile использовал
UL[0,20,20], DL[0,27] и штатные mixer gains; прежние ручные параметры MT27
отличались, а MT32/MO18 отправляли ARM silence.

За6s TX/RX по23396 слов, RX nonzero0, failed0. loop=a9, timing=01ef2001,
process=7, clock=00010f03, divisor=00200019/00010032 удерживались во всех
шести readbacks. Приём речи с телефона ещё не доказан; следующим отдельным
тестом проверяется речь пользователя и возврат через ограниченный RAM echo.
Речь и номер не сохраняются. Внешний PCM16LE16000/320 не менялся.

`build/cs-mo21-full-voice-arm-tone-{live,test,restore}.json` связывают
наблюдение и модуль SHA256
`ee56a942e1ad95c32813782d4a196c571831ed4f64c025dadda62c7683357adc`.
Восстановлены header/config, AP/tone/registers, profile27/flags0/0,
LTE/IMS/guards и original callbacks/MM. Тот же boot/native1620/SIP1680;
inactive mo21 pinned до reboot. Production CS↔SIP duplex и voice fallback
ещё не установлены. Отбой отложен по просьбе пользователя.

### Приоритет: цифровой звук для GSM↔SIP (2026-10-10)

Пользователь попросил сначала закончить звук, отбой отложить. DSP-тон слышен,
но последний PCM-тест MO18 получил только нули ARM RX. Production CS/SIP audio
и автоматический voice fallback ещё не установлены. На момент MO20 следующий шаг был проверить цифровой audio route;
подтверждённый ARM uplink MO21 описан выше.

MO20 без DSP-команд завершился на телефоне автоматически примерно через минуту,
по сообщению пользователя. Локальный DISCONNECT отправлен через 10.47 секунды
после CONNECT; RELEASE пришёл через 0.190 секунды. Быстрый удалённый отбой не
подтверждён. `build/cs-mo20-clear-signaling-{live,test,restore}.json` подтверждают
восстановление profile27/flags0/0/IMS/guards и original callbacks/MM на прежнем
boot/native1620/SIP1680. MO20/ASC2 остаются неактивными pinned до reboot.

Отложенный signalling audit нашёл штатный N(SD) helper BF29BE71: вызывающий
BF29BEA8 добавляет общий MM/CC/SS номер перед AAD4, а диагностический raw sender
обходит этот шаг. BF4C1730 распознаёт CC task по registry BF55E8BC. Это offline
находка; передатчик и счётчик на устройстве пока не менялись.

### MO19: удалённый разговор продолжался60s (2026-10-10)

Пользователь оставил телефон после прекращения DSP-тона и сам нажал сброс
на60-й секунде: автоматический удалённый отбой не работает. Passive ASC
подтвердил исходящий DISCONNECT/Cause16/coding0/location0, входящий
RELEASE через0.185s с Cause126/coding3/location0 и исходящий RELEASE COMPLETE.
Исправление прежней интерпретации: coding3 — стандарт GSM PLMN,
по TS24.008 table10.5.122; значение126 относится к fallback127 (interworking,
unspecified), table10.5.123. Предыдущая запись о нестандартном coding3 ошибочна. Местный CC/MM участок
освободился, но это не завершение удалённого звонка. Дополнительные одинаковые
вызовы без диагностического изменения не выполняются.

`build/cs-mo19-clear-tone-{live,test,restore}.json`: original CC/ASC/admission/MM,
profile27/flags0/0/IMS/guards восстановлены, boot1c2740a7/native1620/SIP1680
сохранены. Inactive mo19/ASC1 pinned; экземпляры не переиспользовать до reboot.
ARM I2S не включался, звук генерировался DSP. Production voice backend/fallback
ещё не установлен. Следующий audit проверяет actual B03 AAD4→RR serialization
и ownership N(SD), без предположения, что raw packet сам проставляет sequence.

### Подготовка отдельной проверки удалённого отбоя (2026-10-10)

Пользователь уточнил MO18: после прекращения тона он сам нажал сброс.
`test-cs-clear-tone.py` выполняет один разрешённый MO19 с прежними DSP-тонами,
без ARM I2S; passive ASC1 читает только CC header/Cause scalars. MO устанавливается
до ASC строго последовательно, отдельный100s ASC expiry ожидается перед route
audit/production restore. Default report всегда remote_hangup_verified=false;
удалённое завершение подтверждает только наблюдение телефона. Номер stdin/RAM,
raw PDU/речь не сохраняются. MO19/ASC1 kernel relocation audit PASS. После
остановки тона пользователь наблюдает телефон ещё30s. Production CS/SIP/fallback
по-прежнему не установлен; результат этой новой проверки ещё не получен.

### MO18: DSP-тон слышен; удалённый отбой не подтверждён (2026-10-10)

Corrected outgoing-only MO18 соединился. Public PCM ARM master передал11789
слов и получил11789 нулевых слов, failed0. Пользователь слышал писк до конца,
но уточнил: через примерно10s звук замолк, а звонок не сбросился. Это не
подтверждённый автоматический отбой. Локально DISCONNECT отправлен через10.393s
после CONNECT; спустя0.148s пришёл RELEASE, отправлен RELEASE COMPLETE,
MM refs стали0 и callback/admission восстановлены. В
[TS24.008 §5.4.3.2](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/08.18.00_60/ts_124008v081800p.pdf)
RELEASE имеет локальное значение и не подтверждает clearing у удалённого
абонента. Следующая проверка должна отдельно наблюдать таймер/отбой телефона
и Cause сетевого RELEASE; остановка генератора не является завершением вызова.

Отчёты `build/cs-mo18-public-pcm-live.json`, `-test.json` и `-restore.json`:
исходные profile27/flags0/0/IMS/guards, параметры/AP/tone и original
CC/ASC/admission/MM проверены на том же boot1c2740a7/native1620/SIP1680.
Source regression default MO/tone-only/public PCM прошёл offline; MO17
отменён до набора и полностью восстановлен. Inactive mo17/mo18 pinned до
reboot. Реальный ARM↔DSP PCM/CS↔SIP и production voice fallback ещё не готовы;
внешний PCM16LE16000/320 сохранён.

### MO17 отменён до набора: исправлен выбор source (2026-10-10)

Расширение MO/I2S встретило старое безусловное присваивание
`source=cs-mt-tone-probe` при `--i2s-pcm-candidate`. Поэтому файл с MO именем
содержал MT callback. Armer не нашёл ожидаемое MO arming event; destination
не отправлялся, SIM вызовов/PCM writes не было. MT idle control `stop` выключил
answer window и вернул callback. Независимый route audit и
`cs-mo17-public-pcm-restore.json` подтвердили полное восстановление на том же
boot/native/SIP. Inactive misnamed mo17 остаётся pinned; повторно не загружать.

Source override теперь только для `--connect-probe`. Builder проверяет MO
source и compiled binary contract (call_budget/incoming_answer=0, отсутствует
connect_budget). Armer независимо проверяет source/hash и actual artifact до
upload. Wrapper ждёт удаления обоих MT/MO sysfs перед radio restore. Offline rebuild проверки default MO, tone-only и public PCM прошли; физическая
MO18 проверка описана выше, production CS/fallback не готов.


### Public PCM API: обе idle проверки завершены (2026-10-10)

Full Open/public input2-output3/real PCM builder согласуют clock profile после
refresh (который иначе возвращает PCM0). Init+PCM loop=99, полные mixer gains.
`cs-public-pcm-live.json`: TX8035/RX8035, nonzero0, failed0.
`cs-public-pcm-arm-slave-live.json`: TX16/RX0, failed0. Оба получили все11
negative ACK, выгрузили модуль, вернули local header/config/AP/tone/registers,
profile27/flags0/0/IMS/guards на том же boot/native/SIP. No SIM calls.

MO17 отменён до набора; corrected one-call MO18 завершён с DSP-tone control2s, затем6s public
PCM/ARM RX. Builder/armer требуют explicit public PCM opt-in и exact restored
idle receipt/параметры/config hashes. Новый MO I2S polling использует1..1.5ms
вместо tone-only10ms; default/tone-only код сохраняет прежнюю ветку. Incoming
answers запрещены, destination только stdin/RAM, local stop10s, restore after actual
CC/MM clearing. Source/kernel relocation audit PASS. Это диагностический
следующий этап; production CS audio/fallback не установлен.


### MO16: DSP-тон слышен, PCM в исследованных окнах не найден (2026-10-10)

Один исходящий вызов CONNECT/три фазы/автоматическое завершение10s подтверждены;
пользователь слышал три тона. В семи pointer-bounded SRAM окнах period8/16/32
не обнаружен. Окно6 менялось554 раза, в том числе до CONNECT; окно4 дважды,
остальные статичны. Это не PCM classification и не доказательство отсутствия
других аудиобуферов. `build/cs-mo16-pcm-metadata-tone-test.json` и отдельный
`-restore.json` подтверждают возврат callback/admission/MM, sampler unload,
profile27/flags0/0/IMS/guards, тот же boot/native1620/SIP1680.

Автовосстановление первоначально остановилось на старом MT32 expiry log,
который успел ротироваться, сохранив защитный guard. Fresh route audit уже
подтверждал actual original callbacks/MM refs0 на этом boot и точный набор
модулей. Restore теперь принимает этот независимый audit и для MT, как уже
делал для MO; recovery завершён. Offline regression проверил rotated log,
правильный audit и отказ до изменения policy при чужом boot/module set или
неподтверждённом route. Исправлена также передача stdin: read-only ADB helper
использует DEVNULL, только явный dial writer получает destination pipe.
Production CS↔SIP/fallback ещё не готов; внешний PCM16LE16000/320 сохранён.


### MT32: полный voice API не открыл PCM (2026-10-10)

`cs-mt32-full-voice-open-live.json`: incoming CONNECT подтверждён; пользователь
слышал писк в начале, затем более жужжащий звук. DSP-only control и полный AFE
набор приняты с negative ACK. ARM master TX23102/RX23106, nonzero0, failed0.
Звонок автоматически завершён, MM refs0, callback/AP/tone/registers возвращены.
Все проверки `cs-mt32-full-voice-open-restore.json` прошли: исходные profile27,
flags0/0, LTE/IMS, guards и PIDs1620/1680, тот же boot1c2740a7. Local header/config
также восстановлены. Изменённые mixer levels и inactive PCM tail сами по себе
не открыли ARM PCM. Production CS↔SIP/fallback не установлен. Дальше изучается
выбор цифрового источника через реальный voice path API; новых звонков пока нет.

### Полный voice API: idle проверка и подготовка MT32 (2026-10-10)

Реальные reference Open/Enable/path/unmute дали другие mixer levels и нулевой
PCM tail для AFE, чем прежний ручной builder. `cs-full-voice-open-live.json`
подтвердил все11 DSP ACK, TX15667/RX15670, nonzero0, failed0; исходные
registers/AP/tone/header/config/profile27/flags0/0/IMS/guards восстановлены.
Готовится один входящий MT32 с этим набором на активном TCH:2s проверенный
DSP-писк, затем6s новый AFE набор/ARM RX. Builder/armer требуют explicit opt-in
и matching restored idle receipt. Production CS↔SIP/fallback ещё не готов;
внешний PCM16LE16000/320 не меняется. Детали в [DSP-ABI.md](DSP-ABI.md).

### DSP ACK и исходная частота I2S (2026-10-10)

`build/cs-audio-mailbox-ack-live.json`: короткий GSM idle test без SIM вызова
подтвердил negative ACK для всех11 audio commands, включая enable/stop/reset.
Pending flag теперь проверяется вместе с ACK; отвергнутая команда прерывает
последовательность. Boot/native/SIP, callbacks/MM, profile27, flags0/0, IMS,
AP/tone/registers и guards восстановлены. PCM ещё не подтверждён.

Offline открыт дополнительный источник PMB887x ROM/audio ABI и собран его
Teakra fork. B03 ROM0902 отличается от описанного0801; чужие READ/PCM
команды не выполнялись. Новый decoder оставил те же7/4 uncertain instructions.
Источник выявил возможный Shared RAM PCM, но адреса/ownership на B03 неизвестны.
Подробности и checksum-bound source receipts — в [DSP-ABI.md](DSP-ABI.md).

Проверка точных source bytes отклонила гипотезу неверной частоты ещё offline:
voice-inner24ACCA68 уже содержит8000Hz;16000Hz относится к generic24ACC850.
Принудительный тест16k не запускался, временные опции удалены. Emulator теперь
явно записывает исходную/выбранную частоту и действительно ли она отличается.
Внешний PCM16LE/16000/320 не меняется; production fallback ещё не установлен.

### I2S: расширенная проверка clocks без изменения радио (2026-10-10)

`build/cs-i2s-extended-clock-live.json`: прочитаны LSP controls58/5C/60/64/68,
GSM clock F843B068 и exact CP record53 (`gsm_48m`). GSM register=1F,
hw flag1; отсутствие GSM clock не подтверждается. Дополнительные LSP controls
имеют reset-like FFFF0000/4; назначение полей не установлено. Writes, FIFO data,
DSP commands, SIM calls, radio transitions и boot changes отсутствуют. Probe
unloaded, RAM file/guard removed, тот же boot/native1620/SIP1680/IMS ready.
Расширенный binary SHA25619fd6e54a32cd61d74bce0b28f0a050480517e184e638bfa20f1857809eb0b4c,
exact B03 relocation audit PASS. Host parser group0 ошибка исправлена из
сохранённых live measurements, без повторного аппаратного теста.
Новый wrapper `test-cs-i2s-clock-readonly.py` сохраняет receipt и убирает guard
в finally. ARM↔DSP PCM и production fallback по-прежнему не доказаны.

### DSP ABI: пассивное наблюдение штатной инициализации (2026-10-10)

После MT31 ARM PCM по-прежнему отсутствует; LTE/IMS восстановлен.
Новый hash-bound offline Teak decoder разбирает boot patches, но полный GSM
DSP ROM и точный digital audio ABI остаются неизвестными. В B03 подтверждён
штатный self-check request21; назначение его полей ещё не доказано.
Подготовлен bounded observer реальных vendor вызовов: исходная функция
chained без изменения аргументов, новых DSP-команд/звонков нет, caller literal
возвращается через120s. Live `build/cs-dsp-boot-watch-live.json`: events0,
LTE→GSM не проходит через этот self-check. Literal/CC/ASC/MM restoration,
profile27/flags0/0/IMS/removed guards подтверждены, boot/native/SIP прежние.
Новый DSP command или SIM вызов не создавался. Подробности и ограничения:
[DSP-ABI.md](DSP-ABI.md). Production voice/fallback не установлены.
Read-only module-loader ABI preflight прошёл: `build/cs-module-layout-probe-live.json`,
layout_verified=1, immediate unload/RAM cleanup/guard removal, IMS и PIDs сохранены.
Hooks/notifiers/DSP/boot изменений не было.
Paired no-call I2S extra-cycle проверка завершена: `build/cs-i2s-extra-cycle-pair-live.json`.
Одинаковые DSP-параметры; enum1 RX15880 нулевых words, enum0 RX0. PCM не появился.
Оба module/register/AP/tone/header/profile/flags/IMS/guards восстановлены, PIDs прежние.
Module-notifier ABI preflight прошёл: `build/cs-module-notifier-live.json`,
COMING/LIVE/GOING1/0/2, immediate unload, IMS/PIDs/guards сохранены. Opt-in
initial-load observer собран/audit PASS. Подготовлен `test-cs-dsp-initial-load.py`:
once marker consumed first, original rc restored before CP, normal second reboot
с original CP base/route/IMS audit. Raw flash/DSP upload/SIM calls нет. One-shot
эксперимент не дал подтверждённой initial-load записи. После прерывания проверен
normal boot 1c2740a7: original rc/CP base/CC/ASC/admission/self-check/MM refs0,
flags0/0/profile27/IMS, removed guards и temporary files. Отчёт:
`build/cs-dsp-initial-load-final-restore.json`. Причина потери начальной записи
не установлена; прежний pre-CP метод quarantined, повторять его нельзя. B03
adbd reboot оказался no-op; shell sync/reboot ранее подтверждён на устройстве.

### MT31: полный clock Open тоже не дал ARM PCM (2026-10-10)

Пользователь слышал DSP-писк все10s и произнёс несколько слов. Candidate
подтвердил clock0=10F03/clock1=10F03 после включения всех четырёх clock lines.
ARM slave FIFO остался неподвижным: TX16 initial / RX0 / nonzero0 за6s.
`build/cs-mt31-reference-open-clocks-live.json`. Дополнительные clock lines
не исправили путь DSP→ARM. Это не подтверждённая невозможность CS audio:
реальный DSP→GSM тон продолжает работать, B03 digital audio ABI/port activation
по-прежнему неизвестны. Дальше нужен независимый путь/источник ABI, а не
повтор того же теста с произвольными format bits.

Controls обоих ARM ports, clocks/cachedflags, AP/tone fields и callback
восстановлены; actual route audit сразу подтвердил MM refs0/quiescent.
Сохранённые profile27/voiceflags0/0 и LTE/IMS восстановлены; guards сняты.
Все checks в `build/cs-mt31-final-restore.json` прошли, тот же boot/native/SIP.
Ни production SIP/native binary, ни boot hook/flash не заменены; PCM contract
unchanged.

### MT31 подготовлен: полный clock шаг reference Open (2026-10-10)

Bounded instance31 повторяет MT30 DSP-master/ARM-slave port-tone test,
добавляя reset/release + hw/sw gate для clocks29/31/30/32, как реальные
instructions24780394..24780438. Дополнительный ARM1 должен иметь process/
IRQ enable0 и правильный ID; его исходные controls, clock gates и cached
flags сохраняются/возвращаются. ARM1 FIFO data, GPIO, IRQ handler и DSP code
не используются. Reset может очистить ARM1 controls, поэтому они отдельно
включены в restore/readback. Внешний PCM16LE16000/320 не меняется.
Build `build/cs-connect-probe31-build.json`, SHA256
e8b073b0d3068a0befa6eb91364170468e06630c4d44887f25102d8f871b935a,
exact B03 relocation audit PASS. Новый opt-in строго требуется builder/armer;
без него прежняя two-clock последовательность сохранена. На момент подготовки
результата ещё не было; завершённый MT31 и restore приведены выше. Production
audio/fallback не установлены.

Независимый offline emulator теперь имеет opt-in `--driver-start` для
настоящих TX/RX Start с synthetic buffers и polling mode, без DMA/IRQ или
устройства. `build/mf283u-voice-inner-slave-init-start-configuration-emulation.json`:
Init/Open/PrepareTX/RX/loop/StartTX/RX все return0. Единственные новые MMIO
writes — FIFO thresholds F00/70F00 и process5/7; дополнительного mux/clock
в Start нет. Старые hash-bound setup reports не перезаписаны.

MT31 armed в RAM с полной clock последовательностью; collector
`build/cs-mt31-reference-open-clocks-live.json`. One-answer/10s auto-hangup,
GSM registration1, IMS temporarilyoff, native/SIP прежние. Эта запись относится
к подготовке; завершённый результат и final restore приведены выше. Boot/rootfs
не изменялись.

### I2S Open/clock audit без звонка (2026-10-10)

Расширенный read-only preflight читает оба ARM порта и CP clock records29..32.
`build/cs-i2s-clock-audit-live.json`: оба process/IRQ enable0, оба clock
registers10303; CP hw/sw cached flags1/1 для всех четырёх записей. Биты gate
в MMIO не совпадают с cached flags, поэтому cached1 само по себе не доказывает
активный clock. Reference Open делает reset/release и SetGate101/103 для всех
четырёх clocks. Дополнительный ARM1 port не использовался кандидатом;
значимость этого расхождения для внутреннего DSP пути ещё не доказана.
Module успешно unloaded, тот же boot/native/SIP/IMS, регистры не менялись,
FIFO data не читался и звонков не было. Ring guard после проверки снят.
Расширение const array сначала сгенерировало unsafe Thumb→ARM memcpy;
relocation audit отклонил этот binary до загрузки. Static const arrays
устранили этот вызов, исправленная сборка прошла audit и live read-only test.

### MT30: DSP master не подаёт clock/data в выбранный ARM порт (2026-10-10)

Пользователь подтвердил: DSP-писк продолжается после включения ARM slave.
Однако ARM FIFO остался неподвижным: TX16 (только начальное заполнение),
RX0/nonzero0 за6s. `build/cs-mt30-dsp-master-port-live.json`. Таким образом
DSP→GSM звук сохраняется в обоих направлениях clock, но цифровой ARM↔DSP
тракт ещё не работает. Это не доказательство физического отсутствия
соединения: остаются активация DSP порта, crossbar/clock и отличие B03 ABI.
Tone/AP fields, controls и CC callback восстановлены; actual MM refs3
очищены idle CFUN0. LTE/IMS/profile27/flags0/0 и снятые guards подтверждены
всеми checks в `build/cs-mt30-final-restore.json`, прежние boot/native/SIP.
Production SIP/PCM backend и автоматический radio fallback не установлены.

Offline аудит настоящих Start функций24780D44/24781200 и helpers2477F878/
2477F6A0 показал пороги FIFO и TX/RX process bits, уже присутствующие в
candidate; нового переключения crossbar там нет. Reference Open24780310
также включает clocks29/31/30/32 обоих ARM I2S, тогда как candidate включает
только29/31. Значимость остальных clocks для DSP внутреннего пути пока
не подтверждена; нужна отдельная проверка mapping/state прежде live changes.

### MT29: длительность исправлена, DSP-тон продолжается (2026-10-10)

С duration16000/restart14+12 пользователь слышал писк и после включения
ARM порта. Следовательно AFE slave профиль сохраняет DSP→GSM аудио;
исчезновение тона MT28 нельзя приписывать разрыву этой цепочки. За 6 s
ARM TX 23242 / RX 23239 words, RX nonzero=0. Tone/AP fields, registers,
CC callback и call clearing восстановлены; actual MM refs потребовали
idle CFUN0. `build/cs-mt29-dsp-port-duration-control-live.json`.
Полное восстановление LTE/IMS и guards подтверждено всеми checks в
`build/cs-mt29-final-restore.json`.
Поля tone status/duration оставались нулевыми и при слышимом писке — их
не использовать как признак отсутствующего звука.

Для проверки направления clock собран instance30 с обратной реальной
ветвью reference Init: ARM slave, DSP AFE master profile2 из24ACC820 и
PCM profile0 из24A89EA8. ARM voice config сохраняет format/rate, master=0;
Init/A9, timing01EF2000; reference не пишет ARM divider. Candidate тоже
не программирует divider в slave mode. Это проверка прохождения clock/data,
не гипотеза изменения GPIO или DSP program. Reports
`build/mf283u-voice-inner-slave-init-configuration-emulation.json`,
`build/mf283u-voice-master-port-tone-parameters-emulation.json`,
`build/cs-connect-probe30-build.json`. Tone/control duration/restart и
10 s auto-hangup прежние; B03 relocation audit прошёл. Clock/source input
пока не аппаратно подтверждён. Два tone gain fields активны; их точная
привязка к физическому ARM output отдельно не доказана.

### MT28 результат и исправление длительности для MT29 (2026-10-10)

Пользователь услышал писк только в начальной DSP-only части MT28. Это
повторно подтверждает DSP→GSM звук на текущей SIM и boot. После перехода
к AFE slave / ARM port: TX 23283 / RX 23281 words, RX nonzero=0;
tone status/duration сразу 0. Оба этапа исполнились, tone/AP fields и
registers восстановлены, callback/MM cleared; actual route сразу refs0.
`build/cs-mt28-dsp-port-control-live.json`.

Во второй части MT28 использована новая duration_raw=48000 для 6 s вместо
проверенной 16000. Её допустимость на B03 не установлена, поэтому MT28
не доказывает, что тон останавливает именно цифровой профиль или отсутствие
clock. Instance29 возвращает ровно MT19 duration16000 и restart14/12 через
каждые 2 s; DSP profile, mixers, ARM loop/timing прежние. Это контроль
единственного дополнительного параметра, а не объявленный audio fix.
Build `build/cs-connect-probe29-build.json` прошёл exact B03 relocation audit.
Production PCM/SIP binaries и radio fallback пока не устанавливались.

Сравнение с положительным MT19 уточняет трактовку telemetry: его слышимые
DSP-тоны тоже имели duration_raw=0 и часто tone_status_raw=0 в тех же AP
полях. Поэтому эти значения не доказывают остановку генератора; они могут
отражать потребление AP-команды, смысл status отдельно не установлен.
Для MT28 исчезновение писка известно из ответа пользователя, а отсутствие
DSP→ARM данных — из RX nonzero=0. Длительность48000 остаётся отдельным
непроверенным параметром. Любые прежние выводы «duration0 ⇒ tone inactive»,
включая no-call A8/A9 probes, считать неподтверждёнными. Полное восстановление
MT28: все checks в `build/cs-mt28-final-restore.json` прошли.

### MT28: контроль DSP-тона вместе с чтением ARM порта (2026-10-10)

Подготовлен отдельный bounded one-answer test instance28. После сетевого
CONNECT сначала на 2 s запускается прежний DSP-only tone1000Hz с параметрами
успешного MT19 (volume100/amplitude8000), ARM I2S ещё выключен. Затем на 6 s
выбирается голосовой AFE duplex и тот же DSP-тон на обоих mixers. ARM TX
передаёт нули, RX считает ненулевые words; дополнительно читаются duration
и status tone generator. Это разделяет проверку известного DSP→GSM пути
и подключения DSP output к ARM без нового предположения о формате ARM тона.

Offline report `build/mf283u-voice-port-tone-parameters-emulation.json`
создан реальными profile/table/mixer builders, tone gains32767/32767.
Build `build/cs-connect-probe28-build.json` привязан к этому report, прежнему
DSP-tone report и ARM Init/A9; точный B03 relocation audit прошёл. Все tone/AP
fields и peripheral controls сохраняются и возвращаются; DSP-owned tone status
не перезаписывается. Duration ограничена, общий auto-hangup10s. Test пока
не доказывает аппаратный PCM или production CS backend; runtime прежний.

### MT27: тишина; проверка выбора всей таблицы маршрутов (2026-10-10)

Пользователь подтвердил тишину в MT27. Исправленный голосовой формат DSP
не дал ненулевых RX: за 6 s TX 23869 / RX 23867 words, RX nonzero=0.
Controls/AP fields/callback возвращены, реальный MM audit после idle CFUN0
показал освобождение ссылок. Сохранённые profile/flags/CFUN1 восстановлены;
LTE/IMS, снятые guards, прежние boot/native/SIP подтверждены всеми checks
в `build/cs-mt27-final-restore.json`. Call report:
`build/cs-mt27-voice-profile-live.json`. Автоответ закончен.

Затем offline выполнен ещё один реальный шаг reference Init:
`24784CD8(24ACCA68)` → `24786208(1)`, который выбирает таблицу
`aud_setting_afei2s`. Адреса route descriptors изменяются, однако для
используемых UL[0,15]/DL[0] итоговые DSP-команды полностью совпадают с MT27.
Reports `build/mf283u-voice-settings-duplex-parameters-emulation.json`
и `build/cs-voice-settings-emulation-delta.json` (changes=[]). Дополнительный
SIM test только из-за этого шага не нужен; hardware port activation/connection
по-прежнему не доказан. Ранее слышимый DSP-only тон MT19 подтверждает
DSP→GSM путь, а не передачу ARM PCM↔DSP. Production audio/fallback не готовы.

### Голосовой профиль DSP перед MT27 (2026-10-10)

В эталонном `zDrvVoiceConfig_Init` выбор ARM inner-I2S master вызывает
`24786ADC(24ACC838)` и `24786BB0(24ABF540)` до выбора DSP режима. Эти функции
меняют только таблицы параметров в RAM. Прежний эмулятор выбирал AFE mode3,
но пропускал этот шаг и использовал его заводскую строку. Новый opt-in
`--voice-profile` выполняет оба реальных обработчика. Проверены их return=0,
полное совпадение обновлённых строк с голосовыми профилями и отсутствие
дополнительных DSP-команд во время изменения таблиц.

Report `build/mf283u-afe-slave-voice-profile-speech-mixer-duplex-parameters-emulation.json`
и delta `build/cs-voice-profile-emulation-delta.json` показывают ровно два
изменения в command0F: payload[8] 3→19, payload[9] 3074→3090. Усиление,
маршруты, прочие DSP-команды и ARM Init/A9 не меняются. PCM mode1 обновляется
как в reference Init, но не выбирается: тест использует AFE, PCM остаётся
mode0. Это новая гипотеза согласования формата ARM↔DSP, ещё не аппаратное
подтверждение звука. Собран bounded one-answer instance27 с hash-bound
параметрами и проверкой точного B03 kernel ABI; production binaries прежние.

### Изолированный SIP↔PCM media test для CS (2026-10-10)

`test-sip-cs-media.py` запускает настоящий ARM SIP gateway в disposable
build container с synthetic UDP cellular peer. SIM/CP/физический модем не
используются. Для PCMU и PCMA проверены SIP→CS и CS→SIP: INVITE/ответ/ACK,
двусторонний RTP↔PCM, BYE/ENDED и отказ503 при backend=none. Каждая из4cases
передала125 RTP frames и125 PCM frames. PCM: mono16LE/16000Hz/320samples,
640bytes плюс4-byte PCM2 header. Energy target1000Hz (RTP→PCM) =1.0;
target500Hz (PCM→RTP) =1.0 PCMU /0.9998 PCMA. Для CS statusvoiceReady=true,
imsReady=false; входящий synthetic cellular event получил SIPANSWER.
`build/sip-cs-media-fixture.json`. Это подтверждает software media flow, но
не physical GSM audio, production CS adapter или автоматическую смену RAT.

### MT26: receive mixer исправлен, аппаратный PCM остаётся нулевым (2026-10-10)

MT26 с ненулевым speech receive mixer тоже подключился, но пользователь
подтвердил тишину. За6s: TX23768 / RX23768 words, RXnonzero=0.
`build/cs-mt26-speech-mixer-live.json`: peripheral controls/AP fields/callback
возвращены, call/MM clearing выполнены, тот же boot/native/SIP. Actual route
после clearing снова требует MM cleanup; idle CFUN0 выполнен, затем возвращены
сохранённые profile/flags/CFUN1. LTE/IMS и полное восстановление подтверждены
`build/cs-mt26-final-restore.json`. Instance26 inactive/pinned до reboot; автоответ закончен.

Source fix speech activation сохраняется: он устраняет подтверждённый нулевой
receive gain в исходных параметрах, но не подтверждает physical I2S↔DSP bridge.
Новые SIM tests пока не запрашиваются без независимой гипотезы. Требуется
проверить ещё аппаратное включение/ownership речевого порта либо иной B03
media route. Положительный результат DSP-only MT19 не доказывает ARM PCM.
Production native/SIP binaries не устанавливались; GSM↔SIP audio/fallback
остаются незавершёнными. Внешний PCM16LE16000/320 контракт не изменён.

### MT25: тишина; исправлена активация речевого микшера (2026-10-10)

MT25 с Init/A9 подключился, но пользователь подтвердил тишину. FIFO за6s:
TX23827 / RX23829 words, RXnonzero=0; controls/AP fields/callback/MM cleanup
вернулись, boot/native/SIP не менялись. После actual MM refs audit, idle
CFUN0 и возврата profile/flags/CFUN1 восстановление LTE/IMS и снятие guards
подтверждены `build/cs-mt25-final-restore.json`. Подробный call report:
`build/cs-mt25-voice-inner-init-afe-slave-live.json`.

Найдена независимая ошибка offline audio builder: `251A44E8[0]=1` ставился
до вызова `24785C5C(0,1)`. В reference этот updater при уже равном state
возвращается по `24785C68`, не вызывая mixer updater. Поэтому команды19
содержали speech receive gain=0 даже при активном duplex. Новый opt-in
`emulate-mf283u-audio.py --afe-duplex --afe-slave --speech-mixer` начинает
с inactive resource, активирует штатным updater и выполняет exact unmute
handler(event6B, resource0, enable1, channel2). Последние семь DSP commands
отличаются только command19/payload[3]: 0→28309. Report
`build/cs-speech-mixer-emulation-delta.json`; параметры
`build/mf283u-afe-slave-speech-mixer-duplex-parameters-emulation.json`.
Это source-level исправление нулевого receive mixer, не доказательство
готового аппаратного тракта. Instance26 собран с этим report и A9 init,
checksum-bound header и kernel relocation audit. Живой test отдельно.

### MT24 и восстановленная инициализация I2S (2026-10-10)

MT24 установил CS-соединение, но пользователь снова подтвердил тишину.
За 6 s: TX 23880 / RX 23879 words, RX nonzero=0. AP mailbox и peripheral
controls возвращены, callback/MM clearing выполнены; boot/native/SIP не
менялись (`build/cs-mt24-voice-inner-afe-slave-live.json`). Последующий actual
route audit обнаружил MM refs=3; idle CFUN0 очистил их. Сохранённые radio
profile и voice flags возвращены; LTE/IMS зарегистрировались снова на том же
boot с прежними native/SIP PID. Первый report `build/cs-mt24-first-route.json` не доказывает cleanup.

No-call DSP tone-loop с предыдущим A8 тоже получил только нули
(`build/cs-i2s-afe-a8-dsp-loop-probe-live.json`): TX 15958 / RX 15959 words за 4 s.
DSP tone не оставался активным без TCH; этот тест не доказывает исправный
DSP duplex. Controls, AP/tone fields возвращены, module unloaded, SIM calls
не создавались.

В offline reference обнаружен пропущенный driver Init: функция 24782018,
запись по PC 247820C0, делает `(ARM_I2S_LOOP_CFG & ~0x1ff) | 0xa9`.
Последующий `vp_SetInnerI2sMode` меняет только mask 1F8, сохраняя младшие
биты. Ранние тесты начинали с нулевого B03 register и получали A8 вместо A9.
`work/zte/voice/emulate-mf283u-i2s.py --voice-inner --driver-init` теперь
выполняет настоящую Init в эмуляторе, включая перехват OS clock calls.
Report `build/mf283u-voice-inner-init-configuration-emulation.json` подтверждает
A9 до/после выбора AFE. Назначение bit0 отдельно не установлено; это
новая проверяемая гипотеза, а не доказанный audio fix. Generated header
привязывает value и ownership mask; candidate сохраняет/возвращает bits8:0,
не меняя остальные bits. Instance25 собран с exact B03 relocation audit.
Восстановление MT24 подтверждено всеми checks в `build/cs-mt24-final-restore.json`.
Production GSM↔SIP audio и автоматический radio fallback ещё не подтверждены.

Проверка A9 без вызова завершена: controls/AP/tone fields восстановлены,
module unloaded, тот же boot/PID. TX 15870 / RX 15897 words за 4 s,
RX nonzero=0; tone inactive вне TCH. Report
`build/cs-i2s-afe-a9-dsp-loop-probe-live.json`. Это разрешает отдельную
проверку instance25 на активном CS TCH, но не подтверждает слышимый PCM.

### MT23 и проверка без SIM-вызова (2026-10-10)

Пользователь подтвердил тишину в MT23. PCM loop98 / DSP PCM slave не
дал RX nonzero: tx12219/rx12208 words за6s (~2kwords/s). Из этой частоты
нельзя утверждать правильные8ksamples/s. Peripheral controls и AP mailbox
возвращены, call/MM release выполнены. Первый actual route audit снова
обнаружилMM refs3 после clearing; idle CFUN0 очистил их, сохранённые
profile/flags и CFUN1 возвращены. Report `build/cs-mt23-first-route.json`
не считать restoration proof.

В actual reference `voice_Open`/`zDrvVp_SetInnerI2sCfg` внутренний voice
config находится по24ACCA68, а не generic I2S default24ACC850. При ARM
master I2S он выбирает DSP AFE slave config3. Для следующей проверки
созданы отдельные offline reports `mf283u-voice-inner-configuration-emulation.json`
и `mf283u-idle-afe-tone-loop-emulation.json`. `src/cs-i2s-dsp-loop-probe.c`
сохраняет controls/AP fields и на4s включает digital tone/mixer через
mailbox, читает FIFO counters, затем всё возвращает. CC callback/admission,
SIM dial/answer, GPIO/DMA/IRQ ownership и DSP program не меняются. Этот
no-call test требует idle CS-only/ring guard и отсутствующего speech channel.
Сборка проверена по exact B03 kernel relocation audit. Он не является
production voice service. Backend admission CS остаётся выключенным до
доказанного media path.


### PCM в Teak I2S1: продолжение MT22/MT23 (2026-10-10)

MT22 с AFE duplex тоже дал тишину (подтверждение пользователя). За6s
ARM FIFO передал23815 words, принял23814, все RX words нулевые.
`build/cs-mt22-i2s-afe-pcm-live.json`: connected, clearing, registers restored,
тот же boot/native/SIP. Затем actual CC/ASC/MM audit подтвердил refs0,
profile27/flags0/0/IMSready и отсутствие guards:
`build/cs-mt22-final-restore.json`. Production binaries не обновлялись.

Следующая гипотеза выводится из reference timing table249A2E08:
selector6 = mono PCM/TDM; loop98 = ARM0 PCM к Teak I2S1. Reference
`zDrvVoiceConfig_Init` различает ARM master/DSP slave. В ранних candidates
ARM был master, а DSP PCM оставался в исходном master profile. Для MT23
offline builders выбирают DSP PCM slave index1 и ARM mono PCM master:
timing01EF0009, divider19/100C7, loop98. Reports:
`build/mf283u-pcm-i2s1-configuration-emulation.json`,
`build/mf283u-pcm-slave-duplex-parameters-emulation.json`.
Это reference evidence, совместимость с B03 пока проверяется. Новый header
привязан к обоим SHA256; bounded candidate сохраняет также28 AP mailbox
halfwords и возвращает их после DSP idle. Внешний PCM16LE16k/320 unchanged.
Во время следующего теста GSM CS-only/ring guard включаются временно.


### FIFO words и маршрут MT21/MT22 (2026-10-10)

ARM-local loop прошёл на B03 (`build/cs-i2s-loop-probe-live.json`), без
SIM/DSP команд, выгружен, controls restored. FIFO status low bits оказались
threshold flags: использовать их как empty/full было ошибкой MT20. Live
изменение count fields подтверждает свободные TX words в bits13:8 и RX words
в bits21:16. Reference ISR 2477F258/260 передаёт два последовательных
PCM16 отсчёта в одном word (первый в high halfword). MT21 исправляет both.
За6s tx=23726/rx=23727 words (~4kwords/s=8ksamples/s), но rx_nonzero=0;
пользователь снова подтвердил тишину. DSP route compatibility не доказана.
`build/cs-mt21-i2s-pcm-live.json`: connected/clearing/register restore, same
boot/native/SIP прошли. Первое actual route readback refs3 не считалось
restoration; idle CFUN0 отдельно очистил MM, затем profile/flags и CFUN1
восстановлены для IMS.

Найдено несоответствие: loopA8 ведёт к Teak AFE, а MT20/21 включали I2S1rx/tx.
Offline reference descriptors явно названы Handset mic/Normal earpiece и
I2S1rx/tx; MT22 получает отдельный AFE duplex report
`build/mf283u-afe-duplex-parameters-emulation.json`/header (UL[0,15],DL[0]).
Source меняется только для отдельного bounded MT test, не production.

`build/native-cs-backend-fixture.json` подтверждает source native dispatch
через owned CS child: incoming/outgoing/answer/hangup, stale CONNECTED after
ENDED ignored, PCM socket exclusion, active owner, idle IMS promotion, CS
crash/recovery сохраняют SIP PID и не повторяют DIAL. Это container fixture,
без physical modem access или live CS audio. Собраны native/SIP binaries,
Go control tests прошли. PJSIP isolated registrar fixture с BACKEND cs прошёл
Digest, binding replacement, Disabled и readiness voiceReady=true/imsReady=false.
На модем новые production native/SIP/control binaries ещё не установлены.


### PCM MT20 и проверка контроллера (2026-10-10)

MT20 установил вызов, пользователь подтвердил тишину. Report
`build/cs-mt20-i2s-pcm-live.json`: ARM FIFO tx_words=0/rx_words=0,
status=00202033; DSP команды были приняты, но PCM не пошёл. Вызов очищен,
аудиорегистры восстановлены, callback/admission оригинальные, MM refs=0.
LTE/IMS и исходные voice flags восстановлены, guards удалены, тот же boot и
native/SIP PID: `build/cs-mt20-final-restore.json`.

Добавлен bounded ARM-local loop (`src/cs-i2s-loop-probe.c`,
`build-cs-kernel-probe.py --i2s-loop`): synthetic words, без CC/SIM/DSP
команд, DMA/IRQ ownership и GPIO изменений. Он отдельно проверяет clock/FIFO
и возвращает все 9 сохранённых controls до выхода init; требует idle CS-only.
Открытый [ZTE I2S driver Linux v4.14](https://raw.githubusercontent.com/torvalds/linux/v4.14/sound/soc/zte/zx-i2s.c)
подтверждает совпадающие offsets и reset bits FIFO, но относится к ZX296702:
это дополнительная гипотеза, а не доказательство B03 совместимости.

Native controller получает optional owned CS child через private pipes:
`CS_HELLO/READY/NOT_READY/SUSPENDED/INCOMING/ALERT/CONNECTED/ENDED`, epoch и
call ID проверяются. SIP понимает `BACKEND cs`, status разделяет imsReady и
voiceReady. CS readiness требует signaling и PCM readiness; IMS стартует
только после CS_SUSPENDED (освобождение PCM сокета). Один вызов сохраняет
owner; потеря backend завершает SIP, без повторного DIAL на другом backend.
Это пока source implementation, production CS adapter/PCM и автоматическая
radio policy ещё не установлены и не подтверждены живым SIP/CS вызовом.


## Реализация GSM ↔ SIP и IMS → CS: продолжение 2026-10-10

Пользователь запросил полноценный SIP мост и fallback после подтверждения MT19.
Тон уже слышен, но произвольный PCM ARM↔DSP пока не подтверждён. Для него
в reference восстановлен внутренний ARM0 I2S↔DSP AFE loop. Exact B03 kernel
map_desc подтверждает `0x01405000→0xf8a05000` (I2S0) и
`0x00140060→0xf8440060` (ARM_I2S_LOOP_CFG), report
`build/cs-i2s-b03-mapping-evidence.json`. Пассивный live probe прошёл:
`build/cs-i2s-preflight-live.json`, same boot/native/SIP, unloaded, без clock
enable/register writes/FIFO data reads. Linux clock lookup по именам вернул
ENOENT; CP использует собственную checksum-bound clock table, indices29/31.
Это не повод вызывать Linux clock API с непроверенным указателем.

Офлайн `work/zte/voice/emulate-mf283u-i2s.py` выполняет I2S config только в
эмуляторе с simulated MMIO, не на устройстве. DSP route `[2,15]`/`[4]`
(I2S1 rx + scheduler8k / I2S1 tx) восстановлен отдельным
`emulate-mf283u-audio.py --i2s-duplex`; header генерирует
`prepare-cs-i2s-parameters.py`. Tone report/header MT19 не перезаписываются.
Opt-in `--i2s-pcm-candidate` — one-answer MT20, six seconds synthetic PCM через
ARM FIFO. Нет GPIO/pin mux/DSP program upload. IRQ ownership не меняется;
bounded FIFO batches/polling. Сохранённые I2S/loop/clock controls и CP clock
flags восстанавливаются; W1C IRQ status не копируется обратно. Внешний PCM
контракт остаётся mono PCM16LE16000Hz/320 samples. Это тест транспорта;
production SIP audio/автоматический fallback ещё не включены.


> Архив экспериментов; актуальная граница GSM audio сверена 2026-10-09.

Ниже сохранены этапы 2026-10-05/06: CP флаги, ABI, RPMSG, IPC, userspace ESP
и RAM-аудио. Их упоминания Mac relay, 8000 Hz, отсутствующего автозапуска и
непроверенного WB описывают соответствующий ранний этап. Сейчас локальный
native runtime работает без Mac; PCM16000 Hz, AMR-WB FT8 подтверждён.
Двусторонний GSM voice PCM/SIP по-прежнему не реализован; CS CONNECT/clearing
подтверждены. MF283U B05 builders эмулированы офлайн, восстановлен отдельный
B03 audio mailbox. MT16 обнаружил mode1-only gate rejection; mode1 подтверждён
B03 speech predicate и разрешён в отдельном tone candidate. MT17 выполнил
commands с тишиной. MT18 после включения tone resource mixer дал слабые тоны
с шумом; MT19 с volume100/amplitude8000 дал отчётливый тестовый звук:
пользователь подтвердил «Теперь хорошо слышно». Шум отдельно не оценён.
`build/cs-mt19-working-tone-summary.json`, `build/cs-mt19-dsp-tone-live.json`.
Все3 phases, bounded hangup, MM clearing и AP fields restore прошли без reboot.
После MT19 профиль27/flags0/0, guards сняты, LTE/IMS ready, original callbacks,
admission/MM refs0 проверены actual probe, boot/PIDs прежние:
`build/cs-mt19-final-restore.json`. Production PCM contract не менялся;
IMS→CS voice fallback ещё не включён. MO14/15 RR release metadata уточняет
сбой исходящих, но стабильность MO установки ещё не решена.
Текущие CS reports и границы: [GSM-VOICE.md](GSM-VOICE.md).
Итоги: [STATUS.md](STATUS.md),
[CODECS.md](CODECS.md), [AUTONOMOUS.md](AUTONOMOUS.md).

## Результат эксперимента на физическом MF79U

В cpko найдены `OPEN_VOICE_FLAG` и `VOICE_SUPPORT`; оба подтверждённо
читаются через `AT+ZSET="имя"`. Исходные значения обоих — 0.

Проверены состояния:

1. `OPEN_VOICE_FLAG=1`, `VOICE_SUPPORT=0`.
2. `OPEN_VOICE_FLAG=1`, `VOICE_SUPPORT=1`.

В обоих состояниях CLCC, CLCC test, CHLD test и VTS test возвращали
`+CME ERROR: invalid command`. `AT+ZAMRSUP?` возвращала `0,0`.
Смысл двух полей ZAMRSUP без документации не установлен.

Оба флага восстановлены в 0, чтение подтвердило восстановление.
Перезагрузка с включёнными флагами не выполнялась: влияние на boot-time
инициализацию этим экспериментом не проверено.
В том эксперименте набор номера, ответ, IMS daemon и supplementary services не выполнялись.
Точный журнал: `build/voice-flags-combined-test.json`.
`test-voice-flags.py` меняет флаги временно; это отдельный явный эксперимент,
в сборке прошивки он автоматически не запускается.

## Что удалось восстановить для собственного драйвера

`recover-voice-abi.py` извлекает константы прямых ioctl-вызовов из дизассемблирования
и ELF literal pools. Он не выполняет код модема и оставляет нераспознанные
вызовы unresolved. Результат — `build/voice-abi.json`, со SHA256 бинарников
и адресами инструкций, которые задают номера запросов.

Для `libvoice.so` восстановлены:

| Функция | ioctl | Размер, закодированный в ioctl |
|---|---|---|
| voice_open | 0x4014760a | 20 |
| voice_close | 0x4014760b | 20 |
| voice_GetSlicFlag | 0x8004760c | 4 |
| voice_Vploop | 0x4004760d | 4 |

Эти константы сохранены в `src/voice-uapi.h`. Поля конфигурационной структуры
не восстановлены; присваивать им придуманные значения нельзя.
Драйвер, который реально реализует этот ABI, пока отсутствует.

В `zte_volte_main` дополнительно восстановлены AMR/media-подобные ioctl серии
0x7601–0x7608 и запросы с аргументами 4/8/16/20 байт.
Названия устройств `/dev/amr_device`, `/dev/volte_device` есть в бинарнике,
но сопоставление каждого ioctl конкретному устройству/codec-операции ещё не закончено.
Наличие этих строк не доказывает работоспособность кодека на MF79U.

## Транспорт AP ↔ PS

На живом модеме существуют `/dev/rpm0`–`/dev/rpm9`, major 249, minor 30–39,
и `/dev/at_ps`. Это подтверждает наличие транспорта, но не голосового канала.
Существующие каналы принадлежат работающим системным службам; их нельзя
читать для перехвата сообщений: чтение может забрать сообщения у службы.

Из официального PTCL SDK извлечены 149 дополнительных файлов:
`work/zte/voice/platform-selected/`.
MF79U board code описывает ICP/RPMSG AP↔PS и AP↔M0 с IRAM/DDR ring buffers.
Конфигурация SDK содержит `CONFIG_RPM_ZX29=y` и `# CONFIG_SOUND is not set`.
Это конфигурация опубликованного SDK, не подтверждённая конфигурация живого B03:
в скачанном B03 kernel image маркеров IKCFG_ST/IKCFG_ED не обнаружено.

В открытом экспериментальном драйвере ZX29 описано кадрирование:
little-endian magic 0x5453, длина payload u16, четыре байта заголовка,
payload с выравниванием до четырёх байт; нулевая длина допустима.
`zx-rpmsg.py` декодирует локальный snapshot кольцевого буфера по этому формату.
Проверены wraparound, нулевая длина, padding, пустой буфер и ошибочные кадры.
Применимость этого формата к голосовому каналу именно B03 ещё не подтверждена.

```sh
python3 firmware/mf79u/zx-rpmsg.py --selftest
python3 firmware/mf79u/zx-rpmsg.py --ring local-ring.bin --send-pos 8 --recv-pos 28
work/jffs2-venv/bin/python firmware/mf79u/recover-voice-abi.py
```

Транспортный декодер работает только с локальными файлами, не открывает
устройства и не пишет в физическую память. Его собственные тестовые кадры
не являются перехваченным трафиком модема.

Исходный reference code:

- https://gitlab.com/stefandoesinger/zx297520-kernel/-/blob/dlink/drivers/rpmsg/zx29_smd.c
- https://gitlab.com/stefandoesinger/zx297520-kernel/-/blob/dlink/drivers/remoteproc/zx29_zsp_rproc.c
- https://download.ztedevices.com/device/global/support/opensource/7/20200716_01/PTCL_MF79U_opensource_code.tgz

## Следующая зависимость

Для рабочего драйвера нужны номера/семантика голосовых RPMSG-каналов,
message IDs и структура PCM/AMR обмена. В извлечённых исходниках этой части нет.
Установка заглушки `/dev/voice_device` с успешными ioctl не обеспечит передачу
звука и не считается реализацией бэкенда.

Custom rootfs 0.2 включает расширенный диагностический ARM-компонент:
он показывает отдельно аудиопути и узлы транспорта CP, только через access(F_OK).
В том этапе изменения ядра/радиочасти, запуск IMS и загрузочная проверка rootfs не выполнялись.

## Третий этап: программный AMR-NB на модеме

После переподключения USB подтвердились штатные 19d2:0581, ADB/AT,
оба флага 0 и отсутствие аудиоустройств. Новые значения флагов в этом этапе
не устанавливались; `build/post-replug-flags.json` содержит результат чтения.

Сопоставление debug-строк рядом с ioctl в B03 `zte_volte_main` уточнило границу:
`/dev/amr_device` используется для encoder/decoder init/encode/decode/exit,
а `/dev/volte_device` — для конфигурации и read/write start/stop PCM-устройства.
`inspect-media-abi.py` сохраняет контекст в `build/media-ioctl-context.json`.
Строки рядом с вызовами служат статическим свидетельством; точные структуры
аргументов этих ioctl ещё не восстановлены.

Написан `src/amr-tool.c`, использующий OpenCORE AMR 0.1.6 вместо аппаратного
кодека. Это реальная локальная конверсия PCM↔AMR-NB; radio/ALSA/IMS он не открывает.
Собран статический ARMv7 soft-float бинарник, исполняющийся на текущем ядре.
Режим: mono 8000 Hz signed 16-bit LE ↔ AMR-NB MR122, 12.2 kbit/s, DTX отключён.
AMR-WB encoder и RTP упаковка в этом компоненте не реализованы.

Проверка на физическом MF79U:

| Проверка | Результат |
|---|---|
| Кодирование 10 с искусственного сигнала | 500 кадров, 0.536774 с |
| Декодирование этих кадров | 500 кадров, 0.085449 с |
| Общее время encode+decode | 0.622223 с |
| Размер AMR-файла | 16006 байт |
| Восстановленный PCM | 160000 байт, 10 с |
| Корреляция с исходным тестовым сигналом после подбора задержки | 0.8701 |
| Обрезанный AMR-кадр | Отклонён, success=false |

Это около 16× реального времени на данном искусственном сигнале,
не гарантия такого же результата для любого аудио/нагрузки.
Тест использует сгенерированные тоны 200/600 Hz, не запись разговора.
Бинарник запускался из RAM-backed `/dev`, данные лежали в `/tmp`;
все временные файлы на модеме удалены после теста. Постоянные настройки,
flash и состояние radio/IMS не менялись.

```sh
sh firmware/mf79u/build-codec.sh
python3 firmware/mf79u/test-codec-on-modem.py
```

Журнал измерений: `build/codec-test/result.json`.
Custom rootfs 0.3 включает codec CLI и лицензию Apache 2.0 OpenCORE AMR.
Подключение этого кодека к vendor IMS пока не выполнено. Для собственной
голосовой реализации аппаратный AMR-кодек уже не является обязательной
зависимостью; остаются call control, PCM транспорт и сетевой voice/IMS стек.

Upstream: https://sourceforge.net/projects/opencore-amr/

## Проверка с новой SIM и разрешённым тестовым вызовом

Пользователь заменил SIM и явно разрешил тестовый звонок на указанный им номер.
Ранее действовавшее ограничение на реальные звонки снято для этого номера.
Новая SIM: `AT+CPIN?` → READY; CREG/CEREG показали регистрацию со статусом 1.
Одна попытка голосового ATD с завершающей точкой с запятой вернула
`+CME ERROR: invalid command`. Команды завершения ATH и AT+CHUP тоже отклонены.
AT+CLCC до попытки также возвращала invalid command.
Нет свидетельства запуска вызова; AT-обработчик отверг команду.
AT+CEER вернула OK без дополнительного объяснения.
Настройки флагов, firmware и IMS в этой проверке не менялись.
Журнал: `build/authorized-call-test.json`.

## Изолированный запуск штатного IMS, 2026-10-06

Целевая схема: вызов через SIM, локальный SIP-транк для Asterisk через USB Ethernet.
Регистрация IMS у оператора нужна для VoLTE и не является регистрацией Asterisk.
Локальный SIP endpoint и двусторонний RTP-мост пока не реализованы.

Штатный B03 `zte_volte_main` запускается из RAM `/dev` с приватными IPC-очередями
`0x701e`/`0x700f`. Исходный бинарник совпадает с backup rootfs по SHA256
`3516bf3adfcfe97bbb029b1a89a1ada45b9b1bb578a08170d0141e15a96ab738`.
В тестовой копии отключены проверенный cfg_set/cfg_save wrapper и vendor trace.
Это не полная изоляция системных вызовов или CP: разрешённые команды к настоящей
SIM и IMS bearer действительно выполняются. Flash этим прототипом не прошивается.

Подтверждено на физическом модеме:

- Native parser принимает `CVMOD=3` и runtime IMS APN `ims`.
- Реальные CARDMODE, IMEI/IMSI, CPIN и EF_AD ответы позволяют завершить SIM init.
  Идентификаторы и данные аутентификации не сохраняются в отчётах.
- В B03 точная команда `AT+ZPDPACT=0,"IPV4V6","ims",0,1,1` **открывает** IMS
  bearer CID 5. `ZPDPACT=?` при этом отклоняется. SDK-комментарий о значении 0
  нельзя применять к этой измеренной команде B03.
- `CGCONTRDP=5` возвращает адреса IMS/P-CSCF; Linux `wan5` получает адрес.
- Native IMS отправляет SIP `REGISTER` и получает от оператора `401`.
  Это запрос аутентификации, а не успешная регистрация. Журнал только методов
  и кодов ответа: `build/ims-sip-register-401.log`.
- SIM `AT^MBAU` ответила статусом 0; размеры трёх строковых полей — 32/32/32,
  плюс поле длины. Native parser обрабатывает status 0 как успешную ветвь AKA.
  Значения RES/CK/IK не выводятся и не сохраняются. Отдельный `OK` не является
  достаточной проверкой AKA-статуса.

Есть две нерешённые зависимости:

1. В текущем ядре нет NETLINK_XFRM (`socket` errno 93, Protocol not supported)
   и PF_KEY v2 (errno 97). IPv4 UDP, NETLINK_ROUTE и AF_PACKET доступны под root
   с полными capabilities. Штатная `libsoftap.so::ipsec_set` использует команды
   `ip xfrm state/policy add`, так что её механизм IPsec на этом ядре недоступен.
   Опубликованный SDK config содержит XFRM/ESP, но отличается от живого B03;
   его конфигурацию нельзя выдавать за конфигурацию работающего устройства.
2. При передаче AKA-ответа в native IMS наблюдались самопроизвольные перезагрузки.
   Пользователь подтвердил отсутствие отключения USB. В наблюдавшемся kernel ring
   до обрыва не пойманы Oops/panic/OOM; это не исключает ошибку ядра или CP reset.
   При удержании AKA-ответа (не передавали его в native) тест завершился и модем
   оставался на том же boot спустя более двух минут после остановки процесса.
   Причина сбоя ещё не установлена; IPsec-зависимость сама по себе её не доказывает.

Порядок очистки исправлен: сначала подтверждённо останавливается наш native daemon,
затем завершается probe, затем удаляются только очереди из инвентаря этого запуска
с проверкой key/ctime/owner и отсутствия живых сторонних пользователей.
Изменение порядка очистки не считается доказанным устранением всех перезапусков.

Инструменты:

```sh
sh firmware/mf79u/build-ims-diagnostics.sh
python3 firmware/mf79u/start-private-ims.py --observe-sip
python3 firmware/mf79u/test-private-ims.py --relay --initialize --cp-status \
  --network-state --ims-bearer --ims-auth --stop-native
```

`--hold-aka-reply` выполняет настоящий AKA запрос, но удерживает ответ до native
IMS, чтобы отделить SIM/CP обработку от следующей стадии. Это диагностический
вариант, не свидетельство регистрации. `build/ims-aka-held-test.json` содержит
только статусы/размеры и редактированные события этого эксперимента.

`ims-sip-observer.so` собирается для vendor uClibc с SysV hash и без зависимости
от GNU libc. Его отдельный FD содержит только SIP method/status и IPsec return
codes. Первоначальная сборка с GNU hash загружалась, но не перехватывала нужные
символы; её пустой журнал нельзя использовать как доказательство отсутствия SIP.
`kernel-summary` читает кольцо неразрушающе и фильтрует fatal/reset/OOM события.
`volte-signal-watch` использует ptrace только для нашего RAM daemon и его threads,
сохраняет PC/LR/SP при fatal signal, не читает содержимое памяти, и останавливает
аварийный процесс для контролируемого завершения. После такого останова stop-script
посылает SIGTERM, затем SIGCONT, чтобы pending termination был обработан.

На этапе observer SIP `200`, исходящий вызов и двусторонний звук ещё не были
подтверждены; реальные вызовы тогда не выполнялись. Более поздняя проверка
регистрации через ESP userspace описана ниже.
Экспериментальный JFFS2 rootfs по-прежнему не прошит и не прошёл boot-проверку.

## ESP в userspace: реализация и проверки на 2026-10-06

Штатный B03 после AKA запрашивает четыре SA в порядке out/in/in/out,
AES-CBC и HMAC-MD5-96. Наблюдатель подтвердил: каждая команда `ip xfrm`
завершается кодом 1, но vendor `ipsec_set` всё равно возвращает 0.
Это не успешная установка IPsec. Доказательства: `build/ims-xfrm-failure.log`
и `build/ims-sa-inspection.log`.

Один SIGSEGV наблюдателя был вызван нашей ошибкой разрешения символа:
`RTLD_NEXT` не находил `libsoftap::ipsec_set`, и первоначальный observer
вызывал NULL. Исправлено через явный handle `dlopen("/lib/libsoftap.so")`
и проверку указателя. Это объясняет тот конкретный SIGSEGV, но не устанавливает
причину более ранних самопроизвольных перезагрузок без observer.
Последующие контролируемые запуски завершались без наблюдавшегося fatal signal.

`src/ims-userspace-ipsec.c` заменяет только IPsec transport в RAM-копии IMS:
получает native SA через восстановленный ABI, шифрует UDP в ESP через vendor
OpenSSL, передаёт raw IPv4/ESP по `wan5`, проверяет MAC и replay window на
приёме и возвращает UDP штатному процессу. Ключи остаются в RAM и очищаются
при удалении SA; в журнал попадают методы SIP, коды ответа и этапы проверки.
Поддерживаются IPv4, UDP, AES-CBC-128 либо NULL, HMAC-MD5-96/HMAC-SHA1-96,
64-пакетное окно replay без ESN. TCP, IPv6 и NAT-T пока не реализованы.

Проверено:

- `test-esp-null.py`: независимые Python HMAC и OpenSSL AES oracle,
  integrity, padding, повторы, exhaustion sequence, ограничения буферов,
  1000 некорректных пакетов и размеры UDP 8..4096 байт.
- `ims-crypto-selftest`: на ARM модема прошли публичный AES-CBC vector RFC 3602,
  HMAC-MD5 vector и генерация случайных IV. Это синтетическая проверка,
  не успешный обмен ESP с оператором.
- `udp-injection-selftest`: raw IPv4 UDP принят локальным UDP socket на модеме
  с сохранением исходных адреса/порта peer. Проверка выполнена на loopback.

Сборка `.so` использует SysV hash, vendor uClibc/OpenSSL и статические compiler
helpers libgcc. Отдельный bootstrap использует vendor dynamic loader и
выравнивает ARM stack на 8 байт. GNU libc в зависимостях `.so` отсутствует.

Первый live запуск дошёл до REGISTER/401 и AKA status 0, но адаптер отклонил
native SA при проверке поля mode. `build/ims-userspace-shape.log` показывает
stage 13 для всех четырёх SA. Следующий запуск установил фактическое значение
`mode=trans` (журнал `build/ims-userspace-mode.log`). Добавлена поддержка этого
сокращения transport; iproute2 также принимает его в `xfrm_mode_parse` через
проверку prefix `matches`. Исходник: [ipxfrm.c](https://github.com/iproute2/iproute2/blob/main/ip/ipxfrm.c).
После добавления фрагментации защищённый REGISTER/200 подтверждён; см. результаты ниже.

```sh
sh firmware/mf79u/build-ims-diagnostics.sh
python3 firmware/mf79u/test-esp-null.py
python3 firmware/mf79u/start-private-ims.py --userspace-ipsec
python3 firmware/mf79u/test-private-ims.py --relay --initialize --cp-status \
  --network-state --ims-bearer --ims-auth --stop-native
```

Формат ESP и тестовый vector: [RFC 4303](https://www.rfc-editor.org/rfc/rfc4303),
[RFC 3602](https://www.rfc-editor.org/rfc/rfc3602),
[RFC 2403](https://www.rfc-editor.org/rfc/rfc2403).

### Подтверждённая регистрация с оператором

`build/ims-userspace-first-200.log` фиксирует защищённый REGISTER (1993 байта),
два IPv4 фрагмента при MTU `wan5=1400`, входящий ESP с валидным MAC и SIP 200.
Штатный процесс получил этот UDP и запросил `AT+ZIMSSTATE=1`.
Затем отправлен защищённый SUBSCRIBE и получен защищённый SIP 200.
Это реальная сеть и реальный SIM AKA, а не синтетические ответы.

Причина предыдущего отказа UDP установлена: raw socket с IP_HDRINCL вернул
EMSGSIZE (errno 90) для крупного зашифрованного REGISTER. Реализация
`ipv4-fragments.c` делит уже зашифрованный ESP datagram с одним IPv4 ID,
8-байтными offsets и checksum каждого заголовка. На Mac независимые проверки
checksum/reassembly/границ MTU прошли; на модеме четыре локальных IP-фрагмента
с протоколом ESP были собраны ядром до выдачи raw socket.

Повторный запуск `build/ims-userspace-state.log` подтвердил REGISTER/200 и
успешную передачу `AT+ZIMSSTATE=1` в CP. После регистрации native CLCC вернул
пустой список/OK, CVMOD оставался 3. При завершении CP подтвердил
ZPDPDEACT=5 и ZIMSSTATE=0; CID1 сохраняется.

Диагностика также установила наличие входящего ESP с валидным MAC и
Next Header 6 (TCP). Адаптер пока принимает только UDP; такие сообщения
отклоняются. Исходящие TCP-соединения к защищённому peer блокируются,
чтобы не отправлять SIP поверх незащищённого TCP. Native SIP успешно
перешёл на защищённый UDP для REGISTER. Полный TCP transport остаётся
отдельной зависимостью, в частности для входящих SIP-запросов оператора.

Замена SA теперь учитывает direction и selectors: новая аутентификация
с теми же адресами/портами заменяет старую SA и очищает её ключи.
Одновременные поколения SA для handover пока не реализованы.

### Ограниченный тест набора

`--dial-test` разрешает native IPC probe одну попытку только на номер,
явно разрешённый пользователем. Флаг требует проверки регистрации/CP state,
responsive CVMOD=3, отсутствия уже существующего CLCC и controlled shutdown.
C-probe отправляет ATH/CHUP через 30 секунд независимо от host-loop;
host также отправляет отбой и проверяет CLCC перед выключением IMS.
При обычном запуске probe набор номера по-прежнему запрещён.
Эта возможность ещё не означает подтверждённый вызов или рабочий звук.

### Первая отправка INVITE с местным номером

После уточнения пользователя тест использовал местную запись разрешённого номера,
без кода страны (`--local-number`). SIM MCC — 280, serving PLMN — 28010.
Реальный CP вернул одинаковый `+ZNUMTYPE: 0,0`/OK для международной и местной
записи. Сначала relay блокировал запрос классификации, затем `AT+CSTA?`;
оба чтения теперь разрешены. CP отвергает CSTA как invalid command, однако
native обработчик продолжает набор с типом адреса 129. Ответ CSTA не подменялся.
Стандартное значение 129 для записи без `+` описано в
[3GPP TS 27.007, 6.1](https://www.etsi.org/deliver/etsi_ts/127000_127099/127007/17.07.00_60/ts_127007v170700p.pdf).

`build/ims-userspace-local-invite.log` фиксирует защищённый INVITE (2306 байт,
два IPv4 фрагмента) и защищённый SIP 100 Trying. Через 10 секунд watchdog
отправил native hangup: наблюдались CANCEL, SIP 200, SIP 487 и ACK.
SIP 100 подтверждает обработку транзакции, но не правильную маршрутизацию номера,
звонок на телефоне или установление разговора. SIP 180/183/200 для INVITE
не наблюдались. Native события ORIG/CONF тоже не доказывают ответ абонента.

Штатный тестовый процесс завершился без наблюдаемого fatal signal;
uptime не сбросился. После очистки CP подтвердил ZIMSSTATE=0 и деактивацию
CID5, CGACT показал CID1=1 / CID5=0. Обнаружена и исправлена гонка host harness:
после остановки native/QUIT он ещё пытался пересылать CP reply в закрытый pipe.
Эта ошибка произошла уже после успешного CANCEL и не была ошибкой модема.

Временная проверка TUN не создала интерфейс: open узла major 10/minor 200
вернул ENODEV (19); проверочный узел удалён. Штатный список iptables targets
не содержит QUEUE/NFQUEUE. Это не доказывает невозможность добавления модуля,
но готового TUN пути для защищённого TCP на данном ядре не найдено.

### Предыдущий этап с новой SIM: достижение 183 и отказ кодека

После замены SIM и явного изменения разрешённого номера whitelist в C-probe
и Python relay обновлён; прежний номер больше не разрешён. Все новые попытки
использовали местную запись. CPIN=READY, CEREG stat=1, serving PLMN=28020.
С этой SIM снова подтверждены настоящие AKA, защищённый REGISTER/200 и
SUBSCRIBE/200. При одном повторном запуске первые REGISTER получили SIP 500;
штатные повторы затем получили 401 и завершили регистрацию SIP 200.

Первый тест с прежним 10-секундным watchdog получил INVITE/100, затем был
отменён таймером. Лимит увеличен до 30 секунд от подачи ATD (не от INVITE),
host ждёт 32 секунды перед своим отбоем. Наблюдатель fatal signals теперь
имеет лимит 240 секунд, чтобы не замораживать native во время длинного теста.
Ограничение одного набора на процесс probe сохранено.

Две последующие попытки достигли защищённого SIP 183 Session Progress.
До автоматического отбоя native сам отправил CANCEL, затем PRACK; наблюдались
200 для отмены, 487 для INVITE, ACK и 481 для позднего PRACK. Это не SIP 200
для установления разговора. SIP 180 и подтверждения ответа абонента нет.

Добавлен наблюдатель open/ioctl в RAM shim: он пишет только точное имя одного
из трёх media devices, return/errno и числовой ID media ioctl. Буферы ioctl,
аудио и SIP/SDP bodies не записываются; системный вызов и его результат
сохраняются. В последнем тесте непосредственно между получением SIP 183 и
отправкой CANCEL зафиксировано:

```
/dev/amr_device result=-1
MEDIA open errno result=2
```

Это подтвердило отказ открытия отсутствующего драйвера AMR (ENOENT),
блокировавший подключение native media на этом этапе. Тогда самостоятельный
OpenCORE AMR-NB CLI уже был проверен, но к native IMS ещё не подключён.
Ниже описана выполненная замена и результат повторного звонка.

Native после отказа также запросил AT^ZCSVOICESPT. Запрос теперь передаётся
в CP, который реально отвечает invalid command; положительный ответ не
подставляется. Без ответа relay ранее оставлял обработчик ожидающим. В последнем
тесте обработчик завершился, CVMOD вернулся в 0, процесс и его очереди удалены,
CP подтвердил ZIMSSTATE=0 / ZPDPDEACT=5, а CGACT — CID1=1 / CID5=0.
Самоперезагрузки и fatal signal в этих попытках не наблюдались.

Безопасные журналы: `build/ims-new-sim-media-call-sip.log`,
`build/ims-new-sim-media-call-test.log`, `build/ims-new-sim-media-call-report.json`.
Host события последнего теста содержат elapsed_s для сопоставления подачи ATD,
внутренней отмены вызова и последующего watchdog. Прошивка и NV не записывались.

### Программный AMR-NB: подтверждённые звонок и ответ

`src/ims-software-media.c` подключает OpenCORE AMR 0.1.6 к фактическому ARM32
ABI native IMS. Определены layout encoder/decoder init, encode/decode ioctl
и PCM config по коду конкретной B03. Encoder копирует входной PCM, поскольку
OpenCORE изменяет его при обработке. Самопроверка на модеме прошла для всех
восьми режимов AMR-NB: сравнение с независимым экземпляром кодека, размеры
кадров, границы буферов, декодирование и ненулевая энергия синтетического PCM.
AMR-WB не реализован; тест явно выбирает AMR-NB через `AT+ZIMSAMRW=0` и
проверяет ответ `+ZIMSAMRW: 0` перед набором.

Shim перехватывает открытие только отсутствующих `/dev/amr_device` и
`/dev/volte_device`, когда задан `MF79U_SOFTWARE_MEDIA=1`. Он обслуживает
известные ioctl программно. Вместо микрофона и динамика используется
диагностический PCM: источник тишины и приёмник, отбрасывающий звук.
Чтение и запись имеют задержку по длительности PCM, обычно 20 мс.
Это позволяет проверить запуск media и сигнализацию без записи разговора.

В первой версии пользователь подтвердил звонок и ответ, но после запуска PCM
ADB и AT перестали отвечать; потребовалось переподключение USB. Предполагаемая
причина — немедленное завершение виртуальной записи в сочетании с realtime
планированием native потока. Причина не была изолирована отдельным тестом.
Исправлены обе стороны PCM pacing; запросы `pthread_setschedparam` только в
частном IMS-процессе переводятся в `SCHED_OTHER` с нулевым приоритетом.

Повторный тест после переподключения подтвердил:

- Настоящие SIM AKA и защищённую регистрацию IMS.
- INVITE → 183, PRACK/200 → 180 Ringing, PRACK/200.
- SIP 200 для INVITE (996 байт), исходящий ACK и native `^CONN: 1,0`.
- Пользователь подтвердил: «Звонок пришёл, ответил».
- Отбой BYE/200, затем deREGISTER/200 и `CVMOD=0`.
- Отсутствие наблюдаемого fatal signal; ADB отвечал во время соединения.
- После теста PID частного IMS отсутствует, его инвентаризированные очереди
  удалены. CP подтвердил `ZIMSSTATE=0` и `ZPDPDEACT=5`; финальный CGACT:
  CID1=1 / CID5=0. Uptime вырос с 78.93 до 514.17 секунд без перезагрузки.

В момент принятия вызова также наблюдались CANCEL/481; затем native обработал
200 для INVITE, отправил ACK и сообщил соединение. Последующий BYE/200
подтверждает завершение установленного диалога. Эту гонку ещё нужно проверить
при доведении прототипа до постоянной работы.

После теста осталась vendor-очередь 4140: один отправитель — PID тестового
IMS, получателя нет. В native коде есть отправка 12-байтных уведомлений
освобождения audio resource на эту очередь. Она относится к штатному IPC
пространству и не удалялась частным cleanup. Перед постоянным запуском
следует изолировать и этот путь уведомлений. Содержимое очереди не читалось.

Повторяемая сборка и один ограниченный вызов на разрешённый номер:

```sh
sh firmware/mf79u/build-ims-diagnostics.sh
python3 firmware/mf79u/start-private-ims.py --userspace-ipsec --software-media
python3 firmware/mf79u/test-private-ims.py --relay --initialize --cp-status \
  --network-state --ims-bearer --ims-auth --ims-state --post-register-status \
  --dial-test --local-number --prefer-amr-nb --stop-native
```

Готовность на этом этапе: исходящий звонок и ответ доказаны на реальной сети.
Двусторонняя речь, входящие вызовы и SIP-транк для Asterisk не проверены и
не реализованы полностью. TCP внутри IMS ESP также остаётся неподдержанным.
Последние изменения находятся только в RAM-прототипе; rootfs 0.3 не прошивался
и не содержит этой интеграции.

Архивы: `build/ims-software-paced-call-sip.log`,
`build/ims-software-paced-call-report.json`,
`build/ims-software-paced-call-signals.log`,
`build/ims-software-paced-call-postcheck.json` и
`build/ims-software-paced-call-result.json`. Предыдущая попытка с зависанием
сохранена отдельно в `ims-software-first-answered-*`.

## SIP-транк MikoPBX и сетевой PCM

2026-10-06 MikoPBX 2026.5.6 ARM64 запущена в Docker Desktop на Mac и соединена
с PJSIP 2.17 endpoint на модеме `192.168.0.1:5080`. PBX использует USB IPv4
Mac `192.168.0.169`, NAT адреса исправлены в SIP/SDP. Транк — IP peer, без
регистрации в PBX; отдельная регистрация native IMS у оператора сохраняется.

`MF79U_PCM_NETWORK=1` включает реальный обмен signed 16-bit PCM mono 8 kHz
через loopback UDP между native media adapter и custom pjmedia port. PBX RTP
использует PCMU, IMS — программный AMR-NB. Статический синтетический ARM тест
подтвердил оба направления данных, malformed packet и отказ от 16 kHz.
Media pacing и `SCHED_OTHER` сохранены; звук не записывается.

Реальный тест из MikoPBX установил вызов через SIM; пользователь подтвердил
слышимые сигналы PBX. PJSIP/PCM статистика: 807 кадров от native IMS к PBX,
682 к native IMS, из них ненулевых 741 и 363. Последний тест завершён за
29.2 с, после него нет PBX каналов, транк `Avail`, ADB отвечает, LED синий.
Настоящие состояния outgoing/connected/end переключили LED зелёный→синий.

Это подтверждение передачи звука PBX→телефон и обратной аудиоактивности.
Позднее подтверждён входящий SIM-вызов с автоответом PBX и записью речи:
25.78 с исходного mono PCM16 WAV на 8000 Hz, пик −7.42 dBFS, без клиппинга.
Локальный Whisper small распознал повторения «раз-два-три», «проверка» и часть
фраз с ошибками. По этому результату нельзя выставлять оценку MOS или
отделять намеренные паузы от пропусков PCM. После отбоя маршрут возвращён
на 201, временное приложение записи удалено, LED вернулся в синий.
Исправлены SIP Request-URI для входящего транка, identify адреса Docker SNAT,
перехват демонстрационным расписанием PBX и безымянный RING в LED-политике.

Полная оценка качества двусторонней речи, DTMF, повторные вызовы под
нагрузкой и восстановление USB ещё требуют проверки. Сигнализация CP пока
идёт через Mac relay. Сохраняются ограничения UDP-only ESP и vendor IPC 4140.
Подробности: [PBX README](../../outputs/mikopbx/README.md).

Offline rootfs 0.5 содержит компоненты этого этапа. Автозапуск голоса и
запись rootfs на устройство не выполнялись. На модеме работает RAM-версия.
После исправлений образ пересобран и проверен: 1839 путей и CRC,
345 vendor binary paths сохранены. Размер 39315840 байт, SHA256
`cde14b7f3ccc237338f310a200d240ed0e26eef8526489020c02b809831ec390`.
RAM-копии LED daemon, IPC probe и SIP gateway побайтно совпадают со сборкой.

## Адаптивный RAM-мост: AMR-WB и G.722, 2026-10-06

Последние результаты заменяют ограничения ранних AMR-NB прототипов выше.
`run-pbx-gateway.py --adaptive-audio` включает AMR-WB в native IMS и
программные WB encoder/decoder. Между native media и PJSIP передаётся
PCM16 mono 16000 Hz: WB без понижения частоты, резервный NB через FIR
8000↔16000 Hz. SIP endpoint и MF79U provider в MikoPBX допускают G.722/PCMU.
Обычный запуск без флагов сохраняет NB и исходный CMR; `--prefer-high-amr`
включает только запрос максимального разрешённого NB режима.

Входящий вызов пользователя подтвердил AMR-WB PT117, mode-set 0/1/2,
98.51% речевых кадров на 12.65 кбит/с, настоящий native PCM 16000 Hz и
G.722 до PBX. Обе PCM-очереди без underflow/overflow; исходная запись
10.82 с, 16000 Hz, без клиппинга и одиночных нулевых кадров по 20 мс.
Пользователь: «Заметно лучше, но не clearvoice».

PrimeTel предложил также WB PT112 со всеми режимами до 23.85 кбит/с,
PCMU, G.729 и G.722. Более высокий WB профиль и операторский G.722 media
не проверены. Стандартных EVS/AMR-WB+ объявлений в этом вызове не обнаружено;
их codec bridge не реализует. Два остальных payload не распознаны logger.
Это один маршрут вызова, не полный инвентарь операторской сети.

Проверены ARM ABI всех девяти WB режимов, границы буферов, двусторонний
PCM loopback 8000/16000 Hz, SDP/CMR BE/OA NB+WB и сохранение тона 6 kHz
в WB и G.722. Для старого adbd загрузка RAM-файлов выполняется небольшими
блоками с проверкой checksum и атомарной заменой; уже совпадающие файлы
не переписываются. Flash не записывалась. Offline rootfs 0.5 не содержит
этих последних WB/CMR изменений и не прошивался.

Подробные счётчики: [качество](../../outputs/mikopbx/audio-quality.md),
кодеки оператора (historical local artifact: `../../outputs/mikopbx/operator-codecs.json`).

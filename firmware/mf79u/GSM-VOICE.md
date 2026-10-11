> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# GSM voice fallback: текущая граница и защита теста

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
по-прежнему не установлен; результат MO19 приведён выше.

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


### Наблюдение общей DSP RAM: idle preflight (2026-10-10)

`cs-pcm-metadata-idle-live.json`: точный B03 initializer определил семь
pointer-bounded окон FAD014BA..FAD0224C, по 1022 halfwords за проход.
Read-only sampler принят, статистика idle неизменна; модуль выгружен,
profile27/flags0/0/IMS/guards и исходные boot/PIDs восстановлены. Raw samples
и hashes не сохраняются; ownership и PCM classification не подтверждены.
Классификатор period8/16/32 прошёл ARM selftest: три тона распознаны,
тишина/DC/100 noise blocks отвергнуты. Подготовлен один исходящий контроль
с уже слышимым DSP-тоном без включения ARM I2S. Подробности в [DSP-ABI.md](DSP-ABI.md).


### MT32: полный voice API не открыл PCM (2026-10-10)

`cs-mt32-full-voice-open-live.json`: incoming CONNECT подтверждён; пользователь
слышал писк в начале, затем более жужжащий звук. DSP-only control и полный AFE
набор приняты с negative ACK. ARM master TX23102/RX23106, nonzero0, failed0.
Звонок автоматически завершён, MM refs0, callback/AP/tone/registers возвращены.
Все проверки `cs-mt32-full-voice-open-restore.json` прошли: исходные profile27,
flags0/0, LTE/IMS, guards и PIDs1620/1680, тот же boot1c2740a7. Local header/config
также восстановлены. Изменённые mixer levels и inactive PCM tail сами по себе
не открыли ARM PCM. Production CS↔SIP/fallback не установлен. Дальше изучается
выбор цифрового источника через реальный voice path API и общая DSP RAM.

### Полный voice API: idle проверка и подготовка MT32 (2026-10-10)

Реальные reference Open/Enable/path/unmute дали другие mixer levels и нулевой
PCM tail для AFE, чем прежний ручной builder. `cs-full-voice-open-live.json`
подтвердил все11 DSP ACK, TX15667/RX15670, nonzero0, failed0; исходные
registers/AP/tone/header/config/profile27/flags0/0/IMS/guards восстановлены.
Завершён входящий MT32 с этим набором на активном TCH:2s проверенный
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


Тестовый звук во входящем GSM вызове **получен и подтверждён пользователем**:
MT19, 2026-10-09 21:01 UTC / 2026-10-10 local, «Теперь хорошо слышно».
Три tone phases500/1000/1500 Hz, по2s; volume100/amplitude_input8000,
reference tone mixer resource1. `build/cs-mt19-working-tone-summary.json`,
`build/cs-mt19-dsp-tone-live.json`. Это ограниченный DSP tone diagnostic;
двусторонний PCM/SIP voice и production IMS→CS fallback ещё не реализованы.
Устранение остаточного шума пользователь отдельно не подтверждал.

Полное восстановление после MT19 проверено `build/cs-mt19-final-restore.json`:
profile27,0,1,2, flags0/0, IMSready=true, ring-only/CS-only=false, SIP idle.
Boot8e20fcc3/native1694/SIP1813 сохранены, CC/ASC callbacks и admission исходные,
MM CC refs0, sysfs absent, sampler unloaded. Inactive diagnostic modules pinned
до reboot; автоответ/тон после теста не активны. Production binaries/PCM contract
и raw flash не менялись. Первая restore route probe показала refs3 при
protocol255; она не является quiescence proof (`build/cs-mt19-first-route.json`).
Повторная actual probe после LTE/IMS ready подтвердила refs0/quiescent1;
immutable final route: `build/cs-mt19-final-restore-route.json`.

MT16 (2026-10-09 20:46 UTC) соединился и корректно завершился; пользователь
подтвердил тишину. Генератор не выполнил ни одной audio command: фактический
речевой канал имел channel=1/mode=1, прежний gate разрешал только mode=9.
`build/cs-mt16-dsp-tone-live.json`: CONNECT ACK, auto hangup, MM refs=0,
callback restored, тот же boot8e20fcc3/native1694/SIP1813.

Exact B03 predicate BF40FA60..FAA6 использует mask0x783 для speech modes
1/2/8/9/10/11; отдельный AMR predicate BF4105A0 допускает9/11. Поэтому
DSP tone diagnostic расширен только на наблюдавшийся mode1 и прежний9.
AMR frame candidate не менялся. Static evidence:
`build/cs-mt17-speech-gate-evidence.json`. Слышимый звук ещё не подтверждён.

MT17 (2026-10-09 20:51 UTC) впервые реально выполнил audio commands и все
три tone phases в connected mode1/channel1. Пользователь услышал тишину.
Duration16000 записывается, но в samples через1s уже0; tone status raw0/9,
его смысл пока не установлен. Mailbox idle не доказывает слышимый звук.
MM clearing, callback и сохранённые AP fields восстановлены, boot/PIDs прежние.
`build/cs-mt17-dsp-tone-live.json`. Полное LTE/IMS восстановление проверено:
`build/cs-mt17-final-restore.json`, profile27/flags0/0, guards сняты,
callbacks/admission/MM refs verified, IMSready=true.

MT18 (2026-10-09 20:57 UTC) дал **первый подтверждённый пользователем
слышимый CS tone**: «Шум и еле-слышно тоны на фоне». Generator, все3 phases,
MM clearing, callback/AP fields restore прошли; boot/PIDs сохранены.
`build/cs-mt18-dsp-tone-live.json`. Чистый звук, speech PCM и production
fallback ещё не реализованы; audible_test_tone_confirmed=true означает
только эту ограниченную проверку tone candidate.

Исправлен пропуск reference tone mixer: ранняя эмуляция напрямую выставляла
resource0 и пропускала updater; payload11 имел нулевые tone gains18/19.
Reference tone controller24787C50..64 активирует resource1;
updater247885F4..88638 пишет gains+24/+26. Bounded offline emulation выполняет
RAM-only volume defaults и этот updater: volume30, gains32767/32767,
gain по+10=4359. Нет device access/hardware execution.
`build/mf283u-tone-uplink-emulation.json`, SHA e5a2ea66571b0c387c741435201e0a164fcad2f3df091ba4e11c26fd39f23c52.
`prepare-cs-dsp-audio-parameters.py` генерирует проверенный header;
build связывает его с basename/SHA256 immutable report.

MT19 armed2026-10-09 21:00 UTC с volume100 и amplitude_input8000;
reference emulation даёт gain32690 и tone amplitudes3061/5656/7390.
По сравнению с MT18 изменён только gain halfword8 в command11 и waveform
amplitude; audio route12/15 прежний. Расчётный прирост23.52dB, это не
измерение на телефоне. `build/mf283u-tone-uplink-volume100-amplitude8000-emulation.json`,
SHA0ca9aea823cff9553c06f0d3baf05d87ecc229cc15491dd896cc813492135be7.
Нет PCM/clock/peripheral/DSP program writes; ARM relocation audit прошёл.
Во время MT19 GSM CS-only был временно активен, IMS выключен, тот же
boot8e20fcc3/native1694/SIP1813.
MT19 соединился, все3 phases исполнены, пользователь подтвердил хорошую
слышимость; полное restore описано выше. `build/cs-connect-probe19-armed.json`,
`build/cs-mt19-dsp-tone-live.json`. Предыдущая restore verification до test18:
`build/cs-mt17-final-restore.json`.

Последнее полное восстановление перед test16, 2026-10-09 20:41 UTC:
`build/cs-dsp-tone-final-restore.json` и его immutable route audit. На том же
boot8e20fcc3-6d36-46ad-ae25-5e001743f155, native1694/SIP1813, profile27,0,1,2,
flags0/0, IMSready=true, CS-only/ring-only=false, SIP idle. Фактические CC/ASC
callbacks и voice-admission literal исходные, MM CC references=0; sysfs
handlers отсутствуют, channel sampler снят. Неактивные diagnostic modules
pinned до reboot; production native/SIP binaries и PCM contract не менялись.
Ни одного audio mailbox command в новых MO9–15 не исполнено: MO10 CONNECT
не запустил generator, остальные попытки не соединялись. MT13 истёк без
входящего вызова. Слышимый тон и устойчивый CS/SIP fallback не подтверждены.

MT16: `build/cs-connect-probe16-build.json`. Его тишина объясняется блокировкой
generator по mode1; это не завершённая проверка audio commands.

## Разрыв установки MO и typed RR metadata (2026-10-09)

MO14 дополнен passive ASC. MM установился после identity exchange и ciphering
completion; SETUP дошёл до AAD4/ASC (pd3/type05), но ответа CC не было. Через31.4s
пришёл ABD9 length8, затем MM reason10; CONNECT/audio commands отсутствовали.
`build/cs-mo14-dsp-tone-live.json`. Это не проверка звука. Hooks/admission
восстановлены, native1694/SIP1813 и boot8e20fcc3 сохранились; ASC истёк отдельно.

Offline найден exact B03 RR release constructor BF05D184: тело8 bytes очищено;
byte0=context+38A, byte1=context+38F, u16+4=context+38C, byte2=0. Следующий ASC
observer читает только эти3 scalar fields и проверяет constructor signature.
Названия/семантика enum пока не доказаны; не приравнивать MM reason10 к
3GPP MM cause10. Никакие identities/raw PDU не сохраняются. MO15 снова не дошёл до CONNECT;
наблюдались fields0=0,1=1,4=0. Constructor path BF05DEBC преобразует GRRC
release B2DD, field4 получается из его u16+4 через BF05D270; значение0
не является явным CC reject. Field1 — инверсия входного byte8. Семантика
этого флага ещё не доказана. `build/cs-mo15-dsp-tone-live.json`.
MM handler
BF3570DA выбирает internal reason10 в default RR-release ветке (если guard
BF4B1BBD не равен1), что дополнительно ограничивает прежнюю интерпретацию.

## Входящий one-answer tone probe (2026-10-09)

MO12 без radio reattach также завершился MM reason10 до CONNECT;
`build/cs-mo12-dsp-tone-live.json`. Audio commands не выполнялись в MO11/12,
семантика внутреннего reason10 ещё не доказана. Повторные исходящие без нового
диагностического изменения остановлены. Перед MT13: boot8e20fcc3, native1694/SIP1813,
CS registration1, IMS выключен временным CS-only guard, voice flags1/1.
После проб временная policy снята; актуальная restore verification выше.

Подготовлен отдельный `--connect-probe --dsp-tone-candidate`:
`src/cs-mt-tone-probe.c`, `src/cs-mt-state.h`. Один входящий TI0 получает
CALL CONFIRMED/ALERTING/CONNECT; budget тратится до отправки, retransmission
и второй вызов не отвечаются. Генератор запускается только после сетевого
CONNECT ACK, затем три частоты500/1000/1500 Hz по2s. Через10s отправляется
DISCONNECT с обязательной Cause LV (не RELEASE TLV); MM release исполняется
в реальном CC task. Callback восстанавливается после real MM ref clearing;
при неподтверждённой очистке сохраняется. Настройки production PCM/SIP и
voice-admission literal не меняются. Audio mailbox compatibility всё ещё
гипотеза; AP-owned fields сохраняются и возвращаются, скрытый DSP state не
подтверждён. Тот же bounded candidate, что у MO, с отдельным log prefix.

MT lifecycle fixture с ASAN/UBSAN проверил one-answer budget, TI/window gate,
CONNECT ACK, отсутствие повторного ответа, Cause LV/TLV и MM clearing state.
`build/cs-mt-state-fixture.json`. ARM build instance13 прошёл relocation audit
включая checked ktime_get ABI; `build/cs-connect-probe13-build.json`.
`collect-cs-mt-tone.py` сохраняет только scalar state/command evidence, без
номеров/идентификаторов/сырого PDU. Instance13 установлен в RAM без reboot/PID changes; native guard сохранён.
`build/cs-connect-probe13-armed.json`. Запущен collector
`build/cs-mt13-dsp-tone-live.json`, входящий вызов за300s не пришёл. Module13 автоматически восстановил
CC callback; тот же boot/PIDs, audio commands не выполнялись. Это не
отрицательный audio test. Следующая MO14 проба дополнена passive ASC для
уточнения сетевого разрыва/проверки tone при CONNECT.
MT18 позднее подтвердил слабый слышимый тон; чистый звук ещё предстоит. Обычная SIM и ответ уже явно разрешены пользователем в этом чате.

## Отдельный audio mailbox и DSP tone candidate (2026-10-09)

Offline reference MF283U B05 извлечён из RAR5: partition index и SHA256 в
`work/zte/voice/mf283u-reference/partition-index.json`. CP ARM link base
23F00000 подтверждён указателями/векторами; gzip payload SHA256
49c94841f7608e500302e6b4d4cbff1103f6be6e2ec2226b617bed312fb56513.
UBIFS rootfs извлечён только локально. Reference binaries не запускались на
модеме и не прошивались. Небольшие ARM parameter builders эмулированы офлайн
через Unicorn; OS/DSP transport/hardware-control calls перехвачены.
`work/zte/voice/inspect-mf283u.py`, `emulate-mf283u-audio.py`.

Первоначальный вывод «GSM stubs B03 объясняют отсутствие звука» слишком широк:
сопоставленные GSM stub functions присутствуют и в MF283U. Существенное
отличие — полный AUD/voice/PCM driver reference и его отдельный audio mailbox.
GSM DSP shared SRAM layout структурно совпадает: MF283U F600xxxx соответствует
B03 FAD0xxxx; это не разрешение копировать reference VA/код или DSP patch.
Boot/download tables различаются; первые три records и несколько data records
совпадают, code patches нет. `build/mf283u-b03-gsm-dsp-boot-comparison.json`.

Подтверждён B03 audio mailbox ABI BF3E9D40: command + total halfword count
(включая command) + u16 payload + connection; wrapper BF3E9D78 выбирает0.
Mailbox FAD0107A, bit2 notification. Reference command0F передаёт27 halfwords
audio config; 10/11 — фильтры/route gains, 12/13 — tone start/stop, 14 —
phase continuation, 15 — завершение audio path. Reference digital path
«Media to uplink» + «Audio scheduler8kHz» воспроизведён эмуляцией; tone1000 Hz
получил coefficient23170/amplitude2828. Tone parameter pointer соответствует
FAD011B0, scheduler fields FAD011C2/C4. Отчёт с полными параметрами:
`build/mf283u-audio-parameter-emulation.json`.

Новый `--dsp-tone-candidate` — **ограниченная гипотеза совместимости DSP**,
не production backend: собственный connected MO, точные B03 signatures/pointers,
channel1/mode12a1-or9, одна последовательность500/1000/1500 Hz по2s. Audio commands
повторяют reference parameter builders. Используется тот же mailbox/bit2 IRQ,
но timeout100ms не вызывает штатный vendor DSP reset/assert. Нет program patch,
PCM peripheral/clock, FACCH или AMR frame writes. Исходные AP-owned tone fields
и mailbox сохраняются в RAM; tone status остаётся DSP-owned и не пишется.
При завершении посылаются stop/audio-disable/end, восстанавливаются сохранённые
AP fields. Это не доказывает восстановление скрытого внутреннего DSP state.
Worker использует абсолютные monotonic deadlines. B03 ktime_get возвращает
8-byte union через hidden result pointer; этот ABI подтверждён disassembly,
а не предположением о scalar return. Build/arm требуют отдельный opt-in и
kernel relocation audit. Слышимый результат на этом этапе ещё не проверен.

Первая попытка MO9 не дошла до CONNECT: после MM establish/SETUP пришёл MM
release indication через31s, PROCEEDING/ALERTING отсутствовали. Генератор и
audio mailbox не запускались; это **не отрицательный audio test**.
`build/cs-mo9-dsp-tone-live.json`. Hook/admission восстановлены, boot/PIDs
сохранились. Причина отсутствия сетевого ответа пока не установлена.
Builder/armer допускают pinned instances1..32 для новых bounded attempts
без принудительного reboot; это не увеличивает budget1 конкретного модуля.

Повторный MO10 соединился; пользователь подтвердил тишину. Однако ни одна
audio command/phase не зарегистрирована: это **не выполненный DSP tone test**.
`build/cs-mo10-dsp-tone-live.json`. Обнаружена ошибка gate: проверка TCH context
разрешала только kernel heap, хотя exact B03 sampler и предыдущий AMR candidate
также разрешают CP static BSS BF59E000..BF619BA8. Добавлен этот проверенный RAM
range и ограниченный scalar log причины отказа (без payload/identity).
Причину фактического отказа MO10 нельзя восстановить без этого отсутствовавшего
лога; следующая проба должна отдельно подтвердить channel gate и команды.

После прерванного turn при новом preflight наблюдался другой boot
8e20fcc3-6d36-46ad-ae25-5e001743f155, native1694/SIP1813, diagnostics отсутствуют,
profile13/flags1/0, CS-only/ring-only сохранены. Причина reboot не установлена;
MO10 завершился и восстановил hooks ещё на прежнем boot без audio commands.
`build/cs-dsp-tone11-preflight.json`. Перед следующей пробой исходный saved
radio/voice profile возвращается существующим restore helper.

MO11 после этой подготовки снова не дошёл до CONNECT: u16 MM release reason10
прочитан по offset2 exact B03 indication; source sender BF3A8458 подтверждает
поле. PROCEEDING/ALERTING отсутствовали, audio commands не запускались.
`build/cs-mo11-dsp-tone-live.json`. MO12 без новой radio reattach после проверки callbacks/admission/MM refs
также завершился reason10 до CONNECT; см. текущий входящий probe выше. В нём отсутствующие tone
frequencies используют reference coefficient32767 с нулевой amplitude,
добавлена пауза после notification и ограниченные scalar status samples.
Сетевую нестабильность и совместимость audio DSP пока нельзя считать решёнными.
Сводное offline сравнение ABI: `build/mf283u-b03-audio-abi-comparison.json`.

## AMR tone candidate и расширенный DSP test (2026-10-09)

MO7 прошёл MM/CC CONNECT и clearing без reboot. Пользователь подтвердил тишину.
Расширенный read-only sampler проверил семь точных shared SRAM ranges вместо
двух, включая пять ранее unclassified buffers. Речевой поток не появился:
буферы оставались неизменными, кроме единичного перехода управляющего DL range.
Новый scalar `mode_12a=9` в активном TCH context и AMR config `95` отличают
назначенный speech channel от idle; это не доказательство media transport.
Reports: `build/cs-mo7-speech-candidates-live.json`,
`build/cs-speech-candidates-preflight.json`. Самpler снят.

Перед этим во время CFUN/GSM registration USB исчез и boot_id изменился;
экспериментальные модули тогда ещё не были загружены, звонок не выполнялся.
Interrupted preparation сохранила flags0/1; после нового boot readback CFUN1,
profile13 и CS registration1 подтверждены, OPEN_VOICE_FLAG возвращён в1.
Причина reboot не установлена. Отчёт:
`build/cs-channel-preparation-usb-reset.json`. Это не успешное восстановление IMS.

`src/cs-tone-codec.c` и `prepare-cs-tone-frames.py --device-conversion` подготовили
синтетический тон1000 Hz во всех восьми AMR-NB modes на ARM физического модема.
Вход/decoded output остаются mono PCM16LE16000 Hz,320 samples/20ms;
внутри AMR-NB применяется существующий FIR down/up resampler. Для каждого режима
100 frames, tone1.5s + silence0.5s; 98.6–99.96% измеренной энергии после warmup
приходится на1000 Hz. AMR headers/sizes/frame counts, SHA256 и transfer MD5
проверены, RAM conversion files удалены. Ни radio, ни DSP conversion tool не
открывает. `build/cs-tone-frames-verification.json`.

Отдельный opt-in MO8 `--amr-tone-candidate` использует **гипотезу**: штатный
UL copier BF3F5115, чей exact ABI source/length<=46/connection подтверждён,
может подавать packed AMR speech в DSP buffer FAD01348. В B03 найденные реальные
callers этого copier относятся к CSD; speech consumer/packing пока не доказаны.
Поэтому это bounded experiment, не готовый audio backend. Только собственный
connected MO, channel1/mode12a9, проверенный pointer/signature и исходный нулевой
UL range; после nominal1s CONNECT delay не более300 frames. Mode выбирается по active
codec bitmap и UL mode index. Три packing candidates по2s: IETF payload without
ToC, bits reversed per byte, bytes swapped per16-bit word. Нет control/IRQ/ACK
writes, FACCH или unclassified buffer writes. При clearing/invalid channel/expiry
подача прекращается и нулевой UL range восстанавливается. Все sends MM/CC остаются
в real CC task, dial budget1, входящие не отвечаются, номер только RAM stdin.
`src/cs-amr-tone-candidate.h`, `src/cs-tone-pack.h`; sanitizer fixture проверил
mode/length bounds, все2400 frame variants и независимое inverse packing.
`build/cs-tone-pack-fixture.json`. Builder и armer требуют отдельного opt-in;
ARM kernel relocation audit пройден. MO8 соединился, записал все300 frames,
завершился через real MM/CC clearing и восстановил нулевой UL range.
Пользователь подтвердил **только тишину**. Гипотеза speech consumer/packing
не подтверждена: decoded synthetic tone не является слышимым CS звуком.
`build/cs-mo8-amr-candidate-live.json`,
`build/cs-amr-tone-ul-restore-readonly.json`.
Worker использовал50×msleep20 за nominal секунду; фактически300 frames заняли
около7.64s, а nominal10s hangup наступил через13.75s после CONNECT.
Для будущего media backend нужен абсолютный deadline/20ms pacing.
**Production CS audio и IMS→CS fallback не включены.**

После MO8 свежий route audit подтвердил original CC/ASC callbacks, admission
и MM refs0; sampler unloaded. Восстановлены profile27/flags0/0, IMSready=true,
idle и отсутствие cs-only/ring-only guards. Тот же boot
`fabd3a94-55f9-4134-b8d3-38c8a0b76971`, native1710/SIP1820;
`build/cs-amr-candidate-final-restore.json` и отдельная неизменяемая копия route
audit `build/cs-amr-candidate-final-restore-route.json`.

Для offline сравнения скачан MF283U EN_ZTE_HTXMF283UV1.0.0B05 из
[авторского сообщения](https://4pda.to/forum/index.php?showtopic=794816&st=1420#entry113258229).
Archive/binary SHA256 и источник сохранены в
`work/zte/voice/mf283u-reference/source.json`. Разбор нужен для сравнения voice
stubs/ABI с B03; совместимость образа с MF79U не заявляется. Код из этого
образа не запускался на модеме; позднее parameter builders эмулированы офлайн
с перехватом hardware calls, как описано выше. Raw flash не выполнялся.

## Проверка слышимого сигнала: network DTMF (2026-10-09)

По запросу пользователя подготовлен отдельный ограниченный MO diagnostic
`--mo --instance 5 --dtmf-tone`. После CONNECT он один раз отправляет START
DTMF (`35`, Keypad facility `2C`, фиксированная клавиша5), ждёт сетевой ACK36,
через2s отправляет STOP31 и ждёт ACK32. Нет повторного набора/повторного тона;
START/STOP timeout6s. До START ACK STOP не отправляется. Только собственный
MO TI0 и connected state; входящие не отвечаются. Все sends выполняются внутри
настоящего CC task. Номер по-прежнему только RAM stdin, не в отчётах/исходниках.

Это **сигнализация для тона, создаваемого/передаваемого сетью**, не PCM injection
и не доказательство CS речевого backend. `csAudioReady` остаётся false;
DSP writes отсутствуют. Источник процедуры:
[3GPP TS24.008 §5.5.7](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/05.11.00_60/ts_124008v051100p.pdf),
wire сверяется с [Osmocom CC](https://raw.githubusercontent.com/osmocom/osmocom-bb/master/src/host/layer23/src/mobile/gsm48_cc.c).
`src/cs-dtmf-tone.h`, расширенный ASAN/UBSAN fixture
`build/cs-wire-mo-fixture.json`: PASS, включая ACK order, no repeat, timeout,
reject/wrong TI/disconnect. ARM relocation audit PASS;
`build/cs-mo-probe5-build.json` связывает tone option с binary SHA256.
Armer требует явный `--dtmf-tone`, чтобы tone build не загрузился как silent.
Живой MO5 вызов соединился; сеть подтвердила START DTMF и STOP DTMF.
Пользователь подтвердил соединение, но услышал **тишину**, короткого тона не было.
`build/cs-mo5-dtmf-live.json`: connected=true, start/stop ACK=true,
audible_tone_confirmed=false, pcm_speech_backend_confirmed=false.
Clearing завершён через настоящий MM release с reason1; CC callback/admission
и ASC callback восстановлены, native1595/SIP1678 и boot сохранены.
Radio27/flags0/0 и LTE/IMS восстановлены, временный ring-only guard снят.
Network DTMF остаётся отрицательным тестом слышимости, не доказательством CS audio.
Восстановление проверено чтением AT profile/flags и native status:
`build/cs-tone-final-restore.json`.

Следующий bounded observer `--dsp-frame-metadata` читает по46 bytes только
из exact-B03 UL FAD01348 и DL FAD0131A (после status word), с проверкой всех
четырёх исходных CP pointer slots. Каждые5s сохраняет число изменившихся
snapshots и nonzero samples; содержимое и hash не выводятся. Нет writes,
ACK, смены callback, чтения других SRAM областей или RPMSG payload.
Одновременная запись DSP может дать несогласованный snapshot; даже изменения
не доказывают AMR frame format/ownership. Запуск разрешён только в registered
GSM CS-only без IMS/EPS; перед возвратом LTE observer обязательно снимается.
Это диагностический этап поиска media, не тест слышимого звука.

MO6 connected test охвачен новым observer. Пользователь поднял трубку и
сообщил: «Тишина и небольшие помехи». В обоих46-byte buffers changes_min=0
на протяжении всей проверки; UL оставался полностью нулевым, DL ненулевым
и неизменным. DSP control fields менялись, RPMSG cursors не двигались.
Это согласуется с найденным CSD назначением buffers, но не доказывает
отсутствие другого speech interface. `build/cs-mo6-tch-buffer-live.json`.
Никакого PCM/AMR frame injection не выполнялось. MO6 clearing и восстановление
callback/admission прошли без reboot; ASC9 истёк штатно, sampler unloaded.
Fresh route audit проверил оригинальные CC/ASC callbacks, admission и MM refs0;
`verify-cs-test-restored.py` дополнительно сверил AT profile27/flags0/0,
IMSready, отсутствие CS sysfs и временных guards, тот же boot/native1595/SIP1678.
`build/cs-tch-buffer-final-restore.json` сохраняет отдельную копию route audit,
чтобы последующие проверки не меняли его доказательство.

Первая загрузка MO6 была отклонена до создания call/sysfs: ASC8 был загружен
раньше проверки MO original-ASC prerequisite из-за конкурентного запуска armer.
После ASC8 expiry/recovery MO6 загружен полностью, затем ASC9 и sampler строго
последовательно. Rejected outcome сохранён отдельно в
`build/cs-mo6-rejected-concurrent-asc.json`; его не считать вызовом.

Полная exact-B03 таблица DSP pointers восстановлена offline из BF3E9F4C:
`build/cpko-cs-dsp-pointer-layout.json`, `cpko-cs-dsp-mapping-full-init.txt`.
BF3F4550/command5 задаёт таблицы физического AMR channel coding; самостоятельный
PCM/codec input из этого ABI ещё не получен. Дополнительные reports:
`cpko-cs-dsp-tch-buffer-consumers.txt`, `cpko-cs-amr-command5-details.txt`.
Проверки: новый frame observer прошёл exact kernel relocation audit и live
connected/unload проверку; default channel build также прошёл audit без включения
frame reads (`build/cs-channel-default-regression-build.json`). Python syntax,
запрет несовместимых CLI flags до device access, whitespace/newline checks PASS.

Проверка SDK `cs_pcm.sh` обеих voice/csphone копий показала зависимость от
ALSA `hw:0,2` и SLIC/AUX_PCM. На текущем B03 этих устройств/модулей нет.
Строка `audio` CP относится к ramlog module menu (`BF4F9788`), а
`ZcatAudioRegMutex` — к зарегистрированным audio files/test transport; это
не найденный speech task. Полный ELF string index и references сохранены в
`build/cpko-cs-speech-string-index.json`, `cpko-cs-dsp-allsection-refs.json`.
UL writer BF40A9B8/BF3F5114 вызывается BF4100F8 для CSD data frames (9/15/30
bytes, включая idle F8/3D); DL BF411284 разбирает AMR control metadata.
Их использование для PCM/AMR speech пока не подтверждено. Произвольная
запись в эти буферы не выполнялась. Boot/native/SIP перед тестом проверены
актуально: a8a10684 /1595/1678, IMSready=true, call idle.

## ASC и исходящий CS diagnostic (2026-10-09)

Пользователь явно разрешил исходящий тестовый звонок на предоставленный номер;
номер не сохраняется в исходниках/отчётах. На новой загрузке boot
`6c60cfb1-168e-49cf-a132-406d576c75dc` native1658/SIP1735 исходно LTE/IMSready,
csOnly=false/ringOnly=false; старых RAM hooks больше нет. Для ограниченной
диагностики временно восстановлен ring-only guard и включён GSM13/flags1/1,
CS-only. Это ещё не production voice fallback.

`src/cs-asc-watch.c` наблюдает реальный ASC callback, неизменно передавая все
пять аргументов оригиналу. Instance1 увидел три AAD4/MM пакета регистрации
(PD5/type14,19,1B), значит этот маршрут достигает ASC. `queue_result=0` сам
по себе доказывает только локальное enqueue, не отправку по радио. Instance2
подтвердил persistent context BF5CAD70 в pinned CP .bss, state1/substate0/
rat4/connection0. Оба истекли с callback_restored=1, без reboot/PID changes;
останутся pinned до reboot. Reports: `build/cs-asc-watch-armed.json`,
`cs-asc-watch2-armed.json`, `cs-asc-idle-live.json`.

ABDF/12 envelope восстановлен по точному BF05D620: connection byte0,
wire_length word4, owned pointer8. Новый observer читает только два wire header
bytes; для CC clearing — максимум семь bytes и только Cause scalar, без
диагностик/номеров/raw PDU. `src/cs-wire.h` проверяет mandatory DISCONNECT LV,
optional first RELEASE/RELEASE COMPLETE Cause TLV, recommendation extension и
границы. Сравнение с первичной реализацией
[libosmocore gsm48_ie.c](https://raw.githubusercontent.com/osmocom/libosmocore/master/src/gsm/gsm48_ie.c).
Generic NAS PD3 model decoder B03 не имеет полноценного CC switch: размер
выделенного decoded body не доказывает разбор его IE. Нельзя интерпретировать
MM PD5/type25 decoder как CC DISCONNECT Cause.

Для MO восстановлен AA3C/8 CM request: protocol3, normal voice service1;
AA19 относится к domain/RAT coordination и не используется для набора.
MM BF35606C вызывает BF300537, который всегда возвращает1; caller на этой
ветке отклоняет voice request. Отдельный `src/cs-mo-probe.c` временно заменяет
только проверенный data literal BF356258, допуская service1 только во время
собственного MM-pending. Проверяются hash/signatures и privileged-writable
small page. Исходный код CP на диске и инструкции не меняются.

MO probe принимает номер только через root write-only RAM sysfs, очередь
команд передаёт работу в настоящий CC task. Бюджет один; incoming SETUP не
отвечается. Сначала MM establish, после AA3D — собственный SETUP/Bearer
Capability/BCD number, затем CONNECT ACK и clearing. Автоматический stop
после10s connected; восстановление callback/admission только после MM release,
иначе callback сохраняется для завершения. Media/DSP/SIP отсутствуют.
Сравнение с
[Osmocom GSM CC](https://raw.githubusercontent.com/osmocom/osmocom-bb/master/src/host/layer23/src/mobile/gsm48_cc.c)
объясняет отдельный MM establish, но не используется как доказательство ZTE ABI.
Static reports: `build/cpko-cs-downlink-and-mm-clear.txt`,
`cpko-cs-voice-admission-and-owned-send.txt`; sanitized fixture
`build/cs-wire-mo-fixture.json`: PASS с Address/Undefined sanitizers в Linux
container. ARM builder и независимый armer проверяют kernel relocation modes;
старый reboot-associated sampler остаётся quarantined. Live MO результаты ниже.

Первый command-only тест не набирал: настоящий CC callback работает в OSS
phase1, тогда как ASC/UMM — phase2. Ошибка phase была исправлена; instance1
истёк с callback/admission restored=1. Второй тест достиг AA3C, но выбранный
BF4C5C00 только добавляет внутренний descriptor в UMM mailbox+0x948, без
OSS wakeup. AA3C/AA3E остались локально: AA3D, AAD4/SETUP и CONNECT отсутствуют.
Callback был оставлен для clearing; для очистки очередей потребовался штатный
software reboot. `build/cs-mo-first-dispatch-not-dialed.json`,
`cs-mo2-internal-mailbox-not-dialed.json`. Не считать эти попытки реальными
сетевыми звонками. ADB `reboot` не изменил boot_id; `/sbin/reboot` отправлен
через shell, его результат подтверждён новым boot_id ниже.

Исправленный MO candidate использует конечный штатный PS send route:
BF4AFEBC вызывает zOssMsgSend(id, owned payload, length, physical task).
MM logical81 и UMM logical80 проверяются как один runtime UMM task, phase2,
original callback BF4C8811; source сохраняется как настоящий CC task.
Static evidence: `build/cpko-cs-umm-normal-delivery.txt`,
`cpko-cs-umm-delivery-identity.txt`. Live подтверждение приведено ниже.
Статус MO больше не маскирует clearing state8 после запрета нового набора;
эта настройка изолирована от общего production CS status. Legacy ADB может
эхом повторить обе ветки shell command: write helper проверяет только отдельные
marker lines, не выводит номер. Права page table проверяются через PGD
C0044000, соответствующий physical20444000/PHYS_OFFSET20400000; неверный
первоначальный C0004000 был отклонён до установки hook.

### Реальный исходящий CS CONNECT

После подтверждённого штатного reboot новый boot
`46b0cf52-0295-4a64-b576-73ec2c455834`, native1618/SIP1689, старые hooks/sysfs
отсутствовали. MO instance3 успешно прошёл normal-voice admission, MM AA3D,
SETUP, CALL PROCEEDING, ALERTING, network CONNECT и собственный CONNECT ACK.
ASC подтвердил реальные wire headers для каждой фазы. Пользователь подтвердил
полученный звонок, ответ, таймер и собственный hangup. Network DISCONNECT Cause16,
собственный RELEASE, network RELEASE COMPLETE и AB0E наблюдены. Номера,
SMS/identity PDU не сохранялись; `build/cs-mo3-connected-live.json`.
**Это подтверждение исходящей CS сигнализации, без аудио/SIP forwarding.**

Instance3 всё ещё ждал AA3F после собственного MM release. Exact B03
BF356C9C/BF3596E4 показывают, что reason1 очищает active protocol/service и
CC reference byte+0x65; reason0 может оставить active protocol. Исправленный
candidate отправляет reason1, затем только внутри CC task читает два MM scalar
поля (active protocol+0x15, CC reference+0x65) для подтверждения обработки;
не подделывает AA3F и не затрагивает shared SMS/SS references. Старый instance3
очищается штатным reboot после network RELEASE COMPLETE. Static evidence:
`build/cpko-cs-mm-owned-release.txt`, `cpko-cs-mm-release-reason.txt`.
Также проверено на устройстве: vendor shell printf возвращает1 даже после
записи; BusyBox shell builtin возвращает корректный код. Control writer теперь
использует BusyBox sh и сохраняет только execution marker, без destination.

### CONNECT, DSP activity и clearing без reboot

MO instance4, boot `a8a10684-d369-4406-82c8-5f6c995147eb`, native1595/SIP1678,
прошёл второй исходящий CONNECT. Пользователь подтвердил полученный звонок.
MM establish→SETUP→PROCEEDING→ALERTING→CONNECT/ACK; network DISCONNECT→our
RELEASE→network RELEASE COMPLETE. MM reason1 обработан: CC references0,
active protocol255. Callback/admission restored=1, call_idle=1, sysfs удалён,
без reboot/native/SIP restart. `build/cs-mo4-connected-dsp-live.json`.

Sampler покрывал CONNECT целиком. Внутри connected interval, uptime173.271,
UL control `0095,0003,0000`, DL control `0095,0002,0003,0000`, 98 наблюдённых
изменений за последнее окно; TCH channel_8=1/channel_9=0. RPMSG registry29
active descriptors без cursor movement. Эти control changes подтверждают
активность DSP, **не наличие PCM/AMR frames или двустороннего звука**. Sampler
не читает payload, не пишет cursors/IRQ ACK; снят до возврата LTE.
Static TCH access audit показывает, что BF40B130/BF3F5220 возвращают DSP buffer,
а BF4112BC использует его как AMR/CSD control metadata; это ещё не восстановленный
speech transport. `build/cpko-cs-tch-frame-readers.txt`,
`cpko-cs-dsp-buffer-layout-static.txt`. На физическом B03 снова проверено:
voice_device и ALSA отсутствуют; штатный voice.sh ссылается на неустановленные
SLIC/TDM/audio modules. Их заглушка не решит media bridge.

Kernel log успел вытеснить MO/ASC expiry перед restore. Для актуальной проверки
расширен read-only `cs-route-probe.c`: CC/ASC original callbacks, admission
literal, MM CC references и active protocol. Свежий audit подтвердил original
CC BF30053D/ASC BF47BE95, admission original, references0/protocol255,
quiescent1; probe unloaded, без sends/writes. `build/cs-route-probe-live.json`.
Restore принимает эту проверку только для того же boot и точного набора pinned
diagnostics при отсутствии CS sysfs, вместо предположения по отсутствию log.
Возврат обычного LTE/IMS профиля и снятие temporary ring guard подтверждены
в `build/cs-mo-final-restore.json`: IMSready=true, csOnly/ringOnly=false,
radio27/flags0/0, тот же boot/native1595/SIP1678, CS sysfs отсутствуют,
channel sampler unloaded. Неактивные MO4/ASC6 остаются pinned до reboot,
с оригинальными callbacks/admission. Устаревшие MO1/2/3 build reports
помечены live_arm_allowed=false с причиной, чтобы их не загрузили повторно.
Production IMS→CS voice fallback и audio
ещё не реализованы; diagnostic kernel modules не включены в userdata autostart.

## Продолжение: CS media и выбор backend (2026-10-09)

Пользователь уточнил: запрет ответа относился к roaming SIM; установленную
обычную SIM теперь **разрешено отвечать**. Это заменяет прежнее ограничение
для текущей SIM. `native-ring-only` включается временно только на CS diagnostic
сессию; после последнего теста guard снят, LTE/IMSready восстановлены.

Повторный реальный ring-only вызов снова дал гудки. `cs-ring4` обработал SETUP,
отправил CALL CONFIRMED/ALERTING, затем DISCONNECT/RELEASE/RELEASE COMPLETE.
Native2793/SIP2794 и boot не менялись. `build/cs-channel-incoming-live.json`.
Исправлен `cs-kernel-watch.c`: ограничение32 относится к event logging,
AA45 protocol handling продолжается весь armed interval. Полный стабильный
voice backend пока не реализован: TI0 prototype не имеет CS audio/Caller ID/MO.

Добавлен unloadable `cs-channel-watch.c`: только scalar descriptors/cursors
ZSP RPMSG registry, nominal20ms sampling, aggregated5s logging. Нет чтения
payload, consume/курсорных writes, callback replacement или audio init.
Позиции дают лишь lower bounds; полные обороты между samples не обнаруживаются.
Heartbeat доказывает выполнение sampler и число active descriptors. Watch
timer измеряется числом циклов: фактический период зависит от scheduler/HZ.
Первый ring test не показал cursor activity после начала GSM observation;
отсутствие voice channel этим не доказано. Контрольный heartbeat вариант
загружен для CONNECT теста, но истёк **до** вызова (uptime5501.790 vs
CONNECT5529.332). Поэтому по этому тесту нельзя судить о CS audio/RPMSG
activity. Это исправление прежней интерпретации; sampler heartbeat29 относится
только к периоду до вызова. После stop kthread остановлен и module unloaded;
CC callback снимается своим timer и остаётся pinned до reboot.

`build-cs-kernel-probe.py --channels`, `arm-cs-kernel-watch.py --channels`,
`prepare-cs-channel-test.py` и `collect-cs-channel-call.py` обеспечивают
checksum/CP placement/guard/PID/boot checks и sanitized evidence. Original
radio/flag backup не перезаписан. `restore-cs-test.py` сохраняет native guard.

Отдельный `--connect-probe` candidate после CALL CONFIRMED/ALERTING отправляет
**один** MT CONNECT (wire83 07). Бюджет consumed до enqueue: retries и второй
ответ исключены, исходящего SETUP/DIAL нет. Это диагностический ответ без
SIP/audio, а не рабочий CS backend. Caller должен завершить короткий вызов;
автоматического hangup timer пока нет. CONNECT ACK и clearing проверяются
по metadata. Sysfs явно публикует `answer_forbidden=0`, поэтому старый native
strict parser отвергает этот feed и не объявляет audio/voice ready.
После разрешения пользователя candidate загружен в RAM:
`build/cs-connect-probe-armed.json`, SHA256561647d593d9674ab1cdbaa823cf96c550f69be4fba385e536c79b857fd4e218.
Реальный тест: SETUP5529.332 → CALL CONFIRMED/ALERTING/CONNECT enqueue0;
сеть прислала CONNECT ACK0F5530.651. Затем DISCONNECT5559.691 → RELEASE
→ RELEASE COMPLETE5559.871; callback restored/call_idle1 при expiry5561.878.
Пользователь услышал тишину и не смог определить соединение; network ACK
подтверждает только signaling, аудиомоста ещё нет.
Report `build/cs-channel-connected-live.json` явно помечает media observation
inconclusive: sampler истёк до вызова. Restore guard проверил clearing/expiry.
После восстановления live PASS: radio27/flags0/0, LTE/IMSready, idle,
csOnly=false, native2793/SIP2794 и boot сохранены, sampler/sysfs отсутствуют,
kernel fault lines не обнаружены. `build/cs-connect-final-restore.json`.

Устранена ошибка времени наблюдения: `cs_observation_evidence.py` проверяет
монотонные kernel timestamps и heartbeat до CONNECT ACK и после clearing;
`test-cs-observation-evidence.py` отвергает истёкший/неполный sampler. Collector
сохраняет coverage и IRQ metadata отдельно от успешного call signaling.
Новый sampler600s включает только scalar TCH state/config из проверенных
B03 globals (`l1g_tch.c`): без DSP payload/register reads. Новый connect2/300s
перестаёт отвечать за60s до expiry и снимает hook после network clearing.
Каждый pinned observer имеет собственное имя; перед загрузкой проверяются
checksum, callback ownership, boot/PID, idle и текущие voice flags.

Static TCH audit: `build/cpko-gsm-l1-source-refs.json`,
`cpko-l1g-tch-entries.txt`, `cpko-tch-speech-vs-data.txt`.
Три stub BF3838C4/C8/CC возвращают0/0/1; их caller обслуживает буферы9/15/30
bytes. Это **вероятный CSD**, не подтверждённый PCM/speech adapter; их не
подменяли. Размеры согласуются с data TCH72/120/240bits из
[ETSI GSM05.03](https://www.etsi.org/deliver/etsi_gts/05/0503/05.00.00_60/gsmts_0503v050000p.pdf).
Речевой codec/DSP ABI пока не восстановлен. Legacy GSM DSP IRQ handlers
BF425B58/BF425B90 ведут в BF407564/BF421D3C; только offline disassembly,
никаких MMIO writes/hooks по этим адресам.

### Incident при TCH sampler (2026-10-09)

После успешного arming connect2 загружался sampler с TCH metadata;
USB исчез, затем подтверждён **новый boot_id** и uptime55s. Новый вызов
пользователю не запрашивался. До сбоя native2793/SIP2794; после autonomous boot
native1336/SIP1359. Candidate SHA256
2b0f3686d99a46cf8c7d35fdfd21a25340f03105a2f11ae3be7594343b981430
**quarantined**, live armer запрещает его загрузку. Kernel panic/Oops причина
не установлена: предыдущий kernel log/pstore недоступны. Не считать отсутствие
ошибок в новом dmesg доказательством отсутствия предыдущего сбоя.
`build/cs-tch-sampler-recovery.json`. Все pinned hooks и sampler исчезли при
reboot. Saved original radio/flags восстановлены существующим restore script;
LTE/IMSready снова подтверждён, idle/csOnly=false. PCM/rootfs/raw flash не менялись.

Quarantined binary сохранён в `build/quarantined/2b0f3686d99a46cf8c7d35fdfd21a25340f03105a2f11ae3be7594343b981430.ko`.
Его ELF содержит `R_ARM_THM_CALL` по offset0x232 к undefined NOTYPE `memset`;
checksum-bound B03 kernel export `memset=0xc010cb40` работает в ARM mode.
Aggregate zero initialization генерировала этот вызов несмотря на `-fno-builtin`.
Это конкретный ABI defect и **вероятная**, но не доказанная crash log причина.
[Upstream Linux3.4 loader](https://github.com/torvalds/linux/blob/v3.4/arch/arm/kernel/module.c)
не выполняет interworking для Thumb branch relocation; точные изменения
vendor loader этим исходником не установлены.
`b03_kernel_relocations.py` теперь проверяет все undefined direct Thumb calls
по exact B03 kernel exports; builder/armer независимо блокируют even/ARM target.
Armer также сверяет live kernel MD5. Regression
`test-b03-kernel-relocations.py` отвергает сохранённый crash-associated ELF,
включая NOTYPE и отсутствующий export, и проверяет corrected TCH candidate.
Исправленная revision2 убирает `memset` через volatile byte zero loop и
ограничивает TCH printk максимум двумя строками на50 samples. Старый SHA
остаётся запрещённым. Обычный `--channels` не включает TCH чтения.
Corrected revision2 SHA2564e3c62ee5730d6677b87d76dfb597b29b2ff5a39eee96ecee80fac6e7f8cf72a
прошёл15 nominal seconds idle test на LTE: heartbeat250/500/750,
TCH read_failures0, native1336/SIP1359 и boot сохранены, IMSready;
после expiry module unloaded. `build/cs-tch-corrected-idle-live.json`.
Это проверка чтений на idle, не подтверждение audio или поведения при вызове.
Повторный CONNECT с revision2/600s охвачен sampler целиком:
`build/cs-tch-connected-live.json`. SETUP1020.844, CONNECT ACK1022.197,
RELEASE COMPLETE1059.979; callback восстановлен сразу после clearing.
Пользователь подтвердил появление таймера разговора и завершение вызова.
Heartbeat до/после, coverage=true, TCH reads без failures, boot/PID сохранены.
RPMSG cursors и IRQ49 не изменялись; IRQ56/57 увеличились, IRQ61/62 не изменились.
Scalar channel_8/9:4/3 до SETUP →1/0 при соединении →0/3 после clearing.
TCH state/rate_mode оставались0, AMR config bytes0. Эти внутренние значения
пока не сопоставлены с speech codec; отсутствующий RPMSG cursor delta не
доказывает отсутствие отдельного legacy DSP speech interface.
Sampler снят, LTE/IMSready/radio27/flags0/0 восстановлены без reboot/restart:
`build/cs-tch-final-restore.json`. CONNECT module после восстановления callback
остаётся pinned в RAM до reboot, его sysfs удалён и новых ответов нет.

На текущей ordinary SIM roaming guard **снят** по уточнению пользователя:
`build/cs-ordinary-sim-voice-restored.json`. Native ringOnly=false,
csOnly=false, IMSready=true, native1336/SIP1359, boot сохранён. Это возвращает
существующий IMS/SIP answer/dial путь; новых DIAL/ANSWER при снятии marker не
отправлялось. Перед следующей CS diagnostic session guard понадобится снова
временно поставить; permanent roaming restriction не переносится на эту SIM.
Armer пишет phase report **до** mutations и сохраняет original exception при
недоступном USB; cleanup/postcheck errors не скрывают причину. Самpler coverage
fix и новый static TCH audit остаются полезны независимо от этого incident.

### DSP status и последний неуспешный вызов (2026-10-09)

Read-only pointer probe на LTE восстановил conn0 layout: UL control FAD012FE,
DL control FAD0130E, UL data FAD01348, DL data FAD01318; conn1 pointers null.
`build/cs-dsp-pointer-layout-live.json`. Читались только CP pointer globals,
не DSP buffers. Kernel map_desc candidate F8D00000 / PFN F4000 / length03000000
совместим с этими адресами, но остаётся offline inference:
`build/kernel-gsm-map-desc-candidates.json`.

Revision3 sampler отдельно проверяет exact pointer layout и читает только
8 halfwords, использованные original CP: UL control3, DL control4 и первый
DL status halfword. UL data и frame bytes не читаются; writes/ACK/consume нет.
`--dsp-status` требует зарегистрированный GSM/CS-only с IMS/EPS неготовыми,
чтобы не обращаться к GSM block при LTE clock gating. Idle GSM test прошёл
без reboot/PID changes, все8 halfwords0; sampler unloaded:
`build/cs-dsp-status-idle-live.json`.

Последующий реальный test **не соединился**: SETUP1881.896, tx08/01/07
queue_result0, но ни AB0C, ни CONNECT ACK0F не получены. DISCONNECT1897.667,
our RELEASE2D; incoming RELEASE2D1927.561 → our RELEASE COMPLETE2Aqueue0;
callback restored/call_idle1, sampler unloaded. Пользователь подтвердил тишину
и отсутствие таймера. `build/cs-dsp-status-connected-live.json` — историческое
имя файла не означает успешный CONNECT. `connected_call_observation_valid=false`.
Control/status оставались0, но при неустановленном вызове это **не доказывает
отсутствие speech buffers**. Причина DISCONNECT пока не декодирована.
В TS24.008 Rel7 §11.3 MS T313 равен30s и запускается самим CC entity;
15.77s до incoming DISCONNECT нельзя объявлять подтверждённым T313:
[ETSI TS24.008](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/07.14.00_60/ts_124008v071400p.pdf).

Evidence parser теперь различает network RELEASE COMPLETE и входящий RELEASE
с локально queued RELEASE COMPLETE. Последнее доказывает local clearing response,
не операторский ACK этого ответа; connected coverage по-прежнему требует
CONNECT ACK и heartbeat before/after. Fixtures проверяют failed queue и отсутствие
ACK. Collector сохраняет phase/evidence до ожидания, original failure отдельно
от cleanup/postcheck errors. Python syntax и coverage/kernel relocation tests PASS.

После test radio27/flags0/0 и LTE/IMSready восстановлены, temporary ring-only guard
снят для ordinary SIM; native1336/SIP1359 и boot сохранены:
`build/cs-dsp-status-final-restore.json`. Два CONNECT modules inactive с restored
callback, pinned до reboot; sampler/sysfs отсутствуют. CS media transport,
устойчивая call signaling и production IMS→CS voice fallback ещё не готовы.
До следующего вызова требуется уточнить cause/assignment signaling. CP scalar
mode131/frame counter не сопоставлены с speech codec; совпадение offset131
в RR decoded model не означает ту же структуру. Calypso Osmocom DSP ABI — только
сравнение, его offsets/bits/writes неприменимы к B03 без exact evidence.

Создан независимый `voice-backend-policy.h` с fixture/selftest:
IMS preferred; CS требует registration+signaling+verified bidirectional audio;
backend закреплён на время вызова; потеря backend latched до clearing;
нет миграции/повторного набора; Disabled/CS-only; возврат с CS на IMS после
5s непрерывной готовности. Policy пока **не подключён к native runtime**:
нет реального CS media transport. Тесты не являются hardware fallback.
Host и ARM policy/channel tests прошли; прежние native lifecycle/ring-only/
CS-only/status fixtures тоже PASS. `build/cs-backend-tests.json`,
`build/cs-backend-lifecycle-tests.log`. Новый one-call CONNECT fixture отдельно
проверяет prerequisites, one-shot budget и запрет CONNECT в обычном ring builder.
PCM contract неизменен: mono PCM16LE16000Hz,320samples/20ms.

Static audit отбрасывает ложные audio leads: BF44C794 — diagnostic file
transfer;1590 у BF2CDD62 — source line, BF3FD73C — bitmask, не voice indication.
GSM assignment AMR validation BF0D0638 и UMAC rate validation не дают PCM ABI.
Reports: `build/cpko-cs-media-strings.json`, `cpko-cs-speech-detail.txt`,
`cpko-cs-channel-callbacks.txt`, `cpko-cs-phy-interface.txt`.
DSP `evb_cpuphy.bin` скопирован read-only, MD5 local/live verified;
`build/cs-dsp-string-audit.json`. ASCII media strings отсутствуют, это не
доказательство отсутствия речи. [Primary ZX29 loader source](https://gitlab.com/stefandoesinger/zx297520-kernel/-/blob/dlink/drivers/remoteproc/zx29_zsp_rproc.c)
описывает chunk layout и proprietary ZSP ISA; ARM disassembly DSP не применяется.
Raw flash/rootfs/package не обновлялись. Все модули — RAM experiment.

## Подтверждённый этап 2026-10-08

2026-10-08 20:39 UTC: **входящий GSM CS вызов впервые получил гудки**.
Собственный RAM-only CC обработчик отправил CALL CONFIRMED/ALERTING;
пользователь подтвердил гудки. Сеть завершила вызов через
DISCONNECT → RELEASE → RELEASE COMPLETE. CONNECT не отправлялся.
Report `build/cs-ring-incoming-live.json`. **CS audio, Caller ID и SIP
forwarding пока не реализованы**; это подтверждённая ring-only сигнализация.
Во время входящего теста radio profile13, flags1/1, GSM registration1,
csOnly/ringOnly=true, IMS выключен, native1387/SIP1402 без перезапуска.
Обработчик вернул оригинальный CC callback через600s; module pinned до reboot.
Исторический `cs-test-final-restore.json` относится к предыдущему эксперименту.
После CS status integration обычные radio profile27/flags0/0 восстановлены:
LTE/IMS ready, csOnly=false, ringOnly=true, native2793/SIP2794.
Последний report `build/cs-ring-final-restore.json`.
На этом историческом этапе нельзя было отвечать: пользователь сообщил
стоимость входящего50 евро на roaming SIM. Для нынешней обычной SIM позднее
разрешён ответ; актуальный scope и эксперимент приведены выше.

## Постоянная защита от платного ответа

Установлен marker /mnt/userdata/mf79u/native-ring-only (0600). Native controller
проверяет его непосредственно перед DIAL/ANSWER, включая IMS READY; unreadable
marker также блокирует действия. API native status публикует ringOnly=true,
WebUI показывает запрет ответа/набора. При заблокированном ANSWER возможен только
hangup, ATA не отправляется. Marker сохраняется после boot и пока не удалялся.
Он не реализует GSM сигнализацию и не защищает от отдельного чужого AT клиента.
Marker автоматически не снимается. Старые PBX Answer/voicemail helpers не
запускались; новая ordinary-SIM CS answer проверка изолирована от них.

## Пассивная проверка CS сигнализации (2026-10-08)

Первоначально roaming SIM имела CS registration5 / EPS2 / IMSfalse.
`build/cs-voice-audit.json` относится к обычной SIM до окончательной GSM
регистрации: в snapshot CS2/EPS2, IMSfalse. Последующие CS1 snapshots и
восстановление IMS зафиксированы отдельными reports ниже.
`AT+CLCC` и `AT+CLCC=?` отклонены, `CVMOD?` и `ZAMRSUP?` отвечают OK.
`/dev/voice_device`, `/dev/volte_device`, `/dev/slic-0`, ALSA отсутствуют.
Это не означает, что входящее событие обязательно недоступно по другому IPC.

В B03 `libatext.so` восстановлена отдельная CCAPP очередь `0x1023`:

- `atCcapp_RecvDsciInd`, 0x818c: sender 0x100f, command 0x158d,
  payload 64 bytes; id/direction/state/type по offsets 0/4/8/12.
  Caller bytes начинаются с offset16 и не печатаются/не сохраняются probe.
- `atCcapp_RecvZvoicechnlInd`, 0x7b5c: command 0x1590,
  payload 16 bytes, op/active/codec/path.

`src/cs-call-watch.c` создаёт только НОВУЮ очередь с IPC_EXCL, отказывается
потреблять чужую, валидирует framing/source/destination/ranges и удаляет свою
очередь при нормальном завершении/SIGTERM. Он не содержит отправки AT/IPC,
команд ATA/ATD, media activation и SIP forwarding. Валидные call states
передаются текущему LED через локальный socket. Перед запуском обязателен
существующий native-ring-only. Принудительный SIGKILL обходит cleanup: не
удалять оставшуюся очередь без проверки владельца/процессов.

Сборка включена в `build-native-cp.sh`. ARM `--selftest` проверен на модеме:
indexed incoming, truncated message, wrong payload size, invalid id/state.
Бинарник проверен MD5 и запущен только в RAM `/dev/.mf79u-cs-call-watch`.
Native/SIP не перезапускались, настройки/boot hook/voice flags не изменялись.
Результат первого реального входящего теста приведён ниже. Наличие source-level CCAPP
decoder не является доказательством GSM ringing или работающего GSM audio.

## Новая SIM, CS-only и первый входящий тест (2026-10-08)

Пользователь заменил roaming SIM обычной SIM. До изменений устройство имело
EPS=1, CS=1 и IMS ready. Установлен обратимый runtime marker
`/mnt/userdata/mf79u/native-cs-only` (0600). Native controller читает его
на каждом цикле: останавливает собственный IMS даже при ошибке запросов
регистрации, запрещает новые попытки IMS на LTE и публикует `csOnly=true`.
На границе IMS DIAL/ANSWER также проверяется marker. SIP/SMS и CP queries
остаются доступны. Ring-only — отдельная политика; она сохранена.

Radio preference изменён штатным `AT^SYSCONFIG=13,0,1,2`, readback совпал.
Исходный `27,0,1,2` сохранён локально в `build/cs-test-radio-profile.json`
и на модеме в `native-cs-radio-profile.json` (0600). После выбора GSM:
CS=1, EPS=2, IMS=false; `^SYSINFO: 2,3,0,3,1,,3`.

Пользователь сделал входящий вызов: тишина, затем «voice no service».
Пассивный CCAPP watcher завершился с incoming=0, ended=0, connected=0,
channels=0. Ответа, исходящего SIM-вызова и GSM audio не было.
Также добавлен desktop-only `src/cs-usb-watch.c`: пассивно читает USB
AT interface4 / endpoint0x84 без отправки команд, печатает только call-state
metadata, redacts CLIP. Его отсутствие событий не доказывает отсутствие
внутренних CP events; он запущен позднее CCAPP watcher.

Проверен ограниченный эксперимент с двумя voice flags и boot. Исходные
OPEN_VOICE_FLAG=0 / VOICE_SUPPORT=0 сохранены в
`native-cs-voice-flags.json` (0600) и `build/cs-test-voice-flags.json`.
После boot OPEN_VOICE_FLAG прочитан как 0, VOICE_SUPPORT как 1.
В серии последующих probes произошёл разрыв USB AT транспорта; наблюдалась
смена native/SIP PID и малый uptime. Отдельный неожиданный reboot не подтверждён
сравнением boot_id; причина смены runtime и связь с конкретным flag/query
не установлены. Данные после разрыва не являются
валидными результатами команд: `build/cs-voice-post-flags-boot.json`.
Оба флага возвращены в 0, подтверждены readback. Затем CLCC снова отклонён,
ZAMRSUP=0,0; `build/cs-voice-restored-flags.json`.

Реальный boot подтвердил сохранение CS-only/ring-only. После восстановления
флагов 90 s без reboot/restart native/SIP; настройки не менялись.
Vendor SMS backend и SIP SMS worker ready, без SMS mutations.
Отчёты: `build/cs-only-install-live.json`, `build/cs-only-stability.json`,
`build/cs-only-sms-live.json`.

Fixtures в disposable ARM container: прежний searching/GSM/IMS lifecycle,
ring-only forged DIAL/ANSWER, новый `test-cs-only.py` (запрет IMS на LTE,
возврат IMS при снятии marker, остановка IMS при повторной установке marker,
сохранение SIP PID). ARM native selftest также прошёл на устройстве.
Все fixtures повторно прошли для окончательного source; `build/cs-only-tests.json`.
Последняя копия binary дополнительно закрывает IMS DIAL/ANSWER непосредственно
при наличии CS-only marker, установлена с checksum/readback и сохранением
настроек. Её actual SHA256/MD5 — `build/cs-only-install-live.json`.
Boot proof выше относится к первой CS-only копии; окончательная копия проверена
после controlled service restart, отдельный reboot с ней не выполнялся.

Граница этого исторического этапа: **GSM call support ещё не реализован**. Установлена только
управляемая тестовая политика без IMS; SIP voice readiness не подменяется
CS registration. Для дальнейшей реализации нужны работающие CP call-control
события и CS audio transport; найденный CCAPP decoder не даёт аудиоканал.
PCM contract сохраняется: mono PCM16LE / 16000 Hz / 320 samples / 20 ms.
Старый full NAND/SD package не обновлён, raw flash не выполнялся.

### Возврат обычного радио/IMS

`restore-cs-test.py` восстанавливает сохранённые voice flags и radio preference
с readback, затем удаляет только native-cs-only. Ring-only сохраняется.
Перед запуском остановить оба passive watchers. Скрипт проверяет отсутствие
active SIP call/CCAPP receiver. Он не делает reboot и не снимает запрет ответа;
boot-time voice policy после эксперимента может требовать отдельного reboot.
Сохранённые profiles не удаляются. IMS после снятия marker должен снова
пройти обычную регистрацию; подтвердить ready отдельно.

Исходный native binary до CS-only находится в
`build/pre-cs-only-20261008/mf79u-native-gateway` (0700).
`install-cs-only-test.py` — guarded one-shot installer первого candidate;
повторно не запускать без новой backup/checksum проверки.

## Уточнение SIM и runtime-only эксперимент (2026-10-08)

Пользователь подтвердил работу голоса этой SIM в кнопочном Nokia TA-1253.
Это подтверждение работоспособности SIM для голосовой услуги; отдельные
параметры сети телефона не измерялись нами. Входящий отказ на MF79U требует
дальнейшей проверки самого модема и его CS registration/capabilities.

Boot-test выше не проверил входящий с одновременно активными двумя flags:
после boot OPEN_VOICE_FLAG=0. Поэтому подготовлен ограниченный runtime-only
эксперимент: исходные оба0 проверяются, VOICE_SUPPORT и OPEN_VOICE_FLAG
устанавливаются в1 без reboot, оба читаются обратно; boot_id/native/SIP PIDs
и GSM registration проверяются до входящего теста. При ошибке этой проверки
скрипт пытается восстановить исходные flags. Отдельный report:
`build/cs-voice-runtime-flags.json`. Ring-only и CS-only не снимаются.
Совместный входящий тест завершён: пользователь услышал тишину, затем
сообщение оператора о недоступности. CCAPP receiver: incoming=0, ended=0,
connected=0, channels=0; USB observer не получил распознанных call URC.
Оба watchers завершены, их USB interface/CCAPP queue освобождены. Flags
возвращены в0 с readback; CS-only/ring-only и GSM preference13 сохранены.
Таким образом, простого изменения flags после регистрации недостаточно.
Это не доказывает отсутствие CS voice в CP: ещё не проверена новая network
registration с flags=1 и не восстановлен CS audio transport.

## Reattach с flags до регистрации (2026-10-08)

`test-cs-reattach.py` проверяет CS-only/ring-only и отсутствие CCAPP watcher,
выключает радио CFUN=0, выставляет оба flags=1 с readback, включает CFUN=1
и ждёт CS registration не более90s. CFUN query/test подтверждены устройством.
Script не набирает/не отвечает, не перезагружает AP и не снимает guards;
при ошибке пытается восстановить оба flags0 и CFUN1. При успехе оставляет
flags1 для ограниченного supervised incoming test; после него вернуть0.
Report `build/cs-reattach-live.json`.

После предыдущего входящего AT+CEER вернул4,120; значение не интерпретируется
без документации B03 и не объявляется причиной отказа. CLCC всё ещё invalid
command. Sanitized read-only report: `build/cs-post-incoming-diagnostics.json`.

Первый reattach attempt не получил OK за idle timeout USB helper3s.
CFUN=0 при этом реально применился (readback0), поэтому отсутствие OK
не означает отказ команды. Immediate recovery CFUN=1 тоже не получил
своевременный OK; после прерывания чата повторный CFUN=1 получил OK
и readback1. Оба flags подтверждены0. Helper timeout нужно учитывать
в следующем attempt и обязательно проверять реальное состояние при error.

Для asynchronous CFUN добавлено optional wait argument в source
`outputs/zte-native-usb.c`; собран отдельный `build/cs-at-wait`, старый
`outputs/zte-native-usb` binary не заменялся. Terminal OK/ERROR либо deadline
до60s; прежние invocations сохраняют idle policy. Test script теперь
обязательно читает CFUN обратно и записывает результаты recovery.
Исправлена ошибка regex readback (backspace вместо word boundary); второй
attempt откатил flags и radio, третий проверил числовой get_flag напрямую.

Reattach успешно завершён: CFUN0 → оба flags1 → CFUN1; CS registration1,
IMSfalse, csOnly/ringOnlytrue, native784/SIP785, boot_id прежний. Оба flags
сохранились1 после новой регистрации. Report `build/cs-reattach-live.json`.
Запущены passive CCAPP и USB observers для входящего без ответа.

Входящий после reattach завершён: пользователь услышал тишину, затем
сообщение оператора. CCAPP incoming/ended/connected/channels=0, USB
распознанных call URC=0. Простое включение flags перед новой регистрацией
не обеспечило входящий CS вызов. Flags восстановлены0 с readback, GSM
registration1, native784/SIP785, csOnly/ringOnlytrue; observers остановлены.
Полный результат и восстановление: `build/cs-reattach-live.json`.

## Точный CP command audit и граница реализации (2026-10-08)

`audit-cs-command-table.py` декодирует245 записей AT table в исходном B03
`cpko.ko` offline. Привязан к точному SHA256 и отказывается применять
известный address mapping к другому binary. Report:
`build/cpko-at-command-audit.json`. MD5 local/live совпал:
`8138d03644b0417ec3fba9d7175200bc`; CP binary не менялся.

В contiguous table `0x50d200..0x50dd70` есть D, CR, CRC, CVMOD, но нет
A, H, CLCC, CHLD, VTS, ZCSVOICESPT. Наличие D не доказывает voice dial:
он может обслуживать data call, реальный набор этим audit не выполнялся.
Это согласуется с live invalid-command для CLCC и ZCSVOICESPT.
Наличие common libatext CCAPP callbacks не означает, что текущий CP
реализует соответствующую CS команду или выдаёт call event.

Offline Thumb slices: `build/cpko-voice-init-slices.txt`,
`build/cpko-voice-gate.txt`, `build/cpko-voice-gate-callers.txt`.
VOICE_SUPPORT getter (text0x3e527c) читает global+0x35d; setter
(text0x3e5288) меняет байт и вызывает общий helper0x3e40e4.
OPEN_VOICE_FLAG getter (text0x3e6034) читает global+0x45f; setter
(text0x3e601c/0x3e82f6) пишет байт без commit. Это source-level evidence
для разных setter paths; persist/runtime подтверждены также boot tests,
но назначение helper0x3e40e4 полностью не восстановлено.

Live CVMOD=0, ZIMSSTATE=0; test CVMOD=(0-3). Поэтому прежний IMS CVMOD3
не остался включённым во время последних CS tests. ZAMRSUP=0,0 по-прежнему
не интерпретируется без документированного ABI. Report:
`build/cs-voice-mode-queries.json`.

SDK voice application использует отдельный modem adapter и ALSA/SLIC path
в `cs_pcm.sh`; эти интерфейсы на текущем MF79U отсутствуют. В опубликованном
SDK index CP source/driver для реализации B03 CS call/audio не найден.
Один перенос SDK voice daemon не обеспечивает этот missing backend.

Граница вывода: стандартный CS AT backend в текущем B03 не доступен;
не утверждаем аппаратную невозможность голоса или установленную причину
отказа оператора. Для полноценного GSM backend всё ещё нужны совместимые
CP call-control и CS audio интерфейсы, либо восстановленный прямой protocol.
Слепая замена CP/добавление выдуманных команд не выполнялись.

## Итоговое восстановление после тестов (2026-10-08)

`restore-cs-test.py` восстановил исходный SYSCONFIG27,0,1,2 и оба flags0
с readback; удалён только native-cs-only. После возврата EPS1/CS1 native
снова зарегистрировал IMS: ready/imsReadytrue, csOnlyfalse, ringOnlytrue.
Native784/SIP785 сохранились; activeCallfalse. Оба passive watchers завершены,
CCAPP queue0x1023 отсутствует. Report `build/cs-test-final-restore.json`.

Для повторной сборки более долгого USB command helper:

```sh
clang -Os -Wall -Wextra -Werror \
  -I/opt/homebrew/opt/libusb/include/libusb-1.0 \
  -L/opt/homebrew/opt/libusb/lib -lusb-1.0 \
  outputs/zte-native-usb.c -o firmware/mf79u/build/cs-at-wait
python3 firmware/mf79u/audit-cs-command-table.py
```

Public ZTE MF79U support page проверена; опубликованные quick-start guides
не дают CS call/audio API или совместимого CP build с таким backend. Это
ограничение найденных материалов, не доказательство невозможности модификации:
https://support.ztedevices.com/en-gl/select-product/mf79u/

## IMS и поколения радиосети (2026-10-08)

Обычный голос GSM2G и UMTS/WCDMA3G использует CS domain; modem/CP
управляет CS call и выдаёт audio через свой интерфейс. LTE voice использует
VoLTE/IMS поверх IP. При отсутствии VoLTE поддерживаемый network/device
может перейти на2G/3G для CS call (CSFB); это отдельный путь сигнализации
и media. SRVCC — другой механизм: перенос уже идущего VoLTE call в CS.

IMS не ограничен LTE архитектурно: GSMA IR.58 описывает IMS voice over
HSPA3G. Такой режим требует поддержки и оператора, и terminal; обычный
CS call в3G нельзя считать IMS. Доступ к packet data сам по себе не
подтверждает operator IMS service на этом radio access.

Current `src/native-gateway.c` начинает IMS только при EPS registration1/5
и останавливает idle IMS при выходе из EPS registration. Поэтому текущая
реализация подтверждает LTE/IMS, а не VoHSPA. GSM/3G SMS fallback остаётся
отдельным от незавершённого CS voice backend. Изменение EPS gate само по себе
не является реализацией IMS over3G или GSM voice.

Primary sources:
- GSMA VoLTE/CSFB guide: https://www.gsma.com/get-involved/working-groups/wp-content/uploads/2024/04/VoLTE-Implementation-Guide-April-2024.pdf
- GSMA IR.58 Voice over HSPA: https://www.gsma.com/newsroom/gsma_resources/ims-profile-for-voice-over-hspa-version-4-1/

## Продолжение: собственный CP backend (2026-10-08)

Пользователь явно разрешил писать собственные modules для CS. Ring-only
сохраняется для первого этапа. Свежий стартовый runtime: LTE/IMS ready,
native1675/SIP1795, activeCallfalse, cpko basebf000000/core6397096.
Существующие rpm devices и system queues не читаются для перехвата.

Написан read-only module `src/cp-memory.c`: ARMv7 short-descriptor page
table walk, только известная System RAM, отказ от MMIO/supersections и
невалидных mappings. `src/cp-memory-probe.c` создаёт отдельный root0600
char node major1/minor1, открывает O_RDONLY, читает8 bytes известного CP
getter и сравнивает их с exact B03 instructions; только после совпадения
читает два известные boolean flags. Node удаляется после probe.
Никаких RAM/flash writes, AT call commands или RPM reads в module нет.

Live `/proc/iomem`: RAM20440000..23ffffff, kernel code20448000..2080db53.
PGD20444000 — проверяемая гипотеза стандартного ARM layout (kernel text−16KiB);
подтверждение требует чтения mapping и совпадения CP instructions. Статическая
SDK config имеет DEVMEM=y, DEVKMEM/KPROBES disabled, но это ещё не runtime
config. В B03 /dev/mem и /dev/kmem nodes отсутствуют; создание своего node
не доказывает наличие реализации memory driver.

`cp-memory-selftest.c` проверяет independently specified section/small/large
descriptors, missing PTE, MMIO table/target exclusion, supersection и PGD
alignment. Synthetic fixtures не читают устройство. Live результат будет
добавлен в этот раздел после guarded probe. PCM contract не меняется.

Guarded live probe успешно прошёл: ARM descriptor fixtures PASS на самом
модеме; чтение CP text0xbf3e527c совпало с exact B03 bytes, VOICE_SUPPORT0
и OPEN_VOICE_FLAG0 прочитаны из реальной RAM. PGD20444000 и B03 mapping
тем самым подтверждены. Native1675/SIP1795, IMSready и boot_id сохранились;
временный char node удалён. Report `build/cp-memory-live.json`.
Это реальный read-only доступ к CP state, не CS call/audio support.

### Собственный kernel adapter: подготовка

`src/cs-kernel-probe.c` и `build-cs-kernel-probe.py` создают RAM-only GPL
module для exact B03 Linux3.4.110-rt140. Layout module metadata восстановлен
из checksum-verified штатного cfg.ko (328bytes, name12, init188, exit320);
его device MD5 совпал с локальным. MODVERSIONS отсутствует у реального cfg.ko,
хотя исторический SDK config утверждал иное. Verbatim vermagic берётся из
того же verified binary; guesses о kernel structure layout не используются.
Module импортирует только printk, проверяет точные инструкции двух CP getters,
вызывает только эти read-only getters и сверяет значения с RAM. Затем читает
scalar metadata RPMSG registry в CP System RAM. Никаких patch, cursor writes,
RPMSG payload reads, AT, call control или flash writes. Live runner проверяет
exact CP placement/hash, kernel/version, ring-only, отсутствие active call,
загружает module из /dev, выгружает его и проверяет boot/PIDs/IMS.

Static B03 RPMSG registry: family0 ZSP txF83008C0/rxF8300F80,64 channels;
family1 M0 txF8300530/rxF8300400,10 channels. Пока не подтверждено,
какие каналы относятся к CS voice. Разбор CP: build/cpko-rpmsg-config.txt.
Public mainline source подтверждает descriptor ABI6u32 и SRAM pool layout,
но не является source конкретного B03 CS backend:
https://gitlab.com/stefandoesinger/zx297520-kernel/-/blob/dlink/arch/arm/boot/dts/zte/zx297520v3.dtsi

Kernel probe live PASS: own .ko loaded, two CP getters called directly and
matched RAM, ZSP/M0 descriptors and callbacks enumerated without payloads.
Unload PASS; same boot/native1387/SIP1402/IMSready. Kernel taint gained the
normal out-of-tree module bit4096; no oops or reboot observed.
`build/cs-kernel-probe-live.json` ties evidence to the exact module SHA256.
First attempt rejected an incorrect registry offset with EPROTO; corrected
TX/RX fields are +0x50/+0x54 (failure report retained separately).

### Реальный CC dispatch и ограниченный observer

Normal OSS task table is at BF55A954,39 rows of0x58; CC row index9 has
entry BF30053D. Disassembly shows the entire CC handler has only range checks
and payload frees, including nested data for AA45; it has no CC state-machine
or call signaling. Calling it a full available CC backend would be wrong.
`zOss_TaskInit` copies entry to allocated task+0x50; the real dispatcher
reloads that slot per event and calls five arguments (phase/id/data/length/work).
Live taskname/type/callback and slot verified, not guessed:
`build/cpko-cs-dispatch.txt`, `build/cpko-task-handler-storage.txt`,
`build/cs-kernel-probe-live.json` (cc_dispatch=verified).

`src/cs-kernel-watch.c` installs an atomic observer at that verified live slot,
chains the original callback with all five arguments unchanged, records ONLY
phase/id/length (at most32 individual lines), reads no payloads and sends no
messages. A kernel worker restores the original callback after600 seconds.
The observer module deliberately remains pinned in RAM until reboot: vendor
callback dispatch has no RCU/lifetime contract, so unloading text immediately
after restoring the slot could race an already-loaded callback. This is a
RAM experiment, not an autoboot module or a flash patch. Original callback
ownership is checked with compare-and-swap for both arming and restoration.
Build: `python3 firmware/mf79u/build-cs-kernel-probe.py --watch --seconds 600`;
guarded loader: `arm-cs-kernel-watch.py`.

### Входящие события внутри CC и следующий header-only probe

2026-10-08 20:19 UTC: пользователь сообщил тишину при входящем ring-only
тесте. После reattach observer получил AA43/AA44, затем пять AA45 с envelope
length20 и AA3F length4. Это реальные внутренние CC events; их тип и причина
завершения ещё не определены. Report `build/cs-kernel-watch-incoming.json`.
На этом снимке native1387/SIP1402, csOnly/ringOnly=true, IMS отключён,
GSM registration1, voice flags1/1. Ответ/исходящий вызов не выполнялись.

AA45 ABI восстановлен из exact B03 MM/SMS: envelope20bytes, body pointer+16,
length word+12. Body является уже разобранной B03 model, а не wire SDU.
Evidence `build/cpko-aa45-fields-verified.txt`,
`build/cpko-mm-sdu-builders.txt`. Полный CC stub BF30053D освобождает этот
SDU без обработки протокола, что подтверждено разбором всего handler.

`build-cs-kernel-probe.py --headers --seconds 600` строит отдельный
mf79u_cs_header module; `arm-cs-kernel-watch.py --headers` загружает его
только при свободном оригинальном callback. Предыдущий observer должен
сначала автоматически вернуть slot; modules не выгружаются из-под callback.
Header mode читает только два scalar поля envelope и два body bytes через
fault-safe probe_kernel_read, пока исходный handler ещё владеет payload.
Допускается только direct System RAM, envelope20, length2..2048; неизвестные
адреса и extended TI отклоняются. В лог идут только PD/TI/type/length,
не SDU/номер/информационные элементы. Original callback вызывается без
изменения аргументов; сигнализация и audio пока не выполняются.

PD3 и CC types SETUP05 / ALERTING01 / CALL_CONFIRMED08 / DISCONNECT25 /
RELEASE2D / RELEASE_COMPLETE2A сверены с primary Osmocom protocol definitions:
https://downloads.osmocom.org/api/latest/libosmocore/gsm/html/gsm__04__08_8h_source.html
В wire type маскируется0x3F по TS24.007 для Release99+. Для B03 model это
неверная операция: BF4C2994..2998 явно берёт body[1] >>2. Первая live версия
ошибочно использовала wire mask; её report сохраняется с предупреждением
`build/cs-kernel-header-incoming.json`, типы в нём нельзя считать decoded.
У неё получены body sizes1616/1352/1380/1348, но старый log уже потерял верхние
type bits; post-hoc восстановления типа по размеру не выполняем.
Исправленная модель использует shift2 и пишет representation=b03_model.
Новый instance имеет отдельное имя, так как предыдущие modules pinned.

### Минимальный CS ring state и подтверждённый маршрут передачи

`src/cs-route-probe.c` проверил реальные CC и ASC task pointers, registry,
callback/phase и сигнатуру send helper без передачи сообщений. Live PASS:
CC C2803180/phase1 (observer), ASC C280C900/phase2, registry verified;
module unloaded, boot/native1387/SIP1402 сохранены. Report
`build/cs-route-probe-live.json`. Собственные два observer автоматически
вернули callback=BF30053D; остаются pinned до reboot.

В `src/cs-ring-state.h` написан начальный MT call state для наблюдённого
TI0. На SETUP создаются wire CALL_CONFIRMED08 и ALERTING01; на DISCONNECT —
RELEASE2D/cause16; на RELEASE — RELEASE_COMPLETE2A. Builder допускает
только эти четыре типа: CONNECT/SETUP/исходящий набор отсутствуют и
отклоняются. Other TI/native headers остаются unsupported, caller number,
bearer selection, audio и SIP INVITE пока не реализованы. Host fixtures
проверили точные wire bytes, retransmission, clearing и все256 builder
type values: `src/cs-ring-state-selftest.c` PASS.

`--ring` kernel build добавляет bounded экспериментальную передачу этих
пакетов через exact B03 zOss_MsgSend BF438315 к verified ASC. Он принимает
только CS connection0/model header03, сохраняет original CC callback/free
и проверяет flags1/1, ASC phase2, hash-derived signatures. AAD4 envelope12
и ownership восстановлены из NAS sender/OSS queue code:
`build/cpko-cs-queue-ownership.txt`, `build/cpko-cs-send-failure-ownership.txt`.
RAM experiment, не boot/flash install. Network delivery и ringing подтверждены
последующим физическим входящим тестом ниже; полного CS voice backend ещё нет.

### Первый успешный входящий CS ring-only тест (2026-10-08 20:39 UTC)

Первый load ring module был отклонён: штатный kernel не экспортирует
`__kmalloc`. Hook не установился, CP/runtime не изменились. Использован
реальный экспорт `__kmalloc_node(size,0xD0,-1)`, как в CP allocator.
Отказ сохранён в `build/cs-kernel-ring-first-load-rejected.json`.
Исправленный module SHA256
`f5476a1b4fad68ed0c2c071dad14c05c5c80ac53ca86ae06750e9ddfcf287d52`
успешно загружен: `build/cs-kernel-ring-armed.json`.

Пользователь позвонил на обычную SIM и подтвердил гудки. Exact B03 log:
SETUP05/body1616 → CALL CONFIRMED08 + ALERTING01, оба queue_result0;
DISCONNECT25/body1352 → RELEASE2D/cause16, queue_result0;
RELEASE COMPLETE2A/body1348, затем terminal AA3F/AB0E. Вызов завершён.
CONNECT/ответ/исходящий набор не выполнялись. Original CC handler получил
те же аргументы и освободил network payloads. Sanitized report:
`build/cs-ring-incoming-live.json`; номера/полные PDU не сохранялись.

Независимый wire/state fixture также прошёл непосредственно на ARM модема,
без CP/AT IO: `build/cs-ring-state-selftest-live.json`. Boot ID,
native1387/SIP1402 и ring-only сохранены. PCM contract не менялся.
Следующая граница — собственный интерфейс CS состояния для контроллера,
Caller ID/TI/bearer и реальный CS audio transport. SIP voice readiness
по-прежнему не подменяется одной GSM регистрацией или наличием гудков.

### CS status interface и native controller (2026-10-08 20:54 UTC)

Вместо потребления /proc/kmsg/чужих IPC queues добавлен собственный read-only
sysfs `/sys/mf79u_cs/status`, mode0400. Exact kernel ABI проверен отдельным
RAM module: собственный пустой kobject создан/удалён, live show/store instructions
подтвердили offsets8/12 без CONFIG_DEBUG_LOCK_ALLOC guesses.
`build/cs-sysfs-probe-live.json`: load/unload PASS, boot/PIDs/taint сохранены.
Primary ABI references: Linux v3.4
https://github.com/torvalds/linux/blob/v3.4/include/linux/sysfs.h и
https://github.com/torvalds/linux/blob/v3.4/include/linux/kobject.h.
Ring module каждый раз повторно проверяет эти инструкции перед созданием
attribute; нет store callback, номера/SDU/секреты не публикуются.

ABI1: `MF79U_CS 1 armed state events sent errors 1` плюс newline.
state0/1/2 = idle/alerting/releasing; последний1 означает answer_forbidden.
Interface удаляется после compare-and-swap восстановления CC callback;
module text остаётся pinned. Instance2/180s проверен на модеме ARM reader:
`build/cs-status-live.json` — idle/armed, mode400, parser/selftest PASS.
Instance2 истёк с events0/callback_restored1; нового звонка не было.
Source: `src/cs-kernel-status.h`, `src/cs-status.h`,
`src/cs-status-selftest.c`; fixtures входят в `build-native-cp.sh`.

Native controller читает только этот интерфейс при CS-only/ring-only/voice-enabled,
публикует `csSignalingReady`, `csCallState`, `csAudioReady=false` и направляет
CS alert/clear в существующий LED socket через reserved prototype slot8.
Недоступный/невалидный interface очищает CS состояние. Это отдельное состояние:
SIP READY/CONNECTED/INCOMING не отправляются, IMS readiness не подменяется.
Go status API передаёт native runtime map; WebUI layout не менялся.
Реальный LED при новом входящем ещё не проверен; socket events проверены fixture.

Изолированные ARM lifecycle tests прошли: прежний searching/GSM/LTE IMS
timeout/crash/recovery, forged DIAL/ANSWER ring-only guard, CS-only restore,
новый CS idle/alerting/releasing/idle, expiry/malformed input и точные LED events.
Команда: `sh firmware/mf79u/test-native-lifecycle.sh`;
`test-cs-status.py` запускается только внутри disposable fixture container.

`install-cs-status.py` установил controller с проверенной backup/checksum
и ARM --selftest; binary SHA256
`72eeefb26794eb74a11858280598153ba3c04ef675233972c11774b365c7f260`.
Report `build/cs-status-controller-install.json`: same boot, settings/gateway.ini
сохранены; native/SIP перезапущены контролируемо, теперь2793/2794.
Backup `build/pre-cs-status-20261008/mf79u-native-gateway` (0700).
Ring-only не снимался; ядро/boot hook/NAND package не менялись.
Instance3/90s проверяет реальную связку kernel → controller и возврат
csSignalingReady=false после expiry без нового звонка;
runner `test-cs-status-lifecycle-live.py`, report `build/cs-status-lifecycle-live.json`.

Физическая связка kernel → native PASS: readiness=true во время arming,
после90s callback_restored1/events0, sysfs удалён, readiness=false/idle;
boot/native2793/SIP2794 сохранены. Нет нового вызова/CONNECT/audio.
`build/cs-status-tests.json` сохраняет hash controller и перечень fixtures.

После expiry `restore-cs-test.py` вернул исходные radio profile27/flags0/0
с readback и снял только CS-only. IMS снова ready, EPS1/CS1, native2793/SIP2794
сохранены, ringOnly=true; настройки/gateway.ini и boot ID совпали.
`build/cs-ring-final-restore.json`. Все bounded CC callbacks восстановлены;
пять observer modules (watch/header/ring/ring2/ring3) остаются pinned только
в RAM до reboot. Их текст не выгружали, boot/rootfs/PCM не меняли.
Повторный read-only snapshot20:59 UTC подтвердил installed checksum,
LTE/IMS ready, idle/no active SIP call, sysfs cleanup и ровно эти пять
pinned modules: `build/cs-ring-final-verification.json`.

## Воспроизведение рабочих параметров MT19

Offline (без обращения к устройству):

```sh
work/jffs2-venv/bin/python work/zte/voice/emulate-mf283u-audio.py --tone-uplink --tone-volume 100 --tone-amplitude 8000
python3 firmware/mf79u/prepare-cs-dsp-audio-parameters.py --report mf283u-tone-uplink-volume100-amplitude8000-emulation.json
```

Report SHA2560ca9aea823cff9553c06f0d3baf05d87ecc229cc15491dd896cc813492135be7;
header содержит basename/hash и independently emulated coefficients/amplitudes.
Для нового live test нужен новый module instance, protected GSM preparation,
explicit one-answer armer и collector; не загружать заново pinned instance19.
Нормальный runtime после restore не запускает этот candidate.


### Read-only GSMA routing audit after MO19 (2026-10-10)

`cs-route-probe.c` additionally reads the exact B03 GSMA registry descriptor,
validates the persistent task name/active flag and finds it in the39-entry
OSS list. No payload, callback change or send. `build/cs-gsma-route-live.json`
confirmed task index21/callbackBF4A57F1/phase2. Module unloaded; original
CC/ASC/admission/MM and boot/native/SIP/IMS/guards remained verified. GSMA
AAD4 forwarding goes via actual ABA8 handlerBF043729 and buffer copier
BF04294D; this source slice alone does not prove ownership of the later
shared MM+CC+SS send sequence. `build/cpko-cs-gsma-raw-nsd.txt` preserves the
offline slice. No manual N(SD) modification has been sent to the device.
Additional offline flag accessor/initialization slices were inspected in
`cpko-voice-flag-{initialization,accessors}.txt`; no new flag/boot policy applied.

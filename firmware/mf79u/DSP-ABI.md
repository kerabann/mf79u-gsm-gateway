> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# GSM DSP ABI investigation

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


Updated: 2026-10-10. MO21 established audible ARM→GSM PCM: the user heard
three ARM-generated tones after DSP command13 stopped the control oscillator.
TX/RX23396 words, RXnonzero0. Duplex and production CS/SIP remain unfinished.
Profile27/flags0/0/IMS/guards/callbacks/MM were restored on the same boot.
Reports: `build/cs-mo21-full-voice-arm-tone-{live,test,restore}.json`.
MO22 received23365 zero words while testing speech echo; the user heard no echo.
The RAM queue was cleared and all restoration checks passed.
Hangup investigation is deferred at the user's request.

## Complete reference voice API trace (2026-10-10)

`work/zte/voice/emulate-mf283u-voice-open.py` executes the hash-pinned reference
Open/Enable, input/output path setters, unmute and tone resource updater. OS
handles, buffers, scheduling and DSP transport are explicitly simulated; queued
audio messages are passed through the actual `AUD_task` dispatcher24775EB8.
NV ownership and asynchronous timing are not reproduced. This is command
construction evidence, not an end-to-end reference or B03 audio test.

The reference default inner route opens I2S0 through247821DC; the outer I2S1
also opens for external audio. HAL callback table24A6A5C4 registers through
2477D9CC. Open/Enable/SetFs/input/output callbacks at248953C4..24895400 return
zero without MMIO; this table supplies no missing internal hardware mux step.

`build/mf283u-full-voice-open-port-tone-emulation.json` differs from the earlier
manual builder: the actual input path is0 followed by sentinel20, without the
manually inserted path15. AFE-only VB_ON has nine zero PCM-tail words; the
manual builder configured PCM despite selecting AFE. Real mixer parameters
begin8192/8192 and include7959/16383 where the earlier preparation had zeros.
The tone updater still puts32767 on both tone mixers. The exact disable
builder selects switch1, followed by the existing scheduler-stop command15;
the disable switch is not silently replaced with the manual builder's0.
These differences justify separate bounded idle and connected tests, but do
not yet identify the cause of silence.

`prepare-cs-full-voice-parameters.py` validates the generator/source hashes,
real API results, route, gain words, inactive PCM tail and matching8k I2S
configuration. `test-cs-audio-mailbox-ack.py --full-voice-open` stages it under the
existing GSM ring guard and restores the previous header/configuration plus
production policy. It creates no CC hook, SIM call, DSP program or boot change.
The first build stopped offline at the older port-tone-only gate; that gate now
distinguishes the explicit full-API no-call variant. No guard/device mutation
occurred in that failed preparation. The live receipt is
`build/cs-full-voice-open-live.json`: all11 commands received their expected
negative ACK, TX15667/RX15670 words, RXnonzero0, failed0. AP/tone/registers,
previous header/configuration, callbacks/MM, profile27/flags0/0 and IMS/guards
were restored on the same boot/native1620/SIP1680. This idle result does not
establish behavior on an assigned GSM speech channel.

The builder/armer now require explicit `--i2s-full-voice-open` for the connected
variant and bind it to the matching completed idle receipt, parameter/config
hashes, accepted ACKs and verified restoration. `test-cs-full-voice-call.py`
prepares instance32 with one authorized answer, a2s known DSP-tone control,
then6s full voice API parameters with ARM TX silence/RX observation. It restores
the local header/configuration and LTE/IMS automatically after actual CC/MM
clearing; a failure with an active callback retains the guard. No production
binary, DSP program, boot hook or external PCM format is changed.
MT32 completed: `build/cs-mt32-full-voice-open-live.json`. The user heard a
clean tone initially, then a more buzzing tone; ARM TX23102/RX23106 contained
no nonzero words, failed0. Control/new DSP commands were accepted. The call
cleared with MM refs0; registers/AP/tone/callback and local header/configuration
were restored. Every check in `cs-mt32-full-voice-open-restore.json` passed,
including profile27/flags0/0, IMS/guards and the same boot/native/SIP. This
test did not demonstrate received PCM; it transmitted silence from ARM.
MO21 subsequently confirmed ARM uplink with this full profile and actual tones.

The secondary command25 wrapper246B526C and `aud_init`24786714 were inspected.
Its resource12/13 conditions and a stubbed hardware helper do not establish
that this command belongs in the selected AFE voice path. No new secondary-port
command was sent. The reference's32-byte voice-loop buffersF600184C/186C are
encoded voice loop data, not320-sample PCM. Larger GSM shared buffers have no
confirmed audio producer in the bounded xref search; this is not an exhaustive
proof that shared-memory PCM is absent.

## Public paths, data-thread startup and shared RAM (2026-10-10)

`work/zte/voice/emulate-mf283u-voice-paths.py` reuses the hash-pinned complete
voice Open model while suppressing its receipt writer. All20 input/output
combinations run the real public setters and refresh. Input conversion is
[0,1,2,0], output[0,3,2,4,13]. Input2/output3 constructs UL2/DL4 with an active
PCM tail, but input2 logs "voice_SetPahtIn the path not support" despite
returning0. This route remains unresolved; later bounded idle and MO18 tests were sent
to B03, with only zero ARM RX words. Receipt:
`build/mf283u-voice-path-matrix-emulation.json`. The accepted physical idle
receipt was not regenerated or changed.

`work/zte/voice/emulate-mf283u-voice-start.py` executes actual
vp_VoiceI2sStart24783410 after full Open/Enable. OS DMA/IRQ, buffer availability
and buffer commit services are explicitly simulated; DMA-engine MMIO is not
represented. The result0/128 simulated MMIO writes and no additional DSP
commands describe this model, not hardware startup. Receipt:
`build/mf283u-full-voice-start-emulation.json`. Hardware FIFO low bits03
self-clear, so the earlier successful ARM loop readback disproves a continuous
flush explanation; no speculative FIFO change was made.

`work/zte/voice/prepare-b03-pcm-windows.py` runs the exact hash-checked B03
pointer initializer BF3E9F4D offline. Seven windows are bounded by the next
initialized pointer and limited to160halfwords; mailbox/control and shorter
encoded-frame regions below FAD014BA are excluded. The source report
`build/b03-dsp-pcm-windows.json` pins the CP module and generator. The generated
header binds its report SHA. None of these addresses has confirmed PCM
ownership. The loadable sampler `src/cs-channel-watch.c --dsp-pcm-metadata`
checks every pointer slot before reading. It logs changed/nonzero counts and
period8/16/32 hints only. Samples and internal change hashes never leave the
kernel; there are no cursor, SRAM, DSP-command or I2S writes. Unknown sample
rate, concurrent snapshots and possible periodic control data prevent PCM
classification from a periodicity hit alone.

`src/cs-dsp-pcm-period-selftest.c` passed on the physical soft-float ARM:
500/1000/1500Hz synthetic tones were recognized, silence/DC/100 random blocks
rejected. The RAM executable was removed. `test-cs-pcm-metadata-idle.py`
completed the physical no-call preflight: seven accepted windows, static
nonzero contents, no period hits, sampler unloaded and original profile27,
flags0/0, LTE/IMS/guards plus boot/native1620/SIP1680 restored. Receipt:
`build/cs-pcm-metadata-idle-live.json`. `test-cs-pcm-metadata-tone.py` binds to
that successful sampler build for one already authorized outgoing tone call.
It collects statistics before/during/after the known audible DSP tone without
opening ARM I2S, and restores production policy after verified CC/MM clearing.

The connected MO16 control completed and the user confirmed all three audible
tones. Seven windows produced no period8/16/32 hits; index6 changed554 times,
starting before CONNECT, and index4 twice. Static or changing contents alone
remain unclassified. `build/cs-mo16-pcm-metadata-tone-test.json` retains only
statistics. All independent restoration checks passed in `-restore.json`.
The wrapper initially retained its guard because an older MT32 expiry log
had rotated. The restore helper now accepts the same exact boot/module-bound
fresh route audit for MT as it already did for MO. Offline guard regression
rejects a different boot/module set or unsafe route before any policy writes.
The stdin preflight issue was caught before arming/dialing: the read-only ADB
helper now uses DEVNULL; only the explicit dial writer accepts destination data.

## Public PCM route and clock selection (2026-10-10)

`work/zte/voice/emulate-mf283u-public-pcm.py` preserves the frozen complete
Open receipt and executes public input2/output3, real PCM profile builder and
actual mono/TDM prepare helpers. The public input2 warning remains explicit;
this is an experimental route, not a supported B03 API claim. Public refresh
selects PCM0 from its descriptor, overwriting a preceding PCM1 choice. The
real mode builder247863AC is therefore applied after refresh, followed by
VB_ON builder24774EBC without refreshing the descriptor again. ARM master
uses updated PCM1 words154/4112/1625; ARM slave uses PCM0 words48/4113/3250.
The complete reference mixers begin8192/8192, tone gains32767/32767. The
actual Init+PCM loop retains bit0:99, compared with earlier mode-only98.
Configuration selector6 and timing01EF0009/01EF0008 are hash-bound to the
real prepare functions. OS/buffers/DSP/MMIO remain simulated.

`prepare-cs-public-pcm.py` validates the source/generator hashes, real API
results, routes/mixers/tails and matching clock direction before generating a
header. The builder accepts this route only for bounded `--i2s-dsp-loop`;
both connected build attempts were rejected offline before compilation.
`test-cs-audio-mailbox-ack.py --public-pcm [--arm-slave]` prepares one4s
no-call test using the existing audio command IDs and reversible register/AP/
tone restoration. It restores the prior generated header/configuration and
production radio policy after independent callback/MM audits. It installs no
CC callback, DSP program, IRQ/DMA handler or production media backend. A
physical result must be recorded before expanding this gate.

Both physical no-call cases completed: ARM master TX/RX8035/8035, allzero;
ARM slave TX16/RX0. All11 negative ACKs were accepted, failed0, modules
unloaded and local parameters/configuration, AP/tone/registers plus original
profile27/flags0/0/LTE/IMS/guards restored on the same boot/native/SIP.
Receipts: `build/cs-public-pcm-live.json` and `-arm-slave-live.json`.
The connected gate now permits only explicit `--mo --i2s-pcm-candidate
--i2s-port-tone --i2s-public-pcm`, bound to the matching restored idle receipt
and exact parameter/config hashes. Incoming answers remain forbidden. MO17
uses the known2s DSP tone control then6s public PCM port/ARM RX and auto-hangup
at10s. New MO PCM polling uses1..1.5ms; tone-only/default branches are unchanged.
Exact B03 kernel relocation audit passed. `test-cs-public-pcm-call.py` restores
local headers/configuration and production LTE/IMS after actual CC/MM clearing;
it retains the guard on uncertain clearing. No hardware PCM result is claimed.

The first MO17 arming was rejected before destination submission. An old
unconditional I2S source override compiled the incoming MT source under an MO
module name. The actual idle MT control stop cleared its answer window and
restored the callback; no SIM call/audio data writes occurred. All independent
restoration checks passed in `build/cs-mo17-public-pcm-restore.json`.
Source override is now limited to connect-probe. Builder and armer independently
check the outgoing source and compiled artifact contract before upload. The
wrapper waits for both sysfs names on restoration. Inactive misnamed mo17 is
pinned until reboot and must not be reused. The next fresh MO uses this corrected
source selection; no connected PCM result is claimed from the rejected attempt.

## Offline DSP decoding

The boot record comparison is hash-bound in
`build/mf283u-b03-gsm-dsp-boot-comparison.json`. Its command0 records load tiny
program-memory patches; command1 records supply data and command2 enters0x20.
The B03 patches differ from the MF283U reference. Neither image supplies the
full GSM DSP ROM called by these patches.

An offline decoder was built from [Teakra](https://github.com/wwylele/teakra),
commit `3d697a18df504f4677b65129d9ab14c7c597e3eb`, under
`work/zte/voice/teakra`; its MIT license stays with the source. The custom reader
is `work/zte/voice/inspect-teak-image.cpp`. Teakra targets XpertTeak on Nintendo
hardware. Coherent ZTE disassembly is evidence for instruction compatibility,
not proof of the complete ZTE ISA or peripheral map. Its Nintendo memory/MMIO
layout is not used for modem access. No DSP program was uploaded or patched.

Both images' vectors6/0E branch to254C and vector16 to23FD. Initialization0x20
sets SP37A1, calls ROM20D3/294C/29C3/F375/2A26, installs callback pointers, and
ends in an interrupt-enabled loop atD8. B03 contains further callback patches.
The64-word program block1FC0 is a branch table. Its purpose is unresolved;
it must not be labeled the audio command table solely from its length.

## Exact B03 self-check transport

The original function BF3EA118, called through literal BF3E9B98, writes the
fixed host sequence below and pulses general mailbox notification bit0.
The MF283U reference function246B4D18 uses the same sequence. Disassembly is
in `build/b03-gsm-dsp-loader-selfcheck-static.txt`.

| ARM host address | Fixed halfword |
| --- | --- |
| FAD0100A | 0021 |
| FAD0100C | E000 |
| FAD0100E | 0000 |
| FAD01010 | 1020 |
| FAD01012 | 0005 |

The function expects ACK FFDF at FAD0100A and returns pending bit0. It can
invoke vendor reset/assert on failure. The direction and memory-space meanings
of E000/1020/5 are **not established**; this is not a verified ROM-read API.
No modified request or direct call to the vendor function has been made.
General mailbox bit0 belongs to GSM L1, independently of audio mailbox bit2.

`src/cs-dsp-boot-watch.c` observes only real vendor self-check calls. It replaces
the exact checked caller literal, chains the unchanged original function and
arguments, logs five host parameter halfwords, and restores the literal after
120 seconds. It creates no DSP command or call, reads no speculative DSP
address, and remains pinned after expiry to avoid freeing a possible retained
PC. `test-cs-dsp-boot-watch.py` performs the already-tested temporary GSM radio
profile transition and restores flags/profile/IMS/guards. The read-only route
audit now also checks the original self-check literal.

The observer passed exact B03 kernel relocation checks in
`build/cs-dsp-boot-watch-build.json`. The live test completed in
`build/cs-dsp-boot-watch-live.json`: events0 across LTE→GSM registration;
the self-check caller is not reached during that radio transition. The observer
restored the original literal after120s, and a fresh read-only route audit
confirmed the literal plus CC/ASC/admission/MM state. LTE/IMS, profile27,
flags0/0 and removed guards were verified on the same boot/native/SIP PIDs.
The inactive observer stays pinned until reboot. No call or new DSP command
was made. This test neither proves a DSP ROM read API nor physical PCM.

`work/zte/voice/extract-gsm-teak.py` validates both source images and every
boot-record checksum, merges contiguous code records before decoding, and
writes `build/gsm-teak-static-decoding.json`. It decoded B03's1430-word main
patch into1038 instructions and the reference's998-word patch into716. Teakra
marks7/4 instructions as uncertain `mov?`; these remain unresolved. Loader
record boundaries no longer truncate a possible two-word instruction. The
64-word branch tables decode to32 branches in each image. Earlier per-record
listings are retained as history; merged listings are the current analysis.

Reproduce offline:

```sh
cmake -S work/zte/voice/teakra -B work/zte/voice/teakra-build \
  -DTEAKRA_BUILD_TOOLS=OFF -DTEAKRA_BUILD_UNIT_TESTS=OFF \
  -DBUILD_TESTING=OFF -DTEAKRA_WARNINGS_AS_ERRORS=OFF
cmake --build work/zte/voice/teakra-build -j4
clang++ -std=c++17 -O2 -I work/zte/voice/teakra/include \
  work/zte/voice/inspect-teak-image.cpp \
  work/zte/voice/teakra-build/src/CMakeFiles/teakra.dir/disassembler.cpp.o \
  -o work/zte/voice/inspect-teak-image
python3 work/zte/voice/extract-gsm-teak.py
```

## Physical ARM mapping check

`build/cs-i2s-b03-mapping-evidence.json` binds the B03 kernel map descriptors:
I2S0 physical01405000 maps toF8A05000; internal loop physical00140060 maps
toF8440060. The current diagnostic addresses match those descriptors.
Reference ToneMixer/Voice_MixerData mix samples on ARM and still feed I2S;
they do not provide an independent shared-memory PCM bypass.

## Module-loader ABI preflight

`src/cs-module-layout-probe.c` and `test-cs-kernel-probe.py --module-layout`
provide a read-only preflight for a possible initial-load observer. The probe
uses the exact B03 kernel `__module_address` export and checks the recovered
328-byte module structure against live CP name, state, core address, size and
init pointer. Reads are bounded under IRQ exclusion on this single-CPU kernel.
It installs no notifier or hook, accesses no DSP and unloads immediately.
Build and exact relocation evidence: `build/cs-module-layout-probe-build.json`.
Live `build/cs-module-layout-probe-live.json` passed: CP structure BF59D000,
state0, init BF3E30D8, core BF000000, size6397096; `layout_verified=1`.
The module unloaded, its RAM file and ring guard were removed, and the same
boot/native/SIP PIDs with IMS ready were verified. No boot changes or reboot
have been made for this preflight. A future observer loaded before CP would change its address, so all
CP references would need to use its verified dynamic module base.

## Paired I2S extra-cycle preflight

The MF283U `i2s_Configure` validates `tTdmExtCycle` at configuration byte23
as enum0/1. Value0 sets timing bit5 at247801C4; value1 clears it at247802B4.
This establishes a reference API alternative, independently of the unrelated
Linux driver's TEAK_EN name. Its physical meaning on B03 remains unverified.
`emulate-mf283u-i2s.py --voice-inner --driver-init --tdm-extra-cycle 0|1`
produces separate hash-bound offline reports. The paired profiles differ only
in byte23 and timing bit5:01EF2021 versus01EF2001. DSP parameters stay identical.

`test-cs-i2s-extra-cycle.py` prepares the idle GSM test policy, then executes a
four-second tone-loop for each enum with `cs-i2s-dsp-loop-probe.c`. No SIM call,
CC hook, DMA/IRQ ownership, DSP program upload or boot edit is made. Registers
and host AP/tone fields are restored after each case, and finally the previous
generated header plus production profile/flags/IMS/guards are restored. Live
results completed in `build/cs-i2s-extra-cycle-pair-live.json`: cycle1 TX/RX
15880/15880, all RX zero; cycle0 TX15963/RX0. Neither produced PCM. Both
modules unloaded and registers/AP/tone fields restored. Previous header and
production profile27/flags0/0/IMS/removed guards were verified on the same
boot/native/SIP PIDs. These no-call results do not prove SIM/SIP duplex audio.
No boot change was needed for this alternative; the separate initial-load
observer is described below.

## Initial-load notification observer

`src/cs-dsp-load-watch.c` defaults to notifications only. It observes the
read-only module-layout probe's COMING/LIVE/GOING metadata and unregisters on
unload. `test-cs-module-notifier.py` verified this on the physical kernel with
an idle ring guard: all three event/state pairs1/0/2 were observed. The module,
RAM file and guard were removed; same boot/native/SIP PIDs and IMS preserved.
Report: `build/cs-module-notifier-live.json`.
The notification ordering is checked against upstream [Linux3.4 module.c](https://raw.githubusercontent.com/torvalds/linux/v3.4/kernel/module.c):
COMING occurs after relocation and before the module's init. B03 ABI needs the
separate live confirmation; upstream source alone is not compatibility proof.

An explicit `build-cs-kernel-probe.py --dsp-load-watch --dsp-load-observe` build
can observe the unchanged initial self-check when loaded before CP. It checks
CP name/state/size/init offset and function signatures, uses the dynamic core
base, chains the exact original function and restores its literal at expiry.
Only the fixed host command/parameter window is sampled after real vendor
self-check calls; it creates no DSP request/program or SIM call. Parameter
meaning and DSP address mapping remain unverified. Observer and CP are pinned
until reboot to avoid freeing retained PCs. Exact B03 relocation audit passed:
`build/cs-dsp-load-watch-build.json`, SHA256
`c6d96d27b538e5ceace38ca8ab2ba061823df8cfb0467bc96239c81f123a3a9a`.
The bounded initial host parameters are cached and repeated at expiry so boot
log churn does not erase the observation. No DSP-address interpretation is made.

`test-cs-dsp-initial-load.py` prepares offline by default; explicit `--run`
installs one temporary conditional in the checksum-verified production rc.
It backs up rc both locally and in protected userdata, verifies code/staging,
consumes the one-shot marker first, atomically restores rc and remounts root
read-only **before CP loads**, then loads the observer. Unrecognized checksums
skip observation and preserve normal CP startup. A normal second reboot clears
pinned modules and restores the original CP base; a fresh route audit, profile,
flags, IMS, guards, root mount and removal of temporary boot files are verified.
Constant-address diagnostics are not run while CP is relocated by the observer.
No raw flash write, carrier call or extra DSP request is made. The one-boot
experiment was staged with verified backups and an idle ring guard.
The adbd reboot service acknowledged without changing boot ID; the live script
now uses the project's verified `adb shell "sync; reboot"` path. This transport
correction is recorded in `build/cs-dsp-initial-load-reboot-transport.json`.
The initial observation was not captured. The interrupted run timed out before
its capture, and its restore query failed while ADB was unavailable. The cause
of the lost initial record is unknown. A subsequent fresh audit confirmed normal
boot `1c2740a7-7cbf-49e2-b08e-bc6c1e476282`, the original rc checksum, CP base,
CC/ASC/admission/self-check callbacks, zero MM references, profile27, voice
flags0/0 and IMS readiness. Temporary boot files and guards were removed; see
`build/cs-dsp-initial-load-final-restore.json`. The pre-CP loading method is now
quarantined: loading the observer first relocates CP without a full compatibility
proof. Its builder and live armer refuse further execution.

## Extended clock controls, read-only

`test-cs-i2s-clock-readonly.py` runs the expanded preflight under a temporary
ring guard without changing radio profiles. The exact B03 module reads LSP
controls58/5C/60/64/68 and GSM registerF843B068 plus CP clock record53.
`build/cs-i2s-extended-clock-live.json` confirms GSM register1F/hw flag1;
LSP extra registers60/64/68 wereFFFF0000/4/FFFF0000. There is no established
interpretation of those extra fields. No registers, FIFO data, DSP programs
or calls were changed. Probe unload, RAM/guard removal, boot/PIDs and IMS
were preserved. The first host parser used regex group0 incorrectly; it was
corrected from saved measurements without repeating device access.

The extra LSP controls are also noted in the author's
[ZX297520v3 LSP clock patch](https://lists.openwall.net/linux-kernel/2026/08/09/667).
That source alone does not define a DSP audio route. Local exact-platform
DTS describes several GSM blocks as compatible with Infineon PMB8877;
this is a new research lead, not proof of a matching DSP ROM or audio ABI.

## B03 audio acceptance and original voice rate

`test-cs-audio-mailbox-ack.py` measured every response after the unchanged audio
command pipe became idle. The four-second GSM idle run issued no SIM call:
10→FFF0 twice,19→FFE7,11→FFEF,17→FFE9,18→FFE8,0F→FFF1 twice,
12→FFEE,13→FFED,15→FFEB. All11 replies matched -command.
`build/cs-audio-mailbox-ack-live.json` confirms complete production restoration.
The diagnostic transport now requires both idle and that measured negative ACK;
this establishes command acceptance, not duplex audio or all parameter meanings.

The raw, hash-pinned voice-inner configuration24ACCA68 has8000 at offset8;
the generic24ACC850 configuration has16000. A rate-mismatch hypothesis was
rejected offline before device access. The temporary native-rate options were
removed. The emulator now records original/selected rates and whether a real
override occurred; no additional live frequency test was needed. The diagnostic
builder checks FIFO rate against the hash-bound configuration bytes. External
PCM remains mono16LE16000/320.

## PMB887x primary reference, offline only

[PMB887x-dev](https://github.com/siemens-mobile-hacks/pmb887x-dev) commit
`d63cc30d8dd0c848a86cedfcac05ad29a442a62c` supplies ROM0801/0604 dumps,
register definitions and sample audio code. The26-file local cache under
`work/zte/voice/pmb887x-reference` preserves MIT LICENSE and file hashes/URLs in
`source-index.json`. Its [0801 command description](https://github.com/siemens-mobile-hacks/pmb887x-dev/blob/d63cc30d8dd0c848a86cedfcac05ad29a442a62c/rom/dsp/0801.md)
is an ABI lead, not a matching ZTE specification. Older0801 has READ_DSP with
three parameters and VB_ON with13; B03 self-check has four following words,
and reference/B03 audio setup has27 VB_ON parameters. ROM calls also differ.
No READ_DSP, PCM_SUBMIT, Siemens multimedia command, or DSP program from this
reference was sent to the modem. Shared-RAM PCM is described in older ROM
command28, but B03 addresses and ownership are unverified.

The [PMB887x Teakra fork](https://github.com/siemens-mobile-hacks/teakra), commit
`e563358d52ffd2fcf00875a3028c314aef222a7e`, was built separately.
`work/zte/voice/decode-gsm-teak-pmb887x.py` rechecks source/container/commit
hashes and decodes both ZTE patches offline. The pinned source ranges include
one extra word after BRANCH; only that recorded trailing word is excluded
from the fork's strict container input. `build/gsm-teak-pmb887x-decoding.json`
records both hashes. B03/ref retain exactly the same7/4 uncertain mov? opcodes
as the original decoder. No additional ZTE instruction or audio ABI was proven.

## Full-API ARM tone comparison and OS audit (2026-10-10)

The bounded MO21 candidate stops the known DSP tone after2s and sends
500/1000/1500Hz PCM from ARM for6s using the restored full-Open AFE profile.
Earlier full-Open MT32 and public-PCM MO18 transmitted silence from ARM.
The previous ARM-tone MT27 used manual UL[0,15] rather than full API
UL[0,20,20]. This comparison therefore has a different, explicit transmitter
and is not a repeat of the all-zero RX diagnostic. Readbacks record actual
loop, timing, process and clocks each second; no speech/sample values saved.
MO21 subsequently confirmed audible ARM uplink; see its result below.

Offline inspection of the frozen emulator's reference OS interceptions:
23F18C88 sets a RAM activity bit in24DE5F24 under IRQ exclusion;
23F2BAE4 branches to248A3674 and reads task-associated64-bit metadata;
23F3D078 formats/logs a string,23F2A5EC is zOss_Sleep,
23F033A0 is a bounded busy delay. None of these routines reveals an omitted
MMIO audio enable.23F03A6C is process/interrupt registration, not pinmux.
Reference voice Init248958CC confirms the master/slave profile addresses
used by the emulator. Alternate TDM init2478F404 also writes matrix clock
selection01306050 and DMA selection00140120, but no B03 TDM compatibility
or need for these changes is established; no such register was written.
The encoded shared buffers previously inspected are not a proven replacement
for I2S; the old CSD-buffer AMR injection remains a negative result.

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

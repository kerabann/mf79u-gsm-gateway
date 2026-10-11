> Imported project history, snapshot 2026-10-11. Read the [current repository status](STATUS.md) and [agent rules](../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Правила работы
- Все что делаем должно отображаться в md документах
- Всегда проверяй актуальность документации
- Работаем над прошивкой которую потом упакуем и разом будем ставить на модем

# MF79U: контекст проекта и инструкции для следующих чатов

Обновлено: 2026-10-11. Это рабочий проект на физическом ZTE MF79U,
а не только макет интерфейса. Перед изменениями проверяйте актуальное состояние
модема и процессов: подключение USB, адреса, PID и состояние IMS меняются.

## Device IMEI: восстановлено чтение (2026-10-11)

На модеме отсутствовал `/mnt/userdata/mf79u/tools/system-imei`, поэтому поле
System → Device IMEI оставалось пустым. Восстановлен проверенный ARM helper
MD5 `6cea9fd9432d810b99777396b6025db4`, права0700. `install-control-update.py`
теперь восстанавливает отсутствующий helper; другой executable не заменяет.
API возвращает generic `imeiError`; UI показывает ошибку около поля и отключает
Save IMEI до успешного чтения. Refresh восстанавливает отображение.

Два read-only чтения текущего IMEI совпали; значение/хеш не сохранялись.
Go/JS проверки read/error/recovery/auth и browser fixtures всех7 вкладок
1280/390px прошли. System HTML/JS на модеме совпадают с исходниками.
Authenticated live API отдельно не проверялся: для API/UI использованы fixtures,
для реального чтения — hardware helper. Настройки и native/SIP PID сохранены
при нашей Control-only установке; позднее наблюдалась отдельная параллельная
замена runtime на том же boot. Финальный snapshot не считать доказательством
неизменных PID или готового SIP client binding. Мы не меняли IMEI, не делали
reboot/звонки/SMS. Детали и receipts: [SYSTEM.md](../firmware/mf79u/SYSTEM.md),
`build/system-imei-display-{live,ui-fixture}-20261011.json`.

## VoWiFi only SMS (2026-10-11)

Установлен общий UI/REST/SIP dispatcher: VOWIFI отправляет SMS только через
private IMS по текущему Wi-Fi/USB ePDG-туннелю, без сотового SEND_SMS/CMGS/ZMGS
fallback и автоматического повтора. Другие режимы сохраняют B03 SEND_SMS.
Входящие IMS PDU сохраняются до RP-ACK, собираются в отдельном private inbox
и доступны в Modem memory и через SIP. B03 PDU enum проверяется read-only в
owned IMS child; PCM/кодеки/CS driver не менялись. Один разрешённый тест через
USB: HTTP200/RP-ACK за1.54s, submitted1/confirmed1. Пользователь подтвердил
получение и отправил ответ; received1 через private IMS, ответ сохранён в inbox.
После финального native-only update IMS/SMS ready, fenced=false, прежние boot
и настройки; сообщения сохранены. Итоговые2 accepted/2 received включают другую
активность устройства, наш тест отправлял ровно одну SMS. Native MD5
`dde984d74696e64c77069de1f27e6cf9`, Control
`2b2947fe8e7418d1c901d84137671ea7`; SIP/IMS media/CS driver не менялись.
Linphone переоткрыт с прежним аккаунтом: localRegistered=true подтверждено
после native restart, без новой SMS/звонка. Переключатель Connected меняет
presence и не обновляет REGISTER; прежнюю привязку после restart не предполагать.
Для обеих сохранённых входящих IMS SMS подтверждены SIP delivery ACK;
queued/sending SIP jobs отсутствуют. Временные read-only probes удалены из RAM.
Не повторять согласованный SMS тест: receipt содержит guard от повторной отправки.
Документ [SMS-IMS.md](../firmware/mf79u/SMS-IMS.md), receipts
sms-ims-*-20261011.json. Историческая
проверка smsip capability ниже относится к прежней реализации.

## Текущий постоянный CS runtime (2026-10-10)

В userdata установлены persistent CS driver/adapter/PCM, native controller,
SIP и WebUI с AUTO/VOLTE/CS. Подтверждены пользователем исходящий и входящий
CS↔SIP/PBX: тон, эхо и своевременный отбой. SMS через CS отправлена ровно
один раз и получена. Реальный отказ IMS→AUTO GSM fallback прошёл дважды,
включая после software reboot; проверены init ancestry, IMSready и suspended
CS module.40-секундный звонок после fallback не оборвался по старому таймеру.

Пользователь сообщает глухой CS тембр и требует сохранить хороший IMS звук.
Аппаратный CS PCM8k/160 преобразуется в прежний внешний16k/320; actual GSM
codec/rate ещё не измерен. Общий FIR проверен и не изменён, IMS binaries/CMR/
gain и global SIP codec order сохранены. Opus→PCMU сравнение не улучшило тембр.
CS PCM emphasis дал более ясное эхо и закрепляется отдельно от IMS. Найдена
и исправлена ложная потеря heartbeat при DSP bootstrap (unsigned time underflow);
новый pinned driver установлен через software reboot;25-секундный исходящий
звонок на lease-fixed revision прошёл с эхом до конца и нормальным отбоем.
Финальный driver также запускает входящий PCM после SIP ANSWER до CONNECT ACK;
входящий тон/эхо/отбой подтверждены без reboot. AUTO/IMS восстановлен и проверен
после финального fresh boot; IMS26s/SIP29s от native startup. Final driver MD5
`b3440aadf8e7be2e2321d13e539ba078`. Receipts:
`build/persistent-cs-incoming-mt-audio-pending.json`,
`build/registration-autoboot-final-20261010.json`,
`build/cs-audio-final-verification.json`.
См. [CS-AUDIO.md](../firmware/mf79u/CS-AUDIO.md). Это не доказывает HD GSM.
Не заявлять поддержку UMTS или GSM wideband.
Актуальные receipts и ограничения: [REGISTRATION.md](../firmware/mf79u/REGISTRATION.md),
[STATUS.md](../firmware/mf79u/STATUS.md), [audio-quality.md](../outputs/mikopbx/audio-quality.md).
Ниже — история диагностических этапов. Rootfs/SD архивы не обновлены.

## История аудио этапов (2026-10-10)

MO40 PASS: user confirmed SIP echo and automatic handset hangup28s.
No DSP/ARM diagnostic tone or22s/30s media deadline; PBX supplies tone/echo,
then SIP HANGUP→owned CS stop. No reboot; full IMS/radio/guards restoration.
Current confirmed boot e58dfbf0…, native1839/SIP1969. USB was recovered by
moving to another port; prior absence followed user-reported laptop reboot.
Normal-clock production SIP candidate still NOT installed. Persistent CS
adapter, incoming SIP-controlled answer and automatic voice fallback remain
unfinished. Current evidence and exact limits: STATUS.md, MO40 section.

MO39 FIX: handset hangup20s after Cause coding corrected to GSM PLMN(3).
Network RELEASE now cause16 instead126. No reboot; full IMS restoration passed.

Cause corrected Q.931→GSM PLMN in MO/MT/ring; ASan/UBSan passed. MO39
confirmed prompt remote hangup with unchanged SIP audio. Detailed evidence in STATUS.md.
Production CS/fallback still unfinished; normal-clock candidate not installed.

IMS baseline: SIP BYE18s acknowledged immediately; user confirms immediate
handset clear with echo end. RTP900/900, same boot/PIDs, ordinary IMSready.
CS70s delay therefore remains CS-specific. Main normal-clock SIP candidate
passed four isolated ARM RTP/PCM cases; not installed. No test remains armed.

MO38: echo20s, handset70s, no reboot, full IMS restoration. Network RR/MM
release preceded the deferred2s AA3E: immediate MM request is not causal.
Third sequential echo without reboot. Main SIP build now links shared normal
clock wrapper; candidate built but NOT installed. IMS baseline prepared via
single-call SIP tester; no radio/PBX settings changes. See STATUS.md.

MO37 confirmed echo until20s (user corrected2s), remote clear70s, no reboot.
ASC: DISCONNECT18.5s, RELEASE cause126/coding3 after0.14s; RC and MM request
immediate, RR release0.4s later. No CC repeat. Same boot/PIDs/IMS restored.
MO38 prepared with optional2s deferred MM release after RC; ASC150s. Hypothesis
only; default remains0 and production unchanged. Details in STATUS.md.

MO36: user confirmed tone and SIP echo, handset ended at77s. Local DISCONNECT
at18.8s, network RELEASE/RC/MM idle by20s: remote clearing still delayed.
No reboot; native1681/SIP1779 and boota7acac28… retained, IMSready fully restored.
Normal SIP clock measured SCHED_OTHER0. Vendor N(SD) sequence2/3/0/1 confirmed;
it did not fix remote hangup. Kernel PCM queue clean, SIP queue8underflow/9overflow.
Receipts cs-mo36-full-voice-arm-echo-arm1-rx-only-tx-switch-userspace-sip-*.
Next passive ASC metadata under same clock policy. Production fallback unfinished.

Normal-clock idle DSP/SIP overlap PASSED without reboot; all three tone phases
and register restoration/unload complete. Receipt cs-sip-dsp-load-*-normal-clock-cycle1.
IMS returned late after GSM→LTE (initial ZPDPDEACT timeouts); pre-reboot snapshot
already ready. The deliberate software reboot was unnecessary for recovery; see
cs-sip-normal-clock-deliberate-reboot.json. Do not count it as spontaneous reset.
N(SD) exact helper offline emulation8cases passed; MO36 uses this allocator.

MO35 reboot до18s timeout: только писк, пользователь сообщил handset end32s.
Затем reboot воспроизведён БЕЗ SIM вызова и БЕЗ CC hooks: idle DSP/I2S +
synthetic SIP media. Call timeout не необходим для сбоя. Failure receipts
сохранены как cs-sip-dsp-load-{live,kernel}-before-normal-clock.json.
Отдельный recovery: cs-sip-dsp-load-reboot-recovery.json, bootb4066e72…,
native1575/SIP1631, IMSready/profile27/flags0/0/guardsfalse/PBXidle.
Установленное SIP clock реально SCHED_RR99; CP/watchdog ниже. Подготовлен
diagnostic-only PJMEDIA_CLOCK_NO_HIGHEST_PRIO wrapper, причинность не доказана.
Проверять сначала synthetic SIP, затем overlap без SIM. Production не менялся.
Raw CC N(SD) allocator BF29BE71 integrated in MO36, remote delay remains.
Production CS↔SIP/fallback ещё не установлен. Детали/receipts в начале STATUS.md.

## Актуальная точка входа после аудита документации (2026-10-08)

Сводка и индекс ВСЕХ тематических документов: [STATUS.md](../firmware/mf79u/STATUS.md).
При конфликте с историческим этапом ниже использовать текущую сводку/код и
последний относящийся к бинарнику report, не просто наибольшую версию в названии.
Current delivery: userdata overlay, Control0.10 / native0.9 / SIP0.8, без Mac relay;
full NAND0.9 и SD0.8 — устаревшие архивы, rootfs image не прошит. System/SSH,
SIP SMS, GSM fallback и yellow LED уже установлены по соответствующим отчётам;
factory-profile-preserving Reset только спроектирован, НЕ реализован.
Позднее 2026-10-08 подтверждены реальные гудки входящего GSM CS вызова:
собственный bounded RAM CC handler, без CONNECT/ответа. CS audio/SIP forwarding
не реализованы. Native теперь читает отдельный CS status interface; актуальные
отчёты и состояние после восстановления LTE/IMS — GSM-VOICE.md / STATUS.md.
2026-10-09 гудки повторены, ring4 протокол больше не ограничен32events.
Подготовлена отдельно проверенная IMS/CS admission/ownership policy; она ещё
не подключена к native, CS audio не восстановлен. Пользователь уточнил, что
не отвечали на roaming SIM, а текущую обычную SIM разрешено отвечать. Native
ring-only marker пока сохранён для старого IMS/SIP пути; отдельный одноразовый
CS CONNECT получил network ACK и полное clearing; пользователь услышал
тишину, аудиомост пока отсутствует. RPMSG sampler истёк до вызова, поэтому
media observation inconclusive. LTE/IMSready восстановлены: radio27/flags0/0,
csOnly=false, native2793/SIP2794, boot сохранён; cs-connect-final-restore.json.
Позднее TCH sampler сопровождался reboot; его SHA quarantined.
Static audit выявил direct Thumb call к ARM `memset`, вероятную причину;
предыдущий kernel log недоступен. Corrected revision2 убирает libcall,
builder/armer независимо проверяют kernel export modes и live kernel MD5.
Короткий live idle test прошёл без reboot/process changes, module unloaded:
cs-tch-corrected-idle-live.json. Autonomous boot
native1336/SIP1359; LTE/IMSready/radio27/flags0/0 восстановлены, RAM hooks
исчезли. cs-tch-sampler-recovery.json. Перед новым действием сверить
GSM-VOICE.md/report и live callback/status.
Повторный CONNECT с corrected sampler охвачен целиком; пользователь подтвердил
таймер разговора/clearing, cs-tch-connected-live.json. Audio отсутствует,
RPMSG cursors/IRQ49 не двигались, GSM IRQ56/57 работали. LTE/IMS восстановлены,
roaming ring-only guard снят для ordinary SIM: ringOnly=false/csOnly=false,
native1336/SIP1359 и boot сохранены. cs-ordinary-sim-voice-restored.json.
Перед новым CS diagnostic guard временно включать, full voice fallback не готов.

Последний revision3 DSP status test не соединился: нет AB0C/CONNECT ACK,
пользователь сообщил отсутствие таймера. DISCONNECT/RELEASE обработаны,
sampler unloaded/callback restored без reboot/PID changes. Нулевые8 DSP control
halfwords при failed call не являются доказательством отсутствия audio.
cs-dsp-status-connected-live.json (historical filename; connected=false).
Сейчас LTE/IMSready восстановлены, ringOnly=false/csOnly=false,
native1336/SIP1359 и boot сохранены: cs-dsp-status-final-restore.json.
Два CONNECT modules inactive/pinned до reboot. До нового call test выяснять
cause/assignment; production CS media/fallback всё ещё не реализованы.

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

## Цель и требования пользователя

Сделать MF79U шлюзом между звонками через SIM и SIP-транком Asterisk/MikoPBX,
с собственной прошивкой и WebUI вместо стандартной панели ZTE.

- Оператор: AMR-WB, все 9 режимов до 23.85 кбит/с; AMR-NB как резерв.
- SIP: Opus, G.722, G.711 A-law, G.711 µ-law, G.729. Включение/выключение
  и порядок кодеков; UDP/TCP/TLS; сервер, порт, учётная запись и пароль.
- Три SIP-роли: Disabled (голос/SIP выключены, cellular SMS/WebUI/REST сохранены),
  внешний транк/PBX либо встроенный
  однопользовательский SIP-регистратор. В режиме SERVER входящий SIM-вызов
  направляется единственному зарегистрированному клиенту, а его исходящий
  цифровой SIP URI набирается через SIM.
- Передавать номер входящего абонента в From/P-Asserted-Identity отдельно
  от SIP auth username. Учитывать Privacy.
- Состояние сети, IMS, SIP и звонка; чтение/отправка/управление SMS.
- Wi-Fi (требование 2026-10-11): переключаемый Hotspot / Client. Hotspot: SSID /
  Password / Enabled / Hidden network. Client: scan/select или ручной SSID,
  WPA2-Personal / Open, пароль, DHCP. Это заменяет hotspot-only требование.
- Статическая USB/management сеть; штатный DHCP обслуживает клиентов hotspot.
- LTE data на Mobile: запрет обычного мобильного OUTPUT и FORWARD IPv4/IPv6,
  без выключения радио. Только local operator IMS bearer wan5 остаётся разрешён.
  Внешнему SIP при выключенном LTE data нужен USB маршрут.
- VoWiFi (2026-10-11): AUTO предпочитает IMS через Client Wi-Fi; отдельный
  VoWiFi-only запрещает LTE/CS voice fallback. IPv4 ePDG/SIM authentication
  прошла; IMS/call/audio пока требуют live проверки: firmware/mf79u/VOWIFI.md.
- Сетевой LED: красный — нет регистрации в сети; жёлтый (красный+зелёный) —
  сеть зарегистрирована, IMS не готов; синий — VoLTE ready / idle; фиолетовый — VoWiFi ready / idle; зелёный — исходящий
  или соединённый звонок, красный+синий — входящий до ответа. Wi-Fi LED синий
  при активном интерфейсе; оба индикатора теперь принадлежат нашей прошивке.
- Последние пожелания: простые вкладки без украшений; вся админка на английском.
- **PCM не менять**: mono PCM16LE, 16000 Hz, 320 samples / 20 ms.

## Расположение файлов

Корень проекта: `<checkout>`.
`firmware`, `outputs`, `work` сейчас обычные каталоги этого корня, не симлинки.
Ранее они ссылались в <historical-workspace>;
старые отчёты сохраняют этот исторический путь. Path.resolve() теперь ведёт в
текущий workspace. Не предполагать синхронность старой и новой копий. Команды
выполнять из <checkout>. Git-репозитория в корне нет.

- `firmware/mf79u/WEBUI.md` — архитектура управления и границы проверки.
- `firmware/mf79u/AUTONOMOUS.md` — этап 0.9: локальные PDP/AKA/IMS, автозапуск и границы проверки.
- `firmware/mf79u/src/cp-ipc.c`, `firmware/mf79u/src/native-gateway.c` — нативные CP IPC и IMS/SIP controller.
- `firmware/mf79u/build-native-cp.sh`, `firmware/mf79u/test-native-cp.py` — сборка и read-only проверка на ARM.
- `start-native.sh`, `install-native.py`, `verify-standalone.py` — локальный
  supervisor, обратимая B03 service policy и проверка автономной загрузки.
- `firmware/mf79u/control/` — native Go HTTP/API, конфигурация, сеть, vendor API.
- `firmware/mf79u/control/web/` — HTML/CSS/JS без CDN и стороннего frontend runtime.
- `firmware/mf79u/src/modem-sip-gateway.c` — SIP, кодеки, Caller ID.
- `firmware/mf79u/src/sip-registrar.h` — встроенный однопользовательский
  UDP SIP-регистратор и Digest-аутентификация.
- `firmware/mf79u/test-sip-registrar.py` — полностью изолированный fixture;
  `test-sip-registrar-live.py` — безопасная проверка регистратора на модеме
  с нецифровым INVITE и автоматическим возвратом исходной конфигурации.
- `firmware/mf79u/src/ims-userspace-ipsec.c` — IMS transport/media integration.
- `firmware/mf79u/run-pbx-gateway.py` — Mac CP/AKA relay и запуск голосового моста.
- `start-private-ims.py`, `stop-private-ims.py` — изолированный IMS и безопасная очистка.
- `install-control.py` — guarded установка/восстановление загрузки WebUI на B03.
- `prepare.py`, `build.sh`, `verify.py` — offline rootfs overlay и проверка образа.
- `firmware/mf79u/build/` — исполняемые файлы, отчёты, логи, экспериментальный JFFS2.
- `outputs/adb`, `outputs/zte-native-usb`, `outputs/zte-sms.py` — инструменты устройства.
- `outputs/zte-backup/rootfs.mtd5.bin` — проверенная исходная копия rootfs.

## Текущая архитектура и ограничения

Исходная прошивка: `BD_XCBZHKMF79UV1.0.0B03`. ARMv7 soft-float,
Linux 3.4.110, примерно 56 MiB RAM и 12 MiB zram; VFP/NEON не использовать.

WebUI работает непосредственно на модеме из
`/mnt/userdata/mf79u/.mf79u-control`, порт 18080. Собственные правила iptables
переводят LAN HTTP/80 в панель; штатный goform backend остаётся на loopback/80.
Настройки и gateway.ini находятся в `/mnt/userdata/mf79u`, права 0600;
бинарники и wrapper — 0700. Boot hook в `/etc/rc` установлен и проверен.

**С 0.9 PDP/SIM AKA/IMS/SIP работают локально, Mac relay и watcher остановлены.**
Повторные реальные software reboot проверки подтвердили загрузку от init:
start-control.sh -> start-native.sh -> .mf79u-native-gateway -> private IMS/SIP.
Последняя регистрация IMS заняла 18 s от старта контроллера, SIP готов через 21 s.
Не запускать старые run-usb-gateway.py / run-pbx-gateway.py поверх native service.
Это прежний recovery путь, для него сначала выключить/остановить native supervisor.
2026-10-11 добавлен Wi-Fi Client; реальная WPA2 ассоциация и DHCP с Lipetsk-2G
подтверждены (192.168.50.96/24). USB/LAN остаётся 192.168.0.1/24; голосовой PBX
тест использует USB LAN. См. firmware/mf79u/WIFI.md и актуальные receipts. Нативный контроллер не зависит от vendor WebUI session.

B03 PDP ответ 0x159b содержит result, cid, error (12 bytes). Disassembly
zte_mifi 0x225ea подтверждает result=0, CID по offset4; error word на success
не инициализирован. Принимается только точная IMS activation и CID5; затем
читается CGCONTRDP=5, проверяются IMS APN, реальные адреса/P-CSCF и строится
+ZPDPACT для IMS. src/cp-pdp.c проверяет IPv4/IPv6; текущий оператор — IPv4.
Не подменять реальную activation фиктивным OK и не использовать 0x152e:
read-only probes этого альтернативного маршрута не получили ответа.

Лабораторный Docker выходит с фактического primary IPv4 Mac (адрес меняется), а SIP
сервер в UI указан как 192.168.0.169. Защищённый userdata pbx-return-routes
содержит явный /32 return route через USB peer; start-native.sh восстанавливает
его при boot, не перезаписывая чужие маршруты. NAT source также добавлен в
SIP trustedPeers. При смене этой лабораторной адресации обновить оба параметра.
Обычной PBX с прямой связностью этот специфический Docker маршрут не нужен.
Native RAM log ограничен 64 KiB с проверкой каждые 30 s; O_APPEND позволяет
очищать его без дыр в файле. При диагностике запуска сохранять отчёт сразу
после boot: старые события могут быть удалены при достижении этого лимита.

Отключены штатные LED/self-registration startup entries, zte_dm и FOTA
prestartdua/zte_topsw_dua. Backup: daemon.vendor.b03.conf, debug.vendor.b03.sh,
start-control.pre-native.sh в userdata. CP, radio, SIM, SMS, WLAN, router/DHCP,
NTP и watchdog сохраняются. /usr/.../zte_debug.sh и daemon config изменены
атомарно; штатные исполняемые файлы не удалены и не изменены.
Проверка: build/standalone-verification.json. После автономной загрузки был
исходящий SIM/SIP connected; пользователь подтвердил звонок и писк. PCM
received=518/sent=365, nonzero=518/364. Входящий beep/echo тест не получил
нового вызова за 10 min; маршрут PBX восстановлен, temporary app удалён.
Входящий Caller ID после native migration пока не перепроверен.

microSD теперь вставлена, 31,268,536,320 bytes, /dev/mmcblk0, partition
/dev/mmcblk0p1. Пользователь сам скопировал Flipper-файлы и 2026-10-07
явно разрешил форматирование. FAT32/MBR, volume ZTE_SD, start sector 2048.
Наш raw backup отменён; partial image удалён, полного бэкапа файлов проект
не делал. Не утверждать обратное.

21 файл / 20,812,865 bytes ARM runtime 0.8 размещены на карте и сверены
SHA256 на Mac + MD5 на модеме. CP/controller synthetic tests и все пять SIP
codec pipelines прошли непосредственно с карты. Mount:
/mnt/userdata/mf79u/sd, vfat ro,nosuid,nodev,noatime,umask=0077, exec разрешён.
Go WebUI автоматически запустился с SD после реального reboot; settings MD5 остался
80ef3a556d420f4b952516fcd50e19ef. Первоначально wrapper start-control.sh выбирал SD binary
по checksum policy sd-control.md5 (0600), с fallback на внутреннюю копию.
Теперь control-internal-preferred (0600) запрещает старый SD UI: DISABLED/HOTSPOT
требуют нового внутреннего binary. SD остаётся архивом, marker не удалять без
совместимого обновления SD UI.
Pre-SD wrapper сохранён как start-control.pre-sd.sh. /etc/rc не менялся.

Штатные HTTPSHARE_MODE_SET/AUTH_SET на B03 вернули failure. Использован
существующий NV sdcard_mode_option=1, USB card LUN1 отсоединён. До reboot
ro флаг LUN был 1; после reboot он сброшен в 0, но file остаётся пустым;
HTTP_SHARE_STATUS остался Disabled. Простое очищение LUN без NV mode=1
не работает: ZTE экспортирует карту снова, Mac автоматически монтирует её.
Не монтировать карту RW с двух сторон. LUN0 — виртуальный CD, его не трогать.
Wrapper не отсоединяет USB LUN принудительно при boot; mount разрешён
только при уже пустом LUN, NV=1, отсутствии других mmc mounts.
Подробности: firmware/mf79u/SD.md; отчёт build/sd-prepare-report.json.
SD runtime 0.8 остаётся проверенной копией WebUI и архивом предыдущего этапа.
Нативный голос 0.9 и LED запускаются из внутренней userdata. WebUI имеет
внутренний fallback; карте не передана роль kernel/bootloader или swap.
Полный NAND image пока не прошит; kernel/rootfs стартуют из B03 flash.

USB LAN модема обычно `192.168.0.1/24`; Mac en10 — `192.168.0.169/24`.
Основной интернет Mac должен оставаться через обычный uplink (Wi-Fi/VPN). Не менять default route
на модем. Актуальный primary IPv4 Mac надо определять, а не брать из старого лога.

MikoPBX в Docker: контейнер `mf79u-mikopbx`, WebUI `http://127.0.0.1:8180`.
Провайдер `SIP-TRUNK-51091984`, модем SIP `192.168.0.1:5080`.
`outputs/mikopbx/configure.py` не импортировать: у него есть top-level изменения
настроек/учётных записей. Проверять PBX через read-only Asterisk CLI.

## История установок UI/голоса и их подтверждения

Этот большой раздел содержит последовательные этапы. Его «последний/текущий»
внутри пункта относится к дате того этапа, а не отменяет поздние System/fallback
разделы. Актуальный краткий статус — в STATUS.md.

- На этапе 2026-10-07 UI был установлен с пятью вкладками Status / SIP /
  Messages / Wi-Fi / Network, синяя шапка. В SIP теперь нет внутренних
  вкладок: сверху Operation mode, затем локальный Address/Port и форма роли,
  постоянно видимые Codecs (включая Disabled), один Save внизу всех разделов.
  Wi-Fi SSID/Password в одну колонку. Все три поля Password загружают текущие
  сохранённые значения и по умолчанию замаскированы; кнопки Show/Hide меняют
  видимость без изменения настройки. GET /api/settings по-прежнему исключает
  секреты; отдельный GET /api/settings/credentials требует management cookie
  и X-CSRF-Token, возвращает только SIP/Wi-Fi credentials с no-store.
  Администраторский пароль не возвращается. Logout/401 очищает поля и settings
  в памяти страницы; Save и rollback заново загружают credentials. Сравнение
  сетевых настроек учитывает реальный пароль и keep-current blank.
  Последний контрольный SHA256 и live evidence:
  build/ui-password-wpa2-rest-live.json; screenshot ui-password-toggle-desktop.png.
  Предыдущие visible-passwords reports относятся к старой версии UI.
  Старые UI reports — история предыдущих бинарников. Установлена только новая
  WebUI копия; старый wrapper завершил cleanup ДО нового запуска, PID file
  сохранился, новый wrapper от init; SIP PID/IMS сохранились. Последнее применение
  сети/Save послало штатный SIGHUP gateway: client binding сброшен и требует
  повторной регистрации клиента (последний status localRegistered=false).
  Один Save выполняет PUT settings + Apply; только Wi-Fi/LAN требуют отдельного
  подтверждения соединения в течение 90 s. Пустой password (keep current) не
  считается сетевым изменением. Роли DISABLED / TRUNK / SERVER показывают
  соответствующие формы. Все пять разделов и три формы проверены desktop/390 px.
  Последняя раскладка: build/ui-sip-flow-verification.json и screenshots
  ui-sip-flow-desktop.jpg / ui-sip-flow-mobile.jpg. Проверена без изменения
  настроек/SIP PID, IMS и binding сохранились. Перезапущен только WebUI: разовый
  build/detach-control double-fork helper передал wrapper init; Mac не удерживает
  его ADB session. Helper удалён из RAM и не является runtime dependency.
  Предыдущий UI backup: build/pre-ui-modes-20261007/
  mf79u-control.before-sip-layout. Старый ui-modes-verification.json — историческое
  доказательство boot/режимов, его control SHA256 относится к предыдущему UI.
- На этапе UI 2026-10-07 была сохранена роль `SERVER`; на последней проверке
  fallback 2026-10-08 — `TRUNK` (см. раздел GSM / IMS-independent ниже).
  LTE data=false, hotspot=true, hidden=false. Disabled закрывает LAN SIP socket,
  сбрасывает binding и блокирует DIAL/ANSWER/входящий голос в native controller;
  IMS возможен на LTE, GSM SMS не требует IMS. Проверены переключение Disabled, затем SERVER (OPTIONS
  200), без SIM звонков. В `SERVER` одна учётная запись/активная привязка.
- Проверен реальный reboot с сохранённым DISABLED: wrapper и supervisor от init,
  новый внутренний WebUI, постоянный WPA2 hotspot, IMS registered и закрытый
  LAN SIP port. Затем SERVER восстановлен одной кнопкой Save, без reboot IMS.
  Свежий отчёт build/ui-modes-verification.json связывает SHA256 компонентов
  с device MD5; screenshots ui-modes-sip-desktop.jpg / ui-modes-sip-mobile.jpg.
- Исправлен OPEN hotspot: одного psk_enable=2 было недостаточно — фактически
  encmode оставался 0. Теперь выставляются authtype=0, encmode=2, 802_1x=1,
  psk_enable=2, WPA2 AES cipher=8 и сохранённый passphrase. До и после ifconfig up
  читаются MIB и сверяется ключ; при ошибке hotspot остаётся down. get_mib B03
  возвращает десятичные байты; passphrase читается до первого NUL, хвост структуры
  может содержать старые данные. Штатный wlanapp не запускает auth для pure PSK
  AP: handshake выполняет драйвер. CoreWLAN scan с SSID filter подтвердил переход
  OPEN=true/WPA2=false → OPEN=false/WPA2-Personal=true. Сохранённый пароль
  совпал с ключом драйвера; полноценная ассоциация внешнего клиента пока не
  проверена. Ранние утверждения о WPA2 только по psk_enable — неполное доказательство.
- Добавлен SMS REST API и справка внизу Messages. GET/POST/DELETE collection
  /api/v1/sms/messages; DELETE /api/v1/sms/messages/{id}; storage=modem|sim,
  Unicode и bulk delete до 100 IDs. REST number декодирует UTF-16BE без
  добавления предполагаемого кода страны; date — RFC3339 с timezone или null
  для неизвестного/невалидного формата. rawNumber/rawDate сохраняют исходные
  поля. direction=incoming для tag 0/1, outgoing для 2/3, draft для 4, unknown
  иначе; mapping подтверждён штатным smslist.js. Legacy /api/sms не меняется.
  Live: 3 incoming / 2 outgoing, все даты ISO8601 и номера декодированы.
  Fixtures: Unicode sender, plain/local numbers, offset quarters, leap dates,
  invalid dates=null и все направления. Authorization: Basic (admin + пароль админки)
  проверяется через ZTE challenge на каждом запросе, без cookie/Origin/CSRF.
  Header auth ограничена только SMS REST; не даёт доступ к management/passwords.
  Общий vendor cookie jar не ломает другие UI sessions. Cookie auth остаётся
  совместима и требует Origin/CSRF для mutations. Документация SMS-API.md,
  CLI sms-api.py (stdlib, getpass или password-stdin, секреты только в RAM).
  Fixtures проверили отправку/удаление, auth/CSRF, invalid JSON и Unicode;
  live Basic read: modem 5, SIM 0. Невалидный send отклонён 400 до mutation.
  Реальные SMS не отправлялись/не удалялись/не помечались прочитанными.
- Hotspot применяет rtl8189es hiddenAP/security MIB, reuse штатного dnsmasq
  UDP/67. Enabled off/on и Hidden true/false проверены на физическом устройстве;
  внешний Wi-Fi клиент пока не ассоциировался в этой проверке. Старые station
  credentials не используются как AP password; миграция берёт защищённый
  заводской профиль NV. Пароли не менялись и не печатались.
- Новые MF79U_DATA OUTPUT и MF79U_SHARE FORWARD правила стоят первыми;
  для IPv4/IPv6 off пропускает локальный wan5, блокирует прочие wan*.
  Firewall поддерживается каждые 3 s. Это не гарантия тарификации оператора.
- Старые бинарники сохранены локально в build/pre-ui-modes-20261007 (0700).
  На устройстве settings.pre-ui-modes.json / gateway.pre-ui-modes.ini (0600).
  Полный rootfs/package 0.9 ниже собран ДО этих изменений и сейчас устарел;
  не утверждать, что эти функции входят в старый image. Raw flash не выполнялся.
- Локальный сервер пока UDP-only. Digest MD5 реализован как совместимый с SIP
  challenge/response: qop=auth, nonce из `/dev/urandom`, привязка nonce к
  источнику, контроль nonce-count и ограничение частоты. Пароль исключён из
  обычных API, но явно разрешён пользователем в защищённом admin credentials
  endpoint для редактора; должен быть не короче 12 символов. REGISTER использует наблюдаемый
  IP/port клиента, а не произвольный адрес из Contact.
- Изолированный тест проверил challenge, корректный и неверный пароль, replay,
  замену единственной привязки и безопасный нецифровой INVITE. Живой тест через
  USB-LAN на физическом модеме подтвердил authenticated REGISTER, отражение
  binding в status и ответ 484 для `probe`; SIM-вызов не создавался. После
  теста `gateway.ini` и роль `TRUNK` восстановлены автоматически.
- На установленной 0.8 SIP-процесс после live-теста занимает около 2.5 MiB RSS,
  native controller около 0.23 MiB, WebUI около 6.2 MiB при `GOMEMLIMIT=6MiB`. Новый SIP binary
  вырос на 8192 bytes. В userdata после установки свободно около 10.4 MiB,
  на microSD около 29.1 GiB. Встроенный регистратор работает в том же процессе
  и не требует отдельного daemon, поэтому текущих RAM и flash достаточно.

- Простая панель с шестью верхними вкладками установлена на модем.
  Убраны sidebar, иконки, баннер и декоративные карточки; формы сохранены.
  Тогдашние шесть разделов (с отдельной вкладкой Codecs, ещё без System)
  проверены desktop/390 px, горизонтальной прокрутки нет.
- Английская панель установлена: HTML, JS и пользовательские ошибки Go API.
  Содержимое SMS и значения протоколов не переводились. Все вкладки проверены
  при 390 px после перевода; переполнения ширины нет.
- Пользователь сообщил задержку IMS около 20 минут, постоянную ошибку SMS API
  и отсутствие выбора памяти модема. Исправления установлены, подробнее ниже.
- После переподключения голосовой launcher отсутствовал. В последнем запуске
  private IMS появился при uptime ~1019 s, SIP gateway — ~1061 s.
  Между запуском IMS и готовностью SIP прошло примерно 42 s; большая часть
  20 минут была ожиданием запуска Mac relay, а не сетевой IMS регистрацией.
  В `build/gateway-tabs-ui.log` подтверждены IMS registered и GATEWAY_READY.
- Backend SMS требует действительную vendor login session. Без неё возвращается
  `{"sms_data_total":""}`, а не `messages`; это нельзя считать пустым inbox.
  Через существующий пароль и SHA256 challenge получен result=0, cookie и
  корректные списки. Пароль в документацию/код/логи не записывать.
- **Проверено на текущем B03: mem_store=1 — память модема (3 сообщения),
  mem_store=0 — SIM (0 сообщений)**. Счётчики: sms_nvused_total=3,
  sms_sim_total=40, sms_sim_rev_total=0. Не перепутать эти значения.
- Backend cookie jar теперь общий для UI-сессий: новый вход не ломает другую
  вкладку. Перед SMS проверяется loginfo. Короткая vendor session отделена от
  собственной 30-минутной сессии управления. Для каждой management session в
  RAM хранится только `SHA256(password)`; plaintext и производный ключ не
  пишутся во flash, настройки, ответы или логи. При потере vendor cookie backend
  получает свежий LD, выполняет один автоматический LOGIN и один раз повторяет
  исходный status/SMS/Wi-Fi запрос. Ошибка повторного входа оставляет WebUI
  открытым: SMS endpoint возвращает 428, а 401 зарезервирован для собственной
  сессии. Это проверено fixtures и на устройстве.
- Добавлен selector Modem memory / SIM card. Вживую: 3 / 100 в модеме и
  0 сообщений при ёмкости 40 на SIM. sms_capacity_info вызывается через
  отдельный handler без multi_data: NV запрос не возвращает нужные счётчики.
  Успешная загрузка очищает ошибку, ошибки SMS локальны вкладке Messages.
- Отправитель SMS в WebUI теперь показывает обычный номер без изменений и
  декодирует UTF-16BE hex для буквенных sender ID. Время ZTE формата
  `YY,MM,DD,hh,mm,ss,TZ` отображается как английская дата с явным UTC offset;
  поддержаны как signed quarter-hour offsets, так и беззнаковый ноль. Для
  неизвестных форматов остаётся исходное значение. Это установлено и проверено
  на реальных сообщениях без их изменения.
- После перезапуска UI/во время bootstrap вживую ещё раз истекла vendor session.
  Она остаётся короткой и не считается бессрочной, но автоматический LOGIN с
  новым challenge восстанавливает radio/SMS и обе памяти без выхода из админки.
  Точная причина ротации vendor cookie внутри B03 не установлена.
- Отправка/удаление SMS проверены fixtures; в текущей UI проверке реальные
  сообщения не отправлялись, не удалялись и не помечались прочитанными.
- В 0.9 native CP probe/selftest/controller имеют локальный голосовой автозапуск.
  Четыре read-only запроса выполнены локально, synthetic IPC/allowlist tests
  прошли на ARM, queue inventory не изменился. Смотрите build/native-cp-verification.json.
  FD2_VOLTE readonly probe через 0x150c/port1 не получил ответа за 10 s.
  Не заменять на него CP relay без дальнейшего доказательства.
- Vendor session повторно истекла без сетевых изменений даже при polling и
  серверном heartbeat. Последний удалён как неэффективный. Вместо heartbeat
  используется автоматический LOGIN по факту истечения и однократный retry.
  Plaintext пароль не сохраняется; производный ключ живёт только в RAM в течение
  собственной management session.
- Полный образ 0.9 собран и проверен: 40,136,252 bytes / 48 MiB partition,
  883 paths, 345 vendor binary paths unchanged, JFFS2 CRC проверены.
  Native live evidence в manifest связан с SHA256 собранных компонентов.
  Пакет build/mf79u-custom-0.9-experimental.tar.gz содержит образ, manifest,
  live report, документация, SHA256SUMS; без flasher).
  При restart исправлена гонка cleanup userdata wrapper: предыдущий wrapper
  больше не удаляет pidfile/правила нового процесса; fixture прошёл на BusyBox ash.
  Образ **не прошит**. На физическом B03
  стоят обратимые userdata компоненты и boot hook. Не путать эти установки.

## Команды и запуск

Из исходного корня проекта:

```sh
outputs/adb devices
outputs/adb shell 'cat /proc/uptime; ps'
sh firmware/mf79u/build-control.sh
sh firmware/mf79u/build-native-cp.sh
python3 firmware/mf79u/test-native-cp.py
python3 firmware/mf79u/test-sip-registrar.py --gateway firmware/mf79u/build/modem-sip-gateway
# Только при подключённом физическом модеме и отсутствии активного вызова:
python3 firmware/mf79u/test-sip-registrar-live.py
sh firmware/mf79u/build.sh
outputs/adb shell 'cat /dev/.mf79u-native-status.json; cat /dev/.mf79u-gateway-status.json'
docker exec mf79u-mikopbx asterisk -rx 'core show channels count'
docker exec mf79u-mikopbx asterisk -rx 'pjsip show endpoint SIP-TRUNK-51091984'
```

Native voice запускается автоматически. Следующие команды относятся только
к старому Mac recovery launcher; перед ним отключить native-enabled и штатно
остановить наш native supervisor. Выбрать один старый способ:

```sh
python3 firmware/mf79u/run-usb-gateway.py
# Или отдельный ручной запуск вместо наблюдателя:
python3 firmware/mf79u/run-pbx-gateway.py --adaptive-audio
```

После power reconnect `/dev/.mf79u-*` исчезают. Только для старого recovery
launcher постоянные бинарники можно связать с ожидаемыми RAM путями:

```sh
outputs/adb shell 'ln -sf /mnt/userdata/mf79u/.mf79u-volte-private /dev/.mf79u-volte-private; ln -sf /mnt/userdata/mf79u/.mf79u-sip-gateway /dev/.mf79u-sip-gateway; ln -sf /mnt/userdata/mf79u/.mf79u-ims-userspace-ipsec.so /dev/.mf79u-ims-userspace-ipsec.so'
```

Не запускать второй IMS поверх первого. Проверять queue/process ownership.
`stop-private-ims.py` сверяет process executable/checksum и удаляет только
инвентаризированные очереди. Не применять произвольные killall/ipcrm.

## Важные технические ловушки

- Сборка Go закреплена на **1.25.12**. Go 1.26 добавлял 32 MiB FIPS .bss,
  и ядро убивало бинарник на execve. Native Go: GOMAXPROCS=1, GOGC=20,
  GOMEMLIMIT=6MiB. Старый syscall getrandom несовместим; используется /dev/urandom.
- BusyBox ash не поддерживает shell arithmetic expansion `$((...))`.
- Большой `adb push` часто заканчивается EOF и не устанавливает файл.
  `ram_transfer.ram_push` подходит для небольших файлов, использует gzip/4 KiB
  chunks и контрольную сумму; не грузить большой Go binary в RAM параллельно IMS.
- Для большого control binary использовать временный HTTP server на USB IP Mac
  `192.168.0.169:18089` с whitelist одного артефакта, native `build/ram-http-get`,
  staging в userdata, сверку размера/MD5 с локальным файлом и atomic rename.
  Удалять временный server/forward после переноса, не раскрывать каталог.
- UI assets embedded в Go: одного изменения HTML/CSS на Mac недостаточно,
  требуется rebuild и установка native executable.
- После TERM UI дождаться завершения его прежнего wrapper (PPid UI) перед
  запуском нового. Быстрый restart в этом этапе оставил живой UI без pidfile:
  файл восстановлен после проверки checksum/executable/parent. Возможна гонка
  old-wrapper cleanup после предварительной проверки владельца; не считать
  один EXIT guard полным взаимным исключением. Новый wrapper принадлежит init.
- Перезапускать только свой UI daemon по проверенному pidfile/cmdline;
  не перезагружать весь модем ради стилей. Перед голосовыми изменениями
  проверять отсутствие активного вызова.
- Background `adb shell '... &'` может погибнуть с ADB session. Для ручного
  запуска UI держать foreground `adb shell 'sh /mnt/userdata/mf79u/start-control.sh'`.
  При нормальной загрузке wrapper запускается из rc.
- B03 не принимает `ip addr replace`; STATIC адрес добавляется идемпотентно.
- Vendor перестраивает firewall: own rules проверяются каждые 3 секунды,
  не заменять таблицы производителя целиком.
- Собственный `/etc/rc` MD5: b98c87a5d44b5c8b847ca5ad3125b5d7;
  исходный B03: 9b070d96d9bd752f579c8c00d9167204.

## Проверки и аккуратность

Не печатать и не сохранять пароли, AKA ответы, cookies, номера абонентов
и содержимое SMS в общих отчётах. Диагностика SMS должна выводить только
storage, тип ответа, количество и счётчики. Unicode SMS должен сохраняться.
Секреты уже есть в защищённых локальных конфигурациях; не копировать их сюда.

Проверять изменения fixtures/тестами по сути проблемы, затем на физическом
модеме. Для UI проверять все вкладки desktop/mobile и сохранять screenshot
без SMS/секретов. Не делать реальные звонки или SMS mutations ради проверки
стилей/перевода. PCM и операторский профиль не менять в этой работе.

Перед raw flash нужны точная совместимость B03, проверенные backup/checksum,
геометрия и способ восстановления. Обычная userdata установка не является
raw flash. Windows/UTM DL проброс раньше не удалось надёжно наладить;
не возвращаться к нему без необходимости.

Обновляйте этот файл после значимых изменений состояния/архитектуры,
чтобы следующий чат не принимал незавершённые пункты за готовые.

## Shared USB / Wi-Fi LAN DHCP (2026-10-07, latest installed WebUI)

- Network tab now has Subnet / IP gateway / IP pool / DNS servers / Routes via
  DHCP, with English help describing one profile for USB Ethernet and hotspot.
  Current baseline: 192.168.0.0/24, modem .1, pool .2–.253, DNS 1.1.1.1/8.8.8.8,
  no custom routes. Example `1.2.3.4 via 192.168.0.10` is only a placeholder.
- `control/lan.go` migrates legacy LAN settings; derived LAN Address remains
  gateway/prefix and Mode STATIC. Validate subnet/pool/routes before applying.
  DHCP advertises options 3/6 and custom 121/249, including default when 121
  is present. This does not change operator IMS DNS or modem uplink routes.
- Reuse vendor dnsmasq 2.88 on bridge0; validate syntax and atomically update
  /tmp/dnsmasq.conf. Restart only verified exe/config-owned dnsmasq PIDs.
  Preserve vendor leasefile/upstream config; no second persistent daemon.
  First config backup: userdata/dnsmasq.vendor-before-network.conf (0600).
  Native WebUI reconciles current/candidate LAN every 10 s, so vendor config
  regeneration is corrected. Keep normal 90 s apply/confirm/rollback.
- DHCP pool excludes the gateway and fixed USB recovery 192.168.0.1. Client
  DHCP renewal/reconnection is required; manually addressed clients need manual
  updates. Custom next hops need stable, collision-free LAN addresses.
- Physical USB DISCOVER/OFFER verified temporary 192.168.7.0/24, gateway .7.1,
  DNS and default + host route 1.2.3.4/32 via .7.10 in both 121/249, followed by
  explicit rollback and original-profile confirmation. No lease accepted, no
  Mac IP/default-route changes, no calls/SMS mutations. IMS remained ready;
  SIP PID 3074 unchanged. All five tabs desktop/390 px passed without overflow;
  unchanged Save did not trigger network confirmation. Full reboot and an actual
  Wi-Fi DHCP client were not tested for this change.
- Installed control MD5: dae9845aa5d17a21d7a5013d7f040457. Evidence/SHA256:
  firmware/mf79u/build/lan-dhcp-verification.json. Screenshot:
  build/ui-network-dhcp-desktop.png. Architecture/help: firmware/mf79u/NETWORK.md.
  Only internal userdata WebUI updated; existing full 0.9 image is stale.

## Read-only IMEI capability inspection (2026-10-07)

Exact live B03 /lib/libatext.so matches stock MD5 d1ba655c5bc0ae566ea2a7b38fa0fbcd.
It contains MODIMEI/READIMEI and imeiWrite_act_func (0x5a00), factory authorization
check with `+CME ERROR: unauthorized`, 15-digit validation and persistent
`amt_nvro_write(0,8,...)` at 0x5b62. Authorization in the running process was not
tested; no IMEI/NV/flash change, unlock/patch or service restart occurred.
Do not claim our unit is unlocked or successful changing has been tested.
Details: firmware/mf79u/IMEI.md; evidence: build/imei-capability-verification.json.
IMS ready, SIP PID unchanged. No IMEI values recorded in report/documentation.

## Downloaded B03 IMEI modification analyzed (2026-10-08)

Actual B03_MOD_adb_modimei.zip attachment 35470196 downloaded (14,902,353 bytes,
ZIP CRC passed). Its rootfs SHA256 7395d80fded04e5f2e29bc70347fd27dc039e556bc5ff66453ce53853be45ed0
is identical to work/zte/b03mod/rootfs.bin. IMPORTANT: Jefferson ordinary
extraction skips later replacement filenames, leaving obsolete stock binaries.
Latest JFFS2 dirents/replay identify libatext inode 1815 version 415 and
zte_production_server_at inode 1816 version 181. CRCs passed. Accurate recovered
files are in work/zte/b03-adb-modimei/replay; b03mod-extracted/fresh are not
authoritative for them. Stock inspect-rootfs.py rejects deleted-dirent history.

libatext has 32 changed bytes: IMEI and MAC authorization BEQ branches inverted
to BNE; ZteAuthGen redirected to response, with text replaced by OK/author marker.
Existing IMEI length/packing/amt_nvro_write remain identical; no factory key
is recovered. Production server has a two-byte patch to ignore ZADBPSWD
verifier result. adbd restored byte-identical to stock. Our live device remains
stock for these binaries at the end of analysis: no installation/unlock/NV/IMEI change, IMS ready.
Full analysis: firmware/mf79u/IMEI.md; evidence: build/imei-modification-analysis.json.

## IMEI-only device patch (2026-10-08, overrides previous stock-library state)

User requested reproduction on this device. A locally derived exact-B03 patch
now replaces /lib/libatext.so: only byte 0x5a33 d0 -> d1 (BEQ -> BNE), matching
the forum IMEI auth branch. Current MD5 27a21baf57d9ec55e21f62a44e9d8468,
SHA256 6a5b233b701bcd65d84ec4b0f99126b921fa98ea9f52903c5cba3412ca64f636.
15-digit/decimal validation, packing and NV writer unchanged. No MAC/ZAUTH/ADB
bypass; production server/adbd still stock. This is a rootfs file replacement,
not raw flashing; offline 0.9 images/packages remain older and do not contain it.

Original library: /mnt/userdata/mf79u/libatext.vendor.b03.so, mode 0600, verified
stock MD5 d1ba655c5bc0ae566ea2a7b38fa0fbcd. Rootfs/NV saved backup size/SHA256
checks passed. Installer: firmware/mf79u/install-imei-patch.py --install/--restore
(default prepares only). Reboot required to load the replacement; never restart
zte_mifi arbitrarily. Installer restore allows unavailable/unready IMS for recovery.

Live test AT+MODIMEI=0: unauthorized before activation, CME ERROR 8001 after
software reboot. Invalid length rejects before NV write. READIMEI values compared
privately in RAM were equal; NO valid identity write attempted. No identity value
or hash recorded. Do not claim actual NV writing is verified or invent a new IMEI.
Evidence: firmware/mf79u/build/imei-patch-live.json. Actual patch persisted across
reboot; rootfs ro, native ready (hostRelayRequired=false), IMS ready, SIP SERVER
running, no active call, WebUI HTTP 200. No new call/client-registration test.

First rename unlinked old mapped inode and JFFS2 remount-ro returned EBUSY.
Controlled reboot resolved it; installer now keeps /lib/libatext.so.mf79u-previous
hard link on later replacement to avoid unlinking a mapped inode. Never delete
that retention link while its inode is mapped; installer refuses another change
if it already exists. Actual guarded rollback has not been live-tested yet.
Full context and rollback commands: firmware/mf79u/IMEI.md.
The full downloaded forum image remains unapplied; the IMEI-only patch above
was applied and live-tested separately.

## Authorized IMEI NV write (2026-10-08, supersedes prior untested-write state)

User subsequently supplied a specific new IMEI and explicitly authorized it.
firmware/mf79u/set-imei.py --write --reboot validated decimal length/check digit,
verified no active call plus exact library/backups, sent one valid MODIMEI write,
received OK and matched immediate READIMEI to the requested value. Software
reboot verified persistence: READIMEI and cellular CGSN both match. Native IMS
ready and SIP SERVER running after reboot (~93 s observed incl. checks).
No test call/SMS sent. Report: firmware/mf79u/build/imei-write-live.json contains
booleans only, no old/new IMEI or identity hashes. Actual NV writing is now proven.

Original identity saved privately before writing in
outputs/private/imei-original-123456789ABCDEF.json, file 0600/directory 0700.
Do not print/attach/commit that file or preserve its content in common context.
Do not overwrite the original backup during subsequent writes. User-authorized
identity recovery command: python3 firmware/mf79u/set-imei.py --restore-original
--reboot (requires current IMEI patch). Restore identity BEFORE restoring stock
library: library rollback alone does not change NV identity. Recovery itself has
not been live-tested and should not be performed without user instruction.

## Native SIP SMS: первый этап (2026-10-08)

Исторический результат до PBX integration и GSM fallback ниже. Ограничения
первого этапа (TRUNK не проверен, запуск после IMS) впоследствии сняты.

SIP MESSAGE support is installed in the existing ARM SIP gateway and native Go
control process; no Mac relay/new external daemon. src/sip-sms.h handles
authenticated SERVER messages or existing trusted TRUNK peers; text/plain and
CPIM text/plain only. Typing/IMDN is ignored, encrypted/attachment bodies get
415. Incoming modem+SIM inbox polling is every 5 s; From is the actual sender,
messages are not marked read/deleted. SERVER routes to the sole registered
client. TRUNK SMS routing through MikoPBX is not live-tested. DISABLED stops SIP
SMS processing; SIP still follows existing IMS startup, so this does not prove
SMS-only operation with IMS unavailable. PCM/operator codecs are unchanged.

control/sms_sip.go owns root-only sms-sip.sock and atomic sms-sip-state.json in
userdata (0600). Uses existing B03 SHA256 administrator verifier locally in RAM,
not a newly stored credential. Queue max 64 jobs, ack history max 300 IDs.
SIP 202 means durably queued; logical Call-ID/CSeq dedupe prevents normal
retransmission duplicates. Interrupted/failed/timeout sends become uncertain
and are NEVER automatically resent. Incoming ack is persisted after SIP 2xx.
Queued bodies/subscriber data are private; do not print this state file.

Live SERVER test: autonomous reboot restored IMS/SIP (~57 s initial install),
Linphone registered, four existing incoming SMS were delivered/acknowledged.
Exactly one authorized real SMS was sent from the user's open Linphone contact;
the user confirmed receipt on their phone. Despite receipt, B03 returned
sms_cmd_status_result=2 and stored outgoing tag=3. Stock JS treats 2 as failure,
3 as completion; the discrepancy is not resolved. Never treat all 2 results as
success. Local uncertainty notice originally impersonated the recipient;
the installed correction uses separate sender MF79U and explicitly refers to
modem API confirmation, not recipient delivery. Do not resend that test.

Go/race and isolated ARM SMS/registrar fixtures passed; no calls in these tests.
Native binaries are current internal userdata; old SD/runtime and 0.9 full-image
archives do not yet include SMS MESSAGE. Docs: firmware/mf79u/SMS-SIP.md;
report: build/sms-sip-verification.json. Installer --install/--restore is guarded
against changed binaries and active calls. Original own binaries (no settings)
are checksummed in build/pre-sms-sip-20261008; rollback not live-tested.

After the user's Mac reboot, modem uptime confirmed a fresh device boot;
current installed binary checksums match the corrected local builds. Native
state ready, hostRelayRequired=false, IMS ready, SIP SERVER running and Linphone
registered. SMS vendorReady=true, four inbox items, zero pending/queued; five
ack IDs include the earlier status notice. Two retained jobs (one sent, one
uncertain) were observed; no additional SMS was sent by the agent on resume.
Do not interpret job totals as the number of agent-issued test messages.
New isolated ARM fixture also verifies MF79U service notice From/ack. Go race
and existing registrar regression passed. Measured RSS: native 284 KiB, SIP
2284 KiB, control 5548 KiB; userdata free approximately 9.4 MiB.

## System UI / SSH and PBX completion (2026-10-08)

Current on-device **Control is 0.10**; SIP gateway still reports 0.8 and native
IMS remains autonomous. System is the sixth top-level tab. SIP account is
visible only in SERVER, hidden in TRUNK/DISABLED; codecs remain visible.
User declared the PBX call/history/SMS task complete. Do not create more calls
or SMS simply to recheck it.

PBX persistent custom dialplan/PJSIP fragments now route SIP MESSAGE from the
trunk to extension 201, and authenticated numeric messages from 201 to the
trunk. CallerIdSource is pai; Privacy is respected. configure-sip-messages.py
uses API v3 with protected pre-change backup and guarded --apply/--restore.
configure-call-routing.py changes the existing outgoing route 22 in place to
numeric external destinations, retaining internal-extension precedence and
preserving actual destination numbers. Linphone PBX profile domain excludes
:port; registrar/proxy contains the port. The previous malformed profile is
disabled and retained for history. User confirmed outgoing ringing and prior
working incoming call. Rejected ringing is correctly NOANSWER / zero billsec;
multiple PBX legs can share one linkedid. Historical missing identities were
not invented. Mac uplink at that PBX test was 192.168.1.28; private return routes and
SIP trusted peers include it. Recheck addresses before future network work.

System: control/system.go, web/system.js, SYSTEM.md. Admin cookie required,
Origin+CSRF for mutations; SMS Basic auth does not grant System access.
Includes detailed device/software/hardware info, bounded/redacted native/SSH/
kernel logs, admin-password change, guarded IMEI write/readback and reboot.
Admin password mutation uses B03 SHA256 CHANGE_PASSWORD and invalidates all
own sessions after accepted changes. Current admin password was NOT changed
for UI testing. New valid IMEI writes were not repeated during this task;
the narrow helper read is live-proven and previous authorized NV write evidence
remains applicable. Reports contain no identities, passwords or message bodies.

SSH uses official Dropbear 2026.94, BusyBox 1.37.0, checksum-verified sources,
ARMv7 soft-float static builds. Extended BusyBox has 403 applets. B03-compatible
build disables getrandom and SHA hardware instructions. Existing admin UID-0
account uses our private SHA512-crypt password file and tools/ssh-shell;
vendor passwd/shadow and factory BusyBox are unchanged. TCP22 listens only
on configured LAN/loopback, cellular rejected and IPv6 blocked by own rules.
SSH enable/password survive boot; disable closes owned descendants/sessions.
Password must be 12-128 printable ASCII characters. Empty matching fields
preserve a configured password. Temporary test password was removed. After the SSH Save correction, the user
enabled SSH and set their own password through WebUI; SSH was **running** at that verification (fresh audit currently has no modem access).
Do not overwrite/remove this user configuration or run the temporary-password
live test over it. Stable private host key is preserved.

Live test-system-live.py --reboot proved correct/wrong password behavior,
403 applets, extended shell arithmetic, real normal reboot, autonomous SSH/IMS
startup and persistent host key, and disabling active SSH sessions. Temporary
credentials were generated in RAM and removed. Do not run this temporary
credential test over an existing enabled/configured SSH account. Userdata had
approximately 6.3 MiB free at that System installation; inspect before large updates.
Normal boot needs no ADB/Mac. Manual hot-install UI startup needs a foreground
ADB shell; old adbd drops remote background launches.

Installer install-system.py saves/checksums the prior control binary in
build/pre-system-20261008, uses whitelisted HTTP transfer + atomic rename,
and skips tools whose MD5 already matches. Native IMS/SIP stays running.
control-internal-preferred prevents the old SD copy from overriding Control0.10.
The earlier NAND0.9 archive and SD0.8 runtime DO NOT include System or SIP SMS.

Resolved two UI regressions: a malformed selector initially broke app.js/login;
node --check now runs before the Go build. SSH Save errors initially appeared
far above the button. They now appear beside Save, with client-side matching/
length validation and a busy button state. test-system-ui.js fixture and live
Save of the disabled state passed; no permanent SSH password was chosen.
Management idle timeout is 30 min: GET now renews BOTH cookie Max-Age and RAM
expiry. Previously the browser cookie expired 30 min after initial login even
with polling. Hot UI daemon installations also intentionally lose RAM sessions;
do not blame the vendor session for those logouts. Management and short vendor
sessions remain separate, with vendor auto-login+one retry. No keys/cookies are
persisted to bypass management authentication.

Evidence: build/system-install-verification.json, system-live-verification.json,
system-ui-verification.json; management-session-live.json confirms 187.6 seconds / 24 successful polling
cycles, cookie renewal, unchanged control PID, and no UI logout observed. This
limited duration does not prove indefinite uptime. Go fixtures passed including cookie
renewal/expired-session rejection and admin-password invalidation. Desktop tab
and role visibility checks passed with no horizontal overflow. The requested
390px CUA viewport override did not change the actual IAB viewport to 390px;
do not claim a verified mobile breakpoint from that run. System overview screenshot
contains no password/IMEI. Current binary/PIDs must be rechecked next turn.

## Yellow network LED for registered / no IMS (2026-10-08)

Installed LED daemon shows yellow (red+green, RGB mask=3) when cellular
registration exists but owned live native controller imsReady=false. Native
status PID/executable is verified; missing status or exited/foreign PID fails
closed for IMS. There is no separate status-age timeout. Idle with IMS remains blue; no cellular registration remains red;
incoming red+blue and active/outgoing green keep their priority. Wi-Fi policy
is unchanged. Color policy and actual ARM selftests passed; physical status
confirmed registered=true, ims_registered=false, color_mask=hardware_mask=3,
demo=false on the current roaming SIM. Visual perceived color is not separately
user-confirmed. Only LED daemon restarted via one-shot double-fork helper,
parent init; helper removed from RAM. Native/SIP PIDs and settings unchanged.
Report build/yellow-led-live.json; original LED binary
build/pre-yellow-led-20261008/mf79u-net-led. NAND/SD archives remain unchanged.

## GSM / IMS-independent incoming SMS fallback (2026-10-08)

Latest userdata native/controller and Control implement SMS fallback. Native
starts the existing SIP process before IMS; SERVER registration and TRUNK
MESSAGE work without IMS READY. GSM/3G uses the preserved vendor WMS/storage
service, not an IMS bearer or Mac relay. Native status state=sms_only, smsOnly=true
and raw EPS/CS registration states distinguish SMS fallback from working voice.
WebUI says Voice unavailable / SMS only rather than Waiting for calls. Native
API hostRelayRequired stays false for an owned live SMS fallback/SIP process.

Private IMS starts only after EPS home/roaming registration (stat 1/5). On GSM
there is no repeated IMS setup or radio restart. IMS attempt timeout is 300 s,
LTE retry 60 s, radio polling 15 s; failed/timed-out/crashed IMS and LTE->GSM
cleanup preserve SIP PID/client binding and the Go SMS worker. Cleanup ends an
active SIP voice call when IMS fails. Queue/process ownership guards remain.
SIP voice INVITE without validated IMS/frontend readiness returns 503, no DIAL.
GSM circuit-switched voice audio is NOT implemented; PCM is unchanged (16 kHz,
320 mono PCM16LE samples per 20 ms). DISABLED still closes SIP and prevents SIP
SMS; cellular receipt/storage and WebUI/REST remain vendor-owned.

Production native/control installed atomically with backups; real reboot proved
SMS/SIP boot from init before network registration. Final controller was then
updated for active-call cleanup and relaunched by the existing boot supervisor;
control and settings were preserved. Current saved role is TRUNK (not SERVER).
Intended roaming SIM: epic / EDGE, simcard_roam=International, CREG stat=5,
CEREG stat=2, IMS absent. First candidate retained native/SIP PIDs across >300 s
in GSM. Final binary checksums and aggregate SMS diagnostics are in
build/gsm-sms-fallback-live.json. Original binaries:
build/pre-gsm-sms-fallback-20261008; first candidate separately preserved.
No settings, SIM identities, credentials, outgoing SMS/calls or raw flash changed.

Physical aggregate evidence: incoming count 5->6, delivered-ack count 5->7,
pending incoming 1->0. Final counts: incoming=7, delivered=8, pendingIncoming=0,
queued outgoing=0, vendorReady=true with IMS absent. Acknowledgements include
retained messages, so they are not a count of new cellular arrivals.
This establishes inbox/SIP-PBX acknowledgement, not Linphone display. PBX trunk
contact is Avail; extension201 contacts were Unavail. User-identified test SMS
or end-client display confirmation remains unverified. Source messages stay
in modem/SIM storage and are not read/deleted by forwarding.

Tests: real ARM SIP SMS fixture without READY (Unicode, acknowledgements,
authentication/dedupe, numeric INVITE503/no DIAL), registrar regressions, Go/race.
Container-only native-fallback-fixture.c/test-native-fallback.py cover search,
GSM roaming, IMS timeout/crash/recovery, active-call ending and LTE->GSM with
unchanged SIP PID. Never run those fake-CP fixtures on the physical modem.
verify-sms-fallback.py is read-only and uses only opcode4 aggregate diagnostics.
Full NAND0.9 and SD0.8 archives remain unchanged and lack these updates.

## Roaming registration / SYSINFO correction (2026-10-08)

Installed native controller accepts B03's five-field SYSINFO only when system
mode is zero (no radio service). It reports waiting_for_radio_service, still
forwards actual CEREG/CIREP, and skips MODE until a real seven-field response
arrives; no subsystem is invented. Other truncated/malformed responses remain
errors. ARM CP/selftests passed with unchanged IPC queue inventory. The later
SMS fallback update limits the 300-second timeout to IMS attempts on registered
EPS; GSM SMS-only no longer restarts the controller on this timeout.

After the user's replacement with the intended roaming SIM, fresh boot proved
the updated controller waited on five-field SYSINFO without sysinfo_field_missing;
the same PID then observed service. Latest snapshot: epic / EDGE, simcard_roam
International, CREG stat=5, CEREG stat=2, IMS not ready. This proves roaming
cellular registration, not LTE/VoLTE or a working call. No calls/SMS issued.

Control WebUI roaming display previously incorrectly tested only simcard_roam=1.
B03 vendor service uses Home / Internal / International (confirmed in stock
service.js and zte_wan_nwinfor). Updated installed UI displays international or
domestic roaming, Home only for a known home value, unknown for missing/unknown
values, and Not registered for no/limited service or unready SIM. Legacy 0/1
supported. test-roaming-ui.js now runs in build-control.sh; Go tests passed.
Only control was restarted; native PID and settings were preserved. Browser
visual verification was not performed. Reports: build/roaming-sysinfo-live.json,
build/roaming-ui-live.json. Previous binaries: build/pre-roaming-sysinfo-20261008.
Full NAND0.9 and SD0.8 archives remain unchanged and do not contain this fix.

## Preserve factory profile / reset requirement (2026-10-08)

User wants installation to preserve original administrator password, Wi-Fi,
network and IMEI, allow later UI changes, and Reset to restore defaults while
keeping our firmware. Read-only audit and design: FACTORY-RESET.md;
build/factory-reset-audit.json. No reset/device mutation was performed.

This is NOT implemented. Current userdata still mixes code and settings; deleting
settings.json uses lab-oriented compiled defaults/current NV AP settings. Generic
stock default files do not prove unit-specific original credentials. Original
IMEI has a private Mac backup; current modified identity is not a valid factory
baseline. Stock WebUI sends RESTORE_FACTORY_SETTINGS; stock debug script handles
restore markers and deletes SMS/PBM databases, but the complete erase path and
physical button have not been tested. Do not promise our userdata installation
survives stock Reset, or recommend pressing Reset as a safe recovery yet.

Plan: immutable complete code in rootfs; protected per-device original profile
outside the reset-cleared tree (location pending vendor reset/upgrade audit);
separate mutable settings; one verified reset controller for UI/button, original
identity guarded write/readback, credential/AP/LAN restoration, power-loss journal,
SIP/SSH defaults disabled and mobile data blocked. Never embed personal factory
secrets in the shared image, overwrite original with current changed values,
restore entire NV/calibration storage, or replay uncertain SMS. Full image0.9 is
unflashed and predates current SMS/System tools. Packaging/reset validation is
still required before calling this a factory-reset-capable firmware release.

## Documentation audit (2026-10-08)

All maintained project Markdown documents reviewed; STATUS.md added as shared
state/evidence/index. Early CODECS/VOICE/audio-quality RAM limits are labelled
historical; Mac launcher is recovery-only. PBX README now includes actual
numeric route22, PAI/Privacy/CDR, extension201/SIP SMS and Linphone URI correction.
WEBUI/SYSTEM/AUTONOMOUS/NETWORK/SD/IMEI/SMS docs distinguish current features,
old packaged artifacts, bounded tests, rollback not tested, and reset not built.
No firmware/configuration/credentials/calls/SMS changed during audit. Modem live
checks unavailable; PBX read-only checks succeeded. build/documentation-audit.json
contains document coverage, link validation and current-access boundaries.

## WebUI latency / B03 network compatibility fix (2026-10-08)

## Current runtime cleanup (2026-10-08)

The experimental VPN backend, API, seventh tab, stored node identity, SD binary,
Mac test proxy, build scripts, patches, upstream clones and runtime reports have
been removed at the user's request. WebUI has six tabs: Status / SIP / Messages /
Wi-Fi / Network / System. The network compatibility fallback, USB bridge recovery,
precompressed assets, ETag revalidation and parallel settings loads are retained.
API/credentials remain no-store. SD is remounted read-only; ordinary cellular
data remains blocked. Native/SIP PIDs and saved settings are preserved.

Permanent native-ring-only remains enabled: do not dial or answer SIM calls.
GSM voice backend remains unfinished; user reported50EUR for an incoming call.
Do not remove the guard or use automatic-answer helpers. See GSM-VOICE.md.
Read-only CS probe source and audit-cs-voice.py are retained.

Current install: build/control-update-install.json. Removal verification and
memory snapshot: build/runtime-cleanup-verification.json. Older full NAND0.9 and
SD0.8 archives were not rebuilt or flashed.

Final cleanup snapshot: RAM 55924KiB total, 45620KiB occupied including 11520KiB file cache, 10304KiB completely free; zram swap 7128/12284KiB used. Local public HTTP responses7–18ms. Six tabs and matching installed checksum verified; native/SIP PIDs preserved, ringOnly=true.

## GSM CS ring-only signaling (2026-10-08, continuation)

Exact B03 CC task callback BF30053D is a payload-freeing stub. Own bounded
module chains it, decodes AA45 model type as body[1] >>2 and sends only
CALL CONFIRMED/ALERTING/RELEASE/RELEASE COMPLETE through the verified CC→ASC
OSS route. Real SETUP, successful ringback confirmed by the user, network
DISCONNECT and completed clearing: build/cs-ring-incoming-live.json.
No CONNECT, answer, dial, Caller ID, CS audio or SIP forwarding implemented.
Do not interpret the first incorrect header probe's wire-mask types as decoded.

Kernel modules are RAM-only and pinned until reboot. Each bounded callback
restores its own slot by compare-and-swap before cleanup; do not rmmod pinned
text or overwrite somebody else's callback. Our read-only sysfs ABI1 is
/sys/mf79u_cs/status, mode0400, removed on expiry. Exact kernel attribute layout
is checked against live show/store instructions; no guessed vendor structures.
Build/arm scripts support distinct header/ring instances2..9 after prior expiry.

Updated userdata native binary publishes csSignalingReady/csCallState and
csAudioReady=false, sends CS state to LED slot8 only in CS-only/ring-only mode.
SIP READY/CONNECTED/INCOMING remains gated on the existing IMS/audio path.
Source and fixtures: firmware/mf79u/src/cs-status.h, cs-kernel-status.h,
cs-ring-state.h; sh firmware/mf79u/test-native-lifecycle.sh. CS lifecycle/LED
socket fixtures, physical ARM parser, kernel→native readiness/expiry passed.
The last check intentionally made no further incoming calls.
Current native install: build/cs-status-controller-install.json; backup
build/pre-cs-status-20261008/mf79u-native-gateway. Original radio/flags restoration
must wait for CS callback expiry; restore-cs-test.py now enforces that guard.
Reports are under firmware/mf79u/build. NAND/SD archives remain unchanged.
Final restoration verified: build/cs-ring-final-restore.json, radio27/flags0/0,
LTE/IMS ready, csOnly=false, ringOnly=true, native2793/SIP2794, same boot/settings.
All five bounded observer callbacks restored; module text remains pinned in RAM.
Kernel→native idle/readiness/expiry proof: build/cs-status-lifecycle-live.json.

### Full voice API diagnostic (2026-10-10)

Real reference Open/Enable/path/unmute parameters now come from the hash-bound
voice API emulator. Full idle receipt `cs-full-voice-open-live.json` accepted all
11 DSP commands but RX15670 words were zero; failed0 and complete runtime/local
configuration restoration verified. Explicit connected instance32 requires this
matching idle receipt and one authorized answer, with DSP-only tone control then
ARM RX. `test-cs-full-voice-call.py` owns preparation/collection/IMS restoration.
MT32 completed: the user heard a tone then buzzing; ARM TX23102/RX23106 words
were zero, failed0. All checks in cs-mt32-full-voice-open-restore.json passed;
LTE/IMS/profile27/flags0/0/guards, callbacks/MM and local header/config restored.
See DSP-ABI.md and STATUS.md; physical CS/SIP PCM and production fallback
remain unimplemented.

## CS audio continuation: MO16 shared-RAM metadata (2026-10-10)

Seven exact-B03 pointer-bounded SRAM metadata windows passed idle preflight
and a connected MO16 DSP-tone call. The user heard all three tones; none of
the windows had period8/16/32 hits. Index6 changed554 times, also before answer;
this is not PCM ownership evidence. No SRAM sample/hash or destination saved.
The sampler was removed; exact route audit and independent verification restored
profile27, voice flags0/0, LTE/IMS, guards and same boot/native1620/SIP1680.
Reports: build/cs-pcm-metadata-idle-live.json and
build/cs-mo16-pcm-metadata-tone-{test,live,restore}.json.
Inactive connect32 and mo16 remain pinned until reboot; do not reuse them.
`restore-cs-test.py` accepts a current boot/module-bound quiescent route audit
when an older MT expiry log rotated; offline regression rejects stale/unsafe
audits before policy writes. Read-only `test-cs-reattach.py` ADB shell uses
DEVNULL so destination input cannot reach preflight commands. Production
CS media and voice fallback still not installed; do not report CS audio ready.


## CS continuation: MO18 public PCM and remote clearing (2026-10-10)

Outgoing-only source selection is now independently checked by builder/armer.
MO17 loaded a misnamed MT idle callback and was cancelled before destination
submission; stop restored callback and complete independent runtime recovery
passed. Do not reuse its pinned module. Corrected MO18 connected; known DSP
tone remained audible, but public PCM ARM TX/RX11789 contained no nonzero RX.
User says tone stops around10s while the phone call does not hang up. Local
DISCONNECT→RELEASE→RELEASE COMPLETE/MM refs0 is verified; this is not proof
of remote clearing (TS24.008 §5.4.3.2). Investigate remote hangup separately.
`build/cs-mo18-public-pcm-restore.json` verified all original policy, callbacks,
MM, guards and IMS on boot1c2740a7/native1620/SIP1680. Inactive connect32,
mo16/mo17/mo18 pinned. Production CS↔SIP audio/fallback remains uninstalled.

MO19 isolated DSP-tone/ASC test reproduced the remote clearing failure:
user manually hung up at60s. ASC saw DISCONNECT Cause16/coding0, RELEASE
Cause126/coding3 then RELEASE COMPLETE; local MM cleared, remote did not.
All independent restore checks passed on the same boot/PIDs. Inactive mo19
and ASC1 are pinned too. Do not repeat the unchanged call; audit B03 raw
serialization/sequence ownership before another test.

2026-10-10: User reprioritized audio before hangup. MO20 signaling-only remote
call ended automatically at about60s, not the10s target. Full restoration
verified on the same boot/native/SIP; mo20/ASC2 inactive pinned. Offline N(SD)
owner is BF29BE71, applied by BF29BEA8 before AAD4; raw diagnostic sender bypasses
it. No sequence code change deployed. Coding3 is standard GSM PLMN (the earlier
doc interpretation was wrong); Cause126 maps to unspecified interworking127.
Continue ARM↔DSP PCM audio investigation first.

## Последняя LED легенда (2026-10-11)

Красный1 — нет регистрации оператора, синий4 — готов VoLTE, жёлтый3 —
GSM / зарегистрированная сеть без готового IMS, фиолетовый5 — готов VoWiFi.
Просьба сделать GSM бирюзовым отменена следующей точной легендой пользователя.
Все активные вызовы остаются зелёными2. Выбранный VoWiFi Only не является
доказательством регистрации: учитывать фактические imsReady/imsAccess.
См. firmware/mf79u/NETWORK-LED.md и build/led-final-legend-20261011.json.

## VoWiFi Only: красный → фиолетовый (2026-10-11)

В VoWiFi Only регистрация SIM для cellular SMS не включает жёлтый idle.
До фактической готовности IMS через Wi-Fi индикатор красный1, после —
фиолетовый5; активный вызов по прежнему правилу зелёный2. Демон читает
сохранённый voice_mode до запуска native, чтобы загрузка не показывала жёлтый.
При запуске аппаратно устанавливается красный до потенциально медленных CP
запросов. В других режимах GSM остаётся жёлтым, VoLTE — синим.
Сборка и ARM selftest проверяют переходы, независимость от cellular SMS и
приоритет активных вызовов. Физическая reboot-проверка:
firmware/mf79u/build/led-vowifi-only-boot-20261011.json (путь от корня проекта).

## Boot UI / RAM trimming (2026-10-11)

Старый stock index.html заменён boot-wait.html на работающем userdata overlay;
wrapper раньше ставит LAN80→18080. Loopback goform сохранён. Будущий rootfs
packer уже кладёт настоящий custom index/app/style в stock web directory.
B03 daemon run/sync для zte_topsw_data_stat, zte_topsw_pbm и zte_topsw_ussd
отключены: custom UI их не использует. Остальные radio/CP/SIM/SMS/WLAN/router/
NTP/USB/watchdog и adapters оставлены. Измеренный целевой PSS228KiB + swap620KiB;
не суммировать shared RSS и не заявлять всю разницу MemFree как экономию.
Проверенные rollback backups в userdata; install-native.py поддерживает новую
политику и stock index backup. См. firmware/mf79u/BOOT-MEMORY.md.

## VoWiFi recurring red / renewal (2026-10-11)

Current details: firmware/mf79u/VOWIFI.md and STATUS.md. AUTH_LIFETIME1800s
was renewed at360s due default overtime1440s. Operator rejected overlapping
and retained-VIP reauthentication. SWu-specific fresh VIP request passed real
EAP-AKA/IKE/CHILD renewal; full IMS voice recovery remains unproven. Installed
sequential renewal and generation-aware recovery, margin120s (renewal1680s).
Fast registration candidate is BUILT, NOT installed: REGISTER5xx immediate
P-CSCF failover, Wi-Fi final setup wait1s, retry5/10/20/40/60s. USB/ADB and HTTP
became unavailable during validation; do not claim current hardware readiness
or blame an unobserved reboot. No calls/SMS sent. Recheck USB and boot ID first.

## Recovery continuation (2026-10-11)

Current physical USB PID1405 user mode, USB LAN192.168.0.1 works; stock login
works but custom Control18080 and ADB are absent. Do not claim installed speed
changes or current purple/IMS readiness. SET_DEVICE_MODE failed. USB storage
interface claim failed ACCESS(-3); no SCSI command sent. Volumes remounted.
Manual recover-usb-at.py needs user-terminal sudo; privileged path unverified.
See VOWIFI.md / STATUS.md and usb-normal-mode-recovery-20261011.json.

## USB recovery update (2026-10-11)

ADB0581 restored after factory AT recovery/reboot. Userdata is mounted but
our runtime/settings directory is absent; raw RAM-only scan found no old
names. Recovery helper disabled pending stock reset-path audit. Do not run
OPENDL/factory reboot as a data-preserving procedure. See VOWIFI.md and
usb-normal-mode-recovery-20261011.json. Restoration remains in progress.

## Runtime restored after USB recovery (2026-10-11)

Control/native/SIP/VoWiFi artifacts and SERVER/VOWIFI settings recreated.
Lipetsk-2G connected192.168.50.96/24; epic-wifi WPA handshake fails.
Wi-Fi internet ping passes, ePDG sends have no replies, IMS NONE/not ready
and actual LED red1. Faster candidate installed but renewal/purple not verified.
Prior SIP secret unavailable; new private server secret is in modem settings,
Linphone registration pending. No calls/SMS. See current STATUS/VOWIFI receipts.

## USB VoWiFi source (2026-10-11)

UI/API/native USB source is built and installed; gateway192.168.0.169 and
USB/DNS routes applied and confirmed. Host NAT enabled by user via the temporary
share-usb-internet-macos.py helper. USB IMS/internet still unverified: final UI
transfer stalled ADB/HTTP/AT; USB ping remains. Requested physical reconnect.
Suspected RAM pressure is unconfirmed. Reclaim /dev/mf79u/usb-* public staging
BEFORE another large transfer. Never use disabled factory recovery helper.
See current STATUS.md/VOWIFI.md and USB receipts.

## USB/Wi-Fi validation and connection fixes (2026-10-11)

USB VoWiFi with Wi-Fi disabled and Wi-Fi VoWiFi on scanned TP-Link_8C63
(case-sensitive) physically registered; purple hardware mask5. Shared SIP parser
now accepts vowifi_uplink; old parser caused fresh-boot sip_start_failed.
Installation is sequential/compressed staging only, directly expanded to flash;
public rollback binaries are on the host. Final boot Wi-Fi client retry and USB
receipt: CONNECTIVITY-20261011.md and vowifi-usb-reboot-live-20261011.json.
No call/audio proof, calls/SMS, reset or NAND flash in these tests.

## Final USB/Wi-Fi verification near AP (2026-10-11)

Final boot f5a748bd-24e6-42e1-8d43-fd5571b250b3: native1706/SIP1836;
USB VoWiFi only via192.168.0.169, actual purple LED5. Wi-Fi TP-Link_8C63
has192.168.1.44/24. Source WIFI then USB registered in29.7s/22.5s without
native/SIP restart. USB passed120s with Wi-Fi disconnected; Wi-Fi passed60s
near the AP. Final reboot reached USB IMS/SIP at native29s/34s, HTTP49.3s;
Wi-Fi recovered via the boot retry and the full lease/LED gate ended112s.
A subsequent strict60s USB + Wi-Fi test passed. Current UI also shows SIP
Client registered. Call audio and full IKE reauthentication were not tested.
A first USB-return LED transition sample was red, followed by purple; its
failed strict receipt is retained. No DHCP netlink workaround was installed:
original DHCP retained association in the stronger-signal comparison.
Current limits/receipts: firmware/mf79u/CONNECTIVITY-20261011.md.
Read-only repeatable test: firmware/mf79u/verify-vowifi-uplink.py.

## Automatic ADB normal boot (2026-10-11)

Rootfs rc now runs /usr/zte/mf79u/adb-boot before stock adbd and zte_usb_cfg.
Only user/empty NV_RO usb_modetype can become debug; already-debug has no
write/commit. Factory/AMT profiles and special boot paths are preserved.
No persistent watcher or raw image flash. Helper4940bytes, MD5
25e00e0814c791769395564860508471; rc383f796a590fda5d2256b517a2acd6f7.
Normal software reboot7c8a7e60…: ADB28.5s, oneadbd741/PPid1, USB0581
ECM+ADB, boot helper unchanged-debug result, read-only rootfs. USB VoWiFi/SIP
and purple5 restored. Corrected postboot verifier passed; initial observer
failed only daemon checks due to unavailable stock pidof. That failed receipt
is retained. Wi-Fi client was disconnected after this boot; USB readiness held.
Final USB-only30s check passed all3samples; Wi-Fi stayed disconnected despite
the AP at-48dBm and repeat selection. See adb-boot-usb-stability-20261011.json.
Do not claim a cold power cycle or physical NV user-to-debug write test.
See firmware/mf79u/ADB.md and adb-boot-*-20261011.json receipts.
prepare.py/install-control.py now share adb_boot.py; historical image archives
remain stale. Stock rc contains non-UTF8 comments: preserve bytes, not UTF8 text.

## User reboot: full automatic reconnection verified (2026-10-11)

User reports everything reconnected after their reboot. Current read-only
verification: boot8704dd24-6e4d-41c3-8ef2-c12c1a98b52f, adbd740/PPid1,
successful boot helper, ECM+ADB/USB0581, read-only rootfs and exact rc/helper.
Wi-Fi TP-Link_8C63 COMPLETED/DHCP192.168.1.44/24, USB VoWiFi only ready,
native1573/SIP1702, actual purple5, HTTP accessible.30s/all3samples passed,
including Wi-Fi lease. No setting/process changes, calls or SMS during check.
Reboot mechanism/time not observed; prior failed Wi-Fi boot remains historical.
Receipts: adb-boot-user-reboot-20261011.json and
adb-boot-user-reboot-wifi-usb-20261011.json; current ADB/STATUS/WIFI docs updated.

## Mobile tab / button layout (2026-10-11)

Current tabs: Status / Mobile / SIP / Messages / Wi-Fi / Network / System.
Mobile owns Voice registration, LTE data / mobile internet and VoWiFi internet
source, in that order in three bordered blocks. USB gateway/DNS appear below the
source selector. Status retains monitoring and Refresh status. All buttons use
header blue#175a9b and are at least44px high; normal buttons88px minimum width,
codec arrows44px. Existing shared Save, network confirmation and call lock stay.

Control-only userdata install passed; MD5a149bafae93971baecdc07b1bd949725/PID487.
Same boot77358efe… and native1697/SIP1749, ready USB VoWiFi/SIP client; settings
and gateway.ini hashes preserved. JS/Go checks and seven-tab browser fixtures
at1280/390px passed. Installed public assets match source. Browser screenshots
use non-secret fixture APIs; no live configuration writes, call/SMS, reboot or
raw flash. Rootfs/SD archives remain stale. See firmware/mf79u/WEBUI.md,
STATUS.md and build/mobile-tabs-{ui-fixture,live-install}-20261011.json.

## SMSoIP verification boundary (2026-10-11)

Boot77358efe… ready IMS via USB VoWiFi: metadata observed +g.3gpp.smsip in
REGISTER (SMS_IMS_CAPABILITY advertised=1). This is advertised capability,
not proof that a specific SMS traversed IMS. UI/REST/LAN SIP SMS worker submits
through B03 SEND_SMS and reads vendor storage; no per-message bearer telemetry
or SMS-only IMS forcing. VOWIFI-only restricts voice and leaves cellular SMS
enabled. No IMS MESSAGE/delivery/report indications in the retained bounded
metadata during read-only audit; absence does not prove unsupported SMSoIP.
No SMS, radio/settings change or content capture. See SMS-SIP.md/STATUS.md and
build/smsip-readonly-audit-20261011.json; both directions' SMS bearer unverified.

## Shared framed WebUI blocks / scoped Save (2026-10-11)

Every content panel now shares the Mobile thin border,3px corners and20px
(16px mobile) padding; Status metrics and the login form also have frames.
Login grid shrinks at320px. Shared Save is only visible on Mobile/SIP/Wi-Fi/
Network; Status is read-only with Refresh, Messages/System have own actions.
Drafts survive Status/refresh. Source layout and browser fixtures passed all
seven tabs at1280/390/320px; final deployed login passed those widths too.

Final Control PID956, MD5b24e672bfc4aa4ecd4756c800ab122ae; all five public assets match source.
Same boot77358efe…, native1697/SIP1749, ready USB VoWiFi/SIP client; settings
and gateway.ini hashes preserved. No call/SMS, modem reboot or raw flash.
Receipts: firmware/mf79u/build/framed-tabs-{ui-fixture,live-install}-20261011.json.
Current docs: firmware/mf79u/WEBUI.md and STATUS.md. Image archives remain stale.

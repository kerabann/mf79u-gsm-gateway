> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# История проверки качества речи

## Current CS quality investigation (2026-10-10)

The persistent incoming CS→SIP test had tone, speech echo and prompt clearing,
but the user reported a muffled timbre. Its SIP codec was Opus; the checked
CS hardware endpoint is 8000Hz/160samples, while external PCM remains
16000Hz/320samples. Increasing the external sample rate alone does not restore
frequencies absent from that hardware stream. The current GSM bearer advertises
AMR-FR/AMR-HR/EFR/FR/HR; the actual selected cellular codec/rate has not yet been
measured, so it must not be labelled AMR-WB or blamed on a particular AMR rate.

The existing 31-tap 8↔16k FIR passes its real C selftest: 3kHz RMS7086.5/7086.9
for a 10000-amplitude input and rejected 6kHz alias RMS2.0. Coefficient response
is within0.03dB at300–3000Hz and −0.465dB at3400Hz. This excludes severe loss of
upper speech frequencies in that resampler alone, but does not characterize
the DSP voice filters, network transcoding or the complete echo path.
`build/cs-audio-quality-check.json` records the calculation and checked installed
IMS audio hashes. In the40-second postboot CS/PCMU comparison the user confirmed
the same muffled timbre and automatic clearing. Changing the SIP codec alone
therefore did not solve this report. Fresh AUTO/IMS autoboot and physical
failed-IMS→CS fallback also passed; see REGISTRATION.md for receipts.

The CS-only emphasis profile in `src/cs-pcm-clarity.h` is:
`y[n]=x[n]+0.2(x[n]-x[n-1])`, DC unity, +2.60dB at3kHz, bounded +2.92dB.
Synthetic frequency/DC/saturation tests passed under UBSan; the existing real
PCM bridge lifecycle fixture still passes. This is a modest timbre experiment,
not wideband recovery or a measured diagnosis of the DSP filters. The user
reported clearer echo in the25-second trace1 comparison:1249PCM frames,
no RX/TX clipping and normal clearing. The CS adapter now selects this profile
for normal calls; the temporary RAM test marker enables diagnostics only.
Its finally block removes the marker and aggregate statistics. No speech is saved.
Two listening attempts ended immediately after handset answer, before PCM
became online; neither is a valid timbre comparison. The boot was unchanged,
the driver restored audio/MM to reusable idle, and the temporary marker was
removed. `build/cs-clarity-call-live.json` and
`build/cs-clarity-call-retry2.json` preserve the failed trials. Startup stderr
was empty in the instrumented repeat, so a PCM startup error is not established.
The bounded adapter trace exposed a heartbeat-time underflow during DSP startup,
independent of PCM emphasis. The lease-fixed revision passed a25-second outgoing
call with1253PCM frames, no clipping and user-confirmed echo/normal clearing.
The final revision also starts incoming media in ANSWER_PENDING rather than
waiting for network CONNECT ACK. Its incoming tone/echo/normal clearing passed
without reboot, confirmed by the user. The PBX timeout was configured45s, while
the kernel CONNECT ACK→idle observer interval was23.607s; this is not proof of
45seconds of media. AUTO/IMS was restored and passed a fresh standalone boot.
Final receipts and exact revisions: [CS-AUDIO.md](../../firmware/mf79u/CS-AUDIO.md).
Neither IMS binaries nor shared conversion,
gain/CMR policy or configured SIP codec order were changed.
`build/cs-audio-final-verification.json` checks the final loaded CS digest and
unchanged IMS binary/library/shared FIR baseline; test markers are absent.

User requirement: preserve the good IMS sound. Do not change the shared FIR,
IMS AMR-NB/WB conversion, IMS gain/CMR policy or global SIP codec order to tune
CS. Any future CS correction needs its own path and measured comparison.
The following recordings and IMS measurements are historical evidence.

> Архив записей/экспериментов 2026-10-06; сверено 2026-10-08.
> Последующий реальный AMR-WB FT8/23.85 kbit/s тест и ограничения качества
> описаны в [CODECS.md](../../firmware/mf79u/CODECS.md). Текущий PCM — 16000 Hz;
> старые NB/8000 Hz записи неизменны. Native runtime автономен, ранние RAM
> launcher команды не относятся к обычному запуску. Сводка: [STATUS.md](../../firmware/mf79u/STATUS.md).

Исходная входящая запись 2026-10-06:
`recordings/mf79u-incoming-20261006-223154/mf79u-incoming-20261006-223154-receive.wav`.
Пользователь оценил звук как очень плохой. Запись не нормализована и не менялась.
25.78 с, PCM16 mono 8000 Hz, клиппинг 0%, пик −7.42 dBFS. Среди 1289 блоков
по 20 мс есть 322 полностью нулевых, включая 44 одиночных между ненулевыми.
Паузы, DTX и пропуски нельзя различить только по WAV.

В коде подтверждены две причины возможного ухудшения:

- `pcm_get` читал до восьми UDP-кадров и отдавал только последний, теряя остальные.
- Native read/write выполняли относительную задержку 20 мс плюс обработка.
  Такая схема медленнее аудиочасов и накапливает рассинхронизацию.

Добавлены ограниченные очереди по 16 PCM-кадров в оба направления с начальным
буфером 3 кадра (60 мс), тактирование по абсолютным монотонным срокам и PLC
PJSIP для потерь на пути SIM→PBX. На пути PBX→SIM короткие пропуски заполняются
затухающим повтором последнего кадра. Переполнение очереди явно считается,
максимальная задержка ограничена; каждый доступный кадр сохраняется по порядку.
Счётчики не содержат звук, номера или SIM-данные. Счётчик underflow сам по себе
не отличает потерю от операторского DTX.

Проверки на модеме без звонков:

- Порядок кадров при доставке пачками, нулевой PCM, ограничение переполнения,
  обнаружение опустошения, восстановление часов после большой паузы.
- 50 периодов по 20 мс с дополнительной работой по 5 мс: 1.005188 с вместо
  накопления 250 мс задержки.
- Двусторонний loopback, отклонение повреждённого пакета, все восемь режимов
  AMR-NB и границы буферов.
- Загрузка библиотеки реальным uClibc loader и AMR selftest: result=0.

Сохранены исходные бинарники: `firmware/mf79u/build/pre-quality-20261006/`.
Новый вариант запускается из RAM; flash не записывалась.

## Повторная входящая запись

`recordings/mf79u-incoming-20261006-225056/`: исходный receive WAV 11.04 с,
PCM16 mono 8000 Hz. Обе очереди получили 663 кадра и воспроизвели 661;
два кадра оставались в буфере при отбое. Underflow=0, overflow=0,
high-water=3 кадра SIM→PBX и 4 PBX→SIM. В этой записи нет одиночных
полностью нулевых блоков между ненулевыми (в предыдущей было 44). Фразы и
длительности различаются, поэтому это не идентичное сравнение и не оценка MOS.
Локальный Whisper small распознал три повторения «раз, два, три».
Клиппинг 0%, пик −11.39 dBFS. После отбоя LED синий, каналов нет, транк Avail,
маршрут восстановлен на 201; временное приложение записи удалено.

Агрегированные счётчики AMR: 248 речевых кадров режима 1 (5.15 кбит/с),
57 SID, 322 no-data, 0 кадров с плохим Q. Это подтверждает низкий битрейт
на входящем операторском участке; частота остаётся 8000 Hz. Глухой тембр
может быть связан с этим кодированием. Пользователь подтвердил: глухой тембр
сохранился, запинания исчезли. Битрейт и SDP/CMR в этом тесте не изменялись.

Кодек native IMS использует `mode-set` и CMR; стандарт допускает изменение
режима в пределах согласованного набора. Для повышения входящего битрейта
требуется проверить SDP и согласованный набор, затем запрашивать более высокий
допустимый режим. Перекодирование полученных кадров не вернёт потерянные детали.

На этапе этой NB записи операторский путь был AMR-NB на 8000 Hz; SIP — PCMU.
AMR-WB требует отдельного кодека, PCM 16000 Hz и согласования с оператором.
Простая смена SIP-кодека не расширит уже полученное узкополосное аудио.
Форматы и частоты: [RFC 4867](https://www.rfc-editor.org/rfc/rfc4867.html).

## Проверка запроса более высокого AMR-NB режима

Добавлен ограниченный SDP/CMR модуль `src/amr-rate-policy.c`. Он хранит
Call-ID и параметры одного вызова только в RAM, выводит исключительно
PT, маску режимов, тип выравнивания, желаемый битрейт и счётчики.
`run-pbx-gateway.py --prefer-high-amr` включает эксперимент; без этого флага
SDP наблюдается, пакеты не изменяются.

Запрос CMR выбирает максимальный режим в согласованном mode-set. Обе стороны
должны согласовать AMR/8000 mono, RTP/AVP и одинаковое выравнивание. Если offer
задал mode-set, answer обязан вернуть тот же набор. Проверяются локальный порт
и удалённые IPv4/порт из SDP, RTP-заголовок с CSRC/extension/padding, все ToC и
длина AMR payload. Шифрованный RTP, AMR-WB, multicast, несогласованный SDP и
CRC/interleaving/robust-sorting отклоняются. Меняется только старший полубайт
CMR в копии пакета; кодированные речевые кадры и оригинальный буфер неизменны.
Сеть может проигнорировать запрос или выбрать меньший режим; улучшение
проверяется фактическими FT в декодере и повторной пользовательской оценкой.

Синтетические проверки прошли на Mac с UBSan и на ARM модема без сети/звонков:
ограничения mode-set, оба формата BE/OA, все AMR-NB FT, несколько кадров,
CSRC/extension/padding, неверные endpoint/PT, обрезанные пакеты, retransmit,
BYE другого вызова и сброс при renegotiation. Mac ASan не запустился из-за
зависания его runtime при инициализации, до входа в main; это не проверка кода.
Бинарник перед изменением сохранён в `build/pre-amr-rate-20261006/`.

## Входящий тест с CMR: сеть приняла 12.2 кбит/с

Запись `recordings/mf79u-incoming-20261006-231207/`, 9.90 с, исходный PCM16
mono 8000 Hz. RX offer содержит AMR-NB PT 100/101/102/108, TX answer выбирает
PT 108; обе стороны допускают все восемь режимов (`mode-set` не задан), BE.
CMR 7 выставлен в 126 подходящих исходящих пакетах. Декодер принял 197 речевых
кадров FT7 (12.2 кбит/с) и 11 FT1 (5.15), то есть 94.71% речи в максимальном
AMR-NB режиме. Порядок смены режима гистограмма не сохраняет. SID=50,
no-data=310, bad-Q=0. Запрос фактически принят сетью; субъективное улучшение
тембра по этим счётчикам не определяется.

Очередь SIM→PBX: received=605, played=603, underflow=0, overflow=0,
high-water=3. PBX→SIM: received=606, played=604, underflow=0, overflow=0,
high-water=3. Клиппинг 0%, пик −8.80 dBFS. Запись не изменена, ASR выполнялся
локально на отдельной копии. После вызова 0 каналов, транк Avail, LED синий,
маршрут восстановлен и временное приложение автоответа удалено.

RAM-библиотека проверена после обратного копирования с модема:
SHA256 `94bf986a7f9e9260c34a60c90d84c6342f006288dd88966ec04c0cd0247eb43c`.
В текущем RAM-процессе preference включён; обычный запуск без флага его
отключает. Offline rootfs 0.5 пока остаётся предыдущей сборкой с исправлением
PCM; экспериментальный SDP/CMR в образ ещё не перепакован и flash не менялась.
Результат и счётчики: `amr-rate-test-result.json` и `quality-report.json`
в каталоге этой записи. Пользователь оценил тембр как немного лучше, но всё
ещё глухой. Повышение битрейта AMR-NB не устранило эту проблему.

## Адаптивный AMR-WB / AMR-NB: подготовка проверки

Добавлен режим `run-pbx-gateway.py --adaptive-audio`: native IMS объявляет
AMR-WB вместе с AMR-NB, программный мост поддерживает оба семейства, PCM
между IMS и SIP передаётся при 16000 Hz. Согласованный AMR-WB проходит без
понижения частоты; для резервного AMR-NB используется FIR-преобразование
8000↔16000 Hz. MikoPBX и SIP-мост допускают G.722 с резервным PCMU.
G.722 относится к участку модем↔PBX, а не доказывает поддержку этого кодека
в сотовой сети. Частота WAV 16000 Hz также сама по себе не доказывает HD-речь.

CMR выбирает максимальный разрешённый режим согласованного семейства,
включая все девять режимов AMR-WB. Сеть может снизить битрейт или проигнорировать
CMR. При несогласованном SDP или неподдерживаемой упаковке RTP пакет остаётся
неизменным. Обычный запуск без флагов сохраняет AMR-NB без изменения CMR.
EVS не реализован; поддержка любого оператора пока не доказана.

На модеме прошли проверки реального uClibc loader: все девять режимов
AMR-WB, границы буферов, тестовый тон 6 kHz. Проверен G.722: 320 PCM-сэмплов
16000 Hz → 160 байтов RTP, сохранение тона 6 kHz. FIR подавляет алиас 6 kHz
при переходе к 8000 Hz и сохраняет 3 kHz и постоянный уровень.
Проверка SDP/CMR AMR-NB+WB и очередь PCM также прошли на ARM.
Реальный входящий вызов с AMR-WB ещё не проверен.

Диагностика `SDP_AUDIO` выводит только имена из фиксированного списка,
PT и RTP clock; SIP-заголовки, произвольные строки SDP и SIM-данные не сохраняются.
RX — предложение сети, TX — ответ модема; фактический кодек дополнительно
проверяется по `MEDIA_AMR[_WB]` и `MEDIA_PCM_RATE`.

Радиосеть в данном эксперименте: PLMN 28020, PrimeTel. Оператор заявляет HD Voice
на [официальной странице VoLTE](https://primetel.com.cy/el-volte),
но не перечисляет AMR-WB/EVS. До получения нового SDP точный список
кодеков для текущего маршрута вызова остаётся неподтверждённым.
Все изменения модема выполняются в RAM, flash и offline rootfs 0.5 не менялись.

## Реальный AMR-WB: сессия 2026-10-06 23:46:55

Тестовая сессия `recordings/mf79u-incoming-20261006-234655/` подтвердила
входящий вызов с AMR-WB на операторском участке и G.722 на участке до PBX.
Сеть предложила PCMU (PT0), G.722 (PT9), G.729 (PT18), четыре AMR-NB
варианта и два AMR-WB: PT112 со всеми девятью режимами и PT117 с режимами
0/1/2. Native IMS выбрал PT117; это ограничивает согласованный максимум
12.65 кбит/с. Предложенный PT112 допускает до 23.85 кбит/с, но этот вариант
ещё не выбран и его аудиопоток не проверен. Причина выбора PT117 внутри
vendor negotiator пока не установлена; ограничение текущего CMR вытекает
из согласованного mode-set, а не из полного набора предложений сети.

Декодер принял 330 речевых кадров AMR-WB 12.65 и 5 кадров 6.6 кбит/с;
98.51% речи — 12.65. SID=49, no-data=256, lost=0, bad-Q=0.
CMR2 выставлен в 131 из 131 подходящих пакетов. Native и wire PCM — 16000 Hz;
SIP/PBX кодек G.722, исходный receive WAV — PCM16 mono 16000 Hz, 10.82 с.
Частота подтверждена вместе с действующим WB декодером, а не только заголовком WAV.

SIM→PBX: received/played=649/649, underflow/overflow=0/0, high-water=3.
PBX→SIM: 649/647, underflow/overflow=0/0, high-water=4; два кадра остались
в очереди при завершении. Клиппинг 0%, пик −14.71 dBFS, RMS −37.26 dBFS,
нет одиночных полностью нулевых блоков по 20 мс. Это измерения передачи и
уровня, не оценка MOS. Пользовательская оценка: «Заметно лучше, но не clearvoice».

EVS и AMR-WB+ в виде стандартных `rtpmap` в этом вызове не обнаружены.
Whitelist observer проверен на обоих именах. Два дополнительных payload
не распознаны; их PT и имена этот вариант logger не сохранил. Поэтому
полный инвентарь сети и отсутствие EVS/WB+ во всех её маршрутах не доказаны.
G.722 явно предложен оператором, но на сотовом участке реально использовался
AMR-WB; операторский G.722 media не тестировался. `telephone-event` — DTMF,
а не ещё один речевой кодек.

Маршрут восстановлен на 201, приложение 880 удалено, каналов нет,
транк Avail, network LED синий (mask4). Исходный WAV не изменён;
счётчики и только разрешённые метаданные сохранены в `codec-metadata.txt`
и `quality-report.json`; сводка сети — `operator-codecs.json` в этой папке.
На завершении этого исторического теста адаптивный RAM-мост был оставлен
запущенным; позднее его заменил автономный native supervisor.

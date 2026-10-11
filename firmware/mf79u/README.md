> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# MF79U Custom: автономный runtime и подготовка полной прошивки

Актуальная сводка и индекс всех работ: [STATUS.md](STATUS.md), сверено 2026-10-08.
Полный образ 0.9 и текущие userdata-компоненты — разные стадии доставки.

Экспериментальная модификация rootfs конкретного ZTE MF79U HW1.0 durA,
BD_XCBZHKMF79UV1.0.0B03. Сборка выполняется на Mac через Linux-контейнер.

Подготовка автономной сборки: [AUTONOMOUS.md](AUTONOMOUS.md). Установленный
userdata runtime локально запускает CP/PDP/SIM AKA/IMS/SIP, LED и WebUI;
Mac relay для работы не нужен. Автозапуск от init, IMS и двусторонний голос
проверены на физическом устройстве. Полный replacement rootfs ещё не прошит
и не прошёл загрузочную проверку, поэтому manifest честно оставляет
`boot_tested=false` и `autonomy.ready=false`.

Разбор голосового ABI, транспорта AP↔PS и результаты второго этапа:
[VOICE-BACKEND.md](VOICE-BACKEND.md).

Актуальные кодеки и новый интерфейс: [CODECS.md](CODECS.md), [WEBUI.md](WEBUI.md).
Ниже также сохранены результаты предыдущих этапов.

WebUI Control 0.10 и native SIP gateway установлены на текущем B03 через защищённый загрузочный hook и
проверены перезагрузкой. Панель открывается по `http://192.168.0.1/`, использует
прежний пароль устройства и хранит настройки в userdata. Сторона оператора:
AMR-WB до 23.85 кбит/с, затем AMR-NB. SIP: Opus, G.722, PCMA, PCMU, G.729;
UDP/TCP/TLS, отдельные auth credentials и числовой caller ID.
Вкладка SIP также включает однопользовательский локальный UDP-регистратор:
один аккаунт и одна активная привязка, с Digest-аутентификацией. Физический
REGISTER и безопасный нецифровой INVITE проверены без вызова через SIM.
PCM, очереди и преобразование частоты в этом этапе не изменялись.
Панель содержит Status / SIP / Messages / Wi-Fi / Network / System.
SMS WebUI/REST использует штатный backend; [SMS-API.md](SMS-API.md) описывает
REST, [SMS-SIP.md](SMS-SIP.md) — локальные SIP MESSAGE, очередь и проверки.
Ранее пользователь подтвердил получение одного отправленного через Linphone
SMS; его неоднозначный modem API status документирован отдельно.

Обновление 2026-10-08 запускает SIP/SMS до IMS. При GSM/3G регистрации и
недоступном IMS работает SMS fallback; GSM голосовой мост не реализован.
На нужной роуминговой SIM epic подтверждены International roaming, GSM/EDGE,
приём в память модема и SIP ACK от MikoPBX без IMS. Отображение у конечного
SIP-клиента и конкретный пользовательский тест SMS ещё не подтверждены.
IMS стартует только при EPS stat=1/5, его сбой сохраняет SIP/SMS. Voice INVITE
без готового IMS отклоняется 503. Исправлено распознавание роуминга B03
Home/Internal/International и короткого SYSINFO при поиске сети.

Позднее 2026-10-08 собственный RAM-only CC handler обеспечил реальные гудки
входящего GSM CS вызова и его штатное завершение без ответа. Контроллер читает
собственный CS status interface; CS audio/Caller ID/SIP forwarding ещё не
реализованы. Сигнализация остаётся bounded экспериментом, без boot/flash install;
подробности и актуальное состояние: [GSM-VOICE.md](GSM-VOICE.md).

Wi-Fi — постоянный защищённый WPA2 hotspot: Enabled / SSID / Password / Hidden.
Минутный bootstrap и Wi-Fi uplink заменены этим режимом. Внешняя Wi-Fi
ассоциация ещё не подтверждена. USB сохраняет статический адрес управления
и канал восстановления. LTE data off блокирует обычный wan* OUTPUT/FORWARD
IPv4/IPv6, оставляя local IMS wan5; радио и приём SMS сохраняются.

Сетевой LED: красный без регистрации, жёлтый при регистрации без IMS,
синий при IMS idle, зелёный исходящий/connected, красный+синий входящий до
ответа. Оба LED принадлежат нашей прошивке; [NETWORK-LED.md](NETWORK-LED.md).
Последние userdata изменения не входят в старый NAND0.9/SD0.8 архив.
Полный rootfs образ не прошивался.

## Архив раннего RAM-голоса (2026-10-06)

Этот раздел описывает прежний RAM/AMR-NB прототип; обычный запуск сейчас
автономный, PCM 16000 Hz, оператор AMR-WB/NB. Итоговые WB/FT8 доказательства
смотрите в [CODECS.md](CODECS.md).

На физическом модеме подтверждён исходящий VoLTE-вызов: телефон зазвонил,
пользователь ответил, получены защищённые SIP 180/200, отправлен ACK,
native IMS сообщил `^CONN`. Отбой завершён BYE/200. После повторного теста
модем отвечает через ADB/AT, основной CID1 активен, IMS CID5 выключен.

В RAM-прототипе программный OpenCORE AMR-NB заменяет отсутствующий
`/dev/amr_device`. Добавлен двусторонний PCM-мост к PJSIP endpoint на USB LAN.
MikoPBX в Docker на Mac подключена как IP peer. Подтверждён исходящий звонок
из PBX через SIM и доставка тестового звука до телефона; пользователь слышал
сигналы. Также проверен входящий SIM-вызов с автоответом PBX и записью речи:
25.78 с исходного WAV, PCM16 mono 8000 Hz, без клиппинга. Локальное распознавание
восстановило тестовые фразы с ошибками; полноценная оценка качества речи ещё
предстоит. Результаты и команды:
[MikoPBX README](../../outputs/mikopbx/README.md).

Результаты: структурированный отчёт (historical local artifact: `build/ims-software-paced-call-result.json`),
SIP metadata (historical local artifact: `build/ims-software-paced-call-sip.log`),
IPC events (historical local artifact: `build/ims-software-paced-call-report.json`).
Этот прототип запускается из `/dev`. В rootfs 0.5 включены его библиотека,
частный IMS, контроллер событий и PJSIP endpoint; автоматический запуск
голоса пока отсутствует, требуется работающий CP relay на Mac.
Flash, ядро, радиопрошивка и NV во время этих тестов не записывались.

## Что собрано

- `build/rootfs.experimental.jffs2`: образ раздела rootfs JFFS2.
- `build/voice-probe`: наш статический ARMv7 EABI soft-float компонент без libc.
- `build/amr-tool`: программное кодирование/декодирование AMR-NB на CPU модема.
- `build/manifest.json`: исходный SHA256, изменения, геометрия и результаты проверки.
- `build/SHA256SUMS`: контрольные суммы артефактов.
- `build/voice-probe-live.txt`: результат запуска нашего ARM-кода на физическом модеме.

Rootfs основан на сохранённом дампе `outputs/zte-backup/rootfs.mtd5.bin`.
Сборщик принимает только SHA256
`544766bfc6317ba3a1c820c9c9d82b73e14174a2bc4f03fd6962471d5dea564b`.
Версии до 0.7 добавляли SMS и терминал в штатный UI. Версия 0.8 заменяет
штатные frontend assets новой панелью; vendor backend остаётся локальным
источником SMS/радиостатуса. Вместо браузерного shell панель предоставляет
ограниченный API настроек, без выполнения произвольных команд.

Версия 0.5 также включает `/usr/bin/mf79u-amr-tool` и лицензию OpenCORE AMR.
Кодек проверен на физическом модеме отдельно от vendor IMS; подробности
и измерения в [VOICE-BACKEND.md](VOICE-BACKEND.md).

Автономный userdata LED service управляет сетевым RGB и Wi-Fi индикаторами:
[NETWORK-LED.md](NETWORK-LED.md). Последняя аппаратная проверка жёлтого:
build/yellow-led-live.json (historical local artifact: `build/yellow-led-live.json`). Проверки GSM/SMS fallback:
build/gsm-sms-fallback-live.json (historical local artifact: `build/gsm-sms-fallback-live.json`).

В последней сборке 0.9 проверено содержимое 883 путей, inode/data CRC, режимы доступа и ссылки.
345 путей vendor-кода в `/bin`, `/lib`, `/sbin` сохранены без изменения содержимого.
Ядро, радиопрошивка, загрузчик и NV-разделы в этот образ не входят.

Геометрия прочитана с физического модема: erase block 131072 байта,
NAND write size 2048 байт, rootfs 50331648 байт.
Параметр mkfs.jffs2 pagesize — 4096: это размер страницы Linux,
а не размер NAND-записи. Образ little-endian, без cleanmarkers,
без сжатия и с фиксированными временными метками; свободное пространство
до конца раздела не добавлено. Сборщик проверяет размер.

## Повторная сборка

Из корня текущего workspace:

```sh
sh firmware/mf79u/build.sh
```

Нужны Docker, существующий `work/jffs2-venv` с Jefferson 0.4.8/pyelftools и исходники
OpenCORE AMR 0.1.6 в `work/zte/voice/opencore-amr-0.1.6/`.
PJSIP 2.17 находится в `work/zte/voice/pjproject/pjproject-2.17/`; его архив
проверяется по SHA256 `065fe06c06788d97c35f563796d59f00ce52fe9558a52d7b490a042a966facce`.
Архив `work/zte/voice/opencore-amr-0.1.6.tar.gz` проверяется по SHA256
`483eb4061088e2b34b358e47540b5d495a96cd468e361050fae615b1809dc4a1`.
Исходный архив: https://downloads.sourceforge.net/project/opencore-amr/opencore-amr/opencore-amr-0.1.6.tar.gz
Первичная распаковка исходного дампа:

```sh
work/jffs2-venv/bin/jefferson outputs/zte-backup/rootfs.mtd5.bin \
  -d firmware/mf79u/build/stock-rootfs
```

`Dockerfile` задаёт базовый образ по digest и инструменты cross-compile.
Установленные apt-пакеты не закреплены по версиям, поэтому повторяемость
контрольной суммы гарантируется проверкой в текущем окружении, а не для
любой будущей версии Debian-репозитория.

## Проверка собственного кода на устройстве

Компонент делает только `access(F_OK)` для аудиопутей и выводит результат.
Он не открывает аудиоустройства, не отправляет ioctl/AT, не инициирует
регистрацию IMS, вызовы или ответы. Код выхода 2 означает отсутствие всех
проверяемых путей; 0 означает лишь наличие хотя бы одного, не рабочий голос.

Он успешно выполнен из RAM-backed `/dev` и удалён после проверки.
`/tmp` имеет `noexec`, поэтому запуск оттуда отклоняется ядром.
Постоянные файлы устройства, настройки и flash при тесте не менялись.

## Текущая граница готовности

System/SSH, REST/SIP SMS, PBX Caller ID/маршруты, GSM fallback и reset-план
описаны в [STATUS.md](STATUS.md). Последние изменения остаются в userdata;
ранний полный 0.9 пакет устарел, сырая NAND прошивка не выполнялась.

Этот образ ещё не прошёл загрузочную проверку. Он не является подписанным
пакетом обновления ZTE. Перед записью нужны проверенный способ восстановления,
точный формат/процедура записи rootfs с обработкой NAND bad blocks и проверка
boot-time зависимостей. Автоматической прошивки в проекте нет.

Generic voice-приложения из официального SDK
ожидают отсутствующие ALSA/SLIC/voice/AMR/VoLTE интерфейсы. Одна сборка этих
приложений не создаёт драйверы или транспорт звука.

Локальный CP controller и программные AMR-WB/AMR-NB бэкенды подключены
к native IMS; постоянные бинарники находятся в userdata. Сетевой PCM и
SIP endpoint подключены к Asterisk; реальные входящие/исходящие вызовы
проверены, пользователь подтвердил улучшение после AMR-WB FT8. Долговременная
работа, разные операторы и каждый SIP-кодек требуют отдельных проверок.
Для полной замены stock rootfs остаются загрузочная проверка образа и
проверенный путь восстановления NAND; автономный CP frontend уже работает
из userdata без Mac. Тестовые call scripts имеют watchdog и требуют отдельной
авторизации звонка. Постоянный PBX маршрут теперь принимает цифровые внешние
номера; внутренние остаются в PBX. Control 0.10 сохраняет SIP параметры и
применяет их между звонками.

Историческая сборка 0.6 RAM-моста поддерживала адаптивный AMR-WB/AMR-NB и G.722/PCMU до
PBX. Реальный входящий WB вызов на PrimeTel проверен: 12.65 кбит/с,
native/wire PCM 16000 Hz, обе очереди без underflow/overflow. Пользователь
подтвердил заметное улучшение, но ясность голоса ещё недостаточна.
Это legacy recovery launcher, а не обычный запуск. Перед его использованием
требуется штатно остановить native supervisor по проверенному ownership.
Эти изменения отсутствовали в offline rootfs 0.5. Сборка 0.6 включает их;
записи во flash и загрузочной проверки 0.6 ещё не было.

Сборка 0.6 добавляла G.722 также в операторский IMS, программные AMR-WB
режимы 0–8 (до 23.85 кбит/с) и AMR-NB режимы 0–7 как резерв.
С 0.7 оператору предлагаются только AMR-WB/NB; G.722 остаётся на SIP-стороне.
Правила выбора, проверки и границы поддержки описаны в [CODECS.md](CODECS.md).

Исходники и протоколы для дальнейшей работы:

- ZTE source catalog: https://opensource.ztedevices.com/rest/product/findProductByTitle?title=MF79U
- PTCL MF79U SDK: https://download.ztedevices.com/device/global/support/opensource/7/20200716_01/PTCL_MF79U_opensource_code.tgz
- Полный локальный индекс SDK: `work/zte/voice/ptcl-member-index.json`.
- Извлечённые voice-исходники: `work/zte/voice/ptcl-selected/`.
- Протокол предыдущего исследования: `outputs/zte-shell/voice-investigation.txt`.

Проект предназначен для локального устройства. В образе сохранены
проприетарные компоненты производителя; право их распространения не проверено.

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

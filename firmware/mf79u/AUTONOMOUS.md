> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Автономный MF79U runtime: native0.9 / Control0.10

> Current summary: [STATUS.md](STATUS.md), audited 2026-10-08.
>
> Update 2026-10-08: the installed userdata controller starts SIP/SMS before
> IMS and provides GSM/3G SMS fallback. IMS is attempted only with EPS
> registration; IMS failures preserve SIP/SMS. GSM voice audio is not
> implemented. Network LED is yellow for cellular registration without IMS,
> blue for IMS idle, red without registration; call colors retain priority.
> See [SMS-SIP.md](SMS-SIP.md), [NETWORK-LED.md](NETWORK-LED.md) and
> gsm-sms-fallback-live.json (historical local artifact: `build/gsm-sms-fallback-live.json`). The original
> full NAND0.9 image and SD0.8 archive do not contain this update.
>
> Later CS continuation: a bounded RAM CC handler produced real incoming GSM
> ringback and completed clearing without CONNECT. The updated userdata native
> controller reads its own CS state interface and sends LED events. Full CS
> audio/Caller ID/SIP forwarding remain unfinished. See [GSM-VOICE.md](GSM-VOICE.md),
> build/cs-ring-incoming-live.json and build/cs-status-lifecycle-live.json.

Исходный этап 0.9 проверен 2026-10-07 на физическом MF79U HW1.0 durA,
BD_XCBZHKMF79UV1.0.0B03, ARMv7 soft-float, Linux 3.4.110.

PDP, SIM AKA, IMS, SIP, управление LED и WebUI теперь работают внутри модема.
Mac CP relay и USB watcher остановлены. В режиме TRUNK PBX остаётся отдельным
SIP сервером; в лаборатории это MikoPBX в Docker на Mac, в эксплуатации может
быть другая PBX. Режим SERVER позволяет подключить один SIP-клиент прямо к модему.

## SIP-роли

Native SIP gateway 0.8 имеет три роли: `DISABLED`, `TRUNK`, `SERVER`.
`DISABLED` сохраняет попытки IMS в подходящей LTE-сети и штатный приём
SMS в GSM/3G, но закрывает SIP sockets и запрещает голос
в native controller (DIAL, ANSWER, входящий DSCI). Никакая PBX при этом не нужна.
`TRUNK` сохраняет прежний peer/REGISTER к внешней PBX. `SERVER` поднимает на
самом MF79U однопользовательский UDP SIP-регистратор: один аккаунт, одна
активная привязка, все входящие SIM-вызовы на неё и цифровые исходящие SIP URI
в SIM. Встроенный сервер не создаёт отдельного процесса и не меняет локальный
IMS/PCM тракт. Изолированный и физический USB-LAN тесты выполнены без набора
номера в мобильной сети. На проверке fallback 2026-10-08 сохранённая роль
была `TRUNK`; прежняя `SERVER` относится к более раннему UI-тесту.

## Подтверждённые результаты исходного этапа 0.9 (2026-10-07)

| Проверка | Результат |
| --- | --- |
| Локальная IMS activation | CID5, IMS APN и адрес/P-CSCF проверены через AT_CTL |
| SIM AKA | Выполнена внутри модема; значения остаются в RAM |
| Автозапуск | Повторные реальные software reboot; init → wrapper → supervisor → native controller |
| Загрузка этапа 0.9 | IMS зарегистрирован через 18 s от старта controller, SIP готов через 21 s |
| SIP peer | MikoPBX квалифицирует транк как Avail |
| Исходящий звонок | SIM и SIP connected; пользователь подтвердил звонок и тестовый писк |
| Аудиоданные | PCM received=518, sent=365; nonzero=518/364, в обе стороны |
| PCM | Без изменений: mono PCM16LE, 16000 Hz, 320 samples / 20 ms |
| SMS | API: 3 сообщения в памяти модема, 0 на SIM; содержимое не сохранялось в отчёт |
| LED | Наш процесс управляет четырьмя GPIO каналами; stock LED service отсутствует после boot |
| Полный rootfs 0.9 | Offline JFFS2: 40,136,252 bytes / 48 MiB; 883 paths, 345 vendor binaries unchanged |
| Прошивка полного образа | Не выполнена; установлен обратимый runtime/boot overlay на B03 |

Входящий beep/echo тест ожидал вызов 10 минут, нового вызова не было; временный
маршрут восстановлен и приложение удалено. В исходном этапе0.9 Numeric Caller ID после перехода на native controller
ещё не перепроверялся. Позднее PBX получил PAI/Privacy и цифровую маршрутизацию;
пользователь подтвердил звонки. См. [PBX README](../../outputs/mikopbx/README.md). Результат сохранён без номера абонента
и без захвата аудио самим проверочным скриптом. Не считать исходящий звонок
доказательством входящего маршрута или работы всех операторов.

## Исправление B03 PDP IPC

Наш CP клиент создаёт свою reply queue 0x1132..0x1232, mode 0600, и отправляет
в штатный AT_CTL 0x100f request 0x152d с payload 3496 bytes. Он не открывает
/dev/rpm* и не потребляет чужие очереди. Проверяются magic, источник, адресат,
длины и терминальные ответы; ожидание ограничено временем.

AT+ZPDPACT=0,"IPV4V6","ims",0,1,1 возвращает бинарный 0x159b вместо текстового
0x152f. Disassembly B03 zte_mifi 0x22444/0x225ea подтверждает 12-byte layout:
result, cid, error. При success result=0, cid по offset4; error word не
инициализирован и не читается как ошибка. Success принимается только для
точного IMS запроса и CID5. После него читается CGCONTRDP=5 и проверяются
IMS APN, действительный IP и P-CSCF. src/cp-pdp.c формирует реальный ZPDPACT
ответ из этих данных; это не подстановка фиктивного OK.

Адаптер понимает IPv4 с маской, IPv6 в colon/dotted форме и два family rows.
Текущий оператор проверен с IPv4. Другие семейства и malformed responses
покрыты синтетическими тестами, а не живой проверкой оператора.
Альтернативный request 0x152e не дал ответов в read-only тесте и не используется.

## Процессы и загрузка

Внутренние /mnt/userdata/mf79u/.mf79u-native-gateway, .mf79u-volte-private,
.mf79u-ims-userspace-ipsec.so, .mf79u-sip-gateway, .mf79u-net-led доступны без SD.
Обновлённый WebUI загружается из внутренней копии: marker
`/mnt/userdata/mf79u/control-internal-preferred` отключает выбор старого SD
binary 0.8, который не понимает DISABLED/HOTSPOT. SD остаётся архивом.
Wrapper сохраняет прежний checksum selection, если marker отсутствует.
Карта смонтирована read-only; это хранилище, не RAM/swap/bootloader.

Существующий /etc/rc hook запускает start-control.sh. Он запускает наш LED
и start-native.sh. Supervisor проверяет native-enabled, локальный AT_CTL,
исполняемые файлы и gateway.ini. Controller имеет flock, владеет своими
детьми/очередями, чистит только их. SIP/SMS запускается до IMS. IMS разрешён
только после EPS stat=1/5; GSM остаётся в `sms_only`. Опрос радио — 15 s,
IMS attempt — 300 s, повтор IMS на LTE — 60 s. Неудача IMS или потеря LTE
сохраняет SIP PID/binding и SMS worker; активный голосовой вызов завершается.
Это отдельная политика от перезапуска упавшего controller через supervisor.
Supervisor retry delays: 5,15,30,60,120 s, затем
пауза 300 s. Проверка завершения дочернего процесса выполняется каждые 30 s;
эта задержка добавляется перед retry. RAM log ограничен 64 KiB с проверкой
каждые 30 s; O_APPEND позволяет очищать его без дыр в файле. Отдельные RAM
status/log files содержат состояния и счётчики, без AKA, cookies, SMS текста
и телефонных номеров. Отчёт запуска нужно сохранять сразу после boot, пока
старые события не удалены лимитом лога.

WebUI Apply SIP посылает SIGHUP нашему SIP процессу; настройки применяются
без внешнего launcher. Native controller опрашивает radio state и передаёт
изменения IMS. Перерегистрация, привязка к PBX и медиапотоки выполняются
локально. Операторские кодеки: AMR-WB до 23.85 kbit/s и AMR-NB fallback.
SIP: Opus, G.722, PCMA, PCMU, G.729; UDP/TCP/TLS.

## Отключённые службы ZTE

install-native.py удаляет LED и self-registration run/sync entries из
проверенного B03 daemon config, выключает prestartdua (FOTA) и zte_dm
в zte_debug.sh. После reboot эти процессы отсутствуют. Исполняемые файлы
производителя не изменяются и не удаляются. CP, SIM/SMS, radio, WLAN,
router/DHCP, NTP и watchdog сохранены как необходимые зависимости.

Backup в userdata: daemon.vendor.b03.conf, debug.vendor.b03.sh и
start-control.pre-native.sh. Root config меняется через staging/atomic rename;
EXIT trap возвращает корневой mount в read-only. LED: red без регистрации,
yellow (red+green) при регистрации без готового IMS, blue при IMS idle,
green исходящий/connected, red+blue входящий до ответа. Wi-Fi blue
показывает активный Wi-Fi интерфейс (текущий пользовательский режим — AP); всеми четырьмя каналами владеем мы.

## Лабораторный PBX и NAT

Docker Desktop посылает исходящий SIP с primary IPv4 Mac, хотя PBX server
в настройках — USB peer 192.168.0.169. Раньше обратный маршрут добавлял Mac
launcher. Теперь защищённый userdata pbx-return-routes содержит строки
`destination/prefix gateway interface`. Supervisor восстанавливает их сам,
не перезаписывая чужие маршруты. Source address PBX также явно включён в
Trusted PBX IPv4 addresses в UI. При смене адресации лаборатории нужно
обновить маршрут и trusted peer. Обычной PBX с прямой связностью этот
специфический Docker маршрут не нужен.

## Сборка и воспроизводимые проверки

Из <checkout>:

```sh
sh firmware/mf79u/build.sh
python3 firmware/mf79u/test-native-cp.py
python3 firmware/mf79u/verify-standalone.py --audio-confirmed
work/jffs2-venv/bin/python firmware/mf79u/verify.py
python3 firmware/mf79u/pack-image.py
```

Флаг audio-confirmed допустим только после человеческого подтверждения
тестового звука. test-native-cp выполняет read-only CP и synthetic IPC tests,
не звонит и проверяет сохранность queue identities. verify-standalone
сверяет init ancestry, PID/executable identity, SHA256/MD5 установленной
сборки, PDP/AKA/IMS события, SIP доступность и отсутствие Mac relay.
Смотрите build/native-cp-verification.json и build/standalone-verification.json.
Manifest связывает живые доказательства с конкретными artifact hashes.
После перезагрузки без нового звонка можно использовать --previous-call-proof
с ранее сохранённым standalone report. Это допустимо только при совпадении
SHA256 всех четырёх голосовых бинарников; отчёт явно отмечает прошлую загрузку
как источник подтверждения звука, а текущий автозапуск проверяет заново.

Установка runtime: python3 firmware/mf79u/install-native.py --install.
Native/SIP credentials остаются в защищённой userdata, не входят в архив.
Для остановки native service сначала поставить native-enabled=0 и остановить
supervisor по проверенному PID/cmdline; не применять произвольные killall/ipcrm.
Не запускать Mac watcher/relay поверх native controller. Если возвращать stock
LED startup, сначала убрать наш LED из wrapper и остановить его по identity.

## Что ещё не проверено

- Питание только от зарядки и реальная Wi-Fi ассоциация/работа SIP-клиента по AP.
  Подтверждены software reboot/USB LAN. Сейчас AP постоянный защищённый hotspot;
  прежний 60-second setup AP заменён. Wi-Fi uplink больше не является текущим режимом.
- Живой AMR-NB fallback на другом операторе и IPv6 IMS; codec selftests есть.
- Vendor session B03 короткая, но native backend уже автоматически выполняет
  LOGIN и один retry с verifier в RAM. Истечение vendor cookie не закрывает UI.
  Собственная management session имеет rolling30min idle; reboot/restart требует
  входа заново. См. [WEBUI.md](WEBUI.md), [SYSTEM.md](SYSTEM.md).
- Полная загрузка replacement rootfs и recovery flash procedure. Образ 0.9
  собран и проверен offline, но не прошит. Нельзя объявлять его проверенным
  boot image или писать NAND прямым dd.

Stock rootfs backup SHA256:
544766bfc6317ba3a1c820c9c9d82b73e14174a2bc4f03fd6962471d5dea564b.
Геометрия: 48 MiB rootfs, erase128 KiB, NAND write2048, Linux page4096.
Перед полной заменой образа нужны проверка bad blocks и способ восстановления.

## Новая проверка загрузки DISABLED/HOTSPOT

2026-10-07 обновлены внутренние WebUI/SIP/native binaries. Реальный software reboot
с DISABLED подтвердил IMS registered, закрытый LAN SIP port, постоянный hotspot
и цепочку supervisor -> wrapper -> init (без ADB/Mac parent). Затем SERVER
восстановлен через WebUI Save, SIP OPTIONS вернул 200. LTE data=false блокирует
обычный local/forwarded cellular internet, исключая только локальный IMS wan5.
Отчёт build/ui-modes-verification.json; PCM и operator profile не менялись.
Ранее собранный rootfs/package 0.9 не включает это обновление; требуется новая
сборка и актуальные связанные verification reports перед будущей прошивкой.

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

## Boot frontend and optional service trimming (2026-10-11)

Live stock index is replaced by an English starting stub; LAN redirect is
installed earlier. Vendor goform backend remains needed. Persistent daemon
policy now excludes traffic-statistics, phonebook and USSD topsw workers;
measured targeted PSS228KiB plus swap620KiB. Exact workers absent after stop,
critical network/SIM/SMS/voice services retained. Checksummed backups and
remaining validation: [BOOT-MEMORY.md](BOOT-MEMORY.md).

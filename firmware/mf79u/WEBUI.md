> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

## Current UI end-to-end audit, 2026-10-11

See [the current audit matrix](../../docs/UI-E2E-20261011.md). Network confirmation
now waits for backend readiness and displays the remaining deadline; successful
rollback is informational. Save is scoped to its tab and retains other drafts.
Unrelated network/mobile changes no longer reload an unchanged SIP listener and
discard its client binding. Actual failures remain visible on relevant pages.
This new audit supersedes older fixture-only claims for these flows; physical
call/password evidence remains explicitly marked in the matrix.
The delayed apply worker checks cancellation after taking the network lock.
Disabled/switching voice and failed PBX registration have explicit labels.
Authenticated System/IMEI/log reads and real API admin/SSH password rotations
were checked in this audit; older IMEI-only evidence below is historical.

## Current IMEI display restored (2026-10-11)

The modem was missing the persistent IMEI reader. Restored the verified helper
and added an explicit read-error notice beside Device IMEI; Save IMEI is
disabled while the current value is unavailable. Refresh populates the field
and clears the notice after a successful read. The Control updater repairs a
missing helper without changing the device identity.

Go/JS regressions and all seven browser tabs at1280/390px passed. API/UI evidence
uses isolated non-secret fixtures; two hardware helper reads agreed, with no
identity value/hash retained. Current modem-served System markup/JS match source.
No live authenticated System API session was inspected. Only Control was
restarted for this fix, preserving settings and native/SIP PIDs at installation.
A separate subsequent runtime replacement is recorded in the final receipt;
USB VoWiFi remains ready, with no active call. No IMEI write, call/SMS, modem
reboot or raw flash was issued for this fix. Historical image archives remain
outdated. Details: [SYSTEM.md](SYSTEM.md); receipts:
live (historical local artifact: `build/system-imei-display-live-20261011.json`),
UI (historical local artifact: `build/system-imei-display-ui-fixture-20261011.json`).

## Framed blocks on every tab; Save only for settings (2026-10-11)

All content panels use the Mobile border style: 1px #ddd border, 3px corners,
20px desktop padding and16px mobile padding. This includes Status metrics and
all SIP, Messages, Wi-Fi, Network and System blocks; the login form is framed
too. Its grid column now shrinks correctly at320px without horizontal overflow.

Shared Save is visible only on Mobile, SIP, Wi-Fi and Network. Status is
read-only and has Refresh status. Messages and System retain their dedicated
actions. Unsaved settings survive a visit to Status and its refresh; they remain
available when returning to a settings tab. No settings/backend policy changed.

JS fixtures/Go tests passed. All seven tabs, SIP roles and Wi-Fi Client layout
passed browser fixtures at1280/390/320px: every visible article has the shared
frame, correct Save visibility and no overflow or JS errors. Screenshots use
isolated non-secret fixtures. The final modem-served login passed at all three
widths. All five deployed public assets match the final source bytes.

Only Control restarted, final PID956 / MD5b24e672bfc4aa4ecd4756c800ab122ae. Three physical idle samples
over20seconds retained boot77358efe…, native1697/SIP1749, ready USB VoWiFi and
registered SIP client. Settings/gateway.ini hashes were preserved. No call/SMS,
modem reboot or raw flash; historical rootfs/SD archives remain outdated.
Receipts: browser fixture (historical local artifact: `build/framed-tabs-ui-fixture-20261011.json`),
live installation (historical local artifact: `build/framed-tabs-live-install-20261011.json`).

## Mobile tab and button layout (2026-10-11)

Voice registration and LTE data settings moved from Status to Mobile. Its three
bordered blocks are ordered: Registration preference with current voice mode,
LTE data / mobile internet, then VoWiFi internet source. USB gateway/DNS fields
appear below the source selector when USB Ethernet is selected. The existing
shared Save applies these settings; network changes still require confirmation.
Status retains its monitoring, connection details and Refresh status action.

All buttons have a minimum height of44px. Save, Refresh and the other buttons
use the header blue (#175a9b) with white text. Standard buttons are at least88px
wide; compact password controls retain their64px minimum and codec order
buttons are44×44px. Panel headings wrap on narrow
screens. No backend policy or voice/audio processing changed.

Installed only the embedded Control binary in userdata; no modem reboot.
JS fixtures and Go tests passed. Browser fixtures covered all seven tabs at1280px
and390px, SIP roles, Wi-Fi Client layout, moved Save fields, draft persistence,
conditional USB fields and the existing active-call lock. Screenshots contain
fixture data, no private messages or credentials. Installed assets were also
rendered from the modem with isolated fixture API responses; authenticated live
settings writes were not needed for this layout change.

All five deployed public assets match their source bytes. Three physical idle
samples over20seconds retained boot77358efe…, native1697/SIP1749, ready USB
VoWiFi and the registered SIP client. Settings and gateway.ini hashes are
unchanged. Control MD5:a149bafae93971baecdc07b1bd949725, PID487.
Receipts: UI fixture (historical local artifact: `build/mobile-tabs-ui-fixture-20261011.json`),
installation and live check (historical local artifact: `build/mobile-tabs-live-install-20261011.json`).
Historical rootfs/SD image archives were not rebuilt.

## VoWiFi internet source: USB Ethernet (2026-10-11)

Final near-AP reboot restored USB IMS/SIP (native29s/34s) and Wi-Fi via the
boot retry; the full LED/lease gate completed112s after reboot. A subsequent
60-second USB + Wi-Fi steady-state check passed. Wi-Fi initial boot is still
slow. Final source is USB / gateway192.168.0.169, VoWiFi only, actual purple5.
Details and repeatable test: [connection audit](CONNECTIVITY-20261011.md).

On Mobile select VoWiFi internet source: Wi-Fi client or USB Ethernet.
For USB, enter the computer gateway address in the modem management subnet
and 1–3 IPv4 DNS servers. Save and confirm the network change within90seconds.
The computer must share internet; Wi-Fi can remain a hotspot or be disabled.
AUTO and VoWiFi only both use the chosen source. Purple LED means actual
VoWiFi IMS readiness. Older settings default to Wi-Fi.

Current installed configuration: USB gateway192.168.0.169, modem192.168.0.1,
DNS1.1.1.1/8.8.8.8. The host NAT helper has been enabled by the user.
USB IMS with Wi-Fi disabled, Wi-Fi IMS on TP-Link_8C63 and purple hardware LED
have passed physical checks. Shared SIP config compatibility is corrected;
software reboot startup and boot client retry are covered in
[the connection audit](CONNECTIVITY-20261011.md). The source selector is locked
during a call. Installation expands directly to userdata and reclaims staging.

## Wi-Fi Hotspot / Client (2026-10-11)

The Wi-Fi tab now offers Hotspot and Client modes. Client can scan/select a
2.4 GHz SSID or accept a manual/hidden SSID, with WPA2-Personal or Open security.
IP, gateway and DNS use DHCP. WPA3-only, enterprise authentication and WEP are
not offered. Hotspot keeps its WPA2 and hidden-network settings. Save applies
the change; failure or missing confirmation within 90 seconds restores the
prior confirmed network profile. USB management remains available.

Scan briefly borrows the radio when an AP is active or Wi-Fi is disabled,
then restores the confirmed profile before returning. A running client uses
its existing supplicant. Scans during calls/pending applies are rejected.
Network choices use textContent; SSIDs are hex-encoded in the supplicant
configuration and WPA2 keys derived from the passphrase. Runtime configuration
is mode 0600 and never included in public settings or verification receipts.
Switching mode clears the input credentials to avoid reusing an AP password
for an uplink. Only one confirmed Wi-Fi profile is persisted.

USB `bridge0` retains its LAN DHCP service; in Client mode `wlan0` is detached
from the bridge. A client lease overlapping the configured LAN is rejected; changing LAN
subnet allows removal of only the conflicting known old/recovery aliases. Wi-Fi routes prefer its gateway without removing cellular routes;
VoLTE sockets use `wan5`; the VoWiFi candidate uses the authenticated SWu
VIP and owned `vowifi0` route. Actual IMS readiness is reported by native.
VoWiFi-only blocks cellular voice fallback; cellular SMS/radio remain enabled.
Current verification limits: [VOWIFI.md](VOWIFI.md). Cellular data policy remains separate.
Native/CS/SIP audio binaries and external PCM are unchanged by this feature.

Verification and current physical-device results: [WIFI.md](WIFI.md).
This feature replaces the historical hotspot-only requirement below.

## Voice modes (2026-10-11)

AUTO, VOLTE, VOWIFI and CS are selectable. AUTO prefers the selected available
VoWiFi internet source, then LTE/IMS and GSM CS; VOWIFI never falls back to
cellular voice.
WCDMA development and its selectable mode were removed; the improved GSM
CS driver/audio path is retained. Existing SMS behavior is preserved.

# WebUI / Control 0.10

Сверено 2026-10-08 с кодом и отчётами; текущая сводка: [STATUS.md](STATUS.md).

Исходники: `control/` (Go, стандартная библиотека), `control/web/` (без CDN).
Сборка: `sh firmware/mf79u/build-control.sh` из корня проекта.
Статические файлы отдаются с `Cache-Control: no-cache` и ETag; gzip собран
на хосте. При обновлении контроллера браузер повторно проверяет HTML/JS/CSS.

Сторона оператора: AMR-WB, режимы 0–8 до 23850 bit/s; AMR-NB как резерв.
G.722 не предлагается оператору. PCM-мост остаётся mono PCM16LE/16000 Hz,
320 samples / 20 ms, с прежними очередями. SIP: Opus, G722, PCMA, PCMU, G729.
Opus работает с 16-kHz mono аудио, complexity 3, 24 kbit/s; его RTP clock
остаётся стандартным 48000 Hz. G.729 — узкополосный кодек, не способ улучшить WB.

Панель: обзор SIM/радиосети, состояние IMS и SIP, активный кодек, параметры
транка, порядок/выключение кодеков, чтение/отправка/отметка/удаление SMS,
постоянный защищённый Wi-Fi hotspot и статическая сеть управления.
На Mobile расположены Registration preference, LTE data / mobile internet
и VoWiFi internet source в трёх последовательных блоках. В SIP — Disabled / SIP trunk / SIP server,
условные формы и постоянно видимые Codecs (также в Disabled). Порядок SERVER:
Operation mode → Local Address/Port → SIP account → Codecs → Save. SIP account
скрыт в TRUNK/DISABLED. Общая Save находится только на Mobile, SIP, Wi-Fi
и Network и применяет настройки; сетевые изменения отдельно подтверждаются.
На Status, Messages и System общая Save скрыта. Messages и System используют
собственные кнопки для SMS, пароля, IMEI, SSH и reboot.
Семь верхних вкладок: Status / Mobile / SIP / Messages / Wi-Fi / Network / System.
Интерфейс английский: синяя шапка, простые вкладки без sidebar;
содержательные блоки всех вкладок обведены одинаковой тонкой рамкой. Предыдущие пять разделов проверены desktop/390 px; новый System
проверен desktop, отдельный мобильный breakpoint в последней проверке не
подтверждён. Его настройки и проверки описаны в [SYSTEM.md](SYSTEM.md).

Status различает Home / Domestic roaming / International roaming по B03
`simcard_roam=Home/Internal/International`, поддерживает legacy 0/1. Неизвестное
значение не считается домашней сетью; без регистрации показывается Not registered.
`SMS only` означает живой автономный SIP/SMS без готового IMS, а голосовые
INVITE получают 503 без набора SIM. В GSM/3G приём SMS сохраняется через
штатную WMS/storage службу. Сетевой LED при регистрации без IMS жёлтый,
при готовом IMS idle синий. Подробности: [SMS-SIP.md](SMS-SIP.md),
[NETWORK-LED.md](NETWORK-LED.md).

SMS: selector Modem memory / SIM card, B03 mem_store=1/0 соответственно.
В sms_capacity_info не добавляется multi_data: это отдельный handler.
Backend cookie jar общий для UI сессий; loginfo проверяется перед SMS.
Вживую vendor session продолжает истекать даже при активном polling;
серверный heartbeat не устранил это и удалён. Вместо него backend при потере
cookie получает свежий LD, автоматически выполняет LOGIN и один раз повторяет
status/SMS/Wi-Fi запрос. Для этого `SHA256(password)` хранится только в RAM на
время собственной 30-минутной management session; plaintext и производный ключ
не сохраняются во flash, настройки, ответы или логи. Если автоматический вход
не удался, `/api/status` продолжает отдавать локальные IMS/SIP данные с
`vendorSession=false`, SMS использует 428, а 401 означает только истечение
собственной сессии управления. Fixtures проверяют два независимых входа,
внешнюю ротацию vendor cookie, автоматический re-login, storage и Unicode.

Администратор входит существующим паролем ZTE через внутренний goform LOGIN.
Пароль администратора не сохраняется. B03: SHA256(SHA256(password)+LD),
uppercase hex. Cookie goform остаётся в RAM сервера. Собственная сессия UI:
HttpOnly, SameSite=Strict, idle timeout 30 min; успешный management GET
продлевает и RAM session, и cookie Max-Age. Изменения требуют Origin и CSRF token.
Настройки записываются атомарно в `/mnt/userdata/mf79u/settings.json`, mode 0600.
GET settings возвращает только `passwordSet`, пароли исключены. Для редактора
GET /api/settings/credentials требует cookie + X-CSRF-Token и возвращает текущие
SIP/Wi-Fi пароли с no-store; пароль администратора не возвращается. SIP читает
защищённый `gateway.ini`; SIGHUP применяет изменения только между звонками.
TLS проверяет сертификат PBX, допускает TLS 1.2/1.3; для частной CA нужен PEM.

Caller ID берётся из P-Asserted-Identity, затем From защищённого IMS INVITE.
Разрешены только телефонные номера (+ и цифры). `Privacy: id` даёт anonymous.
Номер помещается в From и P-Asserted-Identity на стороне PBX. Digest username
остаётся именем учётной записи. Файл номера временный, mode 0600, без логирования.

На устройстве daemon слушает 18080, а owned iptables redirects переводят
LAN HTTP/80 в новую панель. Штатный goform/80 остаётся доступен по loopback
для backend SMS/радиосети. Доступ к обоим HTTP портам через wan* блокируется.
При выключенном LTE data chain MF79U_SHARE блокирует FORWARD IPv4/IPv6
через wan*. MF79U_DATA стоит первым в OUTPUT и блокирует локальный трафик
через wan*, кроме выделенного IMS bearer wan5. Радио не отключается, IMS/SMS
сохраняются; внешний SIP тогда требует маршрута через USB. Это сетевой запрет,
а не гарантия стоимости услуг оператора. При включении owned chains остаются
пустыми. Disabled закрывает SIP sockets, очищает binding и блокирует DIAL/ANSWER
и входящий голос в native controller; IMS остаётся доступен в подходящей
LTE-сети, а штатный приём SMS в GSM/3G не требует IMS.
Штатная служба ZTE перестраивает firewall при загрузке и изменении радиосети.
Daemon каждые 3 секунды проверяет принадлежащие ему правила и восстанавливает
redirect/ограничения, не заменяя таблицы производителя целиком.

Wi-Fi теперь только HOTSPOT: Enabled, SSID, WPA2-Personal Password (8–63
символа), Hidden network. AP остаётся включённым без таймера. При миграции
старые station credentials удаляются из профиля Wi-Fi, заводской защищённый AP
профиль считывается локально из NV; при отсутствии безопасного профиля AP
остаётся выключенным, USB UI доступен. Обычный GET settings возвращает
только passwordSet; защищённый credentials endpoint для редактора описан выше.
Старая station-служба и её собственные маршруты /1 останавливаются, исходный DNS
восстанавливается. DHCP обслуживает штатный dnsmasq на bridge0; второй сервер
на занятом UDP/67 не запускается. Сетевые изменения требуют подтверждения
в течение 90 секунд; иначе Wi-Fi/LAN откатываются. USB management IP сохраняется
как канал восстановления. Режим Wi-Fi uplink сейчас не используется.

## Границы проверки

Go 1.26 binary имел 32 MiB неиспользуемой FIPS .bss и был завершён ядром на
execve. Go 1.25.12 выбран для target, его .bss около 180 KiB. Модем имеет
56 MiB RAM, поэтому запуск ограничен GOMAXPROCS=1, GOGC=20, GOMEMLIMIT=6MiB.

На физическом MF79U проверены вход прежним паролем, статус PrimeTel/LTE,
чтение 3 SMS без изменения их статуса, сохранение настроек 0600, применение
SIP через SIGHUP между звонками. Все пять кодеков прошли encode/parse/decode
на ARM: Opus около 3 ms на кадр 20 ms, G.729 около 0.6 ms.
Загрузочный wrapper проверен штатным BusyBox ash; он не использует
отсутствующую в B03 shell arithmetic expansion.
Локальный SIP fixture проверил UDP/TCP/TLS 1.3, Digest REGISTER, порядок всех
пяти SDP-кодеков и числовые From/PAI при отдельном auth username. SIM вызовы
в fixture не выполняются. Встроенный UDP-регистратор дополнительно проверен
на Digest challenge, корректный и неверный пароль, защиту nonce-count от replay,
замену единственной активной привязки и нецифровой INVITE, который завершается
484 до команды набора. Та же регистрация проверена на физическом модеме через
USB-LAN без SIM-вызова; после теста сохранённый режим TRUNK восстановлен.
Дополнительно проверены профиль G729→PCMA без
остальных кодеков, выбор адреса по маршруту и отказ при недоверенной CA.
TLS использует OpenSSL 3.5.9 с devrandom seed:
нестандартный syscall 384 старого ядра делает getrandom несовместимым.
Go также использует /dev/urandom вместо этого syscall.
Отправка SMS ожидает sms_cmd=4, удаление — sms_cmd=6, поле
sms_cmd_status_result; проверено fixtures по штатному frontend ZTE.

На физическом устройстве воспроизведён сброс наших правил vendor-службой:
redirect и ограничение WAN HTTP восстановились автоматически. Временный LAN
адрес 192.168.0.2/24 применился рядом с recovery 192.168.0.1/24 и исчез после
90 секунд без подтверждения. Настройки откатились; подтверждение следующей
транзакции прошло. Проверены desktop и mobile 390 px без горизонтальной прокрутки.
Доказательства первоначального этапа: build/native-webui-report.json,
build/native-management-integration.json, build/sip-signalling-native.json.
На том этапе SIM Caller ID в PBX ещё не проверялся. Позднее настроены
PAI/Privacy и цифровой маршрут PBX, пользователь подтвердил звонки; см.
[PBX README](../../outputs/mikopbx/README.md). Старые CDR не переписывались.

Ранее были проверены PSK MIB (psk_enable=2), DHCP и старое выключение AP
после 60 секунд. Теперь применяется постоянный hotspot; ассоциация внешнего
Wi-Fi клиента не считается подтверждённой только по состоянию интерфейса.
Исходные WebUI/SIP 0.8 входят в экспериментальную сборку 0.9. Последующие
Control 0.10, GSM/SMS fallback и жёлтый LED установлены отдельно в userdata
и отсутствуют в старом image/SD архиве. Полный образ не прошивался.

Текущая установленная userdata-конфигурация запускает CP/AKA/IMS/SIP локально
на модеме; Mac relay для обычной работы не нужен. Панель показывает
`Voice control: Native on device`. Экспериментальный native runtime считается
готовым для голоса лишь при живом процессе и подтверждённой IMS/frontend
readiness. Живой owned SIP в sms_only/registering также считается локальным
runtime без требования Mac relay, но не готовым голосом. Реализация и
границы проверки описаны в [AUTONOMOUS.md](AUTONOMOUS.md). Полный NAND image пока не прошит:
используются обратимый boot hook и компоненты в userdata.

## Режим встроенного SIP-сервера

На вкладке SIP выбирается одна из ролей. `SIP trunk / PBX` сохраняет прежнее
подключение к внешней PBX как IP peer либо REGISTER-клиент. `Local SIP server`
включает один локальный аккаунт и одну активную регистрацию. Новая регистрация
того же аккаунта заменяет прежний endpoint. Входящий SIM-звонок направляется
этому endpoint; если клиента нет, вызов отклоняется. Исходящий INVITE разрешает
только телефонный номер из `+` и цифр.

Локальный сервер намеренно поддерживает UDP. Пароль не короче 12 символов,
исключён из обычных API, доступен в отдельном admin credentials endpoint
по запросу пользователя, хранится в файлах mode 0600. Digest использует
qop=auth, одноразовый nonce из `/dev/urandom`, привязку к адресу источника,
контроль nonce-count и bounded rate/nonce tables. Status API сообщает только
факт регистрации и оставшееся время binding, без Contact и учётных данных.

## Установка на текущий B03 без записи полного образа

`install-control.py --install` проверяет точный исходный `/etc/rc` B03,
сохраняет его копию с контрольной суммой в userdata и добавляет один запуск
защищённого `start-control.sh`. Тело штатной загрузки и vendor executables
сохранены; rootfs немедленно возвращается в read-only. Служба работает из
`/mnt/userdata/mf79u/.mf79u-control`, не расходуя tmpfs на большой executable.
При остановке службы её wrapper убирает HTTP redirect, возвращая штатный UI.
Восстановление: `python3 firmware/mf79u/install-control.py --restore`. Оно
проверяет обе контрольные суммы, не перезаписывает чужие изменения. Полный
experimental JFFS2 образ при этом не прошивается.

## Исторический Mac USB recovery launcher

Это прежний fallback для разработки, не зависимость обычного runtime.
Не запускать поверх native supervisor/IMS; сначала штатно выключить native
service и проверить cleanup/ownership. Контекст: [AUTONOMOUS.md](AUTONOMOUS.md).

`python3 firmware/mf79u/run-usb-gateway.py` удерживает одного наблюдателя
с file lock, принимает существующий launcher этого проекта и запускает его
после завершения и появления ADB. На этапе этого watcher теста мост был принят без рестарта;
новый физический reconnect ещё не проверен. Автозапуск при входе в macOS
не настроен. Остановка наблюдателя завершает только запущенный им launcher.
Launcher пишет timestamps и elapsed, без raw CP/AKA ответов.

## Проверка новых режимов и hotspot (2026-10-07)

Установлены новые внутренние control/SIP/native binaries с проверкой MD5.
Отчёт: build/ui-modes-verification.json. Изолированный registrar fixture проверил
закрытие UDP socket в Disabled, блокировку INCOMING и возврат authenticated
REGISTER после включения SERVER. На модеме проверены Disabled + сохранённый IMS,
затем реальный reboot: init-owned supervisor, внутренний WebUI, постоянный AP,
IMS registered, LAN SIP socket закрыт. SERVER восстановлен через Save, OPTIONS
вернул 200. SIM calls и SMS mutations не выполнялись. Messages показал 5 сообщений
в памяти модема без ошибки API (это не доказательство доставки нового incoming SMS).
Hidden AP true/false, Enabled off/on и WPA2 psk_enable=2 проверены через MIB/ifconfig;
внешняя Wi-Fi ассоциация не тестировалась. Desktop и 390 px: пять разделов,
три SIP формы, пять codec rows, без горизонтального overflow.

Marker control-internal-preferred (0600) в userdata предотвращает boot старого
SD UI 0.8 с несовместимыми DISABLED/HOTSPOT settings. Wrapper checksum SD policy
сохранён, если marker отсутствует. Существующий rootfs/package 0.9 не пересобран
с этими изменениями и не прошит; актуален userdata runtime.

Последняя правка раскладки (2026-10-07): build/ui-sip-flow-verification.json
и ui-sip-flow-desktop.jpg / ui-sip-flow-mobile.jpg. Все пять разделов и три
SIP роли проверены desktop/390 px: Codecs постоянно видны, единственный Save
последний. Изменены только embedded UI assets; WebUI перезапущен отдельно
через разовый double-fork helper, wrapper принадлежит init, helper удалён.
SIP PID/IMS/binding и настройки сохранились; reboot/calls/SMS mutations не делались.

Wi-Fi SSID/Password размещены в один столбик на desktop и 390 px.
SIP trunk, SIP account и Wi-Fi password inputs теперь type=text для видимого
ввода. Сохранённые credentials по-прежнему исключены из public settings API;
пустое поле сохраняет прежнее значение. Настройки/credentials не менялись.
WebUI установлен отдельно после полного завершения старого wrapper cleanup;
новый wrapper принадлежит init, SIP PID/IMS/client binding сохранены.
Доказательство данного этапа и control SHA256: build/ui-visible-passwords-verification.json.
Все пять вкладок проверены desktop/390 px без overflow; screenshots
ui-wifi-visible-password-desktop.jpg / ui-wifi-visible-password-mobile.jpg.

## Password editor, WPA2 fix and SMS REST (2026-10-07)

Последняя правка заменяет предыдущий type=text-only вариант: сохранённые
SIP/Wi-Fi пароли загружаются в поля, замаскированы по умолчанию и имеют Show/Hide.
Logout/401 очищает их из DOM/settings; Save/rollback обновляют значения.
Unchanged Save не вызывает ложного network confirmation из-за скрытого пароля.

OPEN hotspot подтверждён на устройстве: encmode=0 при psk_enable=2. Установлены
vendor WPA параметры encmode=2, 802_1x=1, authtype=0, psk_enable=2, WPA2 cipher=8.
Ключ сверяется по readback до/после UP; ошибка оставляет интерфейс down.
CoreWLAN scan с SSID filter показал OPEN → WPA2-Personal. Драйверный passphrase
совпадает с сохранённым; внешняя клиентская ассоциация отдельно не проверялась.
Ранние проверки только по psk_enable не подтверждали шифрование в beacon.

REST: [SMS-API.md](SMS-API.md), [sms-api.py](sms-api.py). Справка расположена внизу
Messages. GET/POST/DELETE /api/v1/sms/messages и single DELETE /{id}; HTTP Basic
username admin / текущий пароль админки в Authorization header, без cookie/CSRF.
Scope header auth — только SMS REST. Каждый запрос проверяет B03 SHA256
challenge; cookie-auth совместима со старым UI и защищена Origin/CSRF.

Установлен только внутренний WebUI; old wrapper cleanup завершён до старта
нового wrapper от init, transfer helpers удалены. IMS/SIP PID сохранились.
Применение сети/Save перезагрузило SIP настройки штатным SIGHUP и сбросило
client binding, поэтому SIP-клиенту требуется повторная регистрация.
Все пять вкладок проверены desktop/390 px без overflow. Read-only API проверен
для обеих памятей; реальные звонки/SMS mutations не выполнялись. Fixture tests
проверили header/password auth, cookie/CSRF, Unicode, send/delete и fail-closed
security readback. SHA256/evidence данного этапа: build/ui-password-wpa2-rest-live.json.
Screenshot: build/ui-password-toggle-desktop.png. Старый полный образ 0.9 устарел и
не содержит этих новых changes; raw flash не выполнялся.

REST metadata уточнена: number декодирует UTF-16BE sender/phone, date возвращает
RFC3339 со смещением (невалидные даты null), direction=incoming/outgoing/draft/unknown.
Tag mapping подтверждён штатным B03 smslist.js: 0/1 incoming, 2/3 outgoing, 4 draft.
Исходные number/date доступны как rawNumber/rawDate; tag сохранён. Legacy SMS
endpoint не менялся. На 5 реальных сообщениях read-only подтверждены 3 incoming,
2 outgoing, корректные даты/номера; содержимое/номера не включены в report.

## Shared LAN / DHCP Network tab (2026-10-07)

Network now edits subnet, modem gateway, DHCP pool, DNS list and optional
classless routes. Help explains the shared USB/Wi-Fi scope and lease renewal.
Native dnsmasq configuration and 10-second reconciliation are in control/lan.go;
90-second confirmation/rollback covers DHCP as well as addresses. Profile verified in that test was 192.168.0.0/24, gateway .1, pool .2–.253, DNS 1.1.1.1/8.8.8.8,
no custom routes. The example route is a placeholder. Details: NETWORK.md.
Real DHCP OFFER verified a changed subnet + options 121/249 and explicit
rollback; original profile confirmed afterwards. IMS ready, SIP PID unchanged.
Desktop/390 px passed all five tabs; no real calls or SMS mutations.
Stage SHA256/evidence: build/lan-dhcp-verification.json. Screenshot:
build/ui-network-dhcp-desktop.png. Wi-Fi DHCP client/full reboot not tested.
The old complete 0.9 image remains stale; only userdata WebUI was installed.

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

## Boot frontend and optional service trimming (2026-10-11)

Live stock index is replaced by an English starting stub; LAN redirect is
installed earlier. Vendor goform backend remains needed. Persistent daemon
policy now excludes traffic-statistics, phonebook and USSD topsw workers;
measured targeted PSS228KiB plus swap620KiB. Exact workers absent after stop,
critical network/SIM/SMS/voice services retained. Checksummed backups and
remaining validation: [BOOT-MEMORY.md](BOOT-MEMORY.md).

## Webhooks / Telegram SMS, 2026-10-11

The current UI has eight tabs. Webhooks adds one framed Telegram SMS block with
bot token, chat ID, interface, Enabled and Delete after send to chat. Its scoped
Save is independent of network/SIP apply. Tokens remain masked in ordinary API
responses and are stored only in protected settings; the input clears after Save.
See [current behavior and verification](../../docs/WEBHOOKS.md).

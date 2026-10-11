> Imported project history, snapshot 2026-10-11. Read the [current repository status](../../docs/STATUS.md) and [agent rules](../../AGENTS.md) first. Dated experiments/commands below may be superseded; use the root Makefile. Private historical receipts and old images are excluded from publication.

# Индикация MF79U Custom

В VoWiFi Only idle: красный до готовности Wi-Fi IMS → фиолетовый после
регистрации. Cellular SMS не даёт жёлтый промежуточный цвет.

Documentation audit 2026-10-08: [STATUS.md](STATUS.md) is the shared state/index.

Актуальная userdata-версия: 2026-10-11. Оба индикатора принадлежат нашей
прошивке; штатный LED startup отключён обратимой B03 service policy.

| Состояние | Индикатор сети | RGB mask |
|---|---|---|
| Нет регистрации в сети | Красный | 1 |
| GSM / регистрация без IMS, вызовов нет | Жёлтый (красный + зелёный) | 3 |
| VoLTE IMS готов, вызовов нет | Синий | 4 |
| VoWiFi IMS готов, вызовов нет | Фиолетовый (красный + синий) | 5 |
| Любой активный вызов: входящий до ответа, исходящий, соединённый или удержанный | Зелёный | 2 |

Цвета вызовов имеют приоритет над idle цветом. Жёлтый означает регистрацию
без готового IMS, включая GSM и ожидание IMS в LTE. VoWiFi фиолетовый только
при фактической готовности IMS через Wi-Fi. Wi-Fi LED синий при активном интерфейсе.

Регистрация читается через локальный AT_CTL/CP IPC: CEREG, CGREG, CREG;
stat=1/5 означает домашнюю/роуминговую регистрацию. IMS readiness берётся из
`/dev/.mf79u-native-status.json`: требуется `imsReady=true`, живой PID и
проверенное имя исполняемого файла нашего native controller. Отсутствующий
status или завершившийся/чужой PID не считается готовым IMS; отдельного
контроля возраста status нет. Опрос повторяется через две секунды после
радиозапросов; при ошибках CP прежняя регистрация сохраняется до 10 s. События вызовов `RING`, `^DSCI`, `^ORIG`, `^CONN`, `^CEND`
передаются контроллером через Unix socket; завершение контроллера сбрасывает
состояние вызова. Динамический перехват native IMS очередей не используется.

## Установка и диагностика

`start-control.sh` запускает внутренний `/mnt/userdata/mf79u/.mf79u-net-led`;
он работает автономно от init, без Mac и SD. Проверка состояния не меняет LED:

```sh
outputs/adb -s 123456789ABCDEF shell '/mnt/userdata/mf79u/.mf79u-net-led --status'
```

Ответ содержит `registered`, `ims_registered`, `color_mask`, `hardware_mask`,
`wifi`, `demo`. `--demo` временно меняет аппаратный цвет и предназначен для
отдельной проверки, а не для обычной диагностики. Старые `start-net-led.py`
и `/dev/.mf79u-net-led-app` относятся к RAM-прототипу: не запускать его поверх
автономного сервиса. Сборка: `sh firmware/mf79u/build-net-led.sh`.

## Проверки и границы

На физическом модеме с нужной роуминговой SIM подтверждены регистрация без IMS
и жёлтый аппаратный mask=3: `registered=true`, `ims_registered=false`,
`color_mask=hardware_mask=3`, `demo=false`. ARM selftests прошли. Перезапущен
только LED daemon; native/SIP PID и настройки сохранились. Восприятие цвета
пользователем отдельно не подтверждено. Отчёт: yellow-led-live.json (historical local artifact: `build/yellow-led-live.json`).
Предыдущий binary: `build/pre-yellow-led-20261008/mf79u-net-led`.

Ранние проверки красного, синего, зелёного и фиолетового, Unix socket и
сопоставления безымянного RING с индексом DSCI сохранены в
`build/net-led-ipc-live-test.log`. Их idle mask=4 относится к политике до
добавления жёлтого; это синтетические события, а не новые реальные вызовы.

Обновлён только обратимый userdata binary. Старый полный NAND image 0.9 и
SD runtime 0.8 не обновлялись и не включают жёлтый. Полный образ не прошит.
GSM/SMS fallback описан в [SMS-SIP.md](SMS-SIP.md), запуск — в
[AUTONOMOUS.md](AUTONOMOUS.md).

## Историческая WCDMA policy (2026-10-10; удалена 2026-10-11)

Отдельный idle цвет WCDMA — бирюзовый, mask6. Источник — живой проверенный
native controller с registrationMode=UMTS и CS registration1/5. Внутреннее
значение UMTS сохранено; UI использует подпись WCDMA. На физическом модеме
подтверждены umts_registered=true и color_mask=hardware_mask=6; визуальное
восприятие цвета пользователем ещё не проверено. Цвета вызовов имеют прежний
приоритет. Подробнее: [UMTS.md](UMTS.md), receipt build/led-umts-install.json.

По уточнению пользователя все активные состояния вызова используют зелёный
mask2. Входящий звонок больше не использует фиолетовый. Вызов имеет приоритет
и над отсутствием регистрации; после clearing восстанавливается idle цвет
сети. Предыдущие упоминания фиолетового выше относятся к историческим тестам.

## Текущая политика после удаления WCDMA (2026-10-11)

Отдельный бирюзовый режим удалён. Все активные вызовы зелёные (mask2),
idle IMS — синий (mask4), зарегистрированная сеть без IMS — жёлтый (mask3),
нет регистрации — красный (mask1). Receipt: `build/led-gsm-lte-install.json`.

## Историческая GSM бирюзовая ревизия (заменена в тот же день)

По текущему требованию пользователя прежний жёлтый idle заменён на mask6.
Установлен userdata LED daemon; ARM selftest=0 проверяет GSM6, VoLTE4,
VoWiFi5, отсутствие регистрации1 и приоритет всех активных вызовов2.
Native2602/SIP2628 при установке сохранены, reboot не выполнялся. Текущая
физическая сеть была VoLTE ready (hardware_mask4); реальный GSM переход
ради проверки цвета не выполнялся. Receipt: led-cyan-gsm-install-20261011.json (historical local artifact: `build/led-cyan-gsm-install-20261011.json`).
Предыдущие разделы с жёлтым относятся к истории. Полные NAND/SD архивы старые.

## Окончательная легенда пользователя (2026-10-11)

Последнее требование заменяет предыдущую просьбу сделать GSM бирюзовым:
красный1 — нет регистрации у оператора; синий4 — готов VoLTE;
жёлтый3 — GSM / оператор зарегистрирован без готового IMS;
фиолетовый5 — готов VoWiFi. Бирюзовый больше не используется.
Все активные вызовы по предыдущему требованию остаются зелёными2.
Выбранный режим VoWiFi Only не подменяет фактическую регистрацию:
фиолетовый появляется только при imsReady и imsAccess=WIFI у живого native.
В режимах с cellular voice зарегистрированная сеть без готового IMS жёлтая.
В VoWiFi Only ожидающий Wi-Fi/IMS индикатор красный; GSM fallback запрещён.
Сборка и ARM selftest прошли, обновлён userdata daemon без перезапуска native/SIP.
Receipt: led-final-legend-20261011.json (historical local artifact: `build/led-final-legend-20261011.json`).

## VoWiFi Only: красный → фиолетовый (2026-10-11)

В VoWiFi Only регистрация SIM для cellular SMS не включает жёлтый idle.
До фактической готовности IMS через Wi-Fi индикатор красный1, после —
фиолетовый5; активный вызов по прежнему правилу зелёный2. Демон читает
сохранённый voice_mode до запуска native, чтобы загрузка не показывала жёлтый.
При запуске аппаратно устанавливается красный до потенциально медленных CP
запросов. В других режимах GSM остаётся жёлтым, VoLTE — синим.
Сборка и ARM selftest проверяют переходы, независимость от cellular SMS и
приоритет активных вызовов. Физическая reboot-проверка:
led-vowifi-only-boot-20261011.json (historical local artifact: `build/led-vowifi-only-boot-20261011.json`).

#!/bin/sh
# Brief RAM-only MF79U LED test. Restores sysfs state and resumes LED service.
set -eu
base=/sys/class/leds
pid=
guard=
is_led() {
    [ "$(cat "/proc/$1/comm" 2>/dev/null || true)" = zte_topsw_led ] &&
        [ "/proc/$1/exe" -ef /bin/zte_topsw_led ]
}
for proc in /proc/[0-9]*; do
    if is_led "${proc##*/}"; then
        [ -z "$pid" ] || { echo 'Multiple LED services; refused'; exit 1; }
        pid=${proc##*/}
    fi
done
[ -n "$pid" ] || { echo 'LED service not found; refused'; exit 1; }
for name in net_red net_green net_blue wifi_blue; do
    trigger=$(cat "$base/led:$name/trigger")
    case "$trigger" in '[none]'*) ;; *) echo 'Active trigger; refused'; exit 1;; esac
done
red=$(cat "$base/led:net_red/brightness")
green=$(cat "$base/led:net_green/brightness")
blue=$(cat "$base/led:net_blue/brightness")
wifi=$(cat "$base/led:wifi_blue/brightness")
restore() {
    # This firmware's printf with %s writes the value but returns status 1.
    echo "$red" > "$base/led:net_red/brightness"
    echo "$green" > "$base/led:net_green/brightness"
    echo "$blue" > "$base/led:net_blue/brightness"
    echo "$wifi" > "$base/led:wifi_blue/brightness"
    if is_led "$pid"; then
        kill -CONT "$pid" || true
    fi
}
cleanup() {
    restore
    if [ -n "$guard" ]; then kill "$guard" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
# Independent bounded fallback if the test shell is forcibly terminated.
(
    sleep 20
    restore
) </dev/null >/dev/null 2>&1 &
guard=$!
kill -STOP "$pid"
off() {
    for off_channel in net_red net_green net_blue wifi_blue; do
        printf '0\n' > "$base/led:$off_channel/brightness"
    done
}
for name in net_red net_green net_blue wifi_blue; do
    off
    echo "BLINK $name: three pulses"
    for pulse in 1 2 3; do
        printf '1\n' > "$base/led:$name/brightness"
        sleep 0.5
        [ "$(cat "$base/led:$name/brightness")" = 1 ]
        printf '0\n' > "$base/led:$name/brightness"
        sleep 0.5
    done
done
for pair in 'net_red net_green' 'net_green net_blue' 'net_red net_blue' 'net_red net_green net_blue'; do
    off
    echo "MIX $pair"
    for name in $pair; do
        printf '1\n' > "$base/led:$name/brightness"
    done
    sleep 0.6
    for name in $pair; do
        echo "READBACK $name=$(cat "$base/led:$name/brightness")"
    done
done
restore
kill "$guard" 2>/dev/null || true
trap - EXIT
echo 'RESTORED LED state and service'

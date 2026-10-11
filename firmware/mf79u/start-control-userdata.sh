#!/bin/sh
# Owned, reversible management service; the stock backend stays available.
base=/mnt/userdata/mf79u
pidfile=/dev/.mf79u-control.pid
bootstrap=--bootstrap
[ "${1:-}" = "--no-bootstrap" ] && bootstrap=""
program="$base/.mf79u-control"
sd_mount="$base/sd"
sd_program="$sd_mount/mf79u/versions/mf79u-custom-0.8-experimental/bin/mf79u-control"
if [ -f "$pidfile" ]; then
 control_pid=$(cat "$pidfile")
 case "$control_pid" in ''|*[!0-9]*) ;; *)
  if kill -0 "$control_pid" 2>/dev/null; then
   if grep -F -q "$base/.mf79u-control" "/proc/$control_pid/cmdline" || grep -F -q "$sd_program" "/proc/$control_pid/cmdline"; then exit 0; fi
  fi ;;
 esac
fi
# Only mount locally when ZTE is configured for local SD use and the card LUN
# is detached. Never detach a host-mounted card from a boot/background service.
lun=/sys/devices/platform/zx29_hsotg.0/gadget/lun1/file
if [ ! -f "$base/control-internal-preferred" ] && [ -f "$base/sd-control.md5" ] && [ -b /dev/mmcblk0p1 ] && [ "$(nv get sdcard_mode_option 2>/dev/null)" = "1" ]; then
 if [ -r "$lun" ] && [ -z "$(cat "$lun")" ]; then
  if ! grep -F -q "/dev/mmcblk0p1 $sd_mount vfat ro," /proc/mounts; then
   if ! grep -F -q '/dev/mmcblk0' /proc/mounts; then
    mkdir -p "$sd_mount"
    chmod 700 "$sd_mount"
    mount -t vfat -o ro,nosuid,nodev,exec,noatime,umask=0077 /dev/mmcblk0p1 "$sd_mount" 2>/dev/null
   fi
  fi
  if grep -F -q "/dev/mmcblk0p1 $sd_mount vfat ro," /proc/mounts && [ -x "$sd_program" ]; then
   expected_sd_md5=$(cat "$base/sd-control.md5")
   actual_sd_md5=$(md5sum "$sd_program" 2>/dev/null | cut -d ' ' -f 1)
   if [ -n "$expected_sd_md5" ] && [ "$actual_sd_md5" = "$expected_sd_md5" ]; then program="$sd_program"; fi
  fi
 fi
fi
[ -x "$program" ] || exit 0
# Install our LAN redirect before the vendor frontend can answer at boot.
# No interface needs to exist yet; loopback goform remains untouched.
for iface in bridge0 wlan0 wlan0-vxd; do
 iptables -t nat -D PREROUTING -i "$iface" -p tcp --dport 80 -j REDIRECT --to-ports 18080 2>/dev/null
 iptables -t nat -I PREROUTING 1 -i "$iface" -p tcp --dport 80 -j REDIRECT --to-ports 18080 2>/dev/null
 done
for ready_count in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60; do
 [ -e /sys/class/net/bridge0 ] && [ -e /sys/class/net/wlan0 ] && break
 sleep 1
done
ifconfig usblan0 up 2>/dev/null
brctl addif bridge0 usblan0 2>/dev/null
if [ -x "$base/.mf79u-net-led" ]; then
 "$base/.mf79u-net-led" >/dev/null 2>&1 &
fi
if [ -x "$base/start-native.sh" ]; then
 sh "$base/start-native.sh" >/dev/null 2>&1 &
fi
cleanup() {
 # An older wrapper can exit after its replacement has already started.
 # Leave the replacement's PID file and firewall rules in place.
 [ "$(cat "$pidfile" 2>/dev/null)" = "$control_pid" ] || return
 for iface in bridge0 wlan0 wlan0-vxd; do
  iptables -t nat -D PREROUTING -i "$iface" -p tcp --dport 80 -j REDIRECT --to-ports 18080 2>/dev/null
 done
 rm -f "$pidfile"
}
trap cleanup EXIT
GOMAXPROCS=1 GOGC=20 GOMEMLIMIT=6MiB "$program" --native $bootstrap --listen 0.0.0.0:18080 --data "$base" --vendor http://127.0.0.1 >/dev/null 2>&1 &
control_pid=$!
echo "$control_pid" > "$pidfile"
wait "$control_pid"

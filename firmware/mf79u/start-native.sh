#!/bin/sh
# Device-local supervisor. The controller owns CP/IMS queues and its children.
# Retry only after that controller has finished its guarded cleanup.
umask 077
base=/mnt/userdata/mf79u
[ ! -f /dev/mf79u/vowifi/diagnostic-enabled ] || export MF79U_WIFI_DIAG=1
[ "$(cat "$base/native-enabled" 2>/dev/null)" = "1" ] || exit 0
pidfile=/dev/.mf79u-native-supervisor.pid
if [ -f "$pidfile" ]; then
 old_pid=$(cat "$pidfile")
 case "$old_pid" in ''|*[!0-9]*) ;; *)
  if kill -0 "$old_pid" 2>/dev/null && grep -F -q 'start-native.sh' "/proc/$old_pid/cmdline"; then exit 0; fi ;;
 esac
fi
echo $$ > "$pidfile"
native="$base/.mf79u-native-gateway"
ims="$base/.mf79u-volte-private"
media="$base/.mf79u-ims-userspace-ipsec.so"
sip="$base/.mf79u-sip-gateway"
cs="$base/.mf79u-cs-voice"
cs_module="$base/.mf79u-cs-voice.ko"
if [ ! -x "$native" ]; then
 native=/usr/bin/mf79u-native-gateway
 ims=/usr/bin/mf79u-ims-private
 media=/lib/mf79u-ims-userspace-ipsec.so
 sip=/usr/bin/mf79u-sip-gateway
fi
child=""
cleanup() {
 if [ -n "$child" ] && [ "/proc/$child/exe" -ef "$native" ]; then kill -TERM "$child" 2>/dev/null; wait "$child"; fi
 [ "$(cat "$pidfile" 2>/dev/null)" = "$$" ] && rm -f "$pidfile"
}
trap 'exit 0' TERM INT
trap cleanup EXIT
for ready_count in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60; do
 if [ -e /sys/class/net/bridge0 ] && grep -q '^ *4111 ' /proc/sysvipc/msg; then break; fi
 sleep 1
done
[ -x "$native" ] && [ -x "$ims" ] && [ -r "$media" ] && [ -x "$sip" ] || exit 1
# A fresh device may receive its first PBX settings through the setup hotspot.
# Stay local and wait for WebUI Apply instead of requiring a host to start us.
while [ ! -f "$base/gateway.ini" ]; do
 [ "$(cat "$base/native-enabled" 2>/dev/null)" = "1" ] || exit 0
 sleep 5
done
# Optional explicit PBX return routes (e.g. Docker's address behind a USB peer).
# This is local configuration, never a host-side boot/runtime dependency.
if [ -f "$base/pbx-return-routes" ]; then
 while read destination gateway iface extra; do
  [ -n "$destination" ] || continue
  case "$destination" in *[!0-9./]*|*/*/*) exit 1 ;; esac
  case "$gateway" in ''|*[!0-9.]*) exit 1 ;; esac
  case "$iface" in bridge0|wlan0|wlan0-vxd) ;; *) exit 1 ;; esac
  [ -z "$extra" ] || exit 1
  route_text=$(ip route show "$destination" | sed 's/[[:space:]]*$//')
  expected="${destination%/32} via $gateway dev $iface"
  if [ -n "$route_text" ]; then
   [ "$route_text" = "$expected" ] || exit 1
  else
   ip route add "$destination" via "$gateway" dev "$iface" || exit 1
  fi
 done < "$base/pbx-return-routes"
fi
# Checked persistent CS runtime. Its driver starts suspended and remains pinned
# after detachment because B03 OSS has no fetched-callback lifetime barrier.
cs_available=0
if [ -x "$cs" ] && [ -x "$base/.mf79u-cs-pcm-bridge" ] && [ -r "$base/cs-runtime.md5" ]; then
 if (cd "$base" && "$base/tools/busybox" md5sum -c cs-runtime.md5 >/dev/null 2>&1); then
  cs_digest=$(md5sum "$cs_module" | cut -d ' ' -f 1)
  if [ ! -d /sys/module/mf79u_cs_voice ]; then
   if insmod "$cs_module"; then echo "$cs_digest" > /dev/.mf79u-cs-driver.md5; fi
  fi
  if [ "$(cat /dev/.mf79u-cs-driver.md5 2>/dev/null)" = "$cs_digest" ] && [ -r /sys/mf79u_cs_voice/session ]; then cs_available=1; fi
 fi
fi
while [ "$(cat "$base/native-enabled" 2>/dev/null)" = "1" ]; do
 for retry_delay in 5 15 30 60 120; do
  [ "$(cat "$base/native-enabled" 2>/dev/null)" = "1" ] || exit 0
  : > /dev/.mf79u-native.log
  # O_APPEND lets the supervisor truncate its RAM log without leaving holes
  # at the controller's old file offset. Bound storage during long uptime.
  if [ "$cs_available" = "1" ]; then
   "$native" "$ims" "$media" "$sip" "$base/gateway.ini" "$cs" >>/dev/.mf79u-native.log 2>&1 &
  else
   "$native" "$ims" "$media" "$sip" "$base/gateway.ini" >>/dev/.mf79u-native.log 2>&1 &
  fi
  child=$!
  while kill -0 "$child" 2>/dev/null && [ "/proc/$child/exe" -ef "$native" ]; do
   sleep 30
   log_bytes=$(wc -c < /dev/.mf79u-native.log)
   if [ "$log_bytes" -gt 65536 ]; then : > /dev/.mf79u-native.log; fi
  done
  wait "$child"
  child=""
  sleep "$retry_delay"
 done
 sleep 300
done

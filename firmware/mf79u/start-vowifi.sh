#!/bin/sh
set -eu
base=/mnt/userdata/mf79u
runtime=/dev/mf79u/vowifi
cleanup_owned() {
 if [ -f "$runtime/interface-owner" ]; then
  read owner index extra < "$runtime/interface-owner"
  case "$owner:$index" in *[!0-9:]*|:*) return 1;; esac
  [ -z "${extra:-}" ] && ! kill -0 "$owner" 2>/dev/null || return 1
  if [ -e /sys/class/net/vowifi0 ]; then
   [ "$(cat /sys/class/net/vowifi0/ifindex)" = "$index" ] || return 1
   [ -z "$(ls /sys/class/net/vowifi0/brif)" ] || return 1
   MF79U_VOWIFI_CLEANUP=1 PLUTO_VERB=down-client "$base/vowifi-updown.sh" || return 1
   ip link set vowifi0 down
   brctl delbr vowifi0 || return 1
  fi
  rm -f "$runtime/interface-owner"
 fi
}
cleanup_stale() {
 cleanup_owned || return 1
 if [ -f "$runtime/address" ]; then
  MF79U_VOWIFI_CLEANUP=1 PLUTO_VERB=down-client "$base/vowifi-updown.sh"
 fi
}
if [ "${1:-}" = "--cleanup-only" ]; then cleanup_stale; exit; fi
cleanup_stale
mkdir -p "$runtime"
chmod 700 "$runtime"
tools="$runtime/tools"
mkdir -p "$tools"
"$base/tools/busybox" xzcat "$base/vowifi-runtime.tar.xz" | "$base/tools/busybox" tar -xf - -C "$tools" .mf79u-vowifi-charon .mf79u-vowifi-swanctl .mf79u-vowifi-prepare
rm -rf "$runtime/swanctl/x509ca"
mkdir -p "$runtime/swanctl"

child=
cleanup() {
 trap - EXIT TERM INT
 [ -z "$child" ] || { kill -TERM "$child" 2>/dev/null || :; for i in 1 2 3 4 5 6 7 8; do kill -0 "$child" 2>/dev/null || break; sleep 1; done; kill -KILL "$child" 2>/dev/null || :; wait "$child" 2>/dev/null || :; }
 cleanup_owned || :
 if [ -f "$runtime/address" ]; then MF79U_VOWIFI_CLEANUP=1 PLUTO_VERB=down-client "$base/vowifi-updown.sh" || :; fi
 rm -f "$runtime/swanctl.conf" "$runtime/pcscf-list" "$runtime/mf79u-pcscf" "$runtime/address" "$runtime/charon.vici"
 rm -rf "$tools" "$runtime/swanctl/x509ca"
}
trap cleanup EXIT
trap 'exit 0' TERM INT
"$tools/.mf79u-vowifi-prepare"
rm -f "$tools/.mf79u-vowifi-prepare"
if [ -f "$runtime/diagnostic-enabled" ]; then
 sed 's@filelog { /dev/null { default = -1@filelog { /dev/mf79u/vowifi/diagnosticlog { default = 1@' "$runtime/strongswan.conf" > "$runtime/strongswan.next"
 mv "$runtime/strongswan.next" "$runtime/strongswan.conf"
fi
export STRONGSWAN_CONF="$runtime/strongswan.conf"
"$tools/.mf79u-vowifi-charon" >/dev/null 2>&1 &
child=$!
for attempt in 1 2 3 4 5 6 7 8 9 10; do
 [ -S "$runtime/charon.vici" ] && break
 kill -0 "$child" || exit 1
 sleep 1
done
"$tools/.mf79u-vowifi-swanctl" --load-all --file "$runtime/swanctl.conf" --uri "unix://$runtime/charon.vici" >/dev/null 2>&1
"$tools/.mf79u-vowifi-swanctl" --initiate --child vowifi --timeout 35 --uri "unix://$runtime/charon.vici" >/dev/null 2>&1
rm -f "$runtime/swanctl.conf"
rm -f "$tools/.mf79u-vowifi-swanctl"
# VICI CHILD-established notification can precede the updown listener.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
 [ -s "$runtime/address" ] && [ -s "$runtime/mf79u-pcscf" ] && break
 kill -0 "$child" 2>/dev/null || exit 1
 sleep 1
done
[ -s "$runtime/address" ] && [ -s "$runtime/mf79u-pcscf" ]
echo VOWIFI_TUNNEL_READY
# Sequential IKE reauthentication temporarily removes the CHILD/VIP. Give the
# same daemon a bounded chance to establish its replacement before teardown.
missing=0
while kill -0 "$child" 2>/dev/null; do
 if [ -s "$runtime/address" ]; then missing=0; else missing=$((missing + 2)); fi
 [ "$missing" -lt 120 ] || exit 1
 sleep 2
done

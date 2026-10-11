#!/mnt/userdata/mf79u/tools/busybox sh
# Only protected RAM metadata and source-specific routes; never a main default.
set -eu
runtime=/dev/mf79u/vowifi
if [ -f "$runtime/diagnostic-enabled" ]; then printf "%s %s %s\n" "${PLUTO_VERB:-}" "${PLUTO_MY_SOURCEIP4_1:-}" "${PLUTO_MY_SOURCEIP:-}" >> "$runtime/updown-observed"; fi
lease=${PLUTO_UNIQUEID:-0}
case "$lease" in ''|*[!0-9]*) exit 1;; esac
case "${PLUTO_VERB:-}" in
 up-client|up-host)
  address=${PLUTO_MY_SOURCEIP4_1:-${PLUTO_MY_SOURCEIP:-}}
  case "$address" in ''|*[!0-9.]*) exit 1;; esac
  # CHILD rekey may repeat updown for the same assigned address.
  if [ "$(cat "$runtime/address" 2>/dev/null)" = "$address" ] &&
     ip rule show | grep -q "^1079:.*from $address.*lookup 79" &&
     ip route show table 79 | grep -Eq "^default dev vowifi0 *(scope link *)?$"; then mkdir -p "$runtime/leases"; : > "$runtime/leases/$lease"; printf '%s\n' "$lease" > "$runtime/generation"; exit 0; fi
  # This table and priority must be available before acquiring ownership.
  [ -z "$(ip route show table 79 2>/dev/null)" ] || exit 1
  ! ip rule show | grep -q '^1079:' || exit 1
  umask 077
  printf '%s\n' "$address" > "$runtime/address"
  ip route replace default dev vowifi0 table 79 || { rm -f "$runtime/address"; exit 1; }
  ip rule add pref 1079 from "$address/32" lookup 79 || { ip route del default dev vowifi0 table 79; rm -f "$runtime/address"; exit 1; }
  mkdir -p "$runtime/leases"
  : > "$runtime/leases/$lease"
  printf '%s\n' "$lease" > "$runtime/generation"
  ;;
 down-client|down-host)
  [ -f "$runtime/address" ] || exit 0
  if [ "${MF79U_VOWIFI_CLEANUP:-0}" != 1 ]; then
   rm -f "$runtime/leases/$lease"
   [ ! -d "$runtime/leases" ] || [ -z "$(ls "$runtime/leases")" ] || exit 0
  fi
  if [ -f "$runtime/address" ]; then
   address=$(cat "$runtime/address")
   case "$address" in ''|*[!0-9.]*) ;; *) ip rule del pref 1079 from "$address/32" lookup 79 || :;; esac
  fi
  ip route del default dev vowifi0 table 79 2>/dev/null || :
  rm -f "$runtime/address" "$runtime/mf79u-pcscf" "$runtime/pcscf-list"
  rm -rf "$runtime/leases"
  ;;
esac

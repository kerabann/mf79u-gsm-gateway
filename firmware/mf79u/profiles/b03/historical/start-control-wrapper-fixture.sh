pidfile=/dev/.mf79u-wrapper-fixture
control_pid=9001
calls=0
iptables() { calls=called; }
cleanup() {
 # An older wrapper can exit after its replacement has already started.
 # Leave the replacement's PID file and firewall rules in place.
 [ "$(cat "$pidfile" 2>/dev/null)" = "$control_pid" ] || return
 for iface in bridge0 wlan0 wlan0-vxd; do
  iptables -t nat -D PREROUTING -i "$iface" -p tcp --dport 80 -j REDIRECT --to-ports 18080 2>/dev/null
 done
 rm -f "$pidfile"
}
echo 9002 > "$pidfile"
cleanup
[ "$(cat "$pidfile")" = 9002 ] && [ "$calls" = 0 ] || exit 1
echo 9001 > "$pidfile"
cleanup
[ ! -e "$pidfile" ] && [ "$calls" = called ] || exit 1
echo PASS_WRAPPER_REPLACEMENT_OWNERSHIP

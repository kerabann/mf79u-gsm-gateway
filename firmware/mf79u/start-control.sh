#!/bin/sh
# The stock adapters initialise bridge0 and the protected AP profile first.
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60; do
 if [ -d /mnt/userdata ] && /sbin/ifconfig bridge0 >/dev/null 2>&1; then break; fi
 sleep 1
done
mkdir -p /mnt/userdata/mf79u
chmod 700 /mnt/userdata/mf79u
[ -f /mnt/userdata/mf79u/native-enabled ] || printf '1\n' > /mnt/userdata/mf79u/native-enabled
/usr/bin/mf79u-net-led >/dev/null 2>&1 &
sh /usr/zte/mf79u/start-native.sh >/dev/null 2>&1 &
export GOMAXPROCS=1 GOGC=20 GOMEMLIMIT=6MiB
exec /usr/bin/mf79u-control --native --bootstrap --listen 0.0.0.0:18080 --data /mnt/userdata/mf79u --vendor http://127.0.0.1

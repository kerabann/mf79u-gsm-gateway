#!/bin/sh
set -eu
cd -P "$(dirname "$0")"
cd ../..
python3 firmware/mf79u/prepare-system-tools.py
docker run --rm -v "$(pwd):/work" -w /work mf79u-system-tools:local sh -eu -c '
 cd work/zte/system-tools/busybox-1.37.0
 make defconfig >/dev/null
 sed -i "s/# CONFIG_STATIC is not set/CONFIG_STATIC=y/; s/CONFIG_USE_BB_CRYPT=n/CONFIG_USE_BB_CRYPT=y/; s/# CONFIG_USE_BB_CRYPT is not set/CONFIG_USE_BB_CRYPT=y/; s/# CONFIG_USE_BB_CRYPT_SHA is not set/CONFIG_USE_BB_CRYPT_SHA=y/" .config
 sed -i "s/CONFIG_SHA1_HWACCEL=y/# CONFIG_SHA1_HWACCEL is not set/; s/CONFIG_SHA256_HWACCEL=y/# CONFIG_SHA256_HWACCEL is not set/" .config
 yes "" | make oldconfig >/dev/null
 make -j4 CROSS_COMPILE=arm-linux-gnueabi- EXTRA_CFLAGS="-Os -march=armv7-a -mfloat-abi=soft" >/dev/null
 cp busybox /work/firmware/mf79u/build/busybox-extended
 cd ../dropbear-2026.94
 ac_cv_func_getrandom=no CC=arm-linux-gnueabi-gcc CFLAGS="-Os -march=armv7-a -mfloat-abi=soft" ./configure --host=arm-linux-gnueabi --enable-static --disable-zlib --disable-syslog --disable-lastlog --disable-utmp --disable-utmpx --disable-wtmp --disable-wtmpx >/dev/null
 make -j4 PROGRAMS="dropbear dropbearkey" MULTI=1 >/dev/null
 arm-linux-gnueabi-strip dropbearmulti
 cp dropbearmulti /work/firmware/mf79u/build/dropbearmulti
 arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft /work/firmware/mf79u/src/cp-ipc.c /work/firmware/mf79u/src/system-imei.c -o /work/firmware/mf79u/build/system-imei
'

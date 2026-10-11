#!/bin/sh
set -eu
cd -P "$(dirname "$0")/../.."
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -nostdlib -no-pie -marm \
  -march=armv7-a -mfloat-abi=soft -fno-stack-protector -Wl,-e,_start \
  -Wl,--hash-style=sysv -Wl,--dynamic-linker=/lib/ld-uClibc.so.0 \
  -Wl,-rpath-link,firmware/mf79u/build/link-sdk/lib \
  -Lfirmware/mf79u/build/link-sdk/lib firmware/mf79u/src/adb-boot.c \
  -l:libnvram.so -l:libuClibc-0.9.33.2.so -l:ld-uClibc-0.9.33.2.so \
  -o firmware/mf79u/build/mf79u-adb-boot
 arm-linux-gnueabi-strip firmware/mf79u/build/mf79u-adb-boot
'

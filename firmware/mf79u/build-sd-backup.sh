#!/bin/sh
set -eu
cd -P "$(dirname "$0")"
cd ../..
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  arm-linux-gnueabi-gcc -O2 -Wall -Wextra -Werror \
    -static -s -Wl,--gc-sections -march=armv7-a -mfloat-abi=soft \
    firmware/mf79u/src/sd-backup-server.c -o firmware/mf79u/build/sd-backup-server
'

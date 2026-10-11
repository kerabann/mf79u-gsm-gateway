#!/bin/sh
set -eu
cd -P "$(dirname "$0")/../.."
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/net-led.c firmware/mf79u/src/net-led-policy.c firmware/mf79u/src/cp-ipc.c \
    -o firmware/mf79u/build/mf79u-net-led
'

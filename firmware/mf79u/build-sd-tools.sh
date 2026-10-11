#!/bin/sh
set -eu
cd -P "$(dirname "$0")"
cd ../..
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s \
    -march=armv7-a -mfloat-abi=soft firmware/mf79u/src/sd-reread.c \
    -o firmware/mf79u/build/sd-reread
'

#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 flags="-Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft"
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/cs-voice-adapter.c -o firmware/mf79u/build/mf79u-cs-voice
 arm-linux-gnueabi-gcc $flags -DCS_PCM_BASE=\"/sys/mf79u_cs_voice\" firmware/mf79u/src/cs-pcm-bridge.c -o firmware/mf79u/build/mf79u-cs-pcm-bridge
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/cs-call-selftest.c -o firmware/mf79u/build/cs-call-selftest-arm
 qemu-arm firmware/mf79u/build/cs-call-selftest-arm
'

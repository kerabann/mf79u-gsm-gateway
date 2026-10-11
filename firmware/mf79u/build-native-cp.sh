#!/bin/sh
set -eu
cd -P "$(dirname "$0")"
cd ../..
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cp-ipc.c firmware/mf79u/src/cp-ipc-probe.c \
    -o firmware/mf79u/build/cp-ipc-probe
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cp-ipc.c firmware/mf79u/src/cp-pdp.c firmware/mf79u/src/native-gateway.c \
    firmware/mf79u/src/net-led-policy.c -o firmware/mf79u/build/mf79u-native-gateway
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cp-ipc.c firmware/mf79u/src/cp-ipc-selftest.c \
    -o firmware/mf79u/build/cp-ipc-selftest
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cs-call-watch.c firmware/mf79u/src/net-led-policy.c \
    -o firmware/mf79u/build/cs-call-watch
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cp-memory.c firmware/mf79u/src/cp-memory-probe.c \
    -o firmware/mf79u/build/cp-memory-probe
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cp-memory.c firmware/mf79u/src/cp-memory-selftest.c \
    -o firmware/mf79u/build/cp-memory-selftest
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cs-ring-state-selftest.c \
    -o firmware/mf79u/build/cs-ring-state-selftest-arm
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cs-status-selftest.c \
    -o firmware/mf79u/build/cs-status-selftest-arm
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cs-channel-selftest.c \
    -o firmware/mf79u/build/cs-channel-selftest-arm
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/voice-backend-selftest.c \
    -o firmware/mf79u/build/voice-backend-selftest-arm
  arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a \
    -mfloat-abi=soft firmware/mf79u/src/cs-connect-probe-selftest.c \
    -o firmware/mf79u/build/cs-connect-probe-selftest-arm
'

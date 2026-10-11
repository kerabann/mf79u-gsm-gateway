#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 touch /tmp/MF79U_ISOLATED_FIXTURE
 b=firmware/mf79u/build
 flags="-Os -Wall -Wextra -Werror -static -march=armv7-a -mfloat-abi=soft"
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/native-fallback-fixture.c -o "$b/native-fallback-fixture"
 ln -sf native-fallback-fixture "$b/test-ims"; ln -sf native-fallback-fixture "$b/test-sip"; ln -sf native-fallback-fixture "$b/test-cs"
 arm-linux-gnueabi-gcc $flags -DMF79U_IMS_TIMEOUT=3 -DMF79U_RADIO_INTERVAL=1 -DMF79U_IMS_RETRY=20 \
  firmware/mf79u/src/cp-ipc.c firmware/mf79u/src/cp-pdp.c firmware/mf79u/src/native-gateway.c firmware/mf79u/src/net-led-policy.c -o "$b/registration-test"
 python3 firmware/mf79u/test-registration-fallback.py
'

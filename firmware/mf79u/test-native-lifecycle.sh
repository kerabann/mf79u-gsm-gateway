#!/bin/sh
# Runs every fake-CP test in a disposable container; never on physical B03.
set -eu
cd "$(dirname "$0")/../.."
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 touch /tmp/MF79U_ISOLATED_FIXTURE
 b=firmware/mf79u/build
 sources="firmware/mf79u/src/cp-ipc.c firmware/mf79u/src/cp-pdp.c firmware/mf79u/src/native-gateway.c firmware/mf79u/src/net-led-policy.c"
 flags="-Os -Wall -Wextra -Werror -static -march=armv7-a -mfloat-abi=soft"
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/voice-backend-selftest.c -o "$b/voice-backend-selftest-arm"
 "$b/voice-backend-selftest-arm"
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/cs-channel-selftest.c -o "$b/cs-channel-selftest-arm"
 "$b/cs-channel-selftest-arm"
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/cs-connect-probe-selftest.c -o "$b/cs-connect-probe-selftest-arm"
 "$b/cs-connect-probe-selftest-arm"
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/native-fallback-fixture.c -o "$b/native-fallback-fixture"
 ln -sf native-fallback-fixture "$b/test-ims"; ln -sf native-fallback-fixture "$b/test-sip"; ln -sf native-fallback-fixture "$b/test-cs"
 arm-linux-gnueabi-gcc $flags -DMF79U_IMS_TIMEOUT=3 -DMF79U_RADIO_INTERVAL=1 -DMF79U_IMS_RETRY=2 $sources -o "$b/native-fallback-test"
 python3 firmware/mf79u/test-native-fallback.py
 arm-linux-gnueabi-gcc $flags firmware/mf79u/src/cs-voice-protocol-selftest.c -o "$b/cs-voice-protocol-selftest-arm"
 "$b/cs-voice-protocol-selftest-arm"
 arm-linux-gnueabi-gcc $flags -DMF79U_IMS_TIMEOUT=3 -DMF79U_RADIO_INTERVAL=1 -DMF79U_IMS_RETRY=15 $sources -o "$b/native-cs-backend-test"
 python3 firmware/mf79u/test-native-cs-backend.py
 arm-linux-gnueabi-gcc $flags -DMF79U_IMS_TIMEOUT=30 -DMF79U_RADIO_INTERVAL=1 \
  -DMF79U_RING_ONLY_FILE=\"/tmp/native-ring-only-test\" $sources -o "$b/native-ring-only-test"
 python3 firmware/mf79u/test-ring-only.py
 arm-linux-gnueabi-gcc $flags -DMF79U_IMS_TIMEOUT=30 -DMF79U_RADIO_INTERVAL=1 \
  -DMF79U_CS_ONLY_FILE=\"/tmp/native-cs-only-test\" $sources -o "$b/native-cs-only-test"
 python3 firmware/mf79u/test-cs-only.py
 arm-linux-gnueabi-gcc $flags -DMF79U_IMS_TIMEOUT=30 -DMF79U_RADIO_INTERVAL=1 \
  -DMF79U_CS_ONLY_FILE=\"/tmp/native-cs-status-policy\" \
  -DMF79U_RING_ONLY_FILE=\"/tmp/native-cs-status-guard\" \
  -DMF79U_CS_STATUS_FILE=\"/tmp/native-cs-status\" $sources -o "$b/native-cs-status-test"
 python3 firmware/mf79u/test-cs-status.py
'

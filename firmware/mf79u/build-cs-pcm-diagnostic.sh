#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
docker run --rm -v "$(pwd):/work" -w /work mf79u-build-tools:local sh -eu -c '
 arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft -DMF79U_DIAGNOSTIC_FAULTS=1 \
  firmware/mf79u/src/cs-pcm-bridge.c -o firmware/mf79u/build/cs-pcm-bridge
 arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft -DMF79U_DIAGNOSTIC_FAULTS=1 \
  -DCS_PCM_UDP_LOCAL=46011 -DCS_PCM_UDP_PEER=46010 \
  firmware/mf79u/src/cs-pcm-bridge.c -o firmware/mf79u/build/cs-pcm-bridge-sip-test
 pj=work/zte/voice/sip-deps/pjproject-2.17
 prefix=/work/work/zte/voice/sip-deps/arm
 arm-linux-gnueabi-gcc -Os -g -Wall -Wextra -Werror -static -Wl,--gc-sections \
  -march=armv7-a -mfloat-abi=soft -DPJ_AUTOCONF=1 -DPJ_IS_BIG_ENDIAN=0 -DPJ_IS_LITTLE_ENDIAN=1 -DPJMEDIA_HAS_SRTP=0 \
  -DMF79U_SIP_PCM_RX=46010 -DMF79U_SIP_PCM_PEER=46011 -DMF79U_SIP_RTP_PORT=12004 -DMF79U_SIP_PCM_LEVELS=1 -DMF79U_DIAGNOSTIC_FAULTS=1 \
  -DMF79U_SIP_STATUS_BASE=\"/dev/.mf79u-cs-sip-status\" -DMF79U_SIP_CALLER_FILE=\"/dev/.mf79u-cs-sip-caller\" \
  -I$pj/pjlib/include -I$pj/pjlib-util/include -I$pj/pjnath/include -I$pj/pjmedia/include -I$pj/pjsip/include \
  firmware/mf79u/src/modem-sip-gateway.c firmware/mf79u/src/cs-sip-clock-diagnostic.c \
  -Wl,--wrap=pjmedia_master_port_create \
  -Wl,--start-group $pj/pjsip/lib/*.a $pj/pjmedia/lib/*.a $pj/third_party/lib/*.a \
   $pj/pjnath/lib/*.a $pj/pjlib-util/lib/*.a $pj/pjlib/lib/*.a -Wl,--end-group \
  $prefix/lib/libopus.a $prefix/lib/libbcg729.a $prefix/lib/libssl.a $prefix/lib/libcrypto.a -lm -lpthread -ldl \
  -o firmware/mf79u/build/cs-sip-media-test.debug
 arm-linux-gnueabi-strip -o firmware/mf79u/build/cs-sip-media-test firmware/mf79u/build/cs-sip-media-test.debug
'
